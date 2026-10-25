"""在前向通路里插入固定二阶级联，重算环路裕度与语音代价（**幅度筛选参考，不是可部署实现**）。

环路（参考取实际播放字）：
    L(f) = g · B(f) · (H(f) − Ĥ(f)) · e^{−jω·2}
B 为前向 EQ 的**幅度响应**，g=0 dB 归一。判据与 diagnose_peak_margin 一致：
小增益 max|L|<1 是充分条件（保守下界），正实轴穿越是 Nyquist 近似估计。

口径限制：此处只用幅度曲线，不含真实因果 SOS 的复频响、系数量化与额外延迟。
所以结果只能标作"筛选参考"；要把某个 EQ 写成可部署收益，必须另补因果 SOS 复频响与量化证据。
本冲刺该候选已被否定，不做这一步。

用法：
  python scripts/eval_forward_eq.py --data-dir <段目录> --model <模型 json> \
      --eq "441:12:4" [--eq "3898:10:4"] [--nfft 8192] [--delay-frames 2]
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from diagnose_peak_margin import (  # noqa: E402
    FMIN_HZ,
    estimate_H,
    load_deployed_model,
    model_response,
    positive_real_crossing,
)


def biquad_notch(f, f0, depth_db, q):
    """二阶陷波的幅度响应（归一化：直流=1，中心处 10^(-depth/20)）。"""
    w = f / f0
    re = 1 - w ** 2
    im = w / q
    # 分子加零点衰减：|1 - jk·γ| / |1 - jk|，γ = 10^(-depth/20)
    g = 10 ** (-depth_db / 20)
    return np.sqrt(re ** 2 + (im * g) ** 2) / np.sqrt(re ** 2 + im ** 2)


def parse_eq(items):
    spec = []
    for it in items or []:
        f0, depth, q = (float(x) for x in it.split(":"))
        spec.append((f0, depth, q))
    return spec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--eq", action="append", default=[],
                    help="f0:depth_db:Q，可重复")
    ap.add_argument("--nfft", type=int, default=8192)
    ap.add_argument("--coherence", type=float, default=0.8)
    ap.add_argument("--delay-frames", type=int, default=2)
    ap.add_argument("--dev-float", action="store_true",
                    help="开发对比：允许退回浮点系数（不是部署口径）")
    ap.add_argument("--expect-q20-sha256", default=None)
    args = ap.parse_args()

    paths = sorted(glob.glob(str(Path(args.data_dir) / "seg_*.npz")))
    if not paths:
        raise SystemExit("no seg_*.npz in %s" % args.data_dir)
    freqs, H, coh, _Suu, nfft, fs = estimate_H(paths, nperseg=args.nfft)
    gate = (coh >= args.coherence) & (freqs >= FMIN_HZ)

    _model, coef, info = load_deployed_model(args.model, allow_float_fallback=args.dev_float)
    if args.expect_q20_sha256 and info["q20_sha256"] != args.expect_q20_sha256:
        raise SystemExit("Q20 身份不符：文件 %s，期望 %s"
                         % (info["q20_sha256"], args.expect_q20_sha256))
    H_hat = model_response(coef, nfft, lag_first=info["lag_first"])
    loop = (H - H_hat) * np.exp(-1j * 2 * np.pi * args.delay_frames * freqs / fs)

    spec = parse_eq(args.eq)
    B = np.ones(len(freqs))
    for f0, depth, q in spec:
        B *= biquad_notch(freqs, f0, depth, q)
    loop_eq = loop * B

    print("数据 %s（%d 段），模型 %s，nfft=%d，过门控 bin %d/%d（%.1f%%）"
          % (Path(args.data_dir).name, len(paths), info["path"], nfft,
             gate.sum(), len(freqs), 100.0 * gate.sum() / len(freqs)))
    print("系数口径 %s，q20 sha256 %s，taps=%d，lag_first=%d + 调度 %d 拍"
          % (info["source"], info["q20_sha256"], info["taps"], info["lag_first"],
             args.delay_frames))
    print("EQ: %s" % (", ".join("%.0f Hz/%.0f dB/Q%.0f" % s for s in spec) or "无"))

    for tag, L in (("无 EQ", loop), ("含 EQ", loop_eq)):
        mag = np.abs(L[gate])
        k = int(np.argmax(mag))
        thr_e, f_e = positive_real_crossing(L, freqs, gate)
        print("  %-6s 小增益 max|L| = %+6.2f dB @ %5.0f Hz -> 下界 %+6.2f dB；"
              "正实轴穿越 %+6.2f dB @ %5.0f Hz"
              % (tag, 20 * np.log10(mag[k]), freqs[gate][k],
                 -20 * np.log10(mag[k]), thr_e, f_e))

    if spec:
        print("\n语音代价（前向幅度响应，dB）")
        for fc in (200.0, 300.0, 400.0, 441.0, 500.0, 700.0, 1000.0, 2000.0, 4000.0):
            k = int(np.argmin(np.abs(freqs - fc)))
            print("  %6.0f Hz  %+6.2f dB" % (freqs[k], 20 * np.log10(B[k])))
        for f0, depth, q in spec:
            bw = f0 / q
            print("  %.0f Hz 处 −3 dB 带宽约 %.0f Hz（Q=%.1f）" % (f0, bw, q))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
