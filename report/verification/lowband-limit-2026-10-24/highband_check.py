# -*- coding: utf-8 -*-
"""补两个数：8.6-10.2k 是否才是限制点；以及低频残差随抽头数的交叉验证趋势。"""
import glob
import json

import numpy as np

FS = 48828.125
NFFT = 4096
F = np.arange(NFFT // 2 + 1) * FS / NFFT


def estimate_H(paths):
    win = np.hanning(NFFT)
    S = [None, None, None]
    for p in paths:
        d = np.load(p)
        ref = np.asarray(d['reference'], float)
        mic = np.asarray(d['microphone'], float)
        for s in range(0, len(ref) - NFFT + 1, NFFT // 2):
            U = np.fft.rfft(ref[s:s + NFFT] * win)
            M = np.fft.rfft(mic[s:s + NFFT] * win)
            acc = [(np.conj(U) * U).real, (np.conj(M) * M).real, np.conj(U) * M]
            S = [b if a is None else a + b for a, b in zip(S, acc)]
    return S[2] / S[0], np.abs(S[2]) ** 2 / (S[0] * S[1])


def resp(coef):
    pad = np.zeros(NFFT)
    pad[:len(coef)] = coef
    w = 2 * np.pi * np.arange(NFFT // 2 + 1) / NFFT
    return np.fft.rfft(pad) * np.exp(-1j * w)


def design(target, taps, w):
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(F, k + 1) / FS) * w[:, None]
    M = np.vstack([A.real, A.imag])
    b = np.concatenate([(target * w).real, (target * w).imag])
    G = M.T @ M
    G += np.eye(taps) * np.trace(G) * 1e-9
    return np.linalg.solve(G, M.T @ b)


files = sorted(glob.glob('D:/Always/QianSai/manifest/seg_*.npz'))
H, coh = estimate_H(files)
gate = (coh >= 0.8) & (F >= 300) & (F <= 10250)

print('=== 按频段看部署模型的 max|H-Hhat|（相干门控 0.8）')
m = json.load(open('models/room_v1/candidate_512.json', encoding='utf-8'))
E = np.abs(H - resp(np.asarray(m['coefficients'], float)))
for lo, hi in ((300, 1000), (1000, 2000), (2000, 3400), (3400, 6000),
               (6000, 8200), (8200, 8600), (8600, 10250)):
    s = gate & (F >= lo) & (F < hi)
    if not s.any():
        print('  %5d-%5d  无相干部' % (lo, hi))
        continue
    k = int(np.argmax(E[s]))
    ff = F[s][k]
    print('  %5d-%5d  max|E| %+6.2f dB @ %5.0f Hz  (|H| %+5.2f, coh %.2f, 阈值 %+5.2f)'
          % (lo, hi, 20 * np.log10(E[s][k]), ff,
             20 * np.log10(np.abs(H[s][k])), coh[s][k], -20 * np.log10(E[s][k])))

print('\n=== 低频残差的交叉验证趋势（训练 seg0-2 / 测试 seg3-5）')
Htr, ctr = estimate_H(files[:3])
Hte, cte = estimate_H(files[3:])
band = (F >= 300) & (F <= 1000)
for taps in (512, 680, 1024, 2048):
    w = np.where(band, 1.0, 0.02)
    h = design(Htr, taps, w)
    print('  taps %4d  训练 %+6.2f dB  测试 %+6.2f dB'
          % (taps, 20 * np.log10(np.abs(Htr - resp(h))[band].max()),
             20 * np.log10(np.abs(Hte - resp(h))[band].max())))
print('  两批 H 自身差 %+6.2f dB（同一批内重复性下限）'
      % (20 * np.log10(np.abs(Htr - Hte)[band].max())))
