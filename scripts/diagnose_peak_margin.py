"""8.4 kHz 共振处的环路裕度诊断：H 与模型 H_hat 的相位/幅度误差、失稳阈值与灵敏度预算。

输出四块：
  1. H 概况（峰值、可用频段、平均相干）。
  2. 误差最大的若干频点（|H|、|H_hat|、相位差、CD、相干）。
  3. 失稳阈值：必要判据 max|H-H_hat|，以及相位一致判据（含 2 拍闭环延迟）。
  4. 灵敏度预算：整拍/亚采样错位、峰值幅度误差各需要多少才把阈值压到目标值。

用法：
  python scripts/diagnose_peak_margin.py --data-dir <npz 目录> --model <模型 json>
      [--emit-dir <候选输出目录>] [--delay-frames 2]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from feedback.calibration import quantize_coefficients  # noqa: E402

FMIN_HZ = 300.0


def welch_cross(reference, microphone, nperseg=4096, overlap=0.5):
    hop = max(1, int(nperseg * (1 - overlap)))
    win = np.hanning(nperseg)
    nbin = nperseg // 2 + 1
    S_uu = np.zeros(nbin)
    S_mm = np.zeros(nbin)
    S_um = np.zeros(nbin, dtype=complex)
    for start in range(0, len(reference) - nperseg + 1, hop):
        U = np.fft.rfft(reference[start:start + nperseg] * win)
        M = np.fft.rfft(microphone[start:start + nperseg] * win)
        S_uu += (np.conj(U) * U).real
        S_mm += (np.conj(M) * M).real
        S_um += np.conj(U) * M
    return S_uu, S_mm, S_um


def estimate_H(paths, nperseg=4096, overlap=0.5):
    S_uu = S_mm = S_um = None
    fs = None
    for p in paths:
        cap = np.load(p)
        fs = float(cap["sample_rate_hz"])
        a, b, c = welch_cross(np.asarray(cap["reference"], float),
                              np.asarray(cap["microphone"], float),
                              nperseg, overlap)
        S_uu = a if S_uu is None else S_uu + a
        S_mm = b if S_mm is None else S_mm + b
        S_um = c if S_um is None else S_um + c
    H = S_um / S_uu
    coh = np.abs(S_um) ** 2 / (S_uu * S_mm)
    freqs = np.arange(len(H)) * fs / nperseg
    return freqs, H, coh, S_uu, nperseg, fs


Q20_SCALE = float(1 << 20)


def q20_sha256(values):
    """Q20 数组的身份哈希：little-endian int32 字节流（与 C 的 coefficients_sha256 同口径）。"""
    arr = np.asarray([int(v) for v in values], dtype=np.int64).astype("<i4")
    return hashlib.sha256(arr.tobytes()).hexdigest()


def load_deployed_model(path, allow_float_fallback=False):
    """按**部署身份**读模型：频响一律由 coefficients_q20 / 2**20 计算。

    浮点 `coefficients` 只允许在显式 `--dev-float` 时用于开发对比，且会被标注为非部署口径。
    返回 (model, coef, info)；coef 单位是"每抽头线性增益"，lag_first 由 info 携带。
    """
    raw = Path(path).read_bytes()
    model = json.loads(raw.decode("utf-8"))
    lag_first = int(model.get("lag_first", 1))
    if lag_first not in (0, 1):
        raise SystemExit("lag_first=%r 不在 {0,1}，先确认因果约定再跑" % lag_first)

    q20 = model.get("coefficients_q20")
    if q20 and len(q20) > 0:
        q20 = [int(v) for v in q20]
        coef = np.asarray(q20, dtype=float) / Q20_SCALE
        source = "coefficients_q20"
    elif allow_float_fallback:
        coef = np.asarray(model["coefficients"], dtype=float)
        q20 = None
        source = "coefficients(float) — 非部署口径，仅开发对比"
    else:
        raise SystemExit(
            "%s 没有 coefficients_q20；部署复算必须用定点系数。"
            "确需比较浮点实现请显式加 --dev-float。" % Path(path).name)

    info = {
        "path": str(Path(path).name),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "q20_sha256": q20_sha256(q20) if q20 is not None else None,
        "taps": int(len(coef)),
        "lag_first": lag_first,
        "source": source,
        "float_vs_q20_max_abs": None,
    }
    flt = model.get("coefficients")
    if q20 is not None and isinstance(flt, list) and len(flt) == len(q20):
        info["float_vs_q20_max_abs"] = float(np.max(np.abs(np.asarray(flt, float) - coef)))
    return model, coef, info


def model_response(coefficients, nfft, delay_samples=0.0, lag_first=1):
    """Ĥ(f)＝Σ h[k]·e^{−jω(lag_first+k)}；额外的整数拍延迟用 delay_samples 单独加，不重复计。"""
    h = np.asarray(coefficients, dtype=float)
    pad = np.zeros(nfft)
    pad[:len(h)] = h
    w = 2 * np.pi * np.arange(nfft // 2 + 1) / nfft
    # lag_first=1：第 k 个系数落在滞后 1+k 上。
    return np.fft.rfft(pad) * np.exp(-1j * w * (lag_first + delay_samples))


def necessary_threshold(E, freqs, gate):
    Eg = np.where(gate, E, 0.0)
    k = int(np.argmax(Eg))
    return -20 * np.log10(E[k]), float(freqs[k]), 20 * np.log10(E[k])


def positive_real_crossing(loop, freqs, gate, fmin=FMIN_HZ, return_all=False):
    """正反馈环路的正实轴穿越点（Nyquist 判据的近似），只接受真实穿越。

    四条硬约束：
      1. **相邻 bin**：只有原始频率网格上一一相邻、且两端都过门控的 bin 才允许插值，
         不跨低相干缺口去连两个不相邻频点。
      2. **正实轴**：虚部过零处插值**复数**环路，必须 Re>0。相位 ±180° 折返对应 Re<0，
         不是穿越，绝不能计入（旧实现按折回后的相位变号判，会把 179°→−179° 误判为穿越）。
      3. **端点也算**：虚部恰为 0 且 Re>0 的 bin，不论它是区间的左端、右端还是内部，
         都算一次穿越；同一次穿越在相邻两对里只会被数到一次（按 bin 去重），不重复计数。
         旧实现只判 `ya*yb<0`，右端恰落在正实轴上时收益被漏掉。
      4. **小增益与穿越分开报**：max|L|<1 是稳定的充分条件，1/max|L| 是下界；
         正实轴穿越给出的是另一套估计，两者不可互相替代。

    返回 (阈值 dB, 频率 Hz)；阈值为该点允许的最大线性增益 1/Re。
    `return_all=True` 时返回全部穿越点 [(Re, Hz)]，只供回归测试检查端点计数。
    **未检出穿越不等于物理上无限稳定**：只说明在过门控的频点上没找到 Re>0 的虚部过零，
    覆盖不足必须单独声明。
    """
    loop = np.asarray(loop, dtype=complex)
    freqs = np.asarray(freqs, dtype=float)
    gate = np.asarray(gate, dtype=bool)
    idx = np.where(gate & (freqs >= fmin))[0]

    hits = []          # [(Re, freq_hz)]
    counted = set()    # 已计过的 bin，防端点重复计数

    def take_endpoint(k):
        k = int(k)
        if k in counted:
            return
        if loop[k].imag != 0.0 or loop[k].real <= 0:
            return
        counted.add(k)
        hits.append((float(loop[k].real), float(freqs[k])))

    for a, b in zip(idx[:-1], idx[1:]):
        if b != a + 1:            # 中间有未过门控的频点，不插值
            continue
        ya, yb = loop[a].imag, loop[b].imag
        if ya == 0.0 or yb == 0.0:
            # 端点恰落在正实轴上：左端/右端都算，去重后每处只计一次
            if ya == 0.0:
                take_endpoint(a)
            if yb == 0.0:
                take_endpoint(b)
            continue
        if ya * yb < 0:
            t = ya / (ya - yb)
            z = loop[a] + t * (loop[b] - loop[a])
            if z.real <= 0:       # ±180° 折返，不是穿越
                continue
            hits.append((float(z.real), float(freqs[a] + t * (freqs[b] - freqs[a]))))
        # 同号：区间内没有虚部过零，不插值

    if len(idx) == 1:             # 只有一个过门控频点，退化为端点判定
        take_endpoint(idx[0])

    if return_all:                # 供回归测试检查"端点是否被重复计数"
        return sorted(hits, key=lambda x: -x[0])
    if not hits:
        return float("inf"), float("nan")
    re_max, f_max = max(hits, key=lambda x: x[0])
    return -20 * np.log10(re_max), f_max


def shift_coefficients(coefficients, delay_samples):
    h = np.asarray(coefficients, dtype=float)
    out = np.zeros_like(h)
    if delay_samples == 0:
        return h.copy()
    if delay_samples > 0:
        out[delay_samples:] = h[:-delay_samples]
    else:
        out[:delay_samples] = h[-delay_samples:]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--emit-dir", default=None)
    ap.add_argument("--delay-frames", type=int, default=2)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--nfft", type=int, default=4096,
                    help="Welch 窗长；结论随窗长变化，必须与引用口径一致")
    ap.add_argument("--coherence", type=float, default=0.8)
    ap.add_argument("--dev-float", action="store_true",
                    help="开发对比：允许在缺 coefficients_q20 时退回浮点系数（结果不是部署口径）")
    ap.add_argument("--expect-q20-sha256", default=None,
                    help="启动时校验部署系数身份，不一致直接退出")
    args = ap.parse_args()

    paths = sorted(glob.glob(str(Path(args.data_dir) / "seg_*.npz")))
    if not paths:
        raise SystemExit("no seg_*.npz in %s" % args.data_dir)
    freqs, H, coh, S_uu, nperseg, fs = estimate_H(paths, nperseg=args.nfft)
    gate = (coh >= args.coherence) & (freqs >= FMIN_HZ)
    mag = np.abs(H)
    kpk = int(np.argmax(np.where(gate, mag, 0)))
    print("段数 %d，fs %.3f Hz，bin 宽 %.1f Hz，相干>=0.8 且 f>=300Hz 的 bin %d/%d，平均相干 %.3f"
          % (len(paths), fs, fs / nperseg, gate.sum(), len(freqs), coh[gate].mean()))
    print("max|H| = %+.2f dB @ %.0f Hz（相干 %.3f）"
          % (20 * np.log10(mag[kpk]), freqs[kpk], coh[kpk]))
    print("宽带 |H|（按参考能量加权）= %+.2f dB"
          % (10 * np.log10(np.sum(np.abs(H[gate]) ** 2 * S_uu[gate]) / np.sum(S_uu[gate]))))

    model, coef, info = load_deployed_model(args.model, allow_float_fallback=args.dev_float)
    if args.expect_q20_sha256 and info["q20_sha256"] != args.expect_q20_sha256:
        raise SystemExit("Q20 身份不符：文件 %s，期望 %s"
                         % (info["q20_sha256"], args.expect_q20_sha256))
    nfft = nperseg
    print("\n模型 %s：taps=%d lag_first=%d，系数口径 %s"
          % (info["path"], info["taps"], info["lag_first"], info["source"]))
    print("  file sha256 %s" % info["file_sha256"])
    print("  q20  sha256 %s" % info["q20_sha256"])
    if info["float_vs_q20_max_abs"] is not None:
        print("  浮点与 Q20 的最大系数差 %.3e（只作参考，频响一律按 Q20）"
              % info["float_vs_q20_max_abs"])
    if len(coef) > nfft:
        raise SystemExit("模型抽头数超过 FFT 长度，先调大 nperseg")

    H_hat = model_response(coef, nfft, lag_first=info["lag_first"])
    E = np.abs(H - H_hat)
    thr_n, f_n, emax = necessary_threshold(E, freqs, gate)
    # 环路 L = (H − Ĥ)·e^{-jω·2}：Ĥ 已含 lag_first，调度延迟只在这里加一次
    loop = (H - H_hat) * np.exp(-1j * 2 * np.pi * args.delay_frames * freqs / fs)
    thr_p, f_p = positive_real_crossing(loop, freqs, gate)
    covered = int(gate.sum())
    print("\n[因果与延迟] Ĥ 含 lag_first=%d 拍；环路再乘 %d 拍调度延迟，合计 %d 拍（各计一次）"
          % (info["lag_first"], args.delay_frames, info["lag_first"] + args.delay_frames))
    print("[覆盖率] 过门控 bin %d / %d（%.1f%%），未覆盖频段按未知处理，不外推；"
          "未检出穿越不等于无限稳定"
          % (covered, len(freqs), 100.0 * covered / len(freqs)))
    print("[阈值] 小增益充分条件 max|L| = %+.2f dB @ %.0f Hz -> 1/max|L| = %+.2f dB（保守下界）"
          % (20 * np.log10(np.abs(loop[gate]).max()),
             freqs[gate][np.argmax(np.abs(loop[gate]))],
             -20 * np.log10(np.abs(loop[gate]).max())))
    print("       正实轴穿越（含 %d 拍调度延迟）-> 估计 %+.2f dB @ %.0f Hz"
          % (args.delay_frames, thr_p, f_p))

    order = np.argsort(np.where(gate, E, 0))[::-1][: args.top]
    print("\n[误差最大的频点]")
    print("   freq     |H|    |H_hat|     |E|     相位差     CD     相干")
    for k in order:
        dphi = np.degrees(np.angle(H_hat[k]) - np.angle(H[k]))
        print("  %6.0f  %+6.2f  %+7.2f  %+7.2f  %+7.1f  %+7.2f  %.3f"
              % (freqs[k], 20 * np.log10(mag[k]), 20 * np.log10(abs(H_hat[k])),
                 20 * np.log10(E[k]), dphi, 20 * np.log10(mag[k] / E[k]), coh[k]))

    print("\n[灵敏度预算：亚采样错位]")
    print("  错位(样点)   相移@%.0fHz   阈值 dB   阈频 Hz" % freqs[kpk])
    for d in (0.0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0):
        Hd = model_response(coef, nfft, delay_samples=d, lag_first=info["lag_first"])
        Ed = np.abs(H - Hd)
        t, f, _ = necessary_threshold(Ed, freqs, gate)
        print("  %+8.2f  %+11.1f  %+8.2f  %7.0f"
              % (d, 360 * d * freqs[kpk] / fs, t, f))

    print("\n[灵敏度预算：峰值幅度相对误差]")
    print("  |H_hat|/|H| 误差 dB   该点 |E| dB   该点阈值 dB")
    kk = kpk
    for err_db in (0.0, 1.5, 2.6, 3.5, 4.5, 6.0):
        # 只在峰值附近把模型按 err_db 缩放，模拟"这一带的模型偏大/偏小"
        Hd = H_hat.copy()
        band = (freqs >= freqs[kk] - 300) & (freqs <= freqs[kk] + 300)
        Hd[band] *= 10 ** (err_db / 20)
        E2 = np.abs(H[band] - Hd[band])
        k2 = int(np.argmax(E2))
        print("  %+19.1f  %+11.2f  %+11.2f"
              % (err_db, 20 * np.log10(E2[k2]), -20 * np.log10(E2[k2])))

    if args.emit_dir:
        out = Path(args.emit_dir)
        out.mkdir(parents=True, exist_ok=True)
        written = []
        for d in (-1, 1):
            name = "model_512_shift%+d.json" % d
            new_coef = shift_coefficients(coef, d)
            alt = dict(model)
            alt["coefficients"] = new_coef.tolist()
            # Q20 必须按平移后的浮点系数重算，否则会带着原模型的定点数组
            alt["coefficients_q20"] = quantize_coefficients(new_coef).tolist()
            alt["taps"] = len(coef)
            alt.pop("validation", None)  # 平移后的验证指标不再适用
            alt["derived_from"] = Path(args.model).name
            alt["derived_by"] = "scripts/diagnose_peak_margin.py --emit-dir"
            alt["status"] = "diagnostic_variant_alignment_test"
            alt["note"] = ("整体平移 %+d 拍（lag_first=1：h[k] 乘 played[n-1-k]）；"
                           "仅用于判定 B 侧模型与 A 侧会话的 ref->mic 延迟是否差整拍，"
                           "不是新模型，不要写进部署清单" % d)
            (out / name).write_text(json.dumps(alt, indent=2) + "\n", encoding="utf-8")
            written.append((name, q20_sha256(alt["coefficients_q20"])))
        print("\n[输出]")
        for name, fp in written:
            print("  %-40s q20 sha256 %s" % (out / name, fp))


if __name__ == "__main__":
    main()
