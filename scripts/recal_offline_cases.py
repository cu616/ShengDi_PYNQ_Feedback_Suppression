"""一键重标定策略的离线复核：用已经发生过的真实情况，逐例给出机器判定与理由。

这不是"跑个 demo"，它做两件事：
  1. 证明四类判定在**真实数据**上给出的是可引用的结论，不是只在合成数据上成立；
  2. 把阈值与已发生的事实对齐。本轮据此改了两处（都写进 reasons 与 README）：
     - MIN_EXCITATION_SNR_DB 6.0 -> 0.0：原阈值会把部署模型自己的训练集（bind4，snr 3.9 dB、
       相干 0.90、门控 73%）判成不可用。主判据改为 gated ratio，SNR 只抓"激励完全没进来"。
     - check_fit 的峰位基准改为**本轮实测延迟**：用旧模型峰位当基准会把 50 cm 重标定
       （实测 128、旧模型 125）判成"换错布置"。

五类情况（队长指定）：
  A 旧模型失配      -> check_fit 拒收，理由是时间原点与本轮采集不符
  B 低信噪比        -> check_capture 拒收，理由是麦克风里没有与参考相干的成分
  C 输入削顶        -> check_capture 拒收，理由是近满幅
  D 322 Hz 负环路提升 -> 该点 INAPPLICABLE（没有可收回的增益），不进成败统计；
                        同一频点若抵消臂更响则 FAIL，两种情况必须分开
  E 50 cm 局部改善  -> 采集与模型都合格，但没有三点验证 -> INCONCLUSIVE，不自动安装

数据缺口（如实列出，不凑）：
  - 没有"真实现场逐次采集 + 逐次三点"的完整闭环记录；D 用的是 10-28 / 10-31 两轮已发表的
    三臂读数（数值硬编码，带来源注释），不是从 npz 重算。
  - 没有 50 cm 布置下的三臂读数，所以 E 的最终判定只能是 INCONCLUSIVE。

用法：
  python scripts/recal_offline_cases.py \
      --inbox D:/Always/QianSai/_inbox \
      --out-dir report/verification/recalibration-policy-2026-11-01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from feedback import recal_policy as rp  # noqa: E402
from answer_new_layout_325 import estimate_lag  # noqa: E402

FS = 48828.125

# 10-28 那轮 322 Hz 三点（A 的宽残差 v3 evidence.json#steady_state_tone_three_point）：
# open 45.44 / bypass 49.19 / cancel 44.43 dB。**只有这一个频点有记录**，不补造第二点。
THREE_POINT_1028 = [
    {"frequency_hz": 322.0, "open_db": 45.44, "bypass_db": 49.19, "cancel_db": 44.43},
]
# 10-31 那轮重拟合候选的三臂（A 的 recalibration-2026-10-31/receipt.json）：
# 以 open=0 为基准，boost=+1.9756、acoustic=-0.2187、over=-2.1944
#   => bypass=1.9756、cancel=+2.1943（抵消臂比无环路臂还响 2.19 dB）
THREE_POINT_1031 = [
    {"frequency_hz": 322.0, "open_db": 0.0, "bypass_db": 1.9756, "cancel_db": 2.1943},
]


def _load_model(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    q = d.get("coefficients_q20")
    if q is None:
        q = [int(round(v * (1 << 20))) for v in d["coefficients"]]
    return np.asarray(q, dtype=np.int64), d


def _capture(path):
    cap = np.load(path, allow_pickle=True)
    ref = np.asarray(cap["reference"], dtype=float)
    mic = np.asarray(cap["microphone"], dtype=float)
    fs = float(cap["sample_rate_hz"]) if "sample_rate_hz" in cap.files else FS
    md = {}
    if "metadata_json" in cap.files:
        try:
            md = json.loads(str(cap["metadata_json"]))
        except Exception:
            md = {}
    return ref, mic, fs, md, cap


def case_old_model(inbox, out):
    model = ROOT / "models" / "room_v1" / "candidate_512.json"
    q, d = _load_model(model)
    got = rp.check_fit(q, FS, expected_peak_tap=184)
    out.append({
        "case": "A_old_model_mismatch",
        "question": "上一套布置（0.5 m）的模型装到本轮（1 m 侧对）数据上，能不能装",
        "inputs": {"model": str(model.relative_to(ROOT)), "fixture": d.get("fixture_id"),
                   "expected_peak_tap": 184},
        "status": got["status"],
        "metrics": {k: got["metrics"][k] for k in
                    ("L1", "L1_over_max", "peak_tap", "peak_tap_delta") if k in got["metrics"]},
        "reasons": got["reasons"],
        "next": got.get("next"),
    })


def case_low_snr(inbox, out):
    p = inbox / "2026-10-22_room256" / "candidate_room_v1_256_final(1)" / "seg_3.npz"
    ref, mic, fs, md, _ = _capture(p)
    got = rp.check_capture(ref, mic, fs, md)
    out.append({
        "case": "B_low_snr_capture",
        "question": "麦克风里没有与参考相干的成分时，采集资格怎么判",
        "inputs": {"file": str(p).replace(str(inbox), "_inbox"),
                   "mic_rms_dbfs": got["metrics"].get("mic_rms_dbfs")},
        "status": got["status"],
        "metrics": {k: got["metrics"].get(k) for k in
                    ("excitation_snr_db", "coherence_median", "coherence_gated_ratio")},
        "reasons": got["reasons"],
        "next": got.get("next"),
    })
    # 对照组：1 m 侧对下 snr 只有 4 dB，但相干够 —— 必须放行，否则会否掉部署模型的训练集
    p2 = inbox / "2026-10-26_bindcapture_rewired" / "bind4_00_1746832927253437612.npz"
    if p2.exists():
        r2, m2, f2, d2, _ = _capture(p2)
        g2 = rp.check_capture(r2, m2, f2, d2)
        out.append({
            "case": "B2_deployed_training_capture_must_pass",
            "question": "部署模型自己的训练段（snr 3.9 dB、相干 0.90、门控 73%）会不会被误拒",
            "inputs": {"file": str(p2).replace(str(inbox), "_inbox")},
            "status": g2["status"],
            "metrics": {k: g2["metrics"].get(k) for k in
                        ("excitation_snr_db", "coherence_median", "coherence_gated_ratio")},
            "reasons": g2["reasons"],
            "next": g2.get("next"),
        })


def case_clipped(inbox, out):
    p = inbox / "2026-10-25_lowband2_return" / "scene" / "mic_check_after_repair.npz"
    ref, mic, fs, md, _ = _capture(p)
    got = rp.check_capture(ref, mic, fs, md)
    out.append({
        "case": "C_clipped_capture",
        "question": "麦克风近满幅时采集资格怎么判",
        "inputs": {"file": str(p).replace(str(inbox), "_inbox"),
                   "mic_peak": got["metrics"].get("mic_peak")},
        "status": got["status"],
        "metrics": got["metrics"].get("fullscale"),
        "reasons": got["reasons"],
        "next": got.get("next"),
    })


def case_322(inbox, out):
    good = rp.check_three_point(THREE_POINT_1028, gain_db=-8.0)
    out.append({
        "case": "D1_322Hz_positive_boost_single_point",
        "question": "322 Hz 有 3.75 dB 环路提升、抵消收回 4.76 dB，但只有这一个频点，够不够判 PASS",
        "inputs": {"source": "10-28 v3 evidence.json#steady_state_tone_three_point（仅 322 Hz 一点）"},
        "status": good["status"],
        "points": good["points"],
        "reasons": good["reasons"],
    })
    bad = rp.check_three_point(THREE_POINT_1031, gain_db=-8.0)
    out.append({
        "case": "D2_322Hz_residual_positive_feedback",
        "question": "残差压了 8.26 dB 但抵消臂比零臂还响 0.22 dB 时怎么判",
        "inputs": {"source": "10-31 recalibration receipt（boost 1.9756 / over -2.1944）"},
        "status": bad["status"],
        "cause": bad.get("cause"),
        "points": bad["points"],
        "reasons": bad["reasons"],
    })
    # 零/负环路提升：该频点没有可收回的增益，不进成败统计
    neg = rp.check_three_point(
        [{"frequency_hz": 322.0, "open_db": 0.0, "bypass_db": 0.2, "cancel_db": -2.0}],
        gain_db=-8.0)
    out.append({
        "case": "D3_322Hz_no_loop_boost_inapplicable",
        "question": "环路提升只有 0.2 dB（低于 0.5）时怎么判",
        "inputs": {"source": "构造：仅用于覆盖规则分支，不是实测"},
        "status": neg["status"],
        "cause": neg.get("cause"),
        "points": neg["points"],
        "reasons": neg["reasons"],
    })


def case_fifty_cm(inbox, out):
    base = inbox / "2026-10-24_side" / "for_b_side"
    files = sorted(base.glob("side16_seg_*.npz"))[:4]
    lags, statuses, snrs, first_capture = [], [], [], None
    for p in files:
        ref, mic, fs, md, _ = _capture(p)
        lags.append(int(estimate_lag(ref, mic)))
        g = rp.check_capture(ref, mic, fs, md)
        statuses.append(g["status"])
        snrs.append(g["metrics"].get("excitation_snr_db"))
        if first_capture is None:
            first_capture = g
    expected = int(np.median(lags)) if lags else None
    q, d = _load_model(base / "model_512_side.json")
    fit = rp.check_fit(q, FS, expected_peak_tap=expected)
    decided = rp.decide(capture=first_capture, fit=fit)
    out.append({
        "case": "E_fifty_cm_relocated",
        "question": "换到 50 cm 后重标定，采集与模型都合格、但没有三点验证，能不能自动装",
        "inputs": {"segments": [p.name for p in files], "lags": lags,
                   "model": "2026-10-24_side/for_b_side/model_512_side.json"},
        "status": decided["decision"]["status"],
        "cause": decided["decision"].get("cause"),
        "capture_statuses": statuses,
        "excitation_snr_db": [round(float(v), 2) if v is not None else None for v in snrs],
        "expected_peak_tap": expected,
        "fit_status": fit["status"],
        "fit_metrics": {k: fit["metrics"][k] for k in ("L1", "peak_tap", "peak_tap_delta")
                        if k in fit["metrics"]},
        "reasons": decided["decision"].get("reasons"),
        "blocked_at": decided["blocked_at"],
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default="D:/Always/QianSai/_inbox")
    ap.add_argument("--out-dir", default=str(ROOT / "report/verification/recalibration-policy-2026-11-01"))
    args = ap.parse_args()

    inbox = Path(args.inbox)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    case_old_model(inbox, cases)
    case_low_snr(inbox, cases)
    case_clipped(inbox, cases)
    case_322(inbox, cases)
    case_fifty_cm(inbox, cases)

    payload = {
        "schema_version": 1,
        "generated_by": "scripts/recal_offline_cases.py",
        "thresholds": {
            "MIN_VALID_FRAMES": rp.MIN_VALID_FRAMES,
            "MIN_EXCITATION_SNR_DB": rp.MIN_EXCITATION_SNR_DB,
            "MIN_GATED_COHERENCE": rp.MIN_GATED_COHERENCE,
            "SPARSE_LINE_DB": rp.SPARSE_LINE_DB,
            "L1_MAX": rp.L1_MAX,
            "PEAK_TAP_TOLERANCE": rp.PEAK_TAP_TOLERANCE,
            "BOOST_MIN_DB": rp.BOOST_MIN_DB,
            "OVER_MIN_DB": rp.OVER_MIN_DB,
            "ACOUSTIC_MIN_DB": rp.ACOUSTIC_MIN_DB,
            "MIN_PASSING_PROBES": rp.MIN_PASSING_PROBES,
        },
        "cases": cases,
    }
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    p = out_dir / "cases.json"
    p.write_bytes(text.encode("utf-8"))
    print("[%s] %d 例" % (p, len(cases)))
    for c in cases:
        print("  %-38s %-18s %s" % (c["case"], c["status"],
                                     (c.get("reasons") or [""])[0][:64]))
    print("\ncases.json sha256 %s" % hashlib.sha256(p.read_bytes()).hexdigest()[:16])


if __name__ == "__main__":
    main()
