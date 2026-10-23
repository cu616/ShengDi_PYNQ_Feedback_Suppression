#!/usr/bin/env python3
"""闭环残差/麦克风 ≠ 开环抵消深度：把两个指标分开算清楚。

问题
----
A 在稳定增益点用 `|residual|/|mic|` 当作"模型在闭环里还剩多少抵消"，并与开环的
`CD(f)=20log10(|H|/|H−Ĥ|)` 直接比较，得出"闭环只有 1.8–3.7 dB、离线有 6 dB"。
这两个量不是同一个东西。

推导（线性、平稳激励）
----------------------
记 Ĥ 为模型、H 为真实路径、g 为数字增益、z⁻² 为 `played[n+2]=g·residual[n]` 的调度延迟，
s 为外部声源（含噪声）。闭环里

    residual = (H−Ĥ)·played + s,   played = g·z⁻²·residual
    ⇒ residual = s / (1 − g·(H−Ĥ)·z⁻²)
    mic      = H·played + s = s·(1 + g·H·z⁻²/(1 − g·(H−Ĥ)·z⁻²))

因此 **有外部声源时**

    residual/mic = 1 / (1 + g·H·z⁻²/(1 − g·(H−Ĥ)·z⁻²))

这个比值由 g 和 H 决定，**模型完全正确时也不等于 0 dB**：此时 residual = s、
played = g·z⁻²·s 很小、mic ≈ s，比值 ≈ 0 dB。反之模型为空（Ĥ=0）时 residual = mic，
比值同样是 0 dB。**所以它在两个极端都回到 0 dB，不能用来评价模型好坏。**

**没有外部声源时（尾段）** 才是开环口径：

    residual/mic = (H−Ĥ)/H  ⇒  20log10 = −CD(f)

这也是为什么尾段余振可以直接测出模型的真实抵消深度，而"有源时"的比值不能。

用法
----
    python scripts/closed_loop_metric_check.py --data-dir <目录> --model <json> \
        [--cross-dir <目录>]

所有量都在同一频带、同一相干门控下算，并同时给出：
  A 列：闭环有源时的 residual/mic（A 用的指标）
  B 列：尾段（无源）时的 residual/mic，等于 −CD
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from feedback.path_analysis import (welch_cross, coherence_from_spectra,  # noqa: E402
                                    fir_response)
from score_time_domain import load_dir, load_model  # noqa: E402

BANDS = [(100, 300), (300, 1000), (1000, 3000), (3000, 6000),
         (6000, 8000), (8200, 8600), (8600, 12000)]
SCHEDULE = 2.0
Q20 = 1 << 20


def estimate_h(captures, nperseg=2048):
    S = None
    fs = captures[0][1].sample_rate_hz
    for _, c in captures:
        f, suu, sum_, smm = welch_cross(c.reference, c.microphone, fs, nperseg=nperseg)
        cur = np.stack([suu, sum_, smm])
        S = cur if S is None else S + cur
    suu, sum_, smm = S
    return f, sum_ / np.maximum(suu, 1e-300), coherence_from_spectra(suu, sum_, smm)


def band_ratio(num, den, freqs, lo, hi):
    """带内能量比 = Σ分子 / Σ分母。逐频点比值求和会被 bin 数污染（+10log10(N)）。"""
    sel = (freqs >= lo) & (freqs < hi)
    return 10 * np.log10(max(float(np.sum(num[sel])), 1e-300)
                         / max(float(np.sum(den[sel])), 1e-300))


def closed_loop_ratio(H, Hh, freqs, fs, gain_db):
    """有外部声源时的 |residual|²/|mic|²，逐频点。"""
    g = 10 ** (gain_db / 20.0)
    z2 = np.exp(-1j * 2 * np.pi * freqs * SCHEDULE / fs)
    loop = g * (H - Hh) * z2
    residual = 1.0 / (1.0 - loop)
    mic = 1.0 + g * H * z2 / (1.0 - loop)
    return np.abs(residual) ** 2, np.abs(mic) ** 2


def report(tag, f, H, Hh, gate, gain_db):
    freqs = f
    # A）有源闭环
    res_p, mic_p = closed_loop_ratio(H, Hh, freqs, 48828.125, gain_db)
    # B）尾段（无源）= |H−Ĥ|²/|H|²
    tail_p = np.abs(H - Hh) ** 2
    h_p = np.abs(H) ** 2
    print("   %-28s 有源闭环  尾段(=CD)    |H|(dB)" % tag)
    for lo, hi in BANDS:
        sel = gate & (freqs >= lo) & (freqs < hi)
        if not sel.any():
            print("   %-28s   ---        ---         ---" % ("%d-%d Hz" % (lo, hi)))
            continue
        a = band_ratio(res_p, mic_p, freqs, lo, hi)
        b = band_ratio(tail_p, h_p, freqs, lo, hi)
        mh = 20 * np.log10(np.max(np.abs(H[sel])))
        print("   %-28s  %+6.1f dB  %+6.1f dB   %+6.1f"
              % ("%d-%d Hz" % (lo, hi), a, b, mh))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--model", required=True, help="模型 JSON（优先用 Q20 整数系数）")
    parser.add_argument("--gain-db", type=float, default=-6.0,
                        help="闭环工作点，取实测稳定点（默认 -6 dB）")
    parser.add_argument("--coherence", type=float, default=0.8)
    parser.add_argument("--limit", type=int, default=15360)
    args = parser.parse_args(argv)

    captures = load_dir(args.data_dir, args.limit, quiet=True)
    fs = captures[0][1].sample_rate_hz
    f, H, coh = estimate_h(captures)
    gate = (f >= 100) & (f <= 12000) & (coh >= args.coherence)

    model = load_model(args.model)
    Hh = fir_response(model["coef"], fs, f)

    print("数据 %s（%d 段，%d 帧/段）  模型 %s（taps=%d, %s, sha256=%s）"
          % (args.data_dir, len(captures), len(captures[0][1].reference),
             args.model, model["taps"], model["kind"],
             (model["sha256"] or "-")[:16]))
    print("工作点 g = %+.1f dB；相干门控 %.2f；频带 100–12000 Hz" % (args.gain_db,
                                                                    args.coherence))
    print()
    print("=== 同一份数据、同一频带下，两个指标差多少 ===")
    report("实测模型（部署系数）", f, H, Hh, gate, args.gain_db)
    print()
    # 完美模型作对照：证明"有源闭环比值"在模型完全正确时也不接近 0 dB
    report("完美模型（Ĥ=H）", f, H, H.copy(), gate, args.gain_db)
    print()
    # 空模型作对照
    report("空模型（Ĥ=0，等价旁路）", f, H, np.zeros_like(H), gate, args.gain_db)

    print()
    print("读法：")
    print("  · 尾段一列就是 −CD，可以拿来和离线拟合结果直接比。")
    print("  · 有源闭环一列随 g 和外部声源大小变化；完美模型与空模型都会趋近 0 dB，")
    print("    所以它不能作为“模型还剩多少抵消”的判据，也不能与离线 CD 相减。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
