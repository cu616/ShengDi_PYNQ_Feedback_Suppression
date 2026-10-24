# -*- coding: utf-8 -*-
"""交叉验证：300-1000 Hz 的残差在 512/680 抽头下到底能做到多少。

训练 = seg_0..2，测试 = seg_3..5，彼此独立。
测试集残差才是可交付的精度；训练集残差会偏低（拟合噪声）。
"""
import glob

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


def design(target, taps, w):
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(F, k + 1) / FS) * w[:, None]
    M = np.vstack([A.real, A.imag])
    b = np.concatenate([(target * w).real, (target * w).imag])
    G = M.T @ M
    G += np.eye(taps) * np.trace(G) * 1e-10
    return np.linalg.solve(G, M.T @ b)


def resp(h):
    pad = np.zeros(NFFT)
    pad[:len(h)] = h
    w = 2 * np.pi * np.arange(NFFT // 2 + 1) / NFFT
    return np.fft.rfft(pad) * np.exp(-1j * w)


files = sorted(glob.glob('D:/Always/QianSai/manifest/seg_*.npz'))
Htr, ctr = estimate_H(files[:3])
Hte, cte = estimate_H(files[3:])
band = (F >= 300) & (F <= 1000)

print('训练集 300-1000 平均相干 %.2f，测试集 %.2f' % (ctr[band].mean(), cte[band].mean()))
print('两批 H 本身的差（会话内重复性）：带内 max|H_tr - H_te| = %+.2f dB'
      % (20 * np.log10(np.abs(Htr - Hte)[band].max())))

print('\n%-20s %-6s %8s %8s %8s' % ('加权', 'taps', '训练|E|', '测试|E|', '测试频点'))
for label, w in (('带内加权', np.where(band, 1.0, 0.05)),
                 ('全带等权', np.ones(len(F))),
                 ('带内加权+限带', np.where(band, 1.0, 0.0))):
    for taps in (256, 512, 680):
        h = design(Htr, taps, w)
        Etr = np.abs(Htr - resp(h))
        Ete = np.abs(Hte - resp(h))
        print('%-20s %-6d %+8.2f %+8.2f %8.0f'
              % (label, taps, 20 * np.log10(Etr[band].max()),
                 20 * np.log10(Ete[band].max()),
                 F[band][np.argmax(Ete[band])]))

# 参考：直接用测试集的 H 当模型（"完美拟合"的上界），看数据本身能把残差压到多低
print('\n参照：把测试集 H 本身当模型时的训练集残差（跨批不一致性下限）%+.2f dB'
      % (20 * np.log10(np.abs(Htr - Hte)[band].max())))
