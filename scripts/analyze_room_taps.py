"""房间夹具：抽头数与低频精度的取舍。

背景：A 报房间夹具 300-1000 Hz 模型不准（模型峰值 -0.68 dB vs 实测 7.71 dB），
并据"宽带预测误差只多 1.3 dB"判断"256 抽头够用、不用改 RTL"。

这个判断用错了量。决定 ASG 的是**最差频点**（max|H−Ĥ|），不是宽带 RMS。
本脚本给出 ASG 口径下的抽头对照，并检查低频是否真的比高频更难。

数据前提（重要）：seg_0 与 seg_2 的 ref→mic 延迟是 124 帧，其余段是 125 帧，
差一帧。跨段拼接时必须整段剔除，否则残差会被这一帧的相位差撑满。
seg_3/4/8 是音响静音时采的（mic −37 dBFS），本来就不能用。

用法：
    python scripts/analyze_room_taps.py --data-dir <含 seg_*.npz 的目录>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path                      # noqa: E402
from feedback.path_analysis import (coherence_from_spectra,             # noqa: E402
                                   fir_response, load_model_artifact,
                                   welch_cross)

FS_DEFAULT = 48828.125
BANDS = [(300, 1000), (1000, 3000), (3000, 6000), (6000, 12000)]
TAP_LIST = (128, 256, 384, 512, 680)
FRAME_BUDGET = 2048
CYCLES_PER_TAP = 3


def load_segment(path, fs, valid_frames):
    z = np.load(str(path), allow_pickle=True)
    md = json.loads(str(z["metadata_json"]))
    # replay_trial 元数据缺这两个字段；A 在 2026-10-21 报告里写明同一 I2S 帧对齐、零丢帧
    md.setdefault("alignment", "same_i2s_frame")
    md.setdefault("dropped_frames", 0)
    n = len(z["reference"]) if valid_frames is None else min(valid_frames, len(z["reference"]))
    return Capture(np.asarray(z["reference"], dtype=float)[:n],
                   np.asarray(z["microphone"], dtype=float)[:n], fs, md).validate()


def mic_dbfs(cap):
    return float(20.0 * np.log10(np.sqrt(np.mean(cap.microphone ** 2)) + 1e-30))


def lag_frames(reference, microphone):
    n = len(reference)
    spec = np.fft.rfft(microphone, 2 * n) * np.conj(np.fft.rfft(reference, 2 * n))
    corr = np.fft.irfft(spec, 2 * n)
    k = int(np.argmax(np.abs(corr)))
    return k if k < n else k - 2 * n


def stack(caps, fs):
    return Capture(np.concatenate([c.reference for c in caps]),
                   np.concatenate([c.microphone for c in caps]),
                   fs, dict(caps[0].metadata)).validate()


def scores(H, coherence, freqs, coef, gate):
    """返回 (全带 ASG, 各子带 (max|H|, 残差, CD))。"""
    Hh = fir_response(coef, fs_ref, freqs)
    band = (freqs >= 100) & (freqs <= 12000) & (coherence >= gate)
    peak_h = np.max(np.abs(H[band]))
    peak_e = np.max(np.abs((H - Hh)[band]))
    sub = {}
    for low, high in BANDS:
        sel = (freqs >= low) & (freqs < high) & (coherence >= gate)
        if not sel.any():
            continue
        resid = np.abs((H - Hh)[sel])
        sub[low] = (
            float(20 * np.log10(np.max(np.abs(H[sel])))),
            float(20 * np.log10(np.max(resid))),
            float(np.min(20 * np.log10(np.maximum(np.abs(H[sel]), 1e-30)
                                       / np.maximum(resid, 1e-30)))),
            float(20 * np.log10(np.max(np.abs(Hh[sel])))),
        )
    return float(20 * np.log10(peak_h / peak_e)), sub


fs_ref = FS_DEFAULT


def run(data_dir, gate=0.5):
    data_dir = Path(data_dir)
    segs = sorted(data_dir.glob("seg_*.npz"))
    if not segs:
        raise SystemExit("no seg_*.npz in " + str(data_dir))
    fs = FS_DEFAULT

    report = {"schema_version": 1, "kind": "room_tap_sweep", "data_dir": str(data_dir),
              "coherence_gate": gate, "segments": []}
    caps = {}
    for path in segs:
        cap = load_segment(path, fs, None)
        lag = lag_frames(cap.reference, cap.microphone)
        level = mic_dbfs(cap)
        usable = level > -25.0
        report["segments"].append({"file": path.name, "mic_rms_dbfs": level,
                                   "ref_to_mic_lag": lag, "usable_level": usable})
        caps[path.stem] = (cap, lag, usable)

    usable_lags = [v[1] for v in caps.values() if v[2]]
    # 只保留延迟与多数一致的段；差一帧的段会把残差撑满，必须整段剔除
    majority = max(set(usable_lags), key=usable_lags.count) if usable_lags else None
    keep = [k for k, v in caps.items() if v[2] and v[1] == majority]
    report["lag_majority"] = majority
    report["segments_kept"] = keep
    if len(keep) < 4:
        raise SystemExit("too few segments with consistent lag: " + str(keep))

    half = len(keep) // 2
    train_names, test_names = keep[:half], keep[half:]
    train = stack([caps[k][0] for k in train_names], fs)
    test = stack([caps[k][0] for k in test_names], fs)
    report["train"] = train_names
    report["test"] = test_names

    freqs, suu, sum_mic, smm = welch_cross(test.reference, test.microphone, fs, nperseg=2048)
    H = sum_mic / np.maximum(suu, 1e-300)
    coherence = coherence_from_spectra(suu, sum_mic, smm)

    models = {}
    shipped = data_dir / "candidate_room_v1_256_final.json"
    if shipped.exists():
        artifact = load_model_artifact(str(shipped))
        models["shipped %d" % artifact["taps"]] = np.asarray(artifact["coefficients"], dtype=float)
    for taps in TAP_LIST:
        models["refit %d" % taps] = np.asarray(fit_path(train, taps=taps)["coefficients"], dtype=float)

    rows = []
    for tag, coef in models.items():
        asg, sub = scores(H, coherence, freqs, coef, gate)
        rows.append({"model": tag, "asg_db": asg, "subbands": sub})
    report["models"] = rows

    # 高频 vs 低频的残差对比：判断"低频是否真的更难"
    report["low_vs_high"] = [
        {"model": r["model"],
         "low_resid_db": r["subbands"][300][1],
         "high_resid_db": r["subbands"][6000][1],
         "low_minus_high_db": r["subbands"][300][1] - r["subbands"][6000][1]}
        for r in rows if 300 in r["subbands"] and 6000 in r["subbands"]]

    report["frame_budget"] = {
        "budget": FRAME_BUDGET,
        "cycles_per_tap": CYCLES_PER_TAP,
        "taps_to_cycles": {str(t): CYCLES_PER_TAP * t + 3
                           for t in (256, 384, 512, 680, 1024)},
        "max_taps": (FRAME_BUDGET - 3) // CYCLES_PER_TAP,
    }
    return report


def report_lines(result):
    out = []
    out.append("房间夹具：抽头数与低频精度")
    out.append("  段：%d 个，延迟多数 %+d 帧，保留 %d 个（%s）"
               % (len(result["segments"]), result["lag_majority"] or 0,
                  len(result["segments_kept"]), ",".join(result["segments_kept"])))
    for seg in result["segments"]:
        out.append("    %-12s mic %+6.2f dBFS  延迟 %+d  %s"
                   % (seg["file"], seg["mic_rms_dbfs"], seg["ref_to_mic_lag"],
                      "可用" if seg["usable_level"] and seg["ref_to_mic_lag"] == result["lag_majority"]
                      else ("静音" if not seg["usable_level"] else "延迟不一致，剔除")))
    out.append("  训练 %s / 评价 %s（样本外）"
               % ("+".join(result["train"]), "+".join(result["test"])))
    out.append("")
    out.append("  全带 ASG（越大越好）与各子带 CD 最差：")
    for row in result["models"]:
        sub = row["subbands"]
        detail = "  ".join("%d-%d CD %+6.2f (|Hhat| %+5.2f)"
                           % (lo, lo if False else next(hi for lo2, hi in BANDS if lo2 == lo),
                              sub[lo][2], sub[lo][3])
                           for lo in sorted(sub))
        out.append("    %-14s ASG %+7.2f dB   %s" % (row["model"], row["asg_db"], detail))
    out.append("")
    out.append("  低频是否比高频难（残差差 > 0 表示低频更差）：")
    for row in result["low_vs_high"]:
        out.append("    %-14s 300-1000 %+6.2f  6-12k %+6.2f  → %+5.2f dB"
                   % (row["model"], row["low_resid_db"], row["high_resid_db"],
                      row["low_minus_high_db"]))
    fb = result["frame_budget"]
    out.append("")
    out.append("  架构：帧预算 %d 拍，每抽头 %d 拍 → 上限 %d 抽头"
               % (fb["budget"], fb["cycles_per_tap"], fb["max_taps"]))
    out.append("    " + "  ".join("%s→%d拍" % (k, v) for k, v in fb["taps_to_cycles"].items()))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--gate", type=float, default=0.5)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    result = run(args.data_dir, gate=args.gate)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        print("written", args.output)
    for line in report_lines(result):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
