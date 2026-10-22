"""用开环采集（含板上 pred）算真实的抵消深度与稳定增益。

为什么要有这个脚本：
1. 阈值反推是单点估计、要推到啸叫、且被音响待机污染过（2026-10-21 的教训）。
   开环采一次 0.67 s 就能拿到全带的 H，不需要任何 β 假设。
2. 相干门控不是可选项。2026-10-22 的实测里，900 Hz 附近相干塌到 0.005，
   不做门控会把 CD 从 +14.8 dB 拖成 -14.3 dB——结论的符号都变了。
3. 如果 npz 里带板上算出的 prediction_pcm，就直接用它算残差，
   这样不依赖任何模型假设（RTL 已由 bit_exact 验证）。

用法：
    python scripts/analyze_live_h.py --npz <采集.npz>
    python scripts/analyze_live_h.py --npz <采集.npz> --coef candidate_box_v1_256.json
    python scripts/analyze_live_h.py --npz <采集.npz> --output out.json

npz 需要 reference / microphone；带 prediction_pcm 时优先用它。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from feedback.path_analysis import (coherence_from_spectra,  # noqa: E402
                                   fir_response, load_model_artifact,
                                   welch_cross)

FULL_SCALE = 1 << 23
COHERENCE_GATE = 0.8
BAND_LOW_HZ = 100.0
BAND_HIGH_HZ = 12000.0


def load_any(path, coef_path=None):
    """读采集；prediction 优先用板上给的，其次用系数算。"""
    z = np.load(str(path), allow_pickle=True)
    meta = {}
    if "metadata_json" in z:
        meta = json.loads(str(z["metadata_json"]))
    reference = np.asarray(z["reference"], dtype=float)
    microphone = np.asarray(z["microphone"], dtype=float)
    fs = float(z["sample_rate_hz"])

    if "prediction_pcm" in z:
        prediction = np.asarray(z["prediction_pcm"], dtype=float) / FULL_SCALE
        source = "board"
    else:
        if coef_path is None:
            raise SystemExit("npz has no prediction_pcm; pass --coef <model.json>")
        artifact = load_model_artifact(str(coef_path))
        taps = int(artifact["taps"])
        # 与 RTL 同口径：pred[n] = sum h[k]·x[n-1-k]
        prediction = np.convolve(reference, artifact["coefficients"])[:len(reference)]
        prediction = np.concatenate([np.zeros(taps), prediction[:len(reference) - taps]]) \
            if taps < len(reference) else prediction
        source = "python"
    return reference, microphone, prediction, fs, meta, source


def time_domain(reference, microphone, prediction):
    """时域抑制量：不依赖窗长、门控与模型。"""
    mic = np.round(microphone * FULL_SCALE)
    res = mic - np.round(prediction * FULL_SCALE)
    peak = 20.0 * np.log10(np.max(np.abs(res)) / np.max(np.abs(mic)))
    rms = 20.0 * np.log10(np.sqrt(np.mean((res / FULL_SCALE) ** 2))
                          / np.sqrt(np.mean(microphone ** 2)))
    return {
        "mic_peak_code": int(np.max(np.abs(mic))),
        "residual_peak_code": int(np.max(np.abs(res))),
        "peak_ratio_db": float(peak),
        "rms_ratio_db": float(rms),
        "mic_clipped_samples": int(np.count_nonzero(np.abs(mic) >= FULL_SCALE - 1)),
    }


def spectra(reference, microphone, prediction, fs, nperseg):
    freqs, suu, sum_mic, smm = welch_cross(reference, microphone, fs, nperseg=nperseg)
    _, _, sum_pred, _ = welch_cross(reference, prediction, fs, nperseg=nperseg)
    H = sum_mic / np.maximum(suu, 1e-300)
    Hp = sum_pred / np.maximum(suu, 1e-300)
    coherence = coherence_from_spectra(suu, sum_mic, smm)
    return freqs, H, Hp, coherence


def peak(magnitude, band, freqs):
    values = np.abs(magnitude[band])
    index = np.where(band)[0][int(np.argmax(values))]
    return float(20.0 * np.log10(values.max() + 1e-30)), float(freqs[index])


def cd_curve(H, H_eff):
    return 20.0 * np.log10(np.maximum(np.abs(H), 1e-30) / np.maximum(np.abs(H_eff), 1e-30))


def negative_segments(freqs, cd, band, min_width_hz=50.0):
    f = freqs[band]
    neg = cd[band] <= 0.0
    segments, start = [], None
    for index, flag in enumerate(neg):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            segments.append((float(f[start]), float(f[index - 1])))
            start = None
    if start is not None:
        segments.append((float(f[start]), float(f[-1])))
    return [{"low_hz": a, "high_hz": b, "width_hz": float(b - a)}
            for a, b in segments if b - a >= min_width_hz]


def run(path, coef_path=None, nperseg_list=(1024, 2048, 4096), gate=COHERENCE_GATE):
    reference, microphone, prediction, fs, meta, source = load_any(path, coef_path)
    result = {
        "schema_version": 1,
        "kind": "live_h_analysis",
        "npz": str(path),
        "prediction_source": source,
        "sample_rate_hz": fs,
        "frames": int(len(reference)),
        "coherence_gate": gate,
        "metadata": {k: meta[k] for k in
                     ("fixture_id", "hp_volume", "frames", "mic_rms_dbfs",
                      "mic_peak_dbfs", "bit_sha256") if k in meta},
    }
    result["time_domain"] = time_domain(reference, microphone, prediction)

    windows = []
    main = None
    for nperseg in nperseg_list:
        freqs, H, Hp, coh = spectra(reference, microphone, prediction, fs, nperseg)
        band = (freqs >= BAND_LOW_HZ) & (freqs <= BAND_HIGH_HZ) & (coh >= gate)
        if not band.any():
            continue
        segments = 1 + (len(reference) - nperseg) // (nperseg // 2)
        peak_H, at_H = peak(H, band, freqs)
        peak_eff, at_eff = peak(H - Hp, band, freqs)
        cd = cd_curve(H, H - Hp)
        entry = {
            "nperseg": int(nperseg),
            "segments": int(segments),
            "bins_used": int(np.count_nonzero(band)),
            "max_abs_H_db": peak_H,
            "max_abs_H_at_hz": at_H,
            "max_abs_H_eff_db": peak_eff,
            "max_abs_H_eff_at_hz": at_eff,
            "asg_db": float(peak_H - peak_eff),
            "cancel_howl_at_gain_db": float(-peak_eff),
            "cd_worst_db": float(cd[band].min()),
            "cd_worst_at_hz": float(freqs[band][np.argmin(cd[band])]),
            "cd_nonpositive_bins": int(np.count_nonzero(cd[band] <= 0.0)),
            "cd_negative_segments": negative_segments(freqs, cd, band),
            "coherence_median": float(np.median(coh[band])),
        }
        windows.append(entry)
        if nperseg == 2048:
            main = (entry, freqs, H, H - Hp, coh, band)

    result["window_sweep"] = windows

    # 门控敏感性：解释"为什么不同人算出不同结论"
    if main is not None:
        _, freqs, H, H_eff, coh, band = main   # H_eff 已是残差 H - H_pred
        sens = []
        for g in (0.0, 0.5, 0.7, 0.8, 0.9):
            sel = (freqs >= BAND_LOW_HZ) & (freqs <= BAND_HIGH_HZ) & (coh >= g)
            if not sel.any():
                continue
            cd = cd_curve(H, H_eff)
            sens.append({
                "gate": g,
                "bins": int(np.count_nonzero(sel)),
                "max_abs_H_eff_db": peak(H_eff, sel, freqs)[0],
                "cd_worst_db": float(cd[sel].min()),
            })
        result["gate_sensitivity"] = sens

        subbands = []
        for low, high in ((100, 300), (300, 600), (600, 1000), (1000, 3000),
                          (3000, 8000), (8000, 12000)):
            sel = (freqs >= low) & (freqs < high) & (coh >= gate)
            if not sel.any():
                subbands.append({"low_hz": low, "high_hz": high, "bins": 0,
                                 "note": "no bin passes the coherence gate"})
                continue
            cd = cd_curve(H, H_eff)
            subbands.append({
                "low_hz": low, "high_hz": high,
                "bins": int(np.count_nonzero(sel)),
                "max_abs_H_db": peak(H, sel, freqs)[0],
                "max_abs_H_eff_db": peak(H_eff, sel, freqs)[0],
                "cd_worst_db": float(cd[sel].min()),
                "coherence_median": float(np.median(coh[sel])),
            })
        result["subbands"] = subbands
    return result


def report_lines(result):
    lines = []
    td = result["time_domain"]
    lines.append("开环采集分析（%d 帧，pred 来源：%s）"
                 % (result["frames"], result["prediction_source"]))
    meta = result.get("metadata", {})
    if meta:
        lines.append("  fixture %s, hp_volume %s, mic RMS %s dBFS"
                     % (meta.get("fixture_id"), meta.get("hp_volume"), meta.get("mic_rms_dbfs")))
    lines.append("")
    lines.append("【时域】不依赖窗长与门控")
    lines.append("  max|mic| %d 码 → max|mic-pred| %d 码：峰值比 %+.2f dB"
                 % (td["mic_peak_code"], td["residual_peak_code"], td["peak_ratio_db"]))
    lines.append("  RMS 比 %+.2f dB（负=抑制，正=放大）" % td["rms_ratio_db"])
    if td["mic_clipped_samples"]:
        lines.append("  ⚠ 麦克风削顶 %d 个样本，本份数据不可用于定量" % td["mic_clipped_samples"])
    lines.append("")
    lines.append("【频域】窗长扫描（门控 %.2f）" % result["coherence_gate"])
    lines.append("  nperseg  段数  max|H|          max|H-Heff|     ASG      CD最差")
    for row in result["window_sweep"]:
        lines.append("  %7d  %4d  %+6.2f@%4.0fHz  %+7.2f@%4.0fHz  %+6.2f  %+7.2f@%4.0fHz"
                     % (row["nperseg"], row["segments"],
                        row["max_abs_H_db"], row["max_abs_H_at_hz"],
                        row["max_abs_H_eff_db"], row["max_abs_H_eff_at_hz"],
                        row["asg_db"], row["cd_worst_db"], row["cd_worst_at_hz"]))
    lines.append("")
    if "gate_sensitivity" in result:
        lines.append("【门控敏感性】同一份数据，只改相干门控")
        for row in result["gate_sensitivity"]:
            lines.append("  相干>=%.1f  %2d bins  max|H-Heff| %+6.2f dB  CD最差 %+7.2f dB"
                         % (row["gate"], row["bins"], row["max_abs_H_eff_db"], row["cd_worst_db"]))
        lines.append("")
    if "subbands" in result:
        lines.append("【逐子带】")
        for row in result["subbands"]:
            if not row.get("bins"):
                lines.append("  %5d-%5d Hz  无可用 bin" % (row["low_hz"], row["high_hz"]))
                continue
            lines.append("  %5d-%5d Hz  %2d bins  max|H| %+6.2f  max|H-Heff| %+6.2f  CD最差 %+7.2f  相干 %.2f"
                         % (row["low_hz"], row["high_hz"], row["bins"], row["max_abs_H_db"],
                            row["max_abs_H_eff_db"], row["cd_worst_db"], row["coherence_median"]))
    lines.append("")
    main = next((r for r in result["window_sweep"] if r["nperseg"] == 2048), None)
    if main:
        lines.append("【CD<=0 的频段】（nperseg 2048）")
        if main["cd_negative_segments"]:
            for seg in main["cd_negative_segments"]:
                lines.append("  %6.0f-%6.0f Hz  宽 %5.0f Hz"
                             % (seg["low_hz"], seg["high_hz"], seg["width_hz"]))
        else:
            lines.append("  无（CD<=0 的 bin 数 %d/%d）"
                         % (main["cd_nonpositive_bins"], main["bins_used"]))
        lines.append("")
        lines.append("【预测的闭环阈值】（仅线性小信号，非实测 ASG）")
        lines.append("  旁路起振 %+.2f dB  |  抵消起振 %+.2f dB  |  ASG %+.2f dB"
                     % (-main["max_abs_H_db"], main["cancel_howl_at_gain_db"], main["asg_db"]))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--npz", required=True)
    parser.add_argument("--coef", default=None, help="npz 无 prediction_pcm 时的模型文件")
    parser.add_argument("--gate", type=float, default=COHERENCE_GATE)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    result = run(args.npz, coef_path=args.coef, gate=args.gate)
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
