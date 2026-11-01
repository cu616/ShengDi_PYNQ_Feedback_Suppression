#!/bin/bash
# After the power cycle: is the audio init healthy, and does the driver rewrite the AUX gain to +6 dB?
#   1 read AUX (expect 0x07 after reboot)
#   2 short capture -> pll_readback health
#   3 set AUX to 0 dB, read back
#   4 another capture, then read AUX again: back to 0x07 means the init flow overwrites it
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
D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')


def read8(fd, reg):
    os.write(fd, reg.to_bytes(2, 'big'))
    d = os.read(fd, 1)
    if len(d) != 1:
        raise IOError('short read')
    return d[0]


def write8(fd, reg, value):
    os.write(fd, reg.to_bytes(2, 'big') + bytes([value]))
    time.sleep(0.002)


def cap(tag):
    o = D / ('postboot_%s.npz' % tag)
    o.unlink(missing_ok=True)
    try:
        replay_trial(str(o), 'room_v1_20261026b', str(D / 'model_recalibrated.json'), np.zeros(16000, np.int16),
                     bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        m = json.loads(str(np.load(str(o))['metadata_json']))
        return {'ok': True, 'stop': m.get('stop_reason'), 'pll': m.get('pll_readback')}
    except Exception as exc:
        return {'ok': False, 'error': repr(exc)[:160]}


fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
print('POSTBOOT aux_at_start %s' % {hex(r): hex(read8(fd, r)) for r in REGS})
os.close(fd)

print('POSTBOOT run1 %s' % cap('1'))

fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
for r in REGS:
    write8(fd, r, (read8(fd, r) & 0xF8) | 0x05)
print('POSTBOOT set_0dB %s' % {hex(r): hex(read8(fd, r)) for r in REGS})
os.close(fd)

print('POSTBOOT run2 %s' % cap('2'))

fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
after = {hex(r): hex(read8(fd, r)) for r in REGS}
print('POSTBOOT aux_after_run2 %s' % after)
reset = any(int(v, 16) & 7 == 7 for v in after.values())
print('POSTBOOT_DRIVER_RESETS_AUX %s' % reset)
if reset:
    for r in REGS:
        write8(fd, r, (read8(fd, r) & 0xF8) | 0x05)
    print('POSTBOOT reapplied_0dB %s' % {hex(r): hex(read8(fd, r)) for r in REGS})
os.close(fd)
PY
