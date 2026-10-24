# -*- coding: utf-8 -*-
"""抽头数与训练/测试划分的稳健性：512 vs 680 vs 1024，三种划分。

结论（README §4）：680 只在前 10/后 6 的划分上给出 +3.8 dB，另两种划分没有；
限制点在 441 Hz 与 8.3–8.4 kHz 之间随划分跳变。
"""
import glob

import numpy as np

FS = 48828.125
NFFT = 4096
F = np.arange(NFFT // 2 + 1) * FS / NFFT
DIR = 'D:/Always/QianSai/_inbox/2026-10-24_lowband2/for_b_lowband'


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


def design(Htr, taps):
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(F, k + 1) / FS)
    M = np.vstack([A.real, A.imag])
    b = np.concatenate([Htr.real, Htr.imag])
    G = M.T @ M
    G += np.eye(taps) * np.trace(G) * 1e-9
    return np.linalg.solve(G, M.T @ b)


def resp(c):
    pad = np.zeros(NFFT)
    pad[:len(c)] = c
    w = 2 * np.pi * np.arange(NFFT // 2 + 1) / NFFT
    return np.fft.rfft(pad) * np.exp(-1j * w)


files = sorted(glob.glob(DIR + '/seg_*.npz'), key=lambda p: int(p.split('seg_')[1][:-4]))
for split in ('前10/后6', '前6/后10', '奇偶'):
    if split == '前10/后6':
        tr, te = files[:10], files[10:]
    elif split == '前6/后10':
        tr, te = files[:6], files[6:]
    else:
        tr, te = files[0::2], files[1::2]
    Htr, ctr = est(tr)
    Hte, cte = est(te)
    ev = (cte >= 0.8) & (F >= 300) & (F <= 10250)
    row = []
    for taps in (512, 680, 1024):
        h = design(Htr, taps)
        E = np.abs(Hte - resp(h))
        row.append('%d: %+6.2f @%4.0f' % (taps, -20 * np.log10(E[ev].max()), F[ev][np.argmax(E[ev])]))
    print('%-10s 评估 bin %3d  ' % (split, ev.sum()) + '  |  '.join(row))
