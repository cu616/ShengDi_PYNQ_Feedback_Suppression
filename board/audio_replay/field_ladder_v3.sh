#!/bin/bash
# Input-peak ladder at ONE distance, output silent (digital gain 0), three takes.
# B (67d28b2) asked for 12/15/20/24 cm; the distance is read from /home/xilinx/ladder_cm.txt so the
# same script serves every step and the number is recorded next to the result.
# Judgement: take the loudest of the three takes as the distance's peak. A distance is usable only
# if that maximum is < -6 dBFS, and the working gain must then be re-checked because raising g
# raises the microphone too (closed-loop boost table in the evidence file).
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
DIR=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
CM=$(cat /home/xilinx/ladder_cm.txt 2>/dev/null || echo 20)
cd $DIR || exit 1
echo "LADDER distance=${CM}cm  three takes, output silent"
/usr/local/share/pynq-venv/bin/python - "$CM" <<'PY'
import json
import sys
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MODEL = DIR / 'rewired_512_20261026.json'
cm = sys.argv[1]
peaks, rows = [], []
for take in range(3):
    out = DIR / ('ladder_%scm_%d_%d.npz' % (cm, take, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), 'room_v1_20261026b', str(MODEL), np.zeros(1000, dtype=np.int16),
                     bypass=False, zero_coeff=True, gain_db=-8.0, seconds=1.0, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        err = repr(exc)[:160]
    if not out.is_file():
        print('LADDER %scm take%d FAILED %s' % (cm, take, err), flush=True)
        continue
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    st = int(meta.get('capture_status') or 0)
    pk = 20*np.log10(max(float(np.max(np.abs(mic))), 1e-12))
    rms = 20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12))
    peaks.append(pk)
    rows.append(dict(take=take, peak=pk, rms=rms, bit22=(st >> 22) & 1,
                     fs=int(np.count_nonzero(np.abs(mic) >= 0.999))))
    print('LADDER %scm take%d rms=%6.1f peak=%6.1f fs=%d bit22=%d'
          % (cm, take, rms, pk, rows[-1]['fs'], rows[-1]['bit22']), flush=True)
if peaks:
    worst = max(peaks)
    print('LADDER_VERDICT %scm worst_peak=%.1f dBFS -> %s (rule: < -6 dBFS, spread of %.1f dB over %d takes)'
          % (cm, worst, 'USABLE at g=-8' if worst < -6.0 else 'NOT usable at g=-8',
             worst - min(peaks), len(peaks)), flush=True)
PY
