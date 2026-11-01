#!/bin/bash
# Does the driver's init rewrite the AUX gain to 7 on every run?
# Read -> run one short capture -> read again. If it is back to 0x07, the init flow must be changed
# (a one-off write does not survive).
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import fcntl
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
    data = os.read(fd, 1)
    if len(data) != 1:
        raise IOError('short read')
    return data[0]


def write8(fd, reg, value):
    os.write(fd, reg.to_bytes(2, 'big') + bytes([value]))
    time.sleep(0.002)


fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)

print('PERSIST before run: %s' % {hex(r): hex(read8(fd, r)) for r in REGS})

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
out = D / 'aux_persist_probe.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
except Exception as exc:
    print('PERSIST run raised %r' % (exc,))

after = {hex(r): hex(read8(fd, r)) for r in REGS}
print('PERSIST after run : %s' % after)
reset = any(int(v, 16) & 7 == 7 for v in after.values())
print('PERSIST_RESET %s (True means the driver put the +6 dB setting back)' % reset)

if reset:
    print('PERSIST re-applying 0 dB and marking the init flow as requiring a change')
    for r in REGS:
        write8(fd, r, (read8(fd, r) & 0xF8) | 0x05)
    print('PERSIST reapplied: %s' % {hex(r): hex(read8(fd, r)) for r in REGS})
os.close(fd)
PY
