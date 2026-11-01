#!/bin/bash
# Restoration check 1: does the OTHER verified package (audio_wide, v3 driver) initialise the codec?
# If it does, the hardware and codec are fine and the fault is specific to the v3-sw run; if it also
# fails, the audio path itself is broken.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_wide || { echo 'RESTORE_FAIL audio_wide missing'; exit 1; }
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
print('RESTORE_PKG audio_wide')
out = D / 'restore_probe.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'rewired_512_20261026.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    m = json.loads(str(np.load(str(out))['metadata_json']))
    print('RESTORE_WIDE ok stop=%s pll=%s' % (m.get('stop_reason'), m.get('pll_readback')))
except Exception as exc:
    print('RESTORE_WIDE_FAIL %r' % (exc,))
PY
