#!/usr/bin/env python3
"""逐段时域评分：模型把麦克风压低多少，分频段看，支持跨场次对照。

为什么不用 CD(f) 或 max|H-Ĥ|
------------------------------
1. CD 在 |H| 的零点附近必然是很大的负数（|H|->0 而残差不为 0），符号没有意义。
2. max|H-Ĥ| 会被单个相干边缘的 bin 决定，换一次估计就差十几 dB。
3. 时域残差与板上真正做的事完全一致（predict 与 RTL 逐样本一致），
   不依赖 Welch、窗长、相干门控。

用法
----
    python scripts/score_time_domain.py --data-dir <目录> --taps 256,512
    python scripts/score_time_domain.py --data-dir <新> --cross-dir <旧>

目录内需有 seg_*.npz（reference / microphone / metadata_json）。
每段独立预测并掐掉前 --warm 点，避免卷积预热与段边界拉低结果。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path, predict  # noqa: E402

FS_DEFAULT = 48828.125
BANDS = [(100, 300), (300, 1000), (1000, 3000), (3000, 6000),
         (6000, 8000), (8200, 8600), (8600, 12000)]


def ref_to_mic_delay(cap):
    """互相关延迟（帧）。同一批里不一致的段不能拼。"""
    n = len(cap.reference)
    spec = np.fft.rfft(cap.microphone, 2 * n) * np.conj(np.fft.rfft(cap.reference, 2 * n))
    corr = np.fft.irfft(spec, 2 * n)
    return int(np.argmax(np.abs(corr[:n])))


def load_dir(path, limit=15360, only=None):
    """读目录下的 seg_*.npz，并做两项自检：静音段、延迟不一致段。

    静音段（麦克风比同批中位低 10 dB 以上）与延迟不一致段必须剔除，
    否则跨段拼接会把抑制数字拉低十几 dB（2026-10-22 实际踩过）。
    """
    out = []
    for npz in sorted(Path(path).glob("seg_*.npz")):
        if only and npz.stem not in only:
            continue
        z = np.load(npz, allow_pickle=True)
        md = json.loads(str(z["metadata_json"]))
        md.setdefault("alignment", "same_i2s_frame")
        md.setdefault("dropped_frames", 0)
        fs = float(z["sample_rate_hz"])
        cap = Capture(np.asarray(z["reference"], dtype=float)[:limit],
                      np.asarray(z["microphone"], dtype=float)[:limit],
                      fs, md).validate()
        out.append((npz.name, cap))
    if not out:
        raise SystemExit("no seg_*.npz under %s" % path)

    levels = np.array([20 * np.log10(np.sqrt(np.mean(c.microphone ** 2)) + 1e-30)
                       for _, c in out])
    delays = [ref_to_mic_delay(c) for _, c in out]
    median_level = float(np.median(levels))
    muted = [lvl < median_level - 10.0 for lvl in levels]
    # 只在非静音段里取延迟的众数，否则静音段的 delay=0 会把众数带偏。
    alive = [d for d, m in zip(delays, muted) if not m]
    mode = max(set(alive), key=alive.count) if alive else 0
    good = []
    for (name, cap), lvl, dly, mut in zip(out, levels, delays, muted):
        note = ""
        if mut:
            note = "静音/待机，剔除"
        elif dly != mode:
            note = "延迟 %d != 本批多数 %d，剔除" % (dly, mode)
        ref_level = 20 * np.log10(np.sqrt(np.mean(cap.reference ** 2)) + 1e-30)
        print("   %-14s mic %+6.2f dBFS  ref %+6.2f dBFS  delay %3d  %s"
              % (name, lvl, ref_level, dly, note or "ok"))
        if not note:
            good.append((name, cap))
    if not good:
        raise SystemExit("no usable segment under %s" % path)
    return good


def fit_from(captures, taps):
    ref = np.concatenate([c.reference for _, c in captures])
    mic = np.concatenate([c.microphone for _, c in captures])
    cap = Capture(ref, mic, captures[0][1].sample_rate_hz,
                  dict(captures[0][1].metadata)).validate()
    return np.asarray(fit_path(cap, taps=taps)["coefficients"], dtype=float)


def score(captures, coef, warm, fs):
    """逐段预测，掐掉预热，返回宽带与分频段的残差/mic 能量比（dB）。"""
    res, mic = [], []
    for _, c in captures:
        res.append((c.microphone - predict(c.reference, coef))[warm:])
        mic.append(c.microphone[warm:])
    res = np.concatenate(res)
    mic = np.concatenate(mic)
    out = {"frames": int(len(res)),
           "rms_db": 20 * np.log10(np.sqrt(np.mean(res ** 2))
                                   / np.sqrt(np.mean(mic ** 2))),
           "peak_db": 20 * np.log10(np.max(np.abs(res)) / np.max(np.abs(mic)))}
    n = len(res)
    window = np.hanning(n)
    spec_r = np.fft.rfft(res * window)
    spec_m = np.fft.rfft(mic * window)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    for low, high in BANDS:
        sel = (freqs >= low) & (freqs < high)
        out["%d-%d" % (low, high)] = float(
            10 * np.log10(np.sum(np.abs(spec_r[sel]) ** 2)
                          / np.sum(np.abs(spec_m[sel]) ** 2)))
    return out


def header():
    line = " %-12s %-10s %7s %7s |" % ("模型", "数据", "RMS", "峰值")
    for low, high in BANDS:
        line += "%8s" % ("%d-%dk" % (low // 1000, high // 1000) if low >= 1000
                         else "%d-%d" % (low, high // 1000))
    return line


def row(tag, name, s):
    line = " %-12s %-10s %+7.2f %+7.2f |" % (tag, name, s["rms_db"], s["peak_db"])
    for low, high in BANDS:
        line += "%+8.1f" % s["%d-%d" % (low, high)]
    return line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--cross-dir", default=None,
                        help="另一个场次的目录；用它检验模型的可迁移性")
    parser.add_argument("--taps", default="256")
    parser.add_argument("--warm", type=int, default=512)
    parser.add_argument("--limit", type=int, default=15360)
    parser.add_argument("--segs", default=None,
                        help="只取这些段，逗号分隔（如 seg_1,seg_5）；默认全取并自动剔除坏段")
    parser.add_argument("--json", default=None, help="把结果写成 JSON")
    args = parser.parse_args(argv)

    taps_list = [int(v) for v in args.taps.split(",")]
    only = [v.strip() for v in args.segs.split(",")] if args.segs else None
    main_caps = load_dir(args.data_dir, args.limit, only)
    fs = main_caps[0][1].sample_rate_hz
    print("数据 %s：可用 %d 段，每段 %d 帧，采样率 %.3f"
          % (args.data_dir, len(main_caps), len(main_caps[0][1].reference), fs))
    print()

    cross_caps = load_dir(args.cross_dir, args.limit, only) if args.cross_dir else None
    if cross_caps:
        print("跨场次对照 %s：%d 段" % (args.cross_dir, len(cross_caps)))
        print()

    print(header())
    results = {}
    models = {}
    for taps in taps_list:
        models["fit本场%d" % taps] = fit_from(main_caps, taps)
        if cross_caps:
            models["fit对照%d" % taps] = fit_from(cross_caps, taps)

    for tag, coef in models.items():
        s = score(main_caps, coef, args.warm, fs)
        results["%s@本场" % tag] = s
        print(row(tag, "本场", s))
        if cross_caps:
            s2 = score(cross_caps, coef, args.warm, fs)
            results["%s@对照" % tag] = s2
            print(row(tag, "对照场", s2))
    print()

    if len(taps_list) > 1:
        print("=== 抽头收益（相对最小抽头，负=更好）===")
        for taps in taps_list[1:]:
            a = results["fit本场%d@本场" % taps_list[0]]
            b = results["fit本场%d@本场" % taps]
            print(" %4d vs %4d  RMS %+6.2f dB  300-1000 %+6.2f dB  3-6k %+6.2f dB"
                  % (taps, taps_list[0], b["rms_db"] - a["rms_db"],
                     b["300-1000"] - a["300-1000"],
                     b["3000-6000"] - a["3000-6000"]))
        print(" 单 MAC 每抽头 3 拍 + 3 拍收尾；帧预算 2048 拍 -> 上限 681 抽头")
        print()

    print("读法：数值是残差与 mic 的能量比，负=减小。宽带 RMS 会被高能量频段主导，")
    print("      必须同时看 300-1000 与 8200-8600 这两段，它们才是决定起振的地方。")

    if args.json:
        payload = {"data_dir": args.data_dir, "cross_dir": args.cross_dir,
                   "warm": args.warm, "bands": BANDS, "results": results}
        Path(args.json).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print("\n写入 %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
