#!/bin/bash
# (1) |H| for bins k=105..112 on the multitone capture, to confirm which bin was measured.
# (2) After the white-noise rerun: the five numbers B wants, computed offline.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
FS = 48828.125
import os
mode = 'table' if os.environ.get('PROBE_TABLE') else 'numbers'

if mode == 'table':
    PKT = D / 'recal_pkt_20250511-110729'
    cap = np.load(str(PKT / 'recal_00.npz'))
    ref = np.asarray(cap['reference'], float)
    mic = np.asarray(cap['microphone'], float)
    n = len(ref)
    R = np.fft.rfft(ref)
    M = np.fft.rfft(mic)
    print('=== k=105..112 |H| on the MULTITONE capture (bin %.3f Hz) ===' % (FS / n))
    for k in range(105, 113):
        H = M[k] / R[k] if abs(R[k]) > 0 else complex(0)
        print('k=%3d  %8.2f Hz  |H|=%+7.2f dB   ref line level %+7.2f dBFS'
              % (k, k * FS / n, 20 * np.log10(max(abs(H), 1e-12)),
                 20 * np.log10(max(abs(R[k]), 1e-12))))
else:
    pkts = sorted([p for p in D.glob('recal_pkt_*') if p.is_dir()], key=lambda p: p.stat().st_mtime)
    PKT = pkts[-1]
    print('=== five numbers on', PKT.name, '===')
    caps = sorted(PKT.glob('recal_*.npz'))
    c0 = np.load(str(caps[0]))
    ref = np.asarray(c0['reference'], float)
    mic = np.asarray(c0['microphone'], float)
    n = len(ref)
    print('ref_rms  = %+7.2f dBFS   (target -19.3)' % (20 * np.log10(max(np.sqrt(np.mean(ref ** 2)), 1e-12))))
    print('mic_rms  = %+7.2f dBFS   mic/ref = %+6.2f dB'
          % (20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12)),
             20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12))
             - 20 * np.log10(max(np.sqrt(np.mean(ref ** 2)), 1e-12))))

    N = n
    cc = np.abs(np.fft.irfft(np.fft.rfft(mic) * np.conj(np.fft.rfft(ref)), 2 * N))[:N]
    kk = int(np.argmax(cc))
    main = cc[kk]
    sec = float(np.max(np.r_[cc[:max(0, kk - 4)], cc[kk + 5:]]))
    w, j = 1, kk - 1
    while j >= 0 and cc[j] > main / 2:
        w += 1
        j -= 1
    j = kk + 1
    while j < N and cc[j] > main / 2:
        w += 1
        j += 1
    print('estimate_lag = %d  (expect 184 +-2)   sec/main = %.3f (expect ~0.58)   FWHM = %d frames (expect ~8)'
          % (kk, sec / max(main, 1e-30), w))

    R = np.fft.rfft(ref)
    M = np.fft.rfft(mic)
    k322 = int(round(322.0 * n / FS))
    H322 = M[k322] / R[k322] if abs(R[k322]) > 0 else complex(0)
    print('|H(322)| k=%d = %+.2f dB   (expect +5.4 +-2)' % (k322, 20 * np.log10(max(abs(H322), 1e-12))))

    p = PKT / 'recalibration_receipt.json'
    if p.is_file():
        r = json.loads(p.read_text(encoding='utf-8'))
        print('receipt: verdict=%s fit_rc=%s L1n/a q20_sha=%s frac_spread=%s arms=%d'
              % (r.get('verdict'), r.get('fit_returncode'), str(r.get('q20_sha256'))[:12],
                 r.get('fractional_spread'), len(r.get('arms') or [])))
        tp = r.get('three_point')
        if tp:
            print('three-point: CD=%.2f loop_boost=%.2f acoustic_diff=%.2f overshoot=%.2f'
                  % (tp['cd_322_db'], tp['loop_boost_db'], tp['acoustic_difference_db'],
                     tp['overshoot_db']))
PY
