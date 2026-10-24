# -*- coding: utf-8 -*-
"""用 A 的 model_512_strong 在留出 6 段上的残差，算前向陷波的收益（README §4）。"""
import glob
import json

import numpy as np

FS = 48828.125
NFFT = 4096
F = np.arange(NFFT // 2 + 1) * FS / NFFT
DIR = 'D:/Always/QianSai/for_b_lowband'


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


def resp(c):
    pad = np.zeros(NFFT)
    pad[:len(c)] = c
    w = 2 * np.pi * np.arange(NFFT // 2 + 1) / NFFT
    return np.fft.rfft(pad) * np.exp(-1j * w)


def notch(f, f0, d, q=4.0):
    w = f / f0
    x = 1 - w ** 2
    y = w / q
    return np.sqrt(x ** 2 + (y * 10 ** (-d / 40)) ** 2) / np.sqrt(x ** 2 + y ** 2)


files = sorted(glob.glob(DIR + '/seg_*.npz'), key=lambda p: int(p.split('seg_')[1][:-4]))
Hte, cte = est(files[10:])
gate = (cte >= 0.8) & (F >= 300) & (F <= 10250)
model = json.load(open(DIR + '/model_512_strong.json', encoding='utf-8'))
E = np.abs(Hte - resp(np.asarray(model['coefficients'], float)))


def thr(x):
    return -20 * np.log10(x[gate].max()), F[gate][np.argmax(x[gate])]


t, f0 = thr(E)
print('A 模型（留出 6 段）总体阈值 %+.2f dB @ %.0f Hz' % (t, f0))
for lo, hi in ((300, 1000), (1000, 2000), (2000, 3400), (3400, 6000),
               (6000, 8200), (8200, 8600), (8600, 10250)):
    s = gate & (F >= lo) & (F < hi)
    if s.any():
        print('  %5d-%5d  %+6.2f dB @ %5.0f Hz' % (lo, hi, -20 * np.log10(E[s].max()),
                                                   F[s][np.argmax(E[s])]))
print('\n加陷波（Q=4，深 12 dB）：')
for spec in ([(435, 12, 4)],
             [(435, 12, 4), (3898, 12, 4)],
             [(435, 12, 4), (3898, 12, 4), (1585, 12, 4)],
             [(435, 12, 4), (3898, 12, 4), (1585, 12, 4), (9048, 10, 4)]):
    n = np.ones(len(F))
    for a, b, c in spec:
        n *= notch(F, a, b, c)
    tt, ff = thr(E * n)
    print('  %-34s 阈值 %+6.2f dB @ %.0f Hz' % (str([s[0] for s in spec]), tt, ff))
