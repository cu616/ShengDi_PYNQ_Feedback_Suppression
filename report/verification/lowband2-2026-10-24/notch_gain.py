# -*- coding: utf-8 -*-
"""在前向通路里加陷波的收益估算（用 lowband2 测试段的模型残差算）。

陷波放在环路内（对播放信号），作用等价于把该频段的环路增益乘上 |notch(f)|。
"""
import glob
import json

import numpy as np

FS = 48828.125
NFFT = 4096
F = np.arange(NFFT // 2 + 1) * FS / NFFT
DIR = 'D:/Always/QianSai/for_b_lowband'
BANDS = ((300, 1000), (1000, 2000), (2000, 3400), (3400, 6000),
         (6000, 8200), (8200, 8600), (8600, 10250))


def est(paths):
    win = np.hanning(NFFT)
    S = [None] * 3
    for p in paths:
        d = np.load(p)
        r = np.asarray(d['reference'], float)
        m = np.asarray(d['microphone'], float)
        for s in range(0, len(r) - NFFT + 1, NFFT // 2):
            U = np.fft.rfft(r[s:s + NFFT] * win)
            M = np.fft.rfft(m[s:s + NFFT] * win)
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


def notch_mag(f, f0, depth_db, q=4.0):
    """二阶陷波的幅度响应（归一化到直流 1）。"""
    w = f / f0
    x = (1 - w ** 2)
    y = w / q
    mag = np.sqrt(x ** 2 + (y * 10 ** (-depth_db / 40)) ** 2) / np.sqrt(x ** 2 + y ** 2)
    return mag


files = sorted(glob.glob(DIR + '/seg_*.npz'), key=lambda p: int(p.split('seg_')[1][:-4]))
Htr, ctr = est(files[:10])
Hte, cte = est(files[10:])
low = (F >= 300) & (F <= 1000)
h = design(Htr, 512, np.where(low, 20.0, np.where((F >= 300) & (F <= 10250), 1.0, 0.05)))
E = np.abs(Hte - resp(h))
gate = (cte >= 0.8) & (F >= 300) & (F <= 10250)


def threshold(emag, gate_mask):
    return -20 * np.log10(emag[gate_mask].max()), F[gate_mask][np.argmax(emag[gate_mask])]


base, f0 = threshold(E, gate)
print('不加陷波：阈值 %+.2f dB（限制点 %.0f Hz）' % (base, f0))
for lo, hi in BANDS:
    s = gate & (F >= lo) & (F < hi)
    if s.any():
        t, ff = threshold(E, s)
        print('   %5d-%5d  %+6.2f dB @ %5.0f Hz' % (lo, hi, t, ff))

print('\n加陷波后的总体阈值（陷波放在环路内，Q=4）')
for label, spec in (
    ('435 Hz 6 dB', [(435, 6, 4)]),
    ('435 Hz 12 dB', [(435, 12, 4)]),
    ('435+3898 各 12 dB', [(435, 12, 4), (3898, 12, 4)]),
    ('435+3898+8762 各 12 dB', [(435, 12, 4), (3898, 12, 4), (8762, 12, 3)]),
    ('435 12dB Q=8（更窄）', [(435, 12, 8)]),
):
    n = np.ones(len(F))
    for f0_, d, q in spec:
        n *= notch_mag(F, f0_, d, q)
    t, ff = threshold(E * n, gate)
    print('  %-26s 阈值 %+6.2f dB（限制点 %.0f Hz）' % (label, t, ff))
