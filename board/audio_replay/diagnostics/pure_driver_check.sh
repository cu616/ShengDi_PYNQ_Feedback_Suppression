#!/bin/bash
# Control experiment: call the driver with NO I2C access at all.
# If this succeeds, our I2C probing is what upsets the codec init; if it fails too, the driver/codec
# is broken independently of anything we do.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
out = D / 'pure_driver_probe.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    m = json.loads(str(np.load(str(out))['metadata_json']))
    print('PURE_DRIVER ok stop=%s pll=%s' % (m.get('stop_reason'), m.get('pll_readback')))
except Exception as exc:
    print('PURE_DRIVER_FAIL %r' % (exc,))
PY
