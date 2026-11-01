#!/bin/bash
# Why did the recalibration entry die during its floor stage? Run exactly three silent captures through
# the repair driver and report the AUX readback, stop reason and any exception for each.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from replay_trial_repair import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
MODEL = D / 'model_50cm_20250511-172202.json'
for i in range(3):
    p = D / ('floor3_%d.npz' % i)
    p.unlink(missing_ok=True)
    try:
        replay_trial(str(p), 'room_v1_20261026b', str(MODEL), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
        m = json.loads(str(np.load(str(p))['metadata_json']))
        print('FLOOR3 %d OK stop=%s aux=%s pll=%s' % (i + 1, m.get('stop_reason'),
                                                      m.get('aux_input_gain_db'), m.get('pll_readback')))
    except Exception as exc:
        print('FLOOR3 %d FAIL %s: %s' % (i + 1, type(exc).__name__, exc))
PY
