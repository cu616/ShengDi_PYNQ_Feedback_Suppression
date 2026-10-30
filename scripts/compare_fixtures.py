"""箱体 vs 房间：抽头数的收益为什么不同，以及高频是不是瓶颈。

两个问题：
1. 箱体上 512 没有改善，是不是因为"冲激响应短、256 已覆盖"？
2. 房间 6-12 kHz 的 CD 为负，那里的绝对电平到底有多大、相位允不允许起振？

用法：
    python scripts/compare_fixtures.py --box-dir <含 training_box_v1.npz 的目录> \
                                      --room-dir <含 seg_*.npz 的目录>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path, load_capture      # noqa: E402
from feedback.path_analysis import (coherence_from_spectra,           # noqa: E402
                                   fir_response, welch_cross)

FS = 48828.125
BANDS = [(300, 1000), (1000, 3000), (3000, 6000), (6000, 12000)]
TAPS = (128, 256, 384, 512)


def impulse_shape(capture, fs, n=8192):
    """能量累积到 95% / 99% 需要多少帧。这是"256 抽头够不够"的直接判据。"""
    freqs, suu, sum_, _ = welch_cross(capture.reference, capture.microphone, fs, nperseg=4096)
    H = sum_ / np.maximum(suu, 1e-300)
    grid = np.fft.rfftfreq(n, 1.0 / fs)
    Hp = (np.interp(grid, freqs, H.real) + 1j * np.interp(grid, freqs, H.imag))
    Hp[0] = Hp[1].real
    ir = np.fft.irfft(Hp, n)
    energy = np.cumsum(ir ** 2)
    energy /= energy[-1]
    return {
        "peak_frame": int(np.argmax(np.abs(ir))),
        "energy_95_frame": int(np.searchsorted(energy, 0.95)),
        "energy_99_frame": int(np.searchsorted(energy, 0.99)),
    }


def tap_table(train, test, fs, taps_list=TAPS, gate=0.5):
    freqs, suu, sum_, smm = welch_cross(test.reference, test.microphone, fs, nperseg=2048)
    H = sum_ / np.maximum(suu, 1e-300)
    coh = coherence_from_spectra(suu, sum_, smm)
    band = (freqs >= 100) & (freqs <= 12000) & (coh >= gate)
    rows = []
    for taps in taps_list:
        coef = np.asarray(fit_path(train, taps=taps)["coefficients"], dtype=float)
        Hh = fir_response(coef, fs, freqs)
        pH, pE = np.max(np.abs(H[band])), np.max(np.abs((H - Hh)[band]))
        sub = {}
        for low, high in BANDS:
            sel = (freqs >= low) & (freqs < high) & (coh >= gate)
            if not sel.any():
                continue
            resid = np.abs((H - Hh)[sel])
            cd = 20 * np.log10(np.maximum(np.abs(H[sel]), 1e-30) / np.maximum(resid, 1e-30))
            sub[low] = {"cd_worst": float(cd.min()),
                        "max_abs_H": float(20 * np.log10(np.max(np.abs(H[sel])))),
                        "max_abs_Hhat": float(20 * np.log10(np.max(np.abs(Hh[sel]))))}
        rows.append({"taps": taps, "asg_db": float(20 * np.log10(pH / pE)),
                     "subbands": sub})
    return rows


def high_freq_check(H, Hh, freqs, coh, low=6000.0, high=12000.0, gate=0.5):
    """列出该频段 |H| 最大的几个点，附环路相位与是否允许起振。"""
    band = (freqs >= low) & (freqs <= high) & (coh >= gate)
    if not band.any():
        return []
    loop = H * np.exp(-1j * 2 * np.pi * freqs * 2 / FS)
    phase = np.unwrap(np.angle(loop))
    turns = phase / (2 * np.pi)
    out = []
    idx = np.where(band)[0]
    for i in idx[np.argsort(-np.abs(H[band]))][:6]:
        deg = float(np.degrees(np.angle(loop[i])))
        out.append({
            "frequency_hz": float(freqs[i]),
            "abs_H_db": float(20 * np.log10(abs(H[i]))),
            "abs_H_eff_db": float(20 * np.log10(abs(H[i] - Hh[i]) + 1e-30)),
            "cd_db": float(20 * np.log10(abs(H[i]) / max(abs(H[i] - Hh[i]), 1e-30))),
            "coherence": float(coh[i]),
            "loop_phase_deg": deg,
            "phase_allows_howl": bool(min(abs(deg), abs(abs(deg) - 360.0)) < 25.0),
        })
    return out


def load_room(room_dir, names, n=15360):
    refs, mics = [], []
    for name in names:
        z = np.load(str(Path(room_dir) / (name + ".npz")), allow_pickle=True)
        refs.append(np.asarray(z["reference"], dtype=float)[:n])
        mics.append(np.asarray(z["microphone"], dtype=float)[:n])
    z = np.load(str(Path(room_dir) / (names[0] + ".npz")), allow_pickle=True)
    md = json.loads(str(z["metadata_json"]))
    md.setdefault("alignment", "same_i2s_frame")
    md.setdefault("dropped_frames", 0)
    return Capture(np.concatenate(refs), np.concatenate(mics), FS, md).validate()


def run(box_dir, room_dir, room_segments):
    result = {"schema_version": 1, "kind": "fixture_compare"}
    box_train = load_capture(str(Path(box_dir) / "training_box_v1.npz"))
    box_test = load_capture(str(Path(box_dir) / "validation_box_v1.npz"))

    result["box"] = {
        "impulse": impulse_shape(box_train, FS),
        "taps": tap_table(box_train, box_test, FS),
    }

    half = len(room_segments) // 2
    train = load_room(room_dir, room_segments[:half])
    test = load_room(room_dir, room_segments[half:])
    result["room"] = {
        "impulse": impulse_shape(train, FS),
        "taps": tap_table(train, test, FS),
        "segments": room_segments,
    }

    # 高频峰检查（用房间的 shipped 256 模型）
    freqs, suu, sum_, smm = welch_cross(test.reference, test.microphone, FS, nperseg=2048)
    H = sum_ / np.maximum(suu, 1e-300)
    coh = coherence_from_spectra(suu, sum_, smm)
    coef256 = np.asarray(fit_path(train, taps=256)["coefficients"], dtype=float)
    result["room"]["high_freq_256"] = high_freq_check(H, fir_response(coef256, FS, freqs), freqs, coh)
    return result


def report_lines(result):
    out = []
    out.append("夹具对照：抽头数的收益与高频瓶颈")
    out.append("")
    out.append("  冲激响应形状（256 抽头 = 256 帧 = 5.24 ms）：")
    for tag in ("box", "room"):
        imp = result[tag]["impulse"]
        out.append("    %-5s 峰值 @%4d 帧，95%% @%4d，99%% @%4d"
                   % (tag, imp["peak_frame"], imp["energy_95_frame"], imp["energy_99_frame"]))
    out.append("")
    out.append("  抽头对照（样本外）：")
    for tag in ("box", "room"):
        for row in result[tag]["taps"]:
            sub = row["subbands"]
            detail = "  ".join("%d-%d CD %+6.2f" % (lo, next(hi for l2, hi in BANDS if l2 == lo),
                                                    sub[lo]["cd_worst"]) for lo in sorted(sub))
            out.append("    %-5s %3d 抽头  ASG %+7.2f dB   %s"
                       % (tag, row["taps"], row["asg_db"], detail))
        out.append("")
    if result["room"].get("high_freq_256"):
        out.append("  房间 6-12 kHz：|H| 最大的几个点（相位允许 = 会成为起振点）")
        for row in result["room"]["high_freq_256"]:
            out.append("    %6.0f Hz  |H| %+6.2f  抵消后 %+6.2f  CD %+6.2f  相干 %.2f  相位 %+7.1f°  %s"
                       % (row["frequency_hz"], row["abs_H_db"], row["abs_H_eff_db"],
                          row["cd_db"], row["coherence"], row["loop_phase_deg"],
                          "允许起振" if row["phase_allows_howl"] else "相位不允许"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--box-dir", required=True)
    parser.add_argument("--room-dir", required=True)
    parser.add_argument("--room-segments", default="seg_1,seg_5,seg_6,seg_7",
                        help="延迟一致的段，逗号分隔（seg_0/2 是 124 帧，不能混进来）")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    segments = [s.strip() for s in args.room_segments.split(",") if s.strip()]
    result = run(args.box_dir, args.room_dir, segments)
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
