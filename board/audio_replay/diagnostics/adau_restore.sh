#!/bin/bash
# Restore the AUX gain to the original +6 dB (0x07) and confirm the driver's init works again.
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

I2C_SLAVE = 0x0703
BUS = '/dev/i2c-1'
ADDR = 0x3B
REGS = (0x400B, 0x400D)


def read8(fd, reg):
    os.write(fd, reg.to_bytes(2, 'big'))
    d = os.read(fd, 1)
    if len(d) != 1:
        raise IOError('short read')
    return d[0]


def write8(fd, reg, value):
    os.write(fd, reg.to_bytes(2, 'big') + bytes([value]))
    time.sleep(0.002)


orig = json.load(open('/home/xilinx/adau176x_aux_original_8bit.json'))['originals']
fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
for reg in REGS:
    key = '0x%04X' % reg
    want = orig.get(key)
    if want is None:
        print('RESTORE skip %s (no original)' % key)
        continue
    write8(fd, reg, want)
    print('RESTORE %s -> 0x%02X readback=0x%02X' % (key, want, read8(fd, reg)))
os.close(fd)

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
out = D / 'restore_check.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    print('RESTORE_RUN ok stop=%s pll=%s' % (meta.get('stop_reason'), meta.get('pll_readback')))
except Exception as exc:
    print('RESTORE_RUN_FAIL %r' % (exc,))

fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
print('AUX_AFTER_RESTORE %s' % {hex(r): hex(read8(fd, r)) for r in REGS})
os.close(fd)
PY
