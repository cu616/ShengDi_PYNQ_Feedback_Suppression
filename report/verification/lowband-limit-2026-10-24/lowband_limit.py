# -*- coding: utf-8 -*-
"""低频段 300-1000 Hz 的可达残差上限：模态结构 + 抽头数扫描。"""
import glob

import numpy as np

FS = 48828.125
NFFT = 4096


def estimate_H(paths):
    win = np.hanning(NFFT)
    S_uu = S_mm = S_um = None
    for p in paths:
        d = np.load(p)
        ref = np.asarray(d['reference'], float)
        mic = np.asarray(d['microphone'], float)
        for s in range(0, len(ref) - NFFT + 1, NFFT // 2):
            U = np.fft.rfft(ref[s:s + NFFT] * win)
            M = np.fft.rfft(mic[s:s + NFFT] * win)
            a, b, c = (np.conj(U) * U).real, (np.conj(M) * M).real, np.conj(U) * M
            S_uu = a if S_uu is None else S_uu + a
            S_mm = b if S_mm is None else S_mm + b
            S_um = c if S_um is None else S_um + c
    return S_um / S_uu, np.abs(S_um) ** 2 / (S_uu * S_mm)


def design(target, freqs, taps, w):
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(freqs, k + 1) / FS) * w[:, None]
    M = np.vstack([A.real, A.imag])
    b = np.concatenate([(target * w).real, (target * w).imag])
    G = M.T @ M + np.eye(taps) * np.trace(M.T @ M) * 1e-10
    return np.linalg.solve(G, M.T @ b)


def resp(h):
    pad = np.zeros(NFFT)
    pad[:len(h)] = h
    w = 2 * np.pi * np.arange(NFFT // 2 + 1) / NFFT
    return np.fft.rfft(pad) * np.exp(-1j * w)


H, coh = estimate_H(sorted(glob.glob('D:/Always/QianSai/_inbox/2026-10-23_room6/manifest/seg_*.npz')))
f = np.arange(len(H)) * FS / NFFT
mag = np.abs(H)

print('=== 300-1000 Hz 明细（每 2 个 bin 一点）')
sel = (f >= 300) & (f <= 1050)
idx = np.where(sel)[0]
for k in idx[::2]:
    bar = '#' * int(max(0, 20 * np.log10(mag[k]) + 8) * 2)
    print('  %5.0f Hz  %+6.2f dB  coh %.2f  %s' % (f[k], 20 * np.log10(mag[k]), coh[k], bar))

band = (f >= 300) & (f <= 1000)
kpk = np.argmax(np.where(band, mag, 0))
print('\n带内峰 %+.2f dB @ %.0f Hz，相干 %.3f' % (20 * np.log10(mag[kpk]), f[kpk], coh[kpk]))
peak = mag[kpk]
# 半高宽
half = peak / np.sqrt(2)
lo = kpk
while lo > 0 and mag[lo] > half:
    lo -= 1
hi = kpk
while hi < len(mag) - 1 and mag[hi] > half:
    hi += 1
width = f[hi] - f[lo]
print('  -3 dB 宽 %.1f Hz -> Q ≈ %.1f' % (width, f[kpk] / max(width, 1e-9)))

print('\n=== 抽头数扫描（300-1000 加权拟合，看带内可达残差）')
for taps in (128, 256, 512, 680, 1024, 2048):
    w = np.where(band, 1.0, 0.05)
    h = design(H, f, taps, w)
    E = np.abs(H - resp(h))
    e_in = 20 * np.log10(E[band].max())
    e_all = 20 * np.log10(E[(f >= 300) & (f <= 10000)].max())
    print('  taps %4d  in-band max|E| %+6.2f dB @ %4.0f Hz   (300-10k 最大 %+6.2f dB)'
          % (taps, e_in, f[band][np.argmax(E[band])], e_all))

print('\n=== 相干对应的估计误差下限（H1 偏差）')
print('  300-1000 平均相干 %.3f -> |H_hat|≈γ²|H|，偏差 %.2f dB'
      % (coh[band].mean(), 20 * np.log10(coh[band].mean())))
