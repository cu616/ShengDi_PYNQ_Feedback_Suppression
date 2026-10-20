"""交叉验证：频域估算的起振增益 vs 整数闭环模拟的实际起振点。

两套完全独立的算法（一个在频域算 max|H-Ĥ|，一个逐帧跑定点环路），
如果对不上，说明分析口径或模拟实现有一处错了，结论不能拿去现场用。

    python scripts/cross_check_stability.py --output tmp/cross-check.txt
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_path import synthetic_capture, synthetic_fixture  # noqa: E402
from feedback.calibration import fit_path, quantize_coefficients  # noqa: E402
from feedback.closed_loop_sim import find_msg  # noqa: E402
from feedback.path_analysis import (analyze_captures, band_slice,  # noqa: E402
                                   estimate_path, fir_response, stability_summary)


def case_summary(estimate, band, model, fs):
    H_hat = fir_response(model["coefficients"], fs, estimate["freqs"])
    summary = stability_summary(estimate["freqs"], estimate["H"], H_hat, band, fs)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=None)
    parser.add_argument("--frames", type=int, default=32768)
    args = parser.parse_args(argv)

    fs = 48828.125
    train_ref, train_mic, impulse = synthetic_fixture(seed=0, frames=args.frames)
    valid_ref, valid_mic, _ = synthetic_fixture(seed=1, frames=args.frames)
    training = synthetic_capture(train_ref, train_mic, fs, "cross_train")
    validation = synthetic_capture(valid_ref, valid_mic, fs, "cross_valid")
    estimate = estimate_path(valid_ref, valid_mic, fs)
    band = band_slice(estimate["freqs"], 20.0, 20000.0, fs)

    rows = []
    # 旁路：模型为零，起点是"什么都不抵消"
    null_hat = np.zeros_like(estimate["H"])
    summary = stability_summary(estimate["freqs"], estimate["H"], null_hat, band, fs)
    rows.append(("旁路", np.zeros(256, dtype=np.int64), True, summary))

    for taps in (256, 512):
        model = fit_path(training, taps=taps)
        summary = stability_summary(estimate["freqs"], estimate["H"],
                                    fir_response(model["coefficients"], fs,
                                                 estimate["freqs"]), band, fs)
        rows.append(("抵消%d抽头" % taps, quantize_coefficients(model["coefficients"]),
                     False, summary))

    lines = ["%-12s %-22s %-10s %s" % ("模式", "预测(conservative)", "预测(phase)", "模拟实测")]
    for name, coefficients, bypass, summary in rows:
        key = "msg_bypass" if bypass else "msg_cancel"
        conservative = summary[key + "_conservative_db"]
        gated = summary[key + "_phase_gated_db"]
        try:
            measured = "%.2f dB" % find_msg(impulse, coefficients, bypass=bypass,
                                            frames=8192)["msg_db"]
        except ValueError as error:
            measured = "未起振(%s)" % str(error).split(";")[0]
        lines.append("%-12s %-22s %-10s %s" % (
            name, "%.2f dB" % conservative, "%.2f dB" % gated, measured))

    # 归纳：相位口径应当命中，保守口径是安全下界。
    lines.append("")
    lines.append("判读：模拟值应落在 conservative..phase 之间，并靠近 phase。"
                 "若模拟值低于 conservative 或高于 phase，先查分析与模拟哪一处错了。")
    text = "\n".join(lines)
    print(text, flush=True)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print("SAVED", str(path), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
