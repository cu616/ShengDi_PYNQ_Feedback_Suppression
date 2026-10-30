#!/usr/bin/env python3
"""声源注入位置决定 residual/mic 的含义：两种实现分别给出方程与可控用例。

背景
----
C 指出 A 的数字回放路径是

    u[n] = sat( source[n] + gain(residual[n−2]) )

即**声源从 DAC 输入端注入**，而不是加在麦克风观测端。这两者的 residual/mic
完全不是一回事，必须分开写。

记号
----
H   真实声学路径（DAC 输入 → 麦克风），Ĥ 模型，g 数字增益，z⁻² 是 `played[n+2]=g·residual[n]`，
s   注入信号（数字注入时在 DAC 端，声学注入时在麦克风端），loop = g·z⁻²·(H−Ĥ)。

**情形 D：数字注入（A 的实现）**
    played = s + g·z⁻²·residual,   mic = H·played,   residual = mic − Ĥ·played
    ⇒ residual = (H−Ĥ)·s/(1−loop),  mic = H·s/(1−loop)
    ⇒ **residual/mic = (H−Ĥ)/H = 1/CD(f)**   逐频点精确，与 g 和 s 的大小无关

**情形 A：声学注入（声源在麦克风端）**
    played = g·z⁻²·residual,  mic = H·played + s,  residual = mic − Ĥ·played
    ⇒ residual = s/(1−loop),  mic = s·[(1−loop) + g·H·z⁻²]/(1−loop)
    ⇒ **residual/mic = 1/[(1−loop) + g·H·z⁻²]**   随 g 与 s 变化，与 CD 无关

所以：
- 在情形 D 下，**有源段的 residual/mic 就是 −CD**，可以直接与离线结果比。
  上一版报告把它一概说成"不含模型信息"，只对情形 A 成立，这里更正。
- 在情形 A 下，完美模型与空模型都回到 0 dB 附近，该比值不能用来评价模型。
- 两种情形都要求：无削顶、无饱和、`reference` 就是真正播放的序列（对齐正确）、
  没有额外的声学源。

进一步的三条限定
----------------
1. **逐频点复数比 vs 宽带能量比**：情形 D 的恒等式是逐频点的。宽带能量比是
   `Σ|H−Ĥ|²·|s|²/|1−loop|² ÷ Σ|H|²·|s|²/|1−loop|²`，被 `|s|²/|1−loop|²` 加权；
   增益越高、越接近失稳，权重越集中在临界频点。所以宽带比更适合回答"还剩多少环路增益"，
   不能当成"平均 CD"。
2. **对齐误差**：残差是按逐样本算的，差一帧在 8.4 kHz 是 62°。一帧错位就能把 CD 从
   +20 dB 打成 −1 dB 左右，与"模型在高电平下失效"在数值上无法区分。先查 `ref→mic`
   与 `pred→mic` 的对齐（相位差随频率是否线性）。
3. **非线性**：`sat()`、DAC 削顶、麦克风/前置放大削顶、功放压缩都会破坏上述恒等式。
   出现削顶时该段不能用于评价 CD。

用法
----
    python scripts/closed_loop_metric_check.py --data-dir <目录> --model <json> \
        [--gain-db -6] [--coherence 0.5] [--verify]

`--verify` 额外跑单音时域仿真，用两种注入各有解析解来交叉验证上面的方程。
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from feedback.calibration import predict  # noqa: E402
from feedback.path_analysis import (welch_cross, coherence_from_spectra,  # noqa: E402
                                    fir_response)
from score_time_domain import load_dir, load_model  # noqa: E402

BANDS = [(100, 300), (300, 1000), (1000, 3000), (3000, 6000),
         (6000, 8000), (8200, 8600), (8600, 12000)]
SCHEDULE = 2.0
FS = 48828.125


def estimate_h(captures, nperseg=2048):
    S = None
    for _, c in captures:
        fs = c.sample_rate_hz
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


def ratio_digital(H, Hh, freqs, gain_db):
    """情形 D：residual/mic = (H−Ĥ)/H，与 g 无关；返回 (分子, 分母) 功率。"""
    return np.abs(H - Hh) ** 2, np.abs(H) ** 2


def ratio_acoustic(H, Hh, freqs, gain_db):
    """情形 A：residual/mic = 1/[(1−loop) + g·H·z⁻²]。"""
    g = 10 ** (gain_db / 20.0)
    z2 = np.exp(-1j * 2 * np.pi * freqs * SCHEDULE / FS)
    loop = g * (H - Hh) * z2
    residual = 1.0 / (1.0 - loop)
    mic = 1.0 + g * H * z2 / (1.0 - loop)
    return np.abs(residual) ** 2, np.abs(mic) ** 2


def table(f, H, Hh, gate, gain_db, label):
    print("   %-24s %-10s %10s %10s" % (label, "频带", "数字注入", "声学注入"))
    dn, dd = ratio_digital(H, Hh, f, gain_db)
    an, ad = ratio_acoustic(H, Hh, f, gain_db)
    for lo, hi in BANDS:
        sel = gate & (f >= lo) & (f < hi)
        if not sel.any():
            print("   %-24s %-10s %10s %10s" % ("", "%d-%d" % (lo, hi), "---", "---"))
            continue
        print("   %-24s %-10s %+9.1f %+10.1f"
              % ("", "%d-%d Hz" % (lo, hi),
                 band_ratio(dn, dd, f, lo, hi), band_ratio(an, ad, f, lo, hi)))


def build_ir(f, H, n=1 << 13, taps=512):
    """把频域 H 插值成时域 IR，供单音时域仿真使用。"""
    fr = np.fft.rfftfreq(n, 1.0 / FS)
    real = np.interp(fr, f, H.real)
    imag = np.interp(fr, f, H.imag)
    h = np.fft.irfft(real + 1j * imag, n)
    return h[:taps]


def tone_case(ir_H, h_model, f0, gain_db, inject, nsamp=8000, settle=4000):
    """单音时域仿真，返回 (实测复数比, 解析复数比)。两种注入各一条路径。"""
    g = 10 ** (gain_db / 20.0)
    n = np.arange(nsamp)
    src = np.cos(2 * np.pi * f0 * n / FS)
    Hlen, Mlen = len(ir_H), len(h_model)
    sched = int(SCHEDULE)
    played = np.zeros(nsamp + sched + 4)
    mic = np.zeros(nsamp)
    residual = np.zeros(nsamp)
    # 取 H 的因果形式：mic[n] = Σ_j ir_H[j]·played[n−j]（ir_H[0] 对应 0 延迟）
    for idx in range(nsamp):
        lo = max(0, idx - Hlen + 1)
        seg = played[lo:idx + 1][::-1]
        mic[idx] = float(np.dot(ir_H[:len(seg)], seg))
        # pred[n] = Σ_k h[k]·played[n−1−k]：模型已含一帧延迟
        lo2 = max(0, idx - Mlen)
        seg2 = played[lo2:idx][::-1]        # played[n−1] 起
        pred = float(np.dot(h_model[:len(seg2)], seg2)) if len(seg2) else 0.0
        if inject == "acoustic":
            mic[idx] += src[idx]
        residual[idx] = mic[idx] - pred
        played[idx + sched] = (src[idx] + g * residual[idx]) if inject == "digital" \
            else g * residual[idx]
    win = slice(settle, nsamp)
    t = n[win]
    ref = np.exp(-2j * np.pi * f0 * t / FS)
    a_mic = 2 * np.mean(mic[win] * ref)
    a_res = 2 * np.mean(residual[win] * ref)
    measured = a_res / a_mic
    # 解析：用 IR 的频响代入上面的闭式
    fr = np.fft.rfftfreq(1 << 14, 1.0 / FS)
    k = int(np.argmin(np.abs(fr - f0)))
    H_at = np.fft.rfft(ir_H, 1 << 14)[k]
    # Ĥ 用 [0,h] 的 FFT 取同一栅格，避免与 fir_response 的采样点不一致
    Hh_at = np.fft.rfft(np.r_[0.0, np.asarray(h_model, dtype=float)], 1 << 14)[k]
    z2 = np.exp(-1j * 2 * np.pi * f0 * SCHEDULE / FS)
    if inject == "digital":
        analytic = (H_at - Hh_at) / H_at
    else:
        loop = g * (H_at - Hh_at) * z2
        analytic = 1.0 / ((1.0 - loop) + g * H_at * z2)
    return measured, analytic


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--gain-db", type=float, default=-6.0)
    parser.add_argument("--coherence", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=15360)
    parser.add_argument("--verify", action="store_true", help="跑单音时域仿真交叉验证")
    args = parser.parse_args(argv)

    captures = load_dir(args.data_dir, args.limit, quiet=True)
    f, H, coh = estimate_h(captures)
    gate = (f >= 100) & (f <= 12000) & (coh >= args.coherence)
    model = load_model(args.model)
    Hh = fir_response(model["coef"], FS, f)

    print("数据 %s（%d 段）  模型 %s（taps=%d, %s）  g = %+.1f dB  相干门控 %.2f"
          % (args.data_dir, len(captures), model["name"], model["taps"],
             model["kind"], args.gain_db, args.coherence))
    print()
    print("=== 1. 同一份数据，两种注入位置下的 residual/mic（dB，负=残差更小）===")
    table(f, H, Hh, gate, args.gain_db, "实测模型")
    table(f, H, H.copy(), gate, args.gain_db, "完美模型 Ĥ=H")
    table(f, H, np.zeros_like(H), gate, args.gain_db, "空模型 Ĥ=0")
    print()
    print("   读法：数字注入一列就是 −CD，与 g 无关；声学注入一列随 g 变，")
    print("        完美模型与空模型都会趋近 0 dB，不能当模型质量的判据。")

    if args.verify:
        print()
        print("=== 2. 可控用例：已知合成路径 + 单音时域仿真 vs 解析式 ===")
        # 用短合成路径做对照：避免实测 IR 截断与近临界收敛问题，
        # 这里检验的是"方程本身"，不是房间。
        ir_H = np.zeros(64)
        ir_H[10] = 0.40
        ir_H[11] = -0.10
        ir_H[31] = 0.05
        h_model = np.zeros(64)
        h_model[10] = 0.38
        h_model[11] = -0.12
        h_model[31] = 0.04
        print("   H 峰值 %.3f@10、%.3f@11、%.3f@31；Ĥ 略作扰动（模拟 5%% 量级误差）"
              % (ir_H[10], ir_H[11], ir_H[31]))
        for f0 in (500.0, 2000.0, 8400.0):
            for inject in ("digital", "acoustic"):
                for gain_db in (-18.0, -12.0):
                    m, a = tone_case(ir_H, h_model, f0, gain_db, inject)
                    err = 20 * np.log10(max(abs(m), 1e-30)) - 20 * np.log10(max(abs(a), 1e-30))
                    print("   %-8s %6.0f Hz  g=%+5.1f dB  仿真 %+6.2f dB  解析 %+6.2f dB  差 %+5.2f dB"
                          % (inject, f0, gain_db,
                             20 * np.log10(max(abs(m), 1e-30)),
                             20 * np.log10(max(abs(a), 1e-30)), err))
        print()
        print("   数字注入：换 g 后比值不变（与方程一致）；声学注入：随 g 明显变化。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
