#!/bin/bash
# Restore the codec with 2-byte data writes (ADAU176x uses 16-bit data words for its registers).
# The earlier single-byte write truncated the I2C frame and left the codec in a broken state.
# Originals from the first 16-bit read: 0x400B = 0x0700, 0x400D = 0x07B3.
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
ORIG = {0x400B: 0x0700, 0x400D: 0x07B3}
D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')


def read16(fd, reg):
    os.write(fd, reg.to_bytes(2, 'big'))
    time.sleep(0.002)
    d = os.read(fd, 2)
    if len(d) != 2:
        raise IOError('short read')
    return int.from_bytes(d, 'big')


def write16(fd, reg, value):
    os.write(fd, reg.to_bytes(2, 'big') + (value & 0xFFFF).to_bytes(2, 'big'))
    time.sleep(0.003)


fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
print('REST16 before %s' % {hex(r): hex(read16(fd, r)) for r in ORIG})
for reg, want in ORIG.items():
    write16(fd, reg, want)
    print('REST16 wrote %s = 0x%04X readback=0x%04X' % (hex(reg), want, read16(fd, reg)))
os.close(fd)

out = D / 'restore16_check.npz'
out.unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    m = json.loads(str(np.load(str(out))['metadata_json']))
    print('REST16_RUN ok stop=%s pll=%s' % (m.get('stop_reason'), m.get('pll_readback')))
except Exception as exc:
    print('REST16_RUN_FAIL %r' % (exc,))

fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
print('REST16 after_run %s' % {hex(r): hex(read16(fd, r)) for r in ORIG})
os.close(fd)
PY
