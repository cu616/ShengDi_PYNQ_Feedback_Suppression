"""导出 H 与 Ĥ 的复数响应，判"高频失配是不是延迟造成的"。

为什么要这个脚本：现场报告里的"相位差"列与"复残差"列用余弦定理对不上
（8350 Hz 报 −152° / 0.815，但按余弦定理应得 2.286）。三列里必有一列
不是同一口径，必须先拿到同一频点、同一网格上的四个实数量才能定案。

本脚本只做测量与报告，不做判断、不改模型。

输入：
  --run-dir   场景 runs/<scene>/io 目录（含 reference/microphone 的 npz）
  --model     model.json（含 coefficients_q20 或 coefficients）
  --taps      模型抽头数，默认 512
  --lag-first 前向调度相对 t=0 的偏移帧，默认 1（与 recal_algorithm 一致）

输出：
  1. 指定频点的 H.re/im、Ĥ.re/im、|H|、|Ĥ|、Δφ、|H−Ĥ|、相干
  2. 由 |H−Ĥ| 反解出的 Δφ（用于交叉检验报告里的相位列）
  3. 相位差对频率的线性拟合 → 等效群延迟差（帧），这是判"延迟问题"的关键
  4. 一份 JSON（便于贴进报告）

用法：
  python scripts/diag_highfreq_phase.py \
      --run-dir ~/.local/state/shengdi/runs/6b2e43d4.../io \
      --model ~/.local/state/shengdi/runs/6b2e43d4.../model.json \
      --out /tmp/hf_phase.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

import numpy as np

FS_DEFAULT = 48828.125
NPERSEG = 4096
HANN = True

# 关心的频点：老报告的六个 + 8.3–8.6 kHz 的细网格
COARSE_HZ = [400, 1000, 2000, 4000, 6000, 8000, 8350, 8500, 9000, 10000]
FINE_LO, FINE_HI, FINE_STEP = 8200.0, 8700.0, 25.0


def load_pairs(run_dir: Path):
    """读一个场景目录下所有含 reference/microphone 的 npz。按文件名排序。"""
    pairs, fs_seen = [], set()
    for p in sorted(glob.glob(str(run_dir / "**" / "*.npz"), recursive=True)):
        try:
            c = np.load(p, allow_pickle=True)
        except Exception:
            continue
        if "reference" not in c.files or "microphone" not in c.files:
            continue
        u = np.asarray(c["reference"], dtype=float).ravel()
        m = np.asarray(c["microphone"], dtype=float).ravel()
        n = min(len(u), len(m))
        if n < NPERSEG * 2:
            continue
        # 源窗口对齐：源比窗口长时要按 first_frame 截，避免尾部空段拉低相干
        if "source_pcm16" in c.files:
            try:
                md = json.loads(str(c["metadata_json"])) if "metadata_json" in c.files else {}
                first = int(md.get("first_frame", 0) or 0)
                src = np.asarray(c["source_pcm16"])
                n = min(n, len(src) - first)
            except Exception:
                pass
        if n < NPERSEG * 2:
            continue
        pairs.append((u[:n], m[:n]))
        if "sample_rate_hz" in c.files:
            fs_seen.add(float(np.asarray(c["sample_rate_hz"]).ravel()[0]))
    fs = fs_seen.pop() if len(fs_seen) == 1 else (sorted(fs_seen)[0] if fs_seen else FS_DEFAULT)
    return pairs, fs, len(fs_seen) > 1


def welch_H(pairs, fs, nperseg=NPERSEG):
    """与 recal_algorithm._welch_complex 同口径：按段累加交叉谱，不跨段拼接。"""
    num = den = syy = None
    f = None
    for u, m in pairs:
        seg = min(nperseg, len(u))
        step = max(1, seg // 2)
        win = np.hanning(seg + 1)[:seg] if HANN else np.ones(seg)
        fr = np.lib.stride_tricks.sliding_window_view(u, seg)[::step]
        fm = np.lib.stride_tricks.sliding_window_view(m, seg)[::step]
        R = np.fft.rfft(fr * win, axis=1)
        M = np.fft.rfft(fm * win, axis=1)
        a = np.mean(np.abs(R) ** 2, axis=0)
        c = np.mean(np.abs(M) ** 2, axis=0)
        x = np.mean(M * np.conj(R), axis=0)
        if num is None:
            num, den, syy = x, a, c
        else:
            num, den, syy = num + x, den + a, syy + c
        f = np.fft.rfftfreq(seg, 1.0 / fs)
    H = num / np.maximum(den, 1e-30)
    coh = np.abs(num) ** 2 / np.maximum(den * syy, 1e-30)
    return f, H, np.clip(coh, 0, 1)


def model_H(h, freqs, fs, lag_first=1):
    k = np.arange(len(h)) + lag_first
    return np.array([np.sum(h * np.exp(-1j * 2 * np.pi * fi * k / fs)) for fi in freqs])


def wrap_deg(x):
    return (np.degrees(x) + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--taps", type=int, default=512)
    ap.add_argument("--lag-first", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = Path(os.path.expanduser(args.run_dir))
    model_path = Path(os.path.expanduser(args.model))
    pairs, fs, mixed_fs = load_pairs(run_dir)
    if not pairs:
        raise SystemExit("在 %s 里没找到可用的 reference/microphone npz" % run_dir)
    if mixed_fs:
        print("注意：检测到多种采样率，已取最小者")

    md = json.loads(model_path.read_text(encoding="utf-8"))
    q = md.get("coefficients_q20")
    if q is None:
        h = np.asarray(md["coefficients"], dtype=float)
    else:
        h = np.asarray(q, dtype=float) / 2 ** 20
    taps = args.taps
    if len(h) < taps:
        h = np.concatenate([h, np.zeros(taps - len(h))])
    h = h[:taps]

    f, H, coh = welch_H(pairs, fs)
    Hh = model_H(h, f, fs, args.lag_first)
    E = H - Hh

    def pick(freq):
        i = int(np.argmin(np.abs(f - freq)))
        return i, float(f[i])

    rows = []
    for want in COARSE_HZ:
        i, fg = pick(want)
        a, b, d = abs(H[i]), abs(Hh[i]), H[i] - Hh[i]
        dphi = wrap_deg(np.angle(H[i] / Hh[i]))
        rows.append({
            "request_hz": want, "grid_hz": round(fg, 3),
            "H_re": float(H[i].real), "H_im": float(H[i].imag),
            "Hh_re": float(Hh[i].real), "Hh_im": float(Hh[i].imag),
            "H_abs": float(a), "Hh_abs": float(b),
            "phase_diff_deg": float(dphi),
            "resid_abs": float(abs(d)), "resid_re": float(d.real), "resid_im": float(d.imag),
            "coherence": float(coh[i]),
        })

    fine = []
    lo, hi = FINE_LO, FINE_HI
    sel = np.where((f >= lo) & (f <= hi))[0]
    for i in sel:
        fine.append({
            "hz": round(float(f[i]), 3),
            "H_abs": float(abs(H[i])), "Hh_abs": float(abs(Hh[i])),
            "phase_diff_deg": float(wrap_deg(np.angle(H[i] / Hh[i]))),
            "resid_abs": float(abs(E[i])), "coherence": float(coh[i]),
        })

    # 关键判据：相位差是否随频率线性增长（= 恒定群延迟差）
    gate = (coh >= 0.8) & (f >= 300) & (f <= 10000)
    ph = wrap_deg(np.angle(H[gate] / Hh[gate]))
    fg_ = f[gate]
    # 去卷绕后再拟合
    ph_un = np.unwrap(np.radians(ph))
    if fg_.size > 8:
        slope, intercept = np.polyfit(fg_, ph_un, 1)      # rad/Hz
        tau = -slope / (2 * np.pi)                        # s
        resid_fit = ph_un - (slope * fg_ + intercept)
    else:
        slope = tau = 0.0
        resid_fit = np.zeros(1)
    delay_frames = tau * fs
    fit_rms_deg = float(np.degrees(np.std(resid_fit)))

    print("=" * 78)
    print("场景: %s" % run_dir)
    print("模型: %s  taps=%d  lag_first=%d  L1=%.6f" % (model_path.name, taps, args.lag_first, np.abs(h).sum()))
    print("段数: %d   fs=%.3f Hz   nperseg=%d   bin=%.3f Hz" % (len(pairs), fs, NPERSEG, fs / NPERSEG))
    print()
    print("%8s %7s %7s %10s %10s %8s %8s" % ("f/Hz", "|H|", "|Ĥ|", "Δφ(°)", "|H−Ĥ|", "相干", "反解Δφ"))
    print("-" * 68)
    for r in rows:
        a, b, rep = r["H_abs"], r["Hh_abs"], r["resid_abs"]
        c = (a * a + b * b - rep * rep) / max(2 * a * b, 1e-12)
        back = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
        print("%8.1f %7.3f %7.3f %10.1f %10.3f %8.3f %7.1f°" % (
            r["grid_hz"], a, b, r["phase_diff_deg"], rep, r["coherence"], back))
    print()
    print("相位差线性拟合（300–10000 Hz，相干>=0.8，n=%d）：" % gate.sum())
    print("  等效群延迟差 = %+.4f 帧  (%.2f μs)" % (delay_frames, tau * 1e6))
    print("  拟合残差 RMS = %.1f°   （残差小 → 是延迟问题；残差大 → 是模型形状问题）" % fit_rms_deg)
    print("  在 8350 Hz，%.3f 帧对应 %.1f°" % (delay_frames, delay_frames * 360 * 8350 / fs))
    print()
    print("8.3–8.6 kHz 细网格（|H| 峰值附近）：")
    pk = max(fine, key=lambda r: r["H_abs"]) if fine else None
    if pk:
        print("  |H| 峰值 %.3f @ %.1f Hz，此处 |Ĥ|=%.3f、Δφ=%.1f°、|H−Ĥ|=%.3f" % (
            pk["H_abs"], pk["hz"], pk["Hh_abs"], pk["phase_diff_deg"], pk["resid_abs"]))
    over = [r for r in fine if r["resid_abs"] * 1.4126 > 1.0]
    print("  +3 dB 下环路>1 的 bin 数：%d / %d" % (len(over), len(fine)))
    for r in over[:6]:
        print("     %.1f Hz  |H|=%.3f |Ĥ|=%.3f Δφ=%+.1f° 残差=%.3f → 环路 %.2f" % (
            r["hz"], r["H_abs"], r["Hh_abs"], r["phase_diff_deg"], r["resid_abs"],
            r["resid_abs"] * 1.4126))

    out = {
        "run_dir": str(run_dir), "model_path": str(model_path),
        "taps": taps, "lag_first": args.lag_first,
        "fs": fs, "nperseg": NPERSEG, "segments": len(pairs),
        "model_L1": float(np.abs(h).sum()),
        "coarse": rows, "fine_8k3_8k6": fine,
        "phase_fit": {
            "delay_frames": float(delay_frames),
            "delay_us": float(tau * 1e6),
            "fit_rms_deg": fit_rms_deg,
            "gated_bins": int(gate.sum()),
            "band_hz": [300.0, 10000.0],
        },
    }
    if args.out:
        Path(os.path.expanduser(args.out)).write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\nJSON 已写: %s" % args.out)


if __name__ == "__main__":
    main()
