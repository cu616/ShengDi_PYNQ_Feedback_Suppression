#!/bin/bash
# Restoration attempt: reset the PL by loading the boot overlay, then load our bitstream again and see
# whether the codec PLL locks. A stuck MCLK path shows up exactly as "unexpected 50 MHz PLL readback".
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from pynq import Overlay, PL

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
print('RESET bitfile_before:', getattr(PL, 'bitfile_name', None))
try:
    PL.reset()
    print('RESET PL.reset() done')
except Exception as exc:
    print('RESET PL.reset failed %r' % (exc,))
try:
    boot = Overlay('/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit')
    print('RESET boot overlay loaded:', getattr(PL, 'bitfile_name', None))
    del boot
except Exception as exc:
    print('RESET boot overlay failed %r' % (exc,))
try:
    ov = Overlay(str(D / 'audio_replay.bit'))
    print('RESET ours loaded:', getattr(PL, 'bitfile_name', None), 'ips=%d' % len(ov.ip_dict))
except Exception as exc:
    print('RESET ours failed %r' % (exc,))

from replay_trial import replay_trial
out = D / 'reset_probe.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    m = json.loads(str(np.load(str(out))['metadata_json']))
    print('RESET_RUN ok stop=%s pll=%s' % (m.get('stop_reason'), m.get('pll_readback')))
except Exception as exc:
    print('RESET_RUN_FAIL %r' % (exc,))
PY
