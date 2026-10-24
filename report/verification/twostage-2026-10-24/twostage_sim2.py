# -*- coding: utf-8 -*-
"""两级预测器仿真（修正版）：512 全速 FIR + 8x 抽取域低频 FIR。

延时预算（关键）：
  抽取器与内插器各 DELAY 个全速样本（线性相位对称 FIR 的群延时 (N-1)/2）。
  内插输出 y_full[n] 对应 y_d[(n-2*DELAY)/8]，所以二级 FIR 要在 y_d[m] 上预测 e1[8m+2*DELAY]。
  可行性要求 2*DELAY < 声学延时（本夹具 ~125 样本），否则等于要求预测未来。
"""
import glob
import json
import sys

import numpy as np

FS = 48828.125
DEC = 8
FSD = FS / DEC
NPROTO = 65
DELAY = (NPROTO - 1) // 2          # 32
TOTAL_DELAY = 2 * DELAY            # 64 全速样本
DIR = 'D:/Always/QianSai/_inbox/2026-10-24_lowband2/for_b_lowband'
BANDS = ((300, 1000), (1000, 2000), (2000, 3400), (3400, 6000),
         (6000, 8200), (8200, 8600), (8600, 10250))


def lowpass(n, fc):
    m = np.arange(n) - (n - 1) / 2
    h = 2 * (fc / FS) * np.sinc(2 * (fc / FS) * m) * np.kaiser(n, 8.0)
    return h / h.sum()


def decimate(x, f):
    y = np.convolve(x, f, mode='full')
    return y[DELAY::DEC]


def interpolate(y, f):
    up = np.zeros(len(y) * DEC)
    up[::DEC] = y
    return np.convolve(up, f, mode='full')


def load_um(paths):
    us, ms = [], []
    for p in paths:
        d = np.load(p)
        us.append(np.asarray(d['reference'], float))
        ms.append(np.asarray(d['microphone'], float))
    return np.concatenate(us), np.concatenate(ms)


def fit_fir(u, y, taps, ridge=1e-8):
    X = np.lib.stride_tricks.sliding_window_view(u, taps)[:-1, ::-1]
    t = y[taps:]
    G = X.T @ X
    G += np.eye(taps) * np.trace(G) * ridge
    return np.linalg.solve(G, X.T @ t)


def apply_fir(u, h):
    out = np.zeros(len(u))
    out[1:] = np.convolve(u, h, mode='full')[:len(u) - 1]
    return out


def band_thresholds(u, resid, mic=None, coh_gate=True):
    nfft = 4096
    win = np.hanning(nfft)
    S = [None] * 3
    for s in range(0, len(u) - nfft + 1, nfft // 2):
        U = np.fft.rfft(u[s:s + nfft] * win)
        R = np.fft.rfft(resid[s:s + nfft] * win)
        acc = [(np.conj(U) * U).real, (np.conj(R) * R).real, np.conj(U) * R]
        S = [b if a is None else a + b for a, b in zip(S, acc)]
    Suu, Srr, Sur = S
    E = np.abs(Sur) / Suu
    F = np.arange(len(E)) * FS / nfft
    gate = (F >= 300) & (F <= 10250)
    if coh_gate and mic is not None:
        win2 = np.hanning(nfft)
        A = B = C = None
        for s2 in range(0, len(u) - nfft + 1, nfft // 2):
            U2 = np.fft.rfft(u[s2:s2 + nfft] * win2)
            M2 = np.fft.rfft(mic[s2:s2 + nfft] * win2)
            x = (np.conj(U2) * U2).real
            y = (np.conj(M2) * M2).real
            z = np.conj(U2) * M2
            A = x if A is None else A + x
            B = y if B is None else B + y
            C = z if C is None else C + z
        coh = np.abs(C) ** 2 / (A * B)
        gate = gate & (coh >= 0.8)
    out = {'all': (-20 * np.log10(E[gate].max()), float(F[gate][np.argmax(E[gate])]))}
    for lo, hi in BANDS:
        s = gate & (F >= lo) & (F < hi)
        if s.any():
            out[(lo, hi)] = (-20 * np.log10(E[s].max()), float(F[s][np.argmax(E[s])]))
    return out


def main():
    files = sorted(glob.glob(DIR + '/seg_*.npz'), key=lambda p: int(p.split('seg_')[1][:-4]))
    tr, te = files[:10], files[10:]
    u_tr, m_tr = load_um(tr)
    u_te, m_te = load_um(te)
    f = lowpass(NPROTO, 1300.0)
    print('原型 %d 抽头，单次延时 %d 样本，两级固定延时 %d 样本（%.2f ms）；声学延时约 125 样本'
          % (NPROTO, DELAY, TOTAL_DELAY, TOTAL_DELAY / FS * 1e3))
    print('剩余可给二级 FIR 的提前量：%d 样本 = %d 个抽取样本'
          % (125 - TOTAL_DELAY, (125 - TOTAL_DELAY) // DEC))

    h1 = fit_fir(u_tr, m_tr, 512)
    e1_tr = m_tr - apply_fir(u_tr, h1)
    e1_te = m_te - apply_fir(u_te, h1)
    print('\n一级 512（全速）：')
    base = band_thresholds(u_te, e1_te, m_te)
    for k, v in base.items():
        print('   %-12s %+6.2f dB @ %5.0f Hz' % (str(k), v[0], v[1]))

    u_d_tr = decimate(u_tr, f)
    u_d_te = decimate(u_te, f)
    # 目标：y_d[m] 预测 e1[8m + TOTAL_DELAY]
    tgt_tr = e1_tr[TOTAL_DELAY::DEC]
    for taps2 in (256, 384, 512):
        n = min(len(u_d_tr) - taps2 - 1, len(tgt_tr) - taps2 - 1)
        X = np.lib.stride_tricks.sliding_window_view(u_d_tr, taps2)[:-1, ::-1][:n]
        G = X.T @ X
        G += np.eye(taps2) * np.trace(G) * 1e-8
        h2 = np.linalg.solve(G, X.T @ tgt_tr[taps2 + 1:taps2 + 1 + n])
        insample = tgt_tr[taps2 + 1:taps2 + 1 + n] - X @ h2
        corr = interpolate(apply_fir(u_d_te, h2), f)
        e2 = e1_te - corr[TOTAL_DELAY:TOTAL_DELAY + len(e1_te)]
        print('\n二级 %d 抽头 @ %.1f Hz（等效 %.0f ms 记忆）：'
              % (taps2, FSD, taps2 / FSD * 1e3))
        print('   训练集上二级把低频残差再压 %.2f dB'
              % (20 * np.log10(np.sqrt((tgt_tr[taps2 + 1:taps2 + 1 + n] ** 2).mean())
                               / np.sqrt((insample ** 2).mean()))))
        two = band_thresholds(u_te, e2, m_te)
        for k, v in two.items():
            d = v[0] - base[k][0]
            print('   %-12s %+6.2f dB @ %5.0f Hz   (%+0.2f vs 一级)'
                  % (str(k), v[0], v[1], d))


if __name__ == '__main__':
    main()
