#!/bin/bash
# Played-output level per arm, measured on the SOURCE-ACTIVE window only.
#
# C 2026-10-28: the alternating run used a 2 s source but a 2.4 s run, so the last ~0.36 s carries
# no source. Averaging the whole capture therefore mixed source-active samples with a silent tail and
# understated the level. This report restricts the RMS to the frames that actually carried injection,
# excludes the gate run from the arm statistics, and prints the mean over the four arms as well as
# the same-condition scatter, which is what decides whether the difference is resolvable.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import glob
import json

import numpy as np

RATE = 48828.125
rows = []
for path in sorted(glob.glob('/home/xilinx/jupyter_notebooks/base/audio/audio_wide/alt_*.npz')):
    name = path.split('/')[-1]
    data = np.load(path)
    meta = json.loads(str(data['metadata_json']))
    played = np.asarray(data['reference'], dtype=np.float64)
    mic = np.asarray(data['microphone'], dtype=np.float64)
    # The alternating run injected a KNOWN 2.0 s source. These captures do not store the source
    # array, so the window is taken from that known duration rather than from a stored array.
    # (C 2026-10-28: the 2.4 s capture contains ~0.36 s with no source; averaging it in understates
    # the level, so it is excluded.)
    # The driver saves the LAST 16384 frames of the ring (0.336 s). A 2.4 s run with a 2.0 s source
    # therefore saves a window that starts at 2.064 s, i.e. entirely AFTER the source ended.
    # C 2026-10-28: that is why -42..-47 dBFS cannot be quoted as "the played output is too quiet".
    src_frames = int(round(2.0 * RATE))
    completed = int(meta.get('completed_frames') or len(played))
    capture_start = completed - len(played)
    active = max(0, min(len(played), src_frames - capture_start))
    seg = slice(0, active) if active else slice(0, len(played))
    rms = 20 * np.log10(max(float(np.sqrt(np.mean(played[seg] ** 2))), 1e-12))
    peak = 20 * np.log10(max(float(np.max(np.abs(played[seg]))), 1e-12))
    mrms = 20 * np.log10(max(float(np.sqrt(np.mean(mic[seg] ** 2))), 1e-12))
    rows.append(dict(name=name, zero=meta.get('zero_coeff'), rms=rms, peak=peak, mrms=mrms,
                     active=active, total=len(played), stop=meta.get('stop_reason'), gate=name.startswith('alt_gate')))

print('%-36s %-5s %8s %8s %8s %9s %s'
      % ('file', 'zero', 'played', 'p_peak', 'mic', 'src_frames', 'stop'))
for r in rows:
    print('%-36s %-5s %8.2f %8.2f %8.2f %9d %s'
          % (r['name'], r['zero'], r['rms'], r['peak'], r['mrms'], r['active'], r['stop']))

arms = [r for r in rows if not r['gate']]
z = [r for r in arms if r['zero']]
c = [r for r in arms if not r['zero']]
if z and c:
    zs = sum(r['rms'] for r in z) / len(z)
    cs = sum(r['rms'] for r in c) / len(c)
    zp = sum(r['peak'] for r in z) / len(z)
    cp = sum(r['peak'] for r in c) / len(c)
    print('PLAYED_MEAN zero %.2f dBFS (n=%d)  candidate %.2f dBFS (n=%d)  difference %+.2f dB rms, %+.2f dB peak'
          % (zs, len(z), cs, len(c), zs - cs, zp - cp))
    if len(z) > 1 and len(c) > 1:
        zsc = max(r['rms'] for r in z) - min(r['rms'] for r in z)
        csc = max(r['rms'] for r in c) - min(r['rms'] for r in c)
        print('SAME_CONDITION_SCATTER zero %.2f dB, candidate %.2f dB -> the arm difference is %s'
              % (zsc, csc, 'smaller than same-condition scatter (NOT resolvable)'
                 if abs(zs - cs) < max(zsc, csc) else 'larger than same-condition scatter'))
if all(r['active'] == 0 for r in rows):
    print('MEASUREMENT_INVALID: the saved window starts after the source ended, so it contains no '
          'program material. No loudness conclusion can be drawn from it; the numbers above are the '
          'decay tail only.')
else:
    print('WINDOW_NOTE level computed on the source-active frames only (src_frames column); any '
          'source-free part of the saved window is excluded.')
PY
