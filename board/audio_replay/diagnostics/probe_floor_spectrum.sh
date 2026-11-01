#!/bin/bash
# What is the -38 dBFS floor actually made of? DC offset, mains hum, or broadband preamp noise.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
from pathlib import Path

import numpy as np

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
FS = 48828.125
cap = np.load(str(D / 'noise_floor_probe.npz'))
mic = np.asarray(cap['microphone'], float)
n = len(mic)
mean = float(np.mean(mic))
ac = mic - mean
print('frames=%d' % n)
print('DC      = %+.2f dBFS   AC RMS = %+.2f dBFS   (difference says how much is offset)'
      % (20 * np.log10(max(abs(mean), 1e-12)), 20 * np.log10(max(np.sqrt(np.mean(ac ** 2)), 1e-12))))
print('peak    = %+.2f dBFS' % (20 * np.log10(max(np.max(np.abs(mic)), 1e-12))))

S = np.abs(np.fft.rfft(ac)) ** 2
f = np.fft.rfftfreq(n, 1 / FS)
tot = S.sum()
print('--- energy by band ---')
for lo, hi in ((0, 20), (20, 60), (60, 120), (120, 300), (300, 1000), (1000, 5000), (5000, 20000)):
    m = (f >= lo) & (f < hi)
    print('  %5d-%5d Hz  %6.1f %%' % (lo, hi, 100 * S[m].sum() / max(tot, 1e-30)))
print('--- strongest bins below 2 kHz ---')
sub = (f < 2000)
idx = np.argsort(np.where(sub, S, 0))[::-1][:8]
for i in sorted(idx):
    print('  %8.2f Hz   %+.1f dBFS' % (f[i], 10 * np.log10(max(S[i], 1e-30) / n / n)))
PY
