# -*- coding: utf-8 -*-
"""在 lowband2 的 16 段上做交叉验证：512 抽头在 300-1000 Hz 到底能到多少。

训练 seg_0..9，测试 seg_10..15（与 A 的划分一致）。
对比：A 的 model_512_strong  vs  低频加权重拟合。
"""
import glob
import json

import numpy as np

FS = 48828.125
NFFT = 4096
F = np.arange(NFFT // 2 + 1) * FS / NFFT
DIR = 'D:/Always/QianSai/_inbox/2026-10-24_lowband2/for_b_lowband'

BANDS = ((300, 1000), (1000, 2000), (2000, 3400), (3400, 6000),
         (6000, 8200), (8200, 8600), (8600, 10250))


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


def design(target, taps, w, ridge=1e-9):
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(F, k + 1) / FS) * w[:, None]
    M = np.vstack([A.real, A.imag])
    b = np.concatenate([(target * w).real, (target * w).imag])
    G = M.T @ M
    G += np.eye(taps) * np.trace(G) * ridge
    return np.linalg.solve(G, M.T @ b)


files = sorted(glob.glob(DIR + '/seg_*.npz'), key=lambda p: int(p.split('seg_')[1][:-4]))
tr, te = files[:10], files[10:]
Htr, ctr = estimate_H(tr)
Hte, cte = estimate_H(te)
gate_tr = (ctr >= 0.8) & (F >= 300) & (F <= 10250)
gate_te = (cte >= 0.8) & (F >= 300) & (F <= 10250)

print('训练 %d 段 / 测试 %d 段；相干(300-1000) 训练 %.2f 测试 %.2f'
      % (len(tr), len(te), ctr[(F >= 300) & (F < 1000)].mean(),
         cte[(F >= 300) & (F < 1000)].mean()))
print('两批 H 自身差（300-1000）%+.2f dB；全带 %+.2f dB'
      % (20 * np.log10(np.abs(Htr - Hte)[(F >= 300) & (F < 1000)].max()),
         20 * np.log10(np.abs(Htr - Hte)[(F >= 300) & (F <= 10250)].max())))

strong = json.load(open(DIR + '/model_512_strong.json', encoding='utf-8'))
print('\nA 的 model_512_strong：taps=%d' % len(strong['coefficients']))
E = np.abs(Hte - resp(np.asarray(strong['coefficients'], float)))
print('  在测试段上的分带 max|E|：')
for lo, hi in BANDS:
    s = gate_te & (F >= lo) & (F < hi)
    if s.any():
        print('    %5d-%5d  %+6.2f dB @ %5.0f Hz' % (lo, hi, 20 * np.log10(E[s].max()),
                                                     F[s][np.argmax(E[s])]))

print('\n=== 重拟合（训练集 10 段）在测试集上的表现')
lowband = (F >= 300) & (F <= 1000)
print('%-26s %8s %8s %8s %8s' % ('加权方案', 'taps', '训练低频', '测试低频', '测试全带'))
for label, w in (
    ('全带等权', np.ones(len(F))),
    ('低频 x5', np.where(lowband, 5.0, 1.0)),
    ('低频 x20', np.where(lowband, 20.0, 1.0)),
    ('低频 x20 + 带外 0.05', np.where(lowband, 20.0, np.where((F >= 300) & (F <= 10250), 1.0, 0.05))),
):
    for taps in (512,):
        h = design(Htr, taps, w)
        Etr = np.abs(Htr - resp(h))
        Ete = np.abs(Hte - resp(h))
        print('%-26s %8d %+8.2f %+8.2f %+8.2f'
              % (label, taps, 20 * np.log10(Etr[lowband].max()),
                 20 * np.log10(Ete[lowband].max()),
                 20 * np.log10(Ete[gate_te].max())))

print('\n=== 435-460 Hz 附近逐点（测试集，A 的模型 vs 低频 x20）')
h20 = design(Htr, 512, np.where(lowband, 20.0, 1.0))
E20 = np.abs(Hte - resp(h20))
sel = gate_te & (F >= 400) & (F <= 520)
for k in np.where(sel)[0][::2]:
    print('  %5.0f Hz |H| %+5.2f  A模型|E| %+6.2f  加权重拟合|E| %+6.2f'
          % (F[k], 20 * np.log10(np.abs(Hte[k])), 20 * np.log10(E[k]),
             20 * np.log10(E20[k])))
