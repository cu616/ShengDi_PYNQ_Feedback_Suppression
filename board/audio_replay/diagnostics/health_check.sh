#!/bin/bash
# Read-only health check after the reboot. No register is written.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import fcntl
import json
import os
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

BUS, ADDR = '/dev/i2c-1', 0x3B
D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')


def read16(fd, reg):
    os.write(fd, reg.to_bytes(2, 'big'))
    time.sleep(0.002)
    d = os.read(fd, 2)
    return int.from_bytes(d, 'big') if len(d) == 2 else None


try:
    fd = os.open(BUS, os.O_RDWR)
    fcntl.ioctl(fd, 0x0703, ADDR)
    print('HEALTH aux %s' % {hex(r): '0x%04X' % (read16(fd, r) or 0) for r in (0x400B, 0x400D)})
    os.close(fd)
except Exception as exc:
    print('HEALTH aux read failed %r' % (exc,))

out = D / 'health_probe.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    m = json.loads(str(np.load(str(out))['metadata_json']))
    print('HEALTH_RUN ok stop=%s pll=%s' % (m.get('stop_reason'), m.get('pll_readback')))
except Exception as exc:
    print('HEALTH_RUN_FAIL %r' % (exc,))
PY
