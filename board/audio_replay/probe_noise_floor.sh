#!/bin/bash
# Measure the room noise floor: a silent capture with the source muted and the gain at zero.
# This is what the excitation has to compete with; if it is high, the open-loop fit is being fed
# mostly noise and no model tuning can fix it.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
RATE = 48828.125


def db(x):
    return 20 * np.log10(max(float(x), 1e-12))


out = D / 'noise_floor_probe.npz'
out.unlink(missing_ok=True)
silent = np.zeros(16000, dtype=np.int16)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'rewired_512_20261026.json'), silent,
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
except Exception as exc:
    print('PROBE_RAISED %r' % (exc,))
if out.is_file():
    cap = np.load(str(out))
    mic = np.asarray(cap['microphone'], float)
    meta = json.loads(str(cap['metadata_json']))
    print('noise floor: mic RMS = %+.2f dBFS   peak = %+.2f dBFS   stop=%s'
          % (db(np.sqrt(np.mean(mic ** 2))), db(np.max(np.abs(mic))), meta.get('stop_reason')))
    # compare with what the excitation produced last run
    last = sorted([p for p in D.glob('recal_pkt_*') if p.is_dir()], key=lambda p: p.stat().st_mtime)[-1]
    c = np.load(str(sorted(last.glob('recal_*.npz'))[0]))
    mic_ex = np.asarray(c['microphone'], float)
    ref_ex = np.asarray(c['reference'], float)
    print('last run %s: mic RMS = %+.2f dBFS, ref RMS = %+.2f dBFS'
          % (last.name, db(np.sqrt(np.mean(mic_ex ** 2))), db(np.sqrt(np.mean(ref_ex ** 2)))))
    print('excitation-to-noise ratio at the microphone = %+.2f dB'
          % (db(np.sqrt(np.mean(mic_ex ** 2))) - db(np.sqrt(np.mean(mic ** 2)))))
PY
