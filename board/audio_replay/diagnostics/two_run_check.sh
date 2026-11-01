#!/bin/bash
# After a PL reset: two consecutive driver runs, with NO I2C access between them.
# If the second fails, the fault is in repeated init (driver/codec), not in our register reads.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from pynq import Overlay, PL
from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
PL.reset()
Overlay('/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit')
Overlay(str(D / 'audio_replay.bit'))
print('TWO_RESET done')


def run(tag):
    o = D / ('two_%s.npz' % tag)
    o.unlink(missing_ok=True)
    try:
        replay_trial(str(o), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                     bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        m = json.loads(str(np.load(str(o))['metadata_json']))
        print('TWO_RUN %s ok pll=%s' % (tag, m.get('pll_readback')))
        return True
    except Exception as exc:
        print('TWO_RUN %s FAIL %r' % (tag, exc))
        return False


first = run('1')
second = run('2') if first else None
print('TWO_RESULT first=%s second=%s' % (first, second))
PY
