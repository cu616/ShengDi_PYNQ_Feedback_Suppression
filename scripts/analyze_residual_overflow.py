"""定位首次残差越界，并比较"现在就在残差处钳到 24 位"与"宽残差保留到增益之后再量化"。

只做给定输入下的算术核对：不加载配置、不播放、不操板。
输入是一个 replay 抓包 npz（正常完成或 guard 抓包都行），字段：
  reference / microphone（浮点，÷2^23 归一化）、prediction_pcm / residual_pcm（24 位整数）、
  coefficients_q20、metadata_json（含 gain_q12）。

它回答四个问题，按顺序：
  [1] 板上记录的 prediction/residual 能不能被本地整数路径逐样本重现（不能就是算术/口径问题，先别谈机理）
  [2] 首次越界在第几帧，那一帧的 mic / pred / residual / 参考各是多少，前后各 16 帧怎么走
  [3] 越界前有没有增长趋势（逐窗 RMS 斜率），还是孤立一个尖峰
  [4] 把宽残差（25 位、不钳）直接乘数字增益，会不会仍然越出输出范围
       —— 这一条决定"残差处钳位"是不是过早
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

Q = 20
SCALE = 1 << 23  # PCM 满幅（计数）；与 verify_r4_waveforms.py 的 SCALE 一致
# 单文件、只依赖 numpy：这样 A 可以直接把本文件拷到板上跑，不需要整个仓库。


def rtl_predict(q20: np.ndarray, u_codes: np.ndarray) -> tuple[np.ndarray, int]:
    """逐样本重现 feedback_fir：int64 累加、(|acc|+2^19)>>20、钳到 ±2^23 计数。"""
    taps = len(q20)
    n = len(u_codes)
    out = np.zeros(n, dtype=np.int64)
    h = q20.astype(np.int64)
    u = u_codes.astype(np.int64)
    sat = 0
    for i in range(n):
        upto = min(taps, i)
        if upto == 0:
            continue
        acc = int(np.dot(h[:upto], u[i - 1::-1][:upto]))
        mag = (abs(acc) + (1 << (Q - 1))) >> Q
        val = -mag if acc < 0 else mag
        if val > SCALE - 1 or val < -SCALE:
            sat += 1
            val = max(-SCALE, min(SCALE - 1, val))
        out[i] = val
    return out, sat


def gain_from_metadata(meta: dict) -> tuple[int, float]:
    q12 = int(meta.get("gain_q12", 0))
    return q12, q12 / 4096.0


def growth_slope(x: np.ndarray, upto: int, win: int = 256) -> list[float]:
    """越界点之前，按窗口算 |x| 的 RMS（dB），返回逐窗序列，用来看是爬升还是孤立尖峰。"""
    lo = max(0, upto - 8 * win)
    out = []
    for s in range(lo, upto - win + 1, win):
        seg = x[s:s + win]
        out.append(float(20 * np.log10(np.sqrt(np.mean(seg.astype(np.float64) ** 2)) / SCALE + 1e-30)))
    return out


def analyze(path: Path, model_q20: np.ndarray | None = None, gain_db: float | None = None) -> dict:
    cap = np.load(path, allow_pickle=True)
    meta = json.loads(str(cap["metadata_json"]))
    fs = float(cap["sample_rate_hz"])
    q20 = (model_q20 if model_q20 is not None
           else np.asarray(cap["coefficients_q20"], dtype=np.int64))
    ref = np.asarray(cap["reference"], dtype=np.float64)
    mic = np.asarray(cap["microphone"], dtype=np.float64)
    n = len(ref)

    ref_c = np.rint(ref * SCALE).astype(np.int64)
    mic_c = np.rint(mic * SCALE).astype(np.int64)

    pred, pred_sats = rtl_predict(q20, ref_c)
    resid_wide = mic_c - pred                      # 25 位，未钳
    resid_narrow = np.clip(resid_wide, -SCALE, SCALE - 1)
    over = np.abs(resid_wide) >= SCALE

    g12, g = gain_from_metadata(meta)
    if gain_db is not None:
        g12 = int(round(4096 * 10 ** (gain_db / 20)))
        g = g12 / 4096.0
    # audio_pl_replay.v: gain_product = residual*gain_q12；gain = (product+2048)>>12
    out_wide = ((resid_wide * g12 + 2048) >> 12)
    out_over = np.abs(out_wide) >= SCALE

    res = {
        "file": path.name,
        "frames": int(n),
        "fixture_id": meta.get("fixture_id"),
        "gain_q12": g12,
        "gain_db": 20 * np.log10(g) if g > 0 else None,
        "bit_ids": {
            "bit_sha256": meta.get("bit_sha256"),
            "coefficients_sha256": meta.get("coefficients_sha256"),
        },
        "recorded": {
            "prediction_saturations": meta.get("prediction_saturations"),
            "residual_saturations": meta.get("residual_saturations"),
            "gain_saturations": meta.get("gain_saturations"),
            "mix_saturations": meta.get("mix_saturations"),
            "stop_reason": meta.get("stop_reason"),
        },
    }

    # [1] 算术可重现性
    npz_q20 = np.asarray(cap["coefficients_q20"], dtype=np.int64)
    coeff_same = bool(np.array_equal(q20, npz_q20))
    rec_pred = np.asarray(cap["prediction_pcm"], dtype=np.int64) if "prediction_pcm" in cap else None
    rec_res = np.asarray(cap["residual_pcm"], dtype=np.int64) if "residual_pcm" in cap else None
    skip = len(q20) + 1
    res["replay"] = {"history_excluded_frames": int(skip), "coefficients_same_as_recorded": coeff_same}
    if rec_pred is not None and not coeff_same:
        res["replay"]["note"] = "系数被外部覆盖，与板上记录不可比，跳过失配计数"
    if rec_pred is not None and coeff_same:
        res["replay"]["prediction_mismatches"] = int(np.count_nonzero(pred[skip:] != rec_pred[skip:]))
        res["replay"]["prediction_evaluated"] = int(n - skip)
    if rec_res is not None and coeff_same:
        res["replay"]["residual_mismatches"] = int(np.count_nonzero(resid_narrow[skip:] != rec_res[skip:]))
        res["replay"]["residual_evaluated"] = int(n - skip)
    res["replay"]["local_prediction_saturations"] = int(pred_sats)

    # [2] 首次越界
    if over.any():
        first = int(np.argmax(over))
    else:
        first = -1
    res["overflow"] = {
        "first_overflow_frame": first,
        "samples_over": int(over.sum()),
        "max_abs_residual_wide": float(np.abs(resid_wide).max() / SCALE),
        "max_abs_residual_narrow": float(np.abs(resid_narrow).max() / SCALE),
        "max_abs_mic": float(np.abs(mic_c).max() / SCALE),
        "max_abs_pred": float(np.abs(pred).max() / SCALE),
        "headroom_to_full_scale_db": (
            float(-20 * np.log10(np.abs(resid_wide).max() / SCALE)) if np.abs(resid_wide).max() > 0 else None),
        "headroom_db_before_overflow": (
            float(-20 * np.log10(np.abs(resid_wide).max() / SCALE)) if np.abs(resid_wide).max() > 0 else None),
    }
    if first >= 0:
        lo, hi = max(0, first - 16), min(n, first + 17)
        res["overflow"]["around_first"] = {
            "frame": list(range(lo, hi)),
            "mic": (mic_c[lo:hi] / SCALE).round(6).tolist(),
            "pred": (pred[lo:hi] / SCALE).round(6).tolist(),
            "residual_wide": (resid_wide[lo:hi] / SCALE).round(6).tolist(),
            "reference": (ref_c[lo:hi] / SCALE).round(6).tolist(),
        }
        res["overflow"]["growth_before_db"] = growth_slope(resid_wide, first)
        seg = resid_wide[max(0, first - 512):first]
        res["overflow"]["rms_512_before_db"] = (
            float(20 * np.log10(np.sqrt(np.mean(seg.astype(np.float64) ** 2)) / SCALE + 1e-30)) if len(seg) else None)

    # [3] 宽残差乘完增益还越界吗
    res["output"] = {
        "over_after_gain": int(out_over.sum()),
        "first_out_overflow_frame": int(np.argmax(out_over)) if out_over.any() else -1,
        "max_abs_after_gain": float(np.abs(out_wide).max() / SCALE),
        "margin_db": float(-20 * np.log10(np.abs(out_wide).max() / SCALE)) if np.abs(out_wide).max() > 0 else None,
        "theoretical_residual_ceiling": float(1.0 / g) if g > 0 else None,
    }

    # [4] 钳位造成的失真（只在真的钳过时才有意义）
    err = resid_narrow - resid_wide
    res["clip_cost"] = {
        "clipped_samples": int(over.sum()),
        "err_rms_db_rel_signal": (
            float(20 * np.log10(np.sqrt(np.mean(err.astype(np.float64) ** 2))
                                / (np.sqrt(np.mean(resid_wide.astype(np.float64) ** 2)) + 1e-30) + 1e-30))
            if over.any() else None),
    }
    return res


def ps_margin(q20: np.ndarray | None, model_label: str | None, fs: float = 48828.125) -> None:
    """PS 拓扑裕量：residual/mic = 1/(1 + g·e^(-j2ω)·Ĥ)，与真实路径无关，只取决于模型与增益。"""
    if q20 is None:
        print("  --ps-margin 需要同时给 --model")
        return
    nfft = 1 << 15
    w_idx = np.arange(nfft // 2 + 1)
    w = 2 * np.pi * w_idx / nfft
    h = q20.astype(float) / (1 << Q)
    # pred = h·u[n-1-k] 给一拍，u = g·residual[n-2] 再给两拍 → 分母里共 3 拍
    Hh = np.fft.rfft(h, nfft) * np.exp(-3j * w)
    freqs = w_idx * fs / nfft
    sel = (freqs >= 300) & (freqs <= 10250)
    print()
    print("=" * 78)
    print(f"PS 拓扑裕量（{model_label}）：residual/mic = 1/(1+g·e^-j2ω·Ĥ)")
    print("=" * 78)
    print("  增益      min|1+…|   @Hz      残差/麦克风   mic 峰值到该值残差即满幅")
    for gdb in (-6.0, -8.0, -10.0, -12.0, -14.0):
        g = 10 ** (gdb / 20)
        den = np.abs(1 + g * Hh)
        k = int(np.argmin(np.where(sel, den, np.inf)))
        print(f"  {gdb:+6.1f}   {den[k]:8.3f}   {freqs[k]:7.1f}   {1 / den[k]:8.2f}x    "
              f"{den[k]:.4f} ({20 * np.log10(den[k]):+.1f} dBFS)")
    g = 10 ** (-8 / 20)
    den = np.abs(1 + g * Hh)
    gate = 10 ** (-6 / 20)
    k = int(np.argmin(np.where(sel, den, np.inf)))
    print(f"  现场门限 −6 dBFS（峰值 {gate:.3f}）时，最差频点残差峰值 = "
          f"{gate / den[k]:.3f}（满幅的 {100 * gate / den[k]:.0f}%）；余量 "
          f"{-20 * np.log10(gate / den[k]):+.2f} dB")
    for lo, hi in ((390.0, 401.0),):
        sub = sel & (freqs >= lo) & (freqs <= hi)
        ks = np.where(sub)[0]
        print(f"  最差点所在带 {lo:.0f}–{hi:.0f} Hz：|Ĥ| = "
              f"{np.abs(Hh[ks]).min():.3f}–{np.abs(Hh[ks]).max():.3f}，"
              f"相位 {np.degrees(np.angle(Hh[ks])).min():+.0f}…{np.degrees(np.angle(Hh[ks])).max():+.0f}°")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", nargs="+", default=[], help="一个或多个 replay 抓包 npz")
    ap.add_argument("--model", default=None,
                    help="用这个模型 JSON 的 Q20 覆盖 npz 里的系数（开环抓包常是零系数）")
    ap.add_argument("--gain-db", type=float, default=None,
                    help="按这个数字增益评输出范围；默认用 npz 的 gain_q12，开环抓包是 0")
    ap.add_argument("--ps-margin", action="store_true",
                    help="只用模型算 PS 拓扑的残差放大表（不需要抓包）")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    print("=" * 78)
    print("残差越界定位（给定输入下的算术，不含闭环稳定性结论）")
    print("口径：PCM 满幅 = 2^23 计数；残差在 feedback_fir 内钳到 24 位，")
    print("      数字增益在 audio_pl_replay 之后才乘 —— 钳位点在增益之前。")
    print("=" * 78)

    model_q20 = None
    if args.model:
        m = json.loads((REPO / args.model).read_bytes().decode("utf-8")) if not Path(args.model).is_absolute() \
            else json.loads(Path(args.model).read_bytes().decode("utf-8"))
        model_q20 = np.asarray(m["coefficients_q20"], dtype=np.int64)
        print(f"系数覆盖：{args.model}（{len(model_q20)} 抽头）")
    if args.ps_margin:
        ps_margin(model_q20 if model_q20 is not None else None, args.model)

    allres = []
    for item in args.npz:
        p = Path(item)
        if not p.exists():
            print(f"  跳过（不存在）：{p}")
            continue
        r = analyze(p, model_q20, args.gain_db)
        allres.append(r)
        print()
        print(f"--- {r['file']}  frames={r['frames']}  gain_q12={r['gain_q12']}  "
              f"gain={r['gain_db']:+.3f} dB" if r["gain_db"] is not None else f"--- {r['file']}")
        print(f"  板上记录：pred_sat={r['recorded']['prediction_saturations']} "
              f"res_sat={r['recorded']['residual_saturations']} "
              f"gain_sat={r['recorded']['gain_saturations']} mix_sat={r['recorded']['mix_saturations']} "
              f"stop={r['recorded']['stop_reason']}")
        rep = r["replay"]
        if rep.get("note"):
            print(f"  [1] {rep['note']}；本地饱和计数 {rep['local_prediction_saturations']}")
        elif "prediction_mismatches" in rep:
            print(f"  [1] 本地整数路径：prediction 失配 {rep['prediction_mismatches']}/"
                  f"{rep['prediction_evaluated']}，residual 失配 {rep.get('residual_mismatches')}/"
                  f"{rep.get('residual_evaluated')}，本地饱和计数 {rep['local_prediction_saturations']}")
        o = r["overflow"]
        print(f"  [2] |mic|max={o['max_abs_mic']:.4f}  |pred|max={o['max_abs_pred']:.4f}  "
              f"|resid_wide|max={o['max_abs_residual_wide']:.4f}（满幅 1.0，"
              f"再抬 {o['headroom_to_full_scale_db']:+.2f} dB 才越界）")
        if o["first_overflow_frame"] >= 0:
            print(f"      首次越界帧 {o['first_overflow_frame']}，越界样本 {o['samples_over']}，"
                  f"开始越界前还有 {o['headroom_db_before_overflow']:+.2f} dB 余量")
            g = o.get("growth_before_db") or []
            if g:
                print("      越界前逐 256 帧 RMS(dBFS)：" + " ".join(f"{v:+.1f}" for v in g))
            if "rms_512_before_db" in o:
                print(f"      越界前 512 帧残差 RMS {o['rms_512_before_db']:+.2f} dBFS")
        else:
            print("      本文件没有越界样本")
        ot = r["output"]
        print(f"  [3] 宽残差乘完增益：|out|max={ot['max_abs_after_gain']:.4f}，"
              f"越界样本 {ot['over_after_gain']}，余量 {ot['margin_db']:+.2f} dB"
              if ot["margin_db"] is not None else "  [3] —")
        print(f"      按增益算，残差最多可以到 {ot['theoretical_residual_ceiling']:.2f} 才越输出（当前钳在 1.00）")
        cc = r["clip_cost"]
        if cc["err_rms_db_rel_signal"] is None:
            print(f"  [4] 钳位代价：没有裁到样本")
        else:
            print(f"  [4] 钳位代价：裁掉 {cc['clipped_samples']} 个样本，"
                  f"失真 RMS 相对残差 {cc['err_rms_db_rel_signal']:+.1f} dB")

    if args.json_out and allres:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(allres, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\n结构化结果写入 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
