#!/bin/bash
# B's three checks: which excitation this really was, whether ref has energy at the 322 Hz bin, and
# whether the microphone itself is notched there (link vs room).
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
PKT = D / 'recal_pkt_20250511-110729'
FS = 48828.125
F0 = 322.0

cap = np.load(str(PKT / 'recal_00.npz'))
meta = json.loads(str(cap['metadata_json']))
ref = np.asarray(cap['reference'], float)
mic = np.asarray(cap['microphone'], float)
n = len(ref)
R = np.fft.rfft(ref)
M = np.fft.rfft(mic)
f = np.fft.rfftfreq(n, 1 / FS)
k = int(round(F0 * n / FS))
bin_hz = FS / n
print('window %d frames, bin %.3f Hz, k322=%d -> %.2f Hz' % (n, bin_hz, k, k * bin_hz))
print('pll_readback:', meta.get('pll_readback'))
print('gain_q12:', meta.get('gain_q12'), 'bypass:', meta.get('bypass'),
      'zero_coeff:', meta.get('zero_coeff'), 'codec(hp_volume):', meta.get('hp_volume'))

print('=== check 1: what excitation is this? strongest ref bins ===')
mag = np.abs(R) ** 2
order = np.argsort(mag)[::-1][:14]
print('  top bins:', ', '.join('%.1f Hz' % f[i] for i in sorted(order)))

print('=== check 2: ref at 322 Hz vs +-20 bin neighbourhood ===')
rel = 10 * np.log10(mag[k] / max(np.median(mag[k - 20:k + 21]), 1e-30))
print('  ref[k322] - median(neighbourhood) = %+.2f dB   (B calibration batch: +4.60 dB)' % rel)

print('=== check 3: mic at 322 Hz vs the 300-460 Hz neighbourhood ===')
band = (f >= 300) & (f <= 460)
mk = 10 * np.log10((np.abs(M[k]) ** 2) / max(np.median(np.abs(M[band]) ** 2), 1e-30))
print('  mic[k322] - median(300-460 Hz) = %+.2f dB' % mk)
rk = 10 * np.log10((np.abs(R[k]) ** 2) / max(np.median(np.abs(R[band]) ** 2), 1e-30))
print('  ref[k322] - median(300-460 Hz) = %+.2f dB' % rk)

print('=== mic spectrum shape near 322 Hz (dB relative to its own 300-460 median) ===')
for lo, hi in ((250, 290), (290, 310), (310, 320), (320, 326), (326, 340), (340, 400), (400, 460)):
    m = (f >= lo) & (f < hi)
    print('  %3d-%3d Hz  mic %+6.2f dB   ref %+6.2f dB'
          % (lo, hi, 10 * np.log10(np.mean(np.abs(M[m]) ** 2) / max(np.median(np.abs(M[band]) ** 2), 1e-30)),
             10 * np.log10(np.mean(np.abs(R[m]) ** 2) / max(np.median(np.abs(R[band]) ** 2), 1e-30))))
PY
