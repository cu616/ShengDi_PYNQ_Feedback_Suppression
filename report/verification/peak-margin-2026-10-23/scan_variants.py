"""对多个模型算 H-Hat 的环路增益裕度与相位一致阈值（排除 DC/低频与低相干）。

输出：每个模型的最大 |H-Hat|、必要阈值、相位一致阈值（含 2 拍闭环延迟）、振荡频点。
"""
import glob
import json
import os

import numpy as np

SEG_GLOB = 'D:/Always/QianSai/_inbox/2026-10-23_room6/manifest/seg_*.npz'
FS_NOM = 48828.125
NFFT = 4096
FMIN = 300.0


def welch_cross(ref, mic, nfft=NFFT):
    hop = nfft // 2
    win = np.hanning(nfft)
    Sxx = np.zeros(nfft // 2 + 1)
    Syy = np.zeros(nfft // 2 + 1)
    Sxy = np.zeros(nfft // 2 + 1, dtype=complex)
    for start in range(0, len(ref) - nfft + 1, hop):
        X = np.fft.rfft(ref[start:start + nfft] * win)
        Y = np.fft.rfft(mic[start:start + nfft] * win)
        Sxx += (np.conj(X) * X).real
        Syy += (np.conj(Y) * Y).real
        Sxy += np.conj(X) * Y
    return Sxx, Syy, Sxy


def model_resp(coef, nfft=NFFT, delay=1):
    h = np.zeros(nfft)
    h[:len(coef)] = coef
    w = 2 * np.pi * np.arange(nfft // 2 + 1) / nfft
    return np.fft.rfft(h) * np.exp(-1j * delay * w)


def shift_coef(coef, d):
    h = np.asarray(coef, dtype=float)
    out = np.zeros_like(h)
    if d == 0:
        return h.copy()
    if d > 0:
        out[d:] = h[:-d]
    else:
        out[:d] = h[-d:]
    return out


def phase_zero_threshold(E, ph, freqs, fmin=FMIN):
    """返回 (阈值 dB, 频点)。相位在 0 附近穿越处插值 |E|，取最大者。"""
    sel = freqs >= fmin
    e = E[sel]
    p = np.degrees(ph[sel])
    f = freqs[sel]
    # 展开相位，便于找 360 的整数倍穿越
    pu = np.unwrap(np.radians(ph[sel]))
    n = np.round(pu / (2 * np.pi))
    x = pu - n * 2 * np.pi
    best, bestf = 0.0, float('nan')
    for k in range(len(x) - 1):
        if x[k] == 0:
            cand, cf = e[k], f[k]
        elif x[k] * x[k + 1] < 0:
            t = x[k] / (x[k] - x[k + 1])
            cand = e[k] + t * (e[k + 1] - e[k])
            cf = f[k] + t * (f[k + 1] - f[k])
        else:
            continue
        if cand > best:
            best, bestf = cand, cf
    if best <= 0:
        return float('inf'), float('nan')
    return 20 * np.log10(1.0 / best), bestf


def main():
    Sxx = Syy = Sxy = None
    fs = FS_NOM
    for p in sorted(glob.glob(SEG_GLOB)):
        d = np.load(p)
        fs = float(d['sample_rate_hz'])
        a, b, c = welch_cross(d['reference'], d['microphone'])
        Sxx = a if Sxx is None else Sxx + a
        Syy = b if Syy is None else Syy + b
        Sxy = c if Sxy is None else Sxy + c
    H = Sxy / Sxx
    coh = np.abs(Sxy) ** 2 / (Sxx * Syy)
    freqs = np.arange(len(H)) * fs / NFFT
    ok = (coh >= 0.8) & (freqs >= FMIN)
    print('相干>=0.8 且 f>=300Hz 的 bin 数 %d/%d，平均相干 %.3f'
          % (ok.sum(), len(freqs), coh[ok].mean()))
    wm = np.sum(np.abs(H[ok]) ** 2 * Sxx[ok]) / np.sum(Sxx[ok])
    print('宽带 |H|（按参考能量加权）= %+.2f dB' % (10 * np.log10(wm)))

    models = {
        'model_256': 'D:/Always/QianSai/_inbox/2026-10-23_room6/manifest/model_256.json',
        'model_256_pad512': 'D:/Always/QianSai/_inbox/2026-10-23_room6/manifest/model_256_pad.json',
        'model_512': 'D:/Always/QianSai/_inbox/2026-10-23_room6/manifest/model_512.json',
        'cand_room_256_final': 'D:/Always/QianSai/candidate_room_v1_256_final(1)/candidate_room_v1_256_final.json',
        'repo_cand_512': 'models/room_v1/candidate_512.json',
    }
    # 派生变体：用来检查"加载路径只吃到前 256 个系数"这类部署故障
    m512 = json.load(open(models['model_512'], encoding='utf-8'))['coefficients']
    derived = {
        'model_512_trunc256': m512[:256],
        'model_512_tailzero': m512[:256] + [0.0] * 256,
        'model_512_frontpad256': [0.0] * 256 + m512[:256],
    }
    print('\n%-24s %-5s %10s %10s %10s %10s' %
          ('model', 'shift', 'max|E|dB', '必要阈值', '相位阈值', '阈频Hz'))
    for name, coef in derived.items():
        for d in (0,):
            c = shift_coef(coef, d)
            Hh = model_resp(c)
            E = np.abs(H - Hh)
            Eg = np.where(ok, E, 0)
            kmax = int(np.argmax(Eg))
            ph = np.angle(H - Hh) - 2 * 2 * np.pi * freqs / fs
            thr, thrf = phase_zero_threshold(E, ph, freqs)
            print('%-24s %+5d %+10.2f %+10.2f %+10.2f %10.0f'
                  % (name, d, 20 * np.log10(E[kmax]),
                     -20 * np.log10(E[kmax]), thr, thrf))
    print()

    for name, path in models.items():
        if not os.path.exists(path):
            print('missing', path)
            continue
        mod = json.load(open(path, encoding='utf-8'))
        coef = mod['coefficients']
        for d in (0, -1, 1):
            c = shift_coef(coef, d)
            Hh = model_resp(c)
            E = np.abs(H - Hh)
            Eg = np.where(ok, E, 0)
            kmax = int(np.argmax(Eg))
            ph = np.angle(H - Hh) - 2 * 2 * np.pi * freqs / fs  # +2 拍闭环延迟
            thr, thrf = phase_zero_threshold(E, ph, freqs)
            print('%-24s %+5d %+10.2f %+10.2f %+10.2f %10.0f'
                  % (name, d, 20 * np.log10(E[kmax]),
                     -20 * np.log10(E[kmax]), thr, thrf))


def Sxx_gate(freqs, ok):
    return ok


if __name__ == '__main__':
    main()
