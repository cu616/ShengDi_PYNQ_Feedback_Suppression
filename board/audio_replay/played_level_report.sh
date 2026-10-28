#!/bin/bash
# Print the played-output level per arm directly from the captures.
# The "reference" channel of a capture is the word sent to the DAC, i.e. what the speaker plays,
# so the audible loudness difference between two arms can be measured without a listener.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import glob
import json
import re

import numpy as np

RATE = 48828.125
rows = []
for path in sorted(glob.glob('/home/xilinx/jupyter_notebooks/base/audio/audio_wide/alt_*.npz')):
    data = np.load(path)
    meta = json.loads(str(data['metadata_json']))
    played = np.asarray(data['reference'], dtype=np.float64)
    mic = np.asarray(data['microphone'], dtype=np.float64)
    rms = 20 * np.log10(max(float(np.sqrt(np.mean(played**2))), 1e-12))
    peak = 20 * np.log10(max(float(np.max(np.abs(played))), 1e-12))
    mrms = 20 * np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12))
    rows.append((path.split('/')[-1], meta.get('zero_coeff'), rms, peak, mrms,
                 int(meta.get('completed_frames') or 0), meta.get('stop_reason')))

print('%-34s %-5s %8s %8s %8s %8s %s' % ('file', 'zero', 'played', 'p_peak', 'mic', 'frames', 'stop'))
for name, zero, rms, peak, mrms, frames, stop in rows:
    print('%-34s %-5s %8.2f %8.2f %8.2f %8d %s' % (name, zero, rms, peak, mrms, frames, stop))

z = [r for r in rows if r[1] is True or r[1] == 1]
c = [r for r in rows if r[1] is False or r[1] == 0]
if z and c:
    zs = sum(r[2] for r in z) / len(z)
    cs = sum(r[2] for r in c) / len(c)
    zp = sum(r[3] for r in z) / len(z)
    cp = sum(r[3] for r in c) / len(c)
    print('PLAYED_DELTA zero-candidate: rms %+.2f dB, peak %+.2f dB  (positive = zero arm louder)'
          % (zs - cs, zp - cp))
    print('LISTENER_EQUIVALENT a difference of %.2f dB rms is what a listener at the speaker hears '
          'between the two arms, independent of who is listening' % abs(zs - cs))
PY
