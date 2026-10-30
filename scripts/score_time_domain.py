#!/usr/bin/env python3
"""同条件评分：部署模型 vs 候选，逐段时域残差 + 分频段能量比。

三条硬约束（都踩过坑，写进工具里）
--------------------------------
1. **逐段独立预测**。不把不连续的采集段拼成一条连续历史——那会在段边界伪造历史，
   并把卷积预热算进残差。每段单独预测，各自掐掉开头 warm 点，再按段累加能量与谱能量。
2. **共同有效窗口**。抽头数不同则预热不同；warm 取参与比较的所有模型中最大的
   (taps + lag_first) 且不小于 512，所有模型用同一个起点，窗长差异不能冒充收益。
3. **评价部署的整数系数**。优先读 `coefficients_q20` 解码成 整数/2^20，
   浮点系数只用于诊断；两者同时存在时打印量化差异。

用法
----
    python scripts/score_time_domain.py --data-dir <目录> --models base.json,cand.json
    python scripts/score_time_domain.py --data-dir <目录> --taps 256,512,680
    python scripts/score_time_domain.py --data-dir <训练> --cross-dir <评价> --models ...

目录内需有 seg_*.npz（reference / microphone / metadata_json）。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path, predict  # noqa: E402

BANDS = [(100, 300), (300, 1000), (1000, 3000), (3000, 6000),
         (6000, 8000), (8200, 8600), (8600, 12000)]
Q20 = 1 << 20


def ref_to_mic_delay(cap):
    """互相关延迟（帧）。同一批里不一致的段不能拼。"""
    n = len(cap.reference)
    spec = np.fft.rfft(cap.microphone, 2 * n) * np.conj(np.fft.rfft(cap.reference, 2 * n))
    return int(np.argmax(np.abs(np.fft.irfft(spec, 2 * n)[:n])))


def load_dir(path, limit=15360, only=None, quiet=False):
    """读 seg_*.npz，剔除静音段与延迟不一致段（同批多数延迟）。"""
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
    median = float(np.median(levels))
    muted = [lvl < median - 10.0 for lvl in levels]
    alive = [d for d, m in zip(delays, muted) if not m]
    mode = max(set(alive), key=alive.count) if alive else 0
    good = []
    for (name, cap), lvl, dly, mut in zip(out, levels, delays, muted):
        note = ""
        if mut:
            note = "静音/待机，剔除"
        elif dly != mode:
            note = "延迟 %d != 本批多数 %d，剔除" % (dly, mode)
        if not quiet:
            print("   %-14s mic %+6.2f dBFS  delay %3d  %s"
                  % (name, lvl, dly, note or "ok"))
        if not note:
            good.append((name, cap))
    if not good:
        raise SystemExit("no usable segment under %s" % path)
    return good


def load_model(path):
    """读模型文件；优先用整数 Q20 系数。"""
    raw = Path(path).read_bytes()
    art = json.loads(raw.decode("utf-8"))
    q20 = art.get("coefficients_q20")
    if q20 is not None:
        coef = np.asarray(q20, dtype=np.int64).astype(np.float64) / Q20
        kind = "q20"
    else:
        coef = np.asarray(art["coefficients"], dtype=np.float64)
        kind = "float"
    rec = {"name": Path(path).stem, "path": str(path),
           "sha256": hashlib.sha256(raw).hexdigest(), "kind": kind,
           "taps": int(len(coef)), "lag_first": int(art.get("lag_first", 1)),
           "fs": art.get("sample_rate_hz"), "coef": coef,
           "fixture_id": art.get("fixture_id"), "status": art.get("status")}
    if kind == "q20" and "coefficients" in art:
        flt = np.asarray(art["coefficients"], dtype=np.float64)
        if len(flt) == len(coef):
            rec["quantization_max"] = float(np.max(np.abs(flt - coef)))
    return rec


def score(captures, coef, warm, fs):
    """逐段独立预测，按段累加能量；返回残差/观测的能量比与峰值比。"""
    res_energy = mic_energy = 0.0
    res_peak = mic_peak = 0.0
    band_res = {b: 0.0 for b in BANDS}
    band_mic = {b: 0.0 for b in BANDS}
    for _, c in captures:
        pred = predict(c.reference, coef)
        res = (c.microphone - pred)[warm:]
        mic = c.microphone[warm:]
        if not len(mic):
            continue
        res_energy += float(np.sum(res ** 2))
        mic_energy += float(np.sum(mic ** 2))
        res_peak = max(res_peak, float(np.max(np.abs(res))))
        mic_peak = max(mic_peak, float(np.max(np.abs(mic))))
        # 每段单独加窗做谱再累加能量：避免段边界跳变造出虚假的低频成分
        window = np.hanning(len(res))
        sr = np.abs(np.fft.rfft(res * window)) ** 2
        sm = np.abs(np.fft.rfft(mic * window)) ** 2
        freqs = np.fft.rfftfreq(len(res), 1.0 / fs)
        for lo, hi in BANDS:
            sel = (freqs >= lo) & (freqs < hi)
            band_res[(lo, hi)] += float(np.sum(sr[sel]))
            band_mic[(lo, hi)] += float(np.sum(sm[sel]))
    out = {"rms_db": 10 * np.log10(res_energy / mic_energy),
           "peak_db": 20 * np.log10(res_peak / mic_peak)}
    for lo, hi in BANDS:
        out["%d-%d" % (lo, hi)] = (10 * np.log10(band_res[(lo, hi)] / band_mic[(lo, hi)])
                                  if band_mic[(lo, hi)] > 0 else float("nan"))
    return out


def header():
    line = " %-20s %-8s %7s %7s |" % ("模型", "数据", "RMS", "峰值")
    for lo, hi in BANDS:
        line += "%8s" % ("%d-%dk" % (lo // 1000, hi // 1000) if lo >= 1000
                         else "%d-%d" % (lo, hi // 1000))
    return line


def row(tag, name, s):
    line = " %-20s %-8s %+7.2f %+7.2f |" % (tag, name, s["rms_db"], s["peak_db"])
    for lo, hi in BANDS:
        line += "%+8.1f" % s["%d-%d" % (lo, hi)]
    return line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--cross-dir", default=None)
    parser.add_argument("--models", default=None,
                        help="逗号分隔的模型 JSON；第 1 个当基线、第 2 个当候选")
    parser.add_argument("--taps", default=None, help="现场拟合的抽头数列表")
    parser.add_argument("--warm", type=int, default=None,
                        help="默认取所有模型 max(taps+lag_first) 与 512 的较大值")
    parser.add_argument("--limit", type=int, default=15360)
    parser.add_argument("--segs", default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    only = [v.strip() for v in args.segs.split(",")] if args.segs else None
    main_caps = load_dir(args.data_dir, args.limit, only)
    fs = main_caps[0][1].sample_rate_hz
    print("数据 %s：可用 %d 段，每段 %d 帧，fs=%.3f"
          % (args.data_dir, len(main_caps), len(main_caps[0][1].reference), fs))

    cross_caps = None
    if args.cross_dir:
        cross_caps = load_dir(args.cross_dir, args.limit, only)
        print("跨场次 %s：可用 %d 段" % (args.cross_dir, len(cross_caps)))

    models = []
    if args.models:
        for path in args.models.split(","):
            m = load_model(path.strip())
            if m["fs"] is not None and abs(float(m["fs"]) - fs) > 1e-6:
                raise SystemExit("采样率不一致：%s" % m["name"])
            models.append(m)
    if args.taps:
        merged = Capture(np.concatenate([c.reference for _, c in main_caps]),
                         np.concatenate([c.microphone for _, c in main_caps]),
                         fs, dict(main_caps[0][1].metadata)).validate()
        for taps in [int(v) for v in args.taps.split(",")]:
            coef = np.asarray(fit_path(merged, taps=taps)["coefficients"])
            models.append({"name": "fit本场%d" % taps, "taps": taps,
                           "lag_first": 1, "kind": "float", "coef": coef,
                           "sha256": None, "fs": fs})
    if not models:
        raise SystemExit("要么给 --models，要么给 --taps")

    warm = args.warm if args.warm is not None else max(
        max(m["taps"] + m["lag_first"] for m in models), 512)
    print("共同有效窗口：每段掐掉前 %d 点，参与统计 %d 帧/段"
          % (warm, len(main_caps[0][1].reference) - warm))
    print()
    for m in models:
        extra = ""
        if "quantization_max" in m:
            extra = "  Q20 量化误差 max %.2e" % m["quantization_max"]
        print(" 模型 %-18s taps=%3d lag_first=%d 系数=%s sha256=%s%s"
              % (m["name"], m["taps"], m["lag_first"], m["kind"],
                 (m["sha256"] or "-")[:16], extra))
    print()

    print(header())
    results = {}
    for m in models:
        s = score(main_caps, m["coef"], warm, fs)
        results["%s@本场" % m["name"]] = s
        print(row(m["name"], "本场", s))
        if cross_caps:
            s2 = score(cross_caps, m["coef"], warm, fs)
            results["%s@跨场" % m["name"]] = s2
            print(row(m["name"], "跨场", s2))
    print()

    if len(models) >= 2:
        base, cand = models[0], models[1]
        for which, tag in (("本场", "本场"), ("跨场", "跨场（更接近现场）")):
            if cross_caps is None and which == "跨场":
                continue
            b = results["%s@%s" % (base["name"], which)]
            c = results["%s@%s" % (cand["name"], which)]
            print("=== 候选 − 基线 · %s（负=更好）===" % tag)
            print("  RMS %+6.2f dB   峰值 %+6.2f dB"
                  % (c["rms_db"] - b["rms_db"], c["peak_db"] - b["peak_db"]))
            for lo, hi in BANDS:
                k = "%d-%d" % (lo, hi)
                print("  %5d-%5d Hz  %+6.2f dB" % (lo, hi, c[k] - b[k]))
        print()

    print("读法：数值是残差与观测的能量比，负=减小。分段独立预测，段边界不参与统计。")
    print("      宽带 RMS 由高能量频段主导，必须同时看 300-1000 与 8200-8600。")

    if args.json:
        payload = {"data_dir": args.data_dir, "cross_dir": args.cross_dir,
                   "warm": warm, "bands": BANDS,
                   "models": [{k: v for k, v in m.items() if k != "coef"} for m in models],
                   "results": results}
        Path(args.json).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print("\n写入 %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
