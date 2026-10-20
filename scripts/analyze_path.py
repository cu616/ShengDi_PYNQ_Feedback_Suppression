"""逐频点抵消深度与稳定增益估算的本地入口。

本地（无板卡、无录音，用已知真值的合成路径自证全部链路）：
    python scripts/analyze_path.py --synthetic --output tmp/analysis_synthetic.json

板上（在 base/audio/audio_calibrate 目录下，由 A 执行）：
    %run path_analysis_box_v1.py

输出口径：
- broadband_reduction_db：现有评价方式（宽带 RMS 预测误差降低），保留以便对照；
- cd_median_db / cd_min_db：逐频点抵消深度 20log10(|H|/|H-Ĥ|)，正值为压下去；
- msg_*：起振增益（dB，相对 Q4.12 的 1.0 倍），conservative 是安全下界，
  phase_gated 是真正的起振点；
- asg_*：抵消相对旁路的稳定增益差。
全部是"从模型算出来的预测"，不是实测 MSG/ASG。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from feedback.calibration import Capture, fit_path, load_capture  # noqa: E402
from feedback.path_analysis import (analyze_captures, band_slice,  # noqa: E402
                                   cancellation_depth_db, estimate_path,
                                   fir_response, load_model_artifact, report_lines)


def synthetic_fixture(fs=48828.125, frames=32768, seed=0, noise_dbfs=-58.0,
                      source_dbfs=-26.0, tail_gain=0.012, tail_decay=260.0,
                      tail_hz=820.0):
    """已知真值的小箱体路径：直接到达 + 反射 + 一个长衰减共振。

    默认参数刻意让共振尾巴长到 256 抽头装不下，因为真实问题就在这儿：
    被截断的那一段正好落在最容易啸叫的频点上。
    返回的 impulse 只用于核对分析程序，不参与任何拟合。
    """
    length = 1400
    impulse = np.zeros(length)
    impulse[44] = 0.22
    impulse[150] = -0.10
    tail = np.arange(1200)
    impulse[60:1260] += (tail_gain * np.exp(-tail / tail_decay)
                         * np.sin(2 * np.pi * tail_hz * tail / fs))
    rng = np.random.default_rng(seed)
    reference = rng.uniform(-1.0, 1.0, frames) * 10.0 ** (source_dbfs / 20.0)
    microphone = np.convolve(reference, impulse)[:frames]
    microphone += rng.standard_normal(frames) * 10.0 ** (noise_dbfs / 20.0)
    if np.any(np.abs(microphone) >= 0.999):
        raise ValueError("synthetic capture clipped; lower the source level")
    return reference, microphone, impulse


def synthetic_capture(reference, microphone, fs, capture_id):
    return Capture(reference, microphone, fs, {
        "schema_version": 1, "capture_id": capture_id, "source": "synthetic",
        "forward_path_open": True, "alignment": "same_i2s_frame",
        "dropped_frames": 0, "fixture_id": "synthetic_box_v1", "hp_volume": 40,
    }).validate()


def truth_check(valid_ref, valid_mic, impulse, fs):
    """把已知 impulse 截断到 N 抽头，看 CD 最差能到多少。

    与"拟合出来的模型"对比，就能区分"估计器不行"和"抽头数不够"。
    """
    estimate = estimate_path(valid_ref, valid_mic, fs)
    band = band_slice(estimate["freqs"], 20.0, 20000.0, fs)
    out = {}
    for taps in (128, 256, 512):
        H_hat = fir_response(impulse[1:taps + 1], fs, estimate["freqs"])
        cd = cancellation_depth_db(estimate["H"], H_hat)[band]
        out[str(taps)] = {"cd_median_db": float(np.median(cd)),
                          "cd_min_db": float(np.min(cd))}
    return out


def run_synthetic(output=None, frames=32768):
    fs = 48828.125
    train_ref, train_mic, impulse = synthetic_fixture(fs=fs, seed=0, frames=frames)
    valid_ref, valid_mic, _ = synthetic_fixture(fs=fs, seed=1, frames=frames)
    training = synthetic_capture(train_ref, train_mic, fs, "synthetic_train")
    validation = synthetic_capture(valid_ref, valid_mic, fs, "synthetic_valid")
    model = fit_path(training, taps=256)
    result = analyze_captures(training, validation, model)
    result["synthetic_truth_check"] = {
        "perfect_impulse_by_length": truth_check(valid_ref, valid_mic, impulse, fs),
        "note": ("truncating the TRUE impulse to N taps and the fitted model at N taps "
                 "give nearly the same worst-case depth -> the limit is length, "
                 "not the estimator"),
    }
    for text in report_lines(result):
        print(text, flush=True)
    truth = result["synthetic_truth_check"]["perfect_impulse_by_length"]
    print("真值核对（已知 impulse 截断到 N 抽头）: " + "  ".join(
        "%s抽头 CD最差 %.1f dB" % (taps, block["cd_min_db"])
        for taps, block in sorted(truth.items(), key=lambda item: int(item[0]))),
        flush=True)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print("RESULT_SAVED", str(path), flush=True)
    return result


def run_real(data_dir, output=None, training="training_box_v1.npz",
             validation="validation_box_v1.npz", model="candidate_box_v1_256.json",
             band_low=20.0, band_high=20000.0, gamma=1.0):
    """本地分析真实标定数据：把三个文件从板卡拷到任意目录即可，不需要板卡在线。

    需要的就是 load_capture 能读的两个 npz 加一个系数 JSON；不加载 overlay、
    不播放、不采集。这是本线的主要工作方式——板卡只在采集和实测时才需要。
    """
    folder = Path(data_dir)
    for name in (training, validation, model):
        if not (folder / name).exists():
            raise FileNotFoundError(str(folder / name))
    train_capture = load_capture(folder / training)
    valid_capture = load_capture(folder / validation)
    artifact = load_model_artifact(folder / model)
    result = analyze_captures(train_capture, valid_capture, artifact,
                              band_low=band_low, band_high=band_high, gamma=gamma)
    result["provenance"] = {
        "training": training, "validation": validation, "model": model,
        "training_sha256": _sha256(folder / training),
        "validation_sha256": _sha256(folder / validation),
        "model_sha256": _sha256(folder / model),
        "model_status": artifact.get("status"),
        "numpy": np.__version__,
    }
    for text in report_lines(result):
        print(text, flush=True)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print("RESULT_SAVED", str(path), flush=True)
    return result


def _sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true",
                        help="用已知真值的合成路径自证，不读任何真实数据")
    parser.add_argument("--data-dir", default=None,
                        help="含训练/验证 npz 与候选系数 JSON 的目录；不需要板卡在线")
    parser.add_argument("--training", default="training_box_v1.npz")
    parser.add_argument("--validation", default="validation_box_v1.npz")
    parser.add_argument("--model", default="candidate_box_v1_256.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--frames", type=int, default=32768)
    parser.add_argument("--gamma", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.data_dir:
        run_real(args.data_dir, args.output, args.training, args.validation,
                 args.model, gamma=args.gamma)
        return 0
    if not args.synthetic:
        parser.error("give --synthetic for the self-check, or --data-dir pointing at "
                     "the two npz files and the candidate JSON")
    run_synthetic(args.output, frames=args.frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
