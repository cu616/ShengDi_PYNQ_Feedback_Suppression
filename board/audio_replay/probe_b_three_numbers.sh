#!/bin/bash
# B's decisive measurement: ref RMS, mic RMS, and the frequency-domain |H(322)| directly from the
# captures (no fitter involved), then compare against the 322 Hz response of the fitted model.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
PKT = D / 'recal_pkt_20250511-110729'          # the -19.3 dBFS run
FS = 48828.125
F0 = 322.0


def db(x):
    return 20 * np.log10(max(float(x), 1e-12))


print('=== per-segment RMS and direct frequency-domain H(322) ===')
rows = []
for i in range(6):
    p = PKT / ('recal_%02d.npz' % i)
    if not p.is_file():
        print('missing', p.name)
        continue
    cap = np.load(str(p))
    meta = json.loads(str(cap['metadata_json']))
    ref = np.asarray(cap['reference'], float)
    mic = np.asarray(cap['microphone'], float)
    n = min(len(ref), len(mic))
    ref, mic = ref[:n], mic[:n]
    ref_rms, mic_rms = float(np.sqrt(np.mean(ref ** 2))), float(np.sqrt(np.mean(mic ** 2)))
    R = np.fft.rfft(ref)
    M = np.fft.rfft(mic)
    k = int(round(F0 * n / FS))
    H1 = np.mean(M * np.conj(R)) / max(np.mean(np.abs(R) ** 2), 1e-30)   # B's estimator
    rows.append((i, db(ref_rms), db(mic_rms), db(mic_rms) - db(ref_rms),
                 db(abs(H1)), int(meta.get('first_frame') or -1)))
    print('seg %02d  ref=%7.2f dBFS  mic=%7.2f dBFS  ratio=%+6.2f dB  |H322|=%+6.2f dB  first_frame=%d'
          % rows[-1])

if rows:
    a = np.array([[r[1], r[2], r[3], r[4]] for r in rows])
    print('--- mean ---')
    print('ref %.2f dBFS  mic %.2f dBFS  mic/ref %+.2f dB  |H322| %+.2f dB (spread %.2f dB)'
          % (a[:, 0].mean(), a[:, 1].mean(), a[:, 2].mean(), a[:, 3].mean(), np.ptp(a[:, 3])))
    print('first_frame per segment:', [r[5] for r in rows])

print('=== the fitted model response at 322 Hz ===')
for name in ('model_candidate_20250511-110729.rejected.json',
             'rewired_512_20261026.json'):
    p = D / name
    if not p.is_file():
        print('missing', name)
        continue
    m = json.loads(p.read_text(encoding='utf-8'))
    h = np.asarray(m.get('coefficients_q20') or m.get('coefficients'), float) / float(1 << 20)
    k = np.arange(len(h))
    resp = complex(np.sum(h * np.exp(-2j * np.pi * F0 * (k + 1) / FS)))
    print('%-46s taps=%d  |H322|=%.2f dB   max|h|(linear)=%.4f  L1(linear)=%.2f'
          % (name, len(h), db(abs(resp)), float(np.max(np.abs(h))), float(np.sum(np.abs(h)))))
PY
