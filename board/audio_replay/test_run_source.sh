#!/bin/bash
# Does the run op now actually emit program audio? Two cases:
#   a) no source -> must refuse with run_requires_source (no silent "run")
#   b) test tone 400 Hz at -20 dBFS -> the mic must see the tone well above the floor
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json

import numpy as np

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)

p.perform({'op': 'prepare', 'request_id': 'r0', 'scene_id': 's1'})
bad = p.perform({'op': 'run', 'request_id': 'r1', 'scene_id': 's1', 'seconds': 2.0, 'gain_q12': 2303})
print('RUNSILENCE %s' % J({k: bad.get(k) for k in ('ok', 'status', 'reason')}))

good = p.perform({'op': 'run', 'request_id': 'r2', 'scene_id': 's1', 'seconds': 2.5,
                  'gain_q12': 2303, 'test_tone_hz': 400.0, 'level_dbfs': -20.0})
print('RUNTONE %s' % J({k: good.get(k) for k in ('ok', 'status', 'effective_mode', 'elapsed_seconds')}))

runp = None
for f in sorted((p.run_root).glob('run_*.npz'))[-1:]:
    runp = f
if runp:
    c = np.load(str(runp))
    mic = np.asarray(c['microphone'], float)
    ref = np.asarray(c['reference'], float)
    d = lambda a: float(20 * np.log10(max(np.sqrt(np.mean(a ** 2)), 1e-12)))
    print('RUNTONE_LEVEL ref=%.2f dBFS mic=%.2f dBFS mic_minus_ref=%+.2f dB'
          % (d(ref), d(mic), d(mic) - d(ref)))
p.mute()
print('RUNSILENCE_OK_REFUSED=%s' % (bad.get('reason') == 'run_requires_source'))
PY
