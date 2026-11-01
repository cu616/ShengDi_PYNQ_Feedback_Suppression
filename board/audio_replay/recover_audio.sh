#!/bin/bash
# Audio-path recovery loop.
#
# The codec PLL locks intermittently after the FPGA has been reconfigured many times: the same
# reset-and-reload sometimes yields pll=000000002803 and sometimes "unexpected 50 MHz PLL readback".
# This loop retries the full sequence a bounded number of times and reports which attempt worked.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import sys
import time
from pathlib import Path

import numpy as np

from pynq import Overlay, PL
from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
BASE = '/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit'
MAX_TRIES = 6


def attempt(i):
    try:
        PL.reset()
        Overlay(BASE)
        Overlay(str(D / 'audio_replay.bit'))
    except Exception as exc:
        return False, 'reset failed: %r' % (exc,)
    o = D / ('recover_%d.npz' % i)
    o.unlink(missing_ok=True)
    try:
        replay_trial(str(o), 'room_v1_20261026b', str(D / 'model_recalibrated.json'),
                     np.zeros(16000, np.int16), bypass=False, zero_coeff=True, gain_db=0.0,
                     seconds=0.40, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
        m = json.loads(str(np.load(str(o))['metadata_json']))
        return True, 'pll=%s' % m.get('pll_readback')
    except Exception as exc:
        return False, repr(exc)[:120]


for i in range(1, MAX_TRIES + 1):
    ok, info = attempt(i)
    print('RECOVER try=%d %s %s' % (i, 'OK' if ok else 'fail', info))
    if ok:
        print('RECOVER_DONE attempt=%d' % i)
        sys.exit(0)
    time.sleep(1.0)
print('RECOVER_FAIL after %d attempts' % MAX_TRIES)
sys.exit(1)
PY
