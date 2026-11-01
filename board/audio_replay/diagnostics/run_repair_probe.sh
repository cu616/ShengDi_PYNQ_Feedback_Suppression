#!/bin/bash
# Run the repair copy once, to make the PLL failure state explicit.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
from pathlib import Path

import numpy as np

from replay_trial_repair import replay_trial as repair_run

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
out = D / 'repair_probe.npz'
out.unlink(missing_ok=True)
try:
    repair_run(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'),
               np.zeros(16000, np.int16), bypass=False, zero_coeff=True, gain_db=0.0,
               seconds=0.40, hp_volume=40, speaker_confirmed=True,
               local_capture_confirmed=True, direct_only=True)
    print('REPAIR_OK')
except Exception as exc:
    print('REPAIR_ERR %s: %s' % (type(exc).__name__, exc))
PY
