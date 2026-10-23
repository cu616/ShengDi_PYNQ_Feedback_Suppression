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


def model_response(coefficients, nfft, delay_samples=0.0):
    h = np.asarray(coefficients, dtype=float)
    pad = np.zeros(nfft)
    pad[:len(h)] = h
    w = 2 * np.pi * np.arange(nfft // 2 + 1) / nfft
    # lag_first=1：第 k 个系数落在滞后 1+k 上。
    return np.fft.rfft(pad) * np.exp(-1j * w * (1.0 + delay_samples))


def necessary_threshold(E, freqs, gate):
    Eg = np.where(gate, E, 0.0)
    k = int(np.argmax(Eg))
    return -20 * np.log10(E[k]), float(freqs[k]), 20 * np.log10(E[k])


def phase_consistent_threshold(E, loop_phase, freqs, gate, fmin=FMIN_HZ):
    sel = gate & (freqs >= fmin)
    e = E[sel]
    f = freqs[sel]
    pu = np.unwrap(loop_phase[sel])
    n = np.round(pu / (2 * np.pi))
    x = pu - n * 2 * np.pi
    best, best_f = 0.0, float("nan")
    for k in range(len(x) - 1):
        if x[k] == 0.0:
            cand, cf = e[k], f[k]
        elif x[k] * x[k + 1] < 0:
            t = x[k] / (x[k] - x[k + 1])
            cand = e[k] + t * (e[k + 1] - e[k])
            cf = f[k] + t * (f[k + 1] - f[k])
        else:
            continue
        if cand > best:
            best, best_f = cand, cf
    if best <= 0:
        return float("inf"), float("nan")
    return 20 * np.log10(1.0 / best), best_f


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


def sha_fingerprint(values):
    payload = json.dumps([int(v) for v in values], separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--emit-dir", default=None)
    ap.add_argument("--delay-frames", type=int, default=2)
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    paths = sorted(glob.glob(str(Path(args.data_dir) / "seg_*.npz")))
    if not paths:
        raise SystemExit("no seg_*.npz in %s" % args.data_dir)
    freqs, H, coh, S_uu, nperseg, fs = estimate_H(paths)
    gate = (coh >= 0.8) & (freqs >= FMIN_HZ)
    mag = np.abs(H)
    kpk = int(np.argmax(np.where(gate, mag, 0)))
    print("段数 %d，fs %.3f Hz，bin 宽 %.1f Hz，相干>=0.8 且 f>=300Hz 的 bin %d/%d，平均相干 %.3f"
          % (len(paths), fs, fs / nperseg, gate.sum(), len(freqs), coh[gate].mean()))
    print("max|H| = %+.2f dB @ %.0f Hz（相干 %.3f）"
          % (20 * np.log10(mag[kpk]), freqs[kpk], coh[kpk]))
    print("宽带 |H|（按参考能量加权）= %+.2f dB"
          % (10 * np.log10(np.sum(np.abs(H[gate]) ** 2 * S_uu[gate]) / np.sum(S_uu[gate]))))

    model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    coef = model["coefficients"]
    nfft = nperseg
    print("\n模型 %s：taps=%d lag_first=%d"
          % (Path(args.model).name, len(coef), model["lag_first"]))
    if len(coef) > nfft:
        raise SystemExit("模型抽头数超过 FFT 长度，先调大 nperseg")

    H_hat = model_response(coef, nfft)
    E = np.abs(H - H_hat)
    thr_n, f_n, emax = necessary_threshold(E, freqs, gate)
    loop_phase = np.angle(H - H_hat) - 2 * np.pi * args.delay_frames * freqs / fs
    thr_p, f_p = phase_consistent_threshold(E, loop_phase, freqs, gate)

    print("\n[阈值] 必要判据 max|H-H_hat| = %+.2f dB @ %.0f Hz -> 阈值 %+.2f dB"
          % (emax, f_n, thr_n))
    print("       相位一致判据（含 %d 拍闭环延迟）-> 阈值 %+.2f dB @ %.0f Hz"
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
        Hd = model_response(coef, nfft, delay_samples=d)
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
            written.append((name, sha_fingerprint(alt["coefficients_q20"])))
        print("\n[输出]")
        for name, fp in written:
            print("  %-40s q20 sha256 %s" % (out / name, fp))


if __name__ == "__main__":
    main()
