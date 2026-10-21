"""标定↔使用耦合失配诊断。

用途：当"按标定数据预测的 ASG"与"板上实测的 ASG"不一致时，判断失配来自
幅度（耦合强弱变了）还是形状（路径本身变了），并给出各候选方案的定量效果。

核心量：beta = 实测耦合 / 标定耦合。
若实时路径 H_live = beta · H_calib，而系数按 H_calib 拟合，则

    max|H_live - Hhat| = |beta·H - Hhat|

beta 一旦小于约 0.5，抵消后的环路峰值就会超过旁路，CD 翻负。

beta 的来源有两种，脚本文档里分开写：
  1) --beta 直接给（分析用）；
  2) --msg-bypass-db 由实测旁路起振增益反推（实测用，更可信）。

用法：
    python scripts/diagnose_mismatch.py --data-dir <目录>
    python scripts/diagnose_mismatch.py --data-dir <目录> --msg-bypass-db -19.5
    python scripts/diagnose_mismatch.py --data-dir <目录> --output out.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path, load_capture  # noqa: E402
from feedback.path_analysis import (coherence_from_spectra,  # noqa: E402
                                   fir_response, load_model_artifact,
                                   welch_cross)

FS_DEFAULT = 48828.125
TAPS_CHOICES = (128, 256, 512)


def estimate_path(capture, fs):
    freqs, suu, sum_, smm = welch_cross(capture.reference, capture.microphone, fs)
    H = sum_ / np.maximum(suu, 1e-300)
    return freqs, H, coherence_from_spectra(suu, sum_, smm)


def usable_band(freqs, coherence, low=100.0, high=12000.0, gate=0.8):
    """参与评价的频带。

    下界 100 Hz 而不是 20 Hz：标定帧数下 100 Hz 以下只有几根谱线，且
    Codec 交流耦合会压低低频，估出来的 H 不可复现。
    上界 12000 Hz：再往上相干掉到 0.5 以下，H 是噪声。
    """
    return (freqs >= low) & (freqs <= high) & (coherence >= gate)


def cd_curve(H_live, H_hat, floor=1e-30):
    return 20.0 * np.log10(np.maximum(np.abs(H_live), floor)
                           / np.maximum(np.abs(H_live - H_hat), floor))


def negative_segments(freqs, cd, band, min_width_hz=50.0):
    """CD <= 0 的连续频段。决定稳定性的是峰值，所以这里只用于描述分布。"""
    f = freqs[band]
    neg = cd[band] <= 0.0
    segments, start = [], None
    for index, flag in enumerate(neg):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            segments.append((f[start], f[index - 1]))
            start = None
    if start is not None:
        segments.append((f[start], f[-1]))
    return [(float(a), float(b), float(b - a)) for a, b in segments if b - a >= min_width_hz]


def phase_gated(freqs, effective, band, frames_ahead=2, fs=FS_DEFAULT, top=8):
    """相位允许起振的频点。

    闭环调度是 played[n+2] = gain(residual[n])，所以环路里多 2 帧延迟，
    必须算进相位条件，否则候选频点会整体偏移。
    """
    loop = effective * np.exp(-1j * 2.0 * np.pi * freqs * frames_ahead / fs)
    phase = np.unwrap(np.angle(loop))
    turns = phase / (2.0 * np.pi)
    index = np.where(band)[0]
    candidates = []
    for a, b in zip(index[:-1], index[1:]):
        # 只有相位真正穿过 2π 的整数倍才允许起振。间隔由群延迟决定
        # （纯延迟 d 帧时约 fs/d），不是任意频点都能叫——写成"相位接近 π 的整数倍"
        # 会让几乎每个 bin 都成为候选，那种候选表没有意义。
        if np.floor(turns[a]) != np.floor(turns[b]):
            candidates.append((float(freqs[a]), float(20.0 * np.log10(abs(effective[a]) + 1e-30))))
    candidates.sort(key=lambda item: -item[1])
    return [{"frequency_hz": hz, "loop_gain_db": db, "howl_at_gain_db": -db}
            for hz, db in candidates[:top]]


def peak(freqs, magnitude, band):
    """返回 (dB, 频率)。峰值处频率才是起振频点，不要只报 dB。"""
    values = np.abs(magnitude[band])
    index = np.where(band)[0][int(np.argmax(values))]
    return float(20.0 * np.log10(np.max(values) + 1e-30)), float(freqs[index])


def subband_table(freqs, H_live, H_hat, edges):
    rows = []
    for low, high in edges:
        mask = (freqs >= low) & (freqs < high)
        if not mask.any():
            continue
        ratio = float(np.max(np.abs((H_live - H_hat)[mask])) / np.max(np.abs(H_live[mask])))
        rows.append({
            "low_hz": float(low),
            "high_hz": float(high),
            "ratio": ratio,
            "ratio_db": float(20.0 * np.log10(ratio)),
            "residual_max_db": float(20.0 * np.log10(np.max(np.abs((H_live - H_hat)[mask])) + 1e-30)),
            "cd_worst_db": float(np.min(cd_curve(H_live, H_hat)[mask])),
        })
    return rows


def scheme_scores(freqs, H_live, coefficients_by_taps, band, beta):
    """各候选方案的 ASG（= 旁路峰值 / 抵消峰值，越大越好）。

    分频段方案给的是**上界**：假设能完美只保留 CD>0 的频段，实际实现做不到
    （FIR 系数无法在频域任意开关），所以它只能证明"这个方向的上限是多少"。
    """
    peak_bypass, _ = peak(freqs, H_live, band)
    scores = {}

    def add(name, effective, note=""):
        peak_eff, at_hz = peak(freqs, effective, band)
        # 完美估计器会让残差趋于 0，ASG 变成 1/0。低于 -60 dB 视为数值下限，
        # 报 None 而不是一个天文数字——那种数字会被误读成"有极大收益"。
        scores[name] = {
            "asg_db": None if peak_eff < -60.0 else float(peak_bypass - peak_eff),
            "effective_peak_db": peak_eff,
            "howl_at_gain_db": float(-peak_eff),
            "peak_at_hz": at_hz,
            "below_numeric_floor": bool(peak_eff < -60.0),
            "note": note,
        }

    for taps in TAPS_CHOICES:
        if taps in coefficients_by_taps:
            add("%d 抽头 + 全带抵消" % taps, H_live - coefficients_by_taps[taps])
    if 256 in coefficients_by_taps:
        cd = cd_curve(H_live, coefficients_by_taps[256])
        band_only = np.where(cd[band] > 0.0, coefficients_by_taps[256][band], 0.0)
        keep = float(np.count_nonzero(cd[band] > 0.0)) / float(np.count_nonzero(band))
        masked = np.zeros_like(coefficients_by_taps[256])
        masked[band] = band_only
        add("分频段（只留 CD>0，上界）", H_live - masked,
            "保留 %.1f%% 的频段；FIR 无法在频域任意开关，这是理想上界" % (100.0 * keep))
        add("幅度匹配 alpha=beta", H_live - beta * coefficients_by_taps[256],
            "系数整体乘 beta，等价于按实测幅度重新标定")
    add("完美估计器（真值 H，不可实现）", H_live - H_live,
        "诊断用上界，不是方案")
    return {"peak_bypass_db": peak_bypass, "schemes": scores}


def refit_at_beta(training, beta, taps, fs):
    """在"耦合缩到 beta 倍"的数据上重新拟合，代表"按当前夹具重新标定"。"""
    scaled = Capture(training.reference, training.microphone * beta, fs, dict(training.metadata))
    return fit_path(scaled, taps=taps)


def run(data_dir, beta=None, msg_bypass_db=None, output=None, taps_main=256):
    data_dir = Path(data_dir)
    training = load_capture(str(data_dir / "training_box_v1.npz"))
    validation = load_capture(str(data_dir / "validation_box_v1.npz"))
    fs = float(training.sample_rate_hz)

    model_path = data_dir / "candidate_box_v1_256.json"
    artifact = load_model_artifact(str(model_path)) if model_path.exists() else None

    freqs, H_calib, coherence = estimate_path(validation, fs)
    band = usable_band(freqs, coherence)

    peak_calib, peak_calib_hz = peak(freqs, H_calib, band)
    result = {
        "schema_version": 1,
        "kind": "calibration_mismatch_diagnosis",
        "data_dir": str(data_dir),
        "sample_rate_hz": fs,
        "usable_band_hz": [float(freqs[band][0]), float(freqs[band][-1])],
        "usable_bins": int(np.count_nonzero(band)),
        "calibration": {
            "peak_abs_H_db": peak_calib,
            "peak_abs_H_at_hz": peak_calib_hz,
            "coherence_at_peak": float(coherence[np.where(band)[0][int(np.argmax(np.abs(H_calib[band])))]]),
            "bypass_howl_at_gain_db": float(-peak_calib),
        },
    }

    # --- beta 的来源
    beta_source = None
    if msg_bypass_db is not None:
        measured_peak = -float(msg_bypass_db)
        if beta is not None:
            raise SystemExit("给 --beta 或 --msg-bypass-db，不要两个都给")
        beta = float(10.0 ** ((measured_peak - peak_calib) / 20.0))
        beta_source = ("由实测旁路起振 %.2f dB 反推：beta = 10^((%.2f - %.2f)/20)"
                       % (msg_bypass_db, measured_peak, peak_calib))
    elif beta is not None:
        beta_source = "命令行直接给出"
    else:
        beta = 1.0
        beta_source = "未给实测阈值，按标定自身（beta=1）评价"

    H_live = beta * H_calib
    result["beta"] = {
        "value": float(beta),
        "db": float(20.0 * np.log10(beta)),
        "source": beta_source,
        "interpretation": "实时耦合 = beta × 标定耦合；beta<1 表示实测比标定弱",
    }

    # --- 各抽头系数
    coefficients = {}
    for taps in TAPS_CHOICES:
        coefficients[taps] = fir_response(fit_path(training, taps=taps)["coefficients"], fs, freqs)
    if artifact is not None:
        shipped = fir_response(artifact["coefficients"], fs, freqs)
        result["shipped_model"] = {
            "taps": int(artifact["taps"]),
            "peak_abs_H_hat_db": float(20.0 * np.log10(np.max(np.abs(shipped[band])))),
            "peak_abs_H_minus_H_hat_db": peak(freqs, H_live - shipped, band)[0],
        }
        coefficients[int(artifact["taps"])] = shipped if int(artifact["taps"]) in TAPS_CHOICES else shipped

    main_hat = coefficients[int(taps_main)]
    result["subbands"] = subband_table(
        freqs, H_live, main_hat,
        [(150, 200), (200, 300), (300, 400), (400, 500), (500, 700), (700, 1000), (1000, 3000)])
    result["cd_negative"] = {
        "segments": [{"low_hz": a, "high_hz": b, "width_hz": w}
                     for a, b, w in negative_segments(freqs, cd_curve(H_live, main_hat), band)],
        "fraction_of_band": float(np.count_nonzero(cd_curve(H_live, main_hat)[band] <= 0.0)
                                  / np.count_nonzero(band)),
    }
    result["phase_gated"] = {
        "cancel": phase_gated(freqs, H_live - main_hat, band, fs=fs),
        "bypass": phase_gated(freqs, H_live, band, fs=fs),
    }
    result["schemes"] = scheme_scores(freqs, H_live, coefficients, band, beta)

    # --- 重新标定能达到什么
    refit = refit_at_beta(training, beta, int(taps_main), fs)
    refit_hat = fir_response(refit["coefficients"], fs, freqs)
    peak_bypass, _ = peak(freqs, H_live, band)
    peak_refit, at_hz = peak(freqs, H_live - refit_hat, band)
    result["refit"] = {
        "taps": int(taps_main),
        "effective_peak_db": peak_refit,
        "howl_at_gain_db": float(-peak_refit),
        "asg_db": float(peak_bypass - peak_refit),
        "peak_at_hz": at_hz,
        "equivalent_to": "把 beta 倍的耦合当作新的标定，重算系数",
    }

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("written", output, flush=True)
    return result


def report_lines(result):
    lines = []
    lines.append("标定 -> 使用 耦合失配诊断")
    lines.append("  评价频带 %.0f-%.0f Hz（%d bins，相干门控）"
                 % (result["usable_band_hz"][0], result["usable_band_hz"][1], result["usable_bins"]))
    cal = result["calibration"]
    lines.append("  标定峰值 |H| = %+.2f dB @%.0f Hz，旁路应起振于 %+.2f dB"
                 % (cal["peak_abs_H_db"], cal["peak_abs_H_at_hz"], cal["bypass_howl_at_gain_db"]))
    beta = result["beta"]
    lines.append("  beta = %.3f（%+.2f dB）：%s" % (beta["value"], beta["db"], beta["source"]))
    lines.append("")
    lines.append("  子带 max|H-Hhat|/max|H|：")
    for row in result["subbands"]:
        lines.append("    %5.0f-%5.0f Hz  ratio %5.3f (%+6.2f dB)  子带内残差峰 %+6.2f dB  子带 CD 最差 %+7.2f dB"
                     % (row["low_hz"], row["high_hz"], row["ratio"], row["ratio_db"],
                        row["residual_max_db"], row["cd_worst_db"]))
    lines.append("")
    neg = result["cd_negative"]
    lines.append("  CD <= 0 占评价频带 %.1f%%，连续段（>=50 Hz）：" % (100.0 * neg["fraction_of_band"]))
    for seg in neg["segments"]:
        lines.append("    %6.0f-%6.0f Hz  宽 %5.0f Hz" % (seg["low_hz"], seg["high_hz"], seg["width_hz"]))
    lines.append("")
    lines.append("  相位允许的起振候选：")
    for tag, key in (("抵消", "cancel"), ("旁路", "bypass")):
        rows = result["phase_gated"][key][:4]
        lines.append("    %s: %s" % (tag, "  ".join("%.0f Hz@%+.1f dB" % (r["frequency_hz"], r["howl_at_gain_db"])
                                                    for r in rows)))
    lines.append("")
    lines.append("  方案对比（ASG 越大越好）：")
    for name, row in result["schemes"]["schemes"].items():
        if row.get("asg_db") is None:
            lines.append("    %-28s ASG 低于数值下限（残差 < -60 dB），不作为方案"
                         % name)
            continue
        lines.append("    %-28s ASG %+7.2f dB   抵消起振 %+7.2f dB @%.0f Hz"
                     % (name, row["asg_db"], row["howl_at_gain_db"], row["peak_at_hz"]))
    refit = result["refit"]
    lines.append("    %-28s ASG %+7.2f dB   抵消起振 %+7.2f dB @%.0f Hz  ← 按实测幅度重标定"
                 % ("重标定 %d 抽头" % refit["taps"], refit["asg_db"],
                    refit["howl_at_gain_db"], refit["peak_at_hz"]))
    lines.append("")
    lines.append("  注意：以上全部为模型推算，输入是标定数据与实测起振增益，不是实测 ASG。")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True,
                        help="含 training_box_v1.npz / validation_box_v1.npz / candidate_box_v1_256.json")
    parser.add_argument("--beta", type=float, default=None, help="直接给耦合比")
    parser.add_argument("--msg-bypass-db", type=float, default=None,
                        help="实测旁路起振增益（dB），用它反推 beta")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    result = run(args.data_dir, beta=args.beta, msg_bypass_db=args.msg_bypass_db,
                 output=args.output)
    for line in report_lines(result):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
