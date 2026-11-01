#!/bin/bash
# Answer B's two questions from the recordings that already exist on the board.
#   (a) gain_q12 of each verify arm from run 1 (recal_pkt_20250511-103038/verify_*.npz)
#   (b) |H| and coherence at 322 Hz from the six open-loop segments of that same run
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
PKT = D / 'recal_pkt_20250511-103038'
FS = 48828.125
F322 = 322.0

print('=== (a) verify arms: gain_q12 and flags ===')
for tag in ('open', 'bypass', 'cancel'):
    p = PKT / ('verify_%s.npz' % tag)
    if not p.is_file():
        print('%-7s missing' % tag)
        continue
    cap = np.load(str(p))
    m = json.loads(str(cap['metadata_json']))
    print('%-7s gain_q12=%-5d bypass=%-5s stop=%-10s capture_status=0x%08x mic=%.2f dBFS'
          % (tag, int(m.get('gain_q12') or 0), str(m.get('bypass')), m.get('stop_reason'),
             int(m.get('capture_status') or 0),
             20 * np.log10(max(np.sqrt(np.mean(np.asarray(cap['microphone'], float) ** 2)), 1e-12))))

print('=== (b) open loop: |H| and coherence at 322 Hz, six segments ===')
np_ = 16384
ns = np.hanning(np_)
bin_hz = FS / np_
k322 = int(round(F322 / bin_hz))
freq = k322 * bin_hz
rows = []
for i in range(6):
    p = PKT / ('recal_%02d.npz' % i)
    if not p.is_file():
        print('segment %02d missing' % i)
        continue
    cap = np.load(str(p))
    u = np.asarray(cap['reference'], float)
    mic = np.asarray(cap['microphone'], float)
    n = min(len(u), len(mic))
    U = np.fft.rfft(u[:n] * ns[:n])
    M = np.fft.rfft(mic[:n] * ns[:n])
    H = M[k322] / U[k322]
    # coherence at that single bin from overlapping sub-windows
    sub, step = 2048, 1024
    a, b = [], []
    for s in range(0, n - sub, step):
        w = np.hanning(sub)
        a.append(np.fft.rfft(u[s:s + sub] * w)[int(round(F322 / (FS / sub)))])
        b.append(np.fft.rfft(mic[s:s + sub] * w)[int(round(F322 / (FS / sub)))])
    a, b = np.array(a), np.array(b)
    coh = abs(np.mean(a * np.conj(b))) ** 2 / max(np.mean(abs(a) ** 2) * np.mean(abs(b) ** 2), 1e-30)
    rows.append((i, 20 * np.log10(abs(H)), np.angle(H, deg=True), float(coh)))
    print('seg %02d  |H322|=%.2f dB  phase=%+7.2f deg  coherence=%.3f' % rows[-1])

if rows:
    H_db = np.array([r[1] for r in rows])
    ph = np.array([r[2] for r in rows])
    coh = np.array([r[3] for r in rows])
    print('--- summary ---')
    print('|H322| mean %.2f dB (spread %.2f dB), phase mean %+.2f deg (spread %.2f deg), coherence mean %.3f'
          % (H_db.mean(), np.ptp(H_db), ph.mean(), np.ptp(ph), coh.mean()))
    g = 10 ** (-8.0 / 20.0)
    Hlin = 10 ** (H_db.mean() / 20.0)
    print('g = %.4f, |H| = %.4f, g|H| = %.4f -> in-phase loop boost bound %.2f dB'
          % (g, Hlin, g * Hlin, -20 * np.log10(abs(1 - g * Hlin))))
PY
