#!/bin/bash
# 3-second listen-only probe: digital gain 0, no output, phone playing.
# Purpose: pick a source level that does NOT reach the ADC rail before spending a 60-second run on it.
# Verdict: PASS if no input full scale (bit22=0) and the microphone peak stays below -6 dBFS.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
echo "LISTEN_PROBE 3 s, no output"
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
out = DIR / ('probe_%d.npz' % time.time_ns())
err = None
try:
    replay_trial(str(out), 'room_v1_20261026b', str(DIR / 'rewired_512_20261026.json'),
                 np.zeros(1000, dtype=np.int16), bypass=False, zero_coeff=True, gain_db=-8.0,
                 seconds=3.0, hp_volume=40, speaker_confirmed=True,
                 local_capture_confirmed=True, direct_only=True)
except Exception as exc:
    err = repr(exc)[:200]
print('PROBE error:', err)
if out.is_file():
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    peak = meta.get('mic_peak_dbfs')
    print('PROBE stop=%s frames=%s bit22=%d mic_rms=%s mic_peak=%s full_scale_samples=%s'
          % (meta.get('stop_reason'), meta.get('completed_frames'), (st >> 22) & 1,
             meta.get('mic_rms_dbfs'), peak, meta.get('mic_full_scale_samples')))
    ok = (st >> 22) & 1 == 0 and peak is not None and float(peak) < -6.0
    print('PROBE_VERDICT', 'PASS' if ok else 'FAIL (need bit22=0 and peak < -6 dBFS)')
else:
    print('PROBE_VERDICT FAIL (no capture)')
PY
