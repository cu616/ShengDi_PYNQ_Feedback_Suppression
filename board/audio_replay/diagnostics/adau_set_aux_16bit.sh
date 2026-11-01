#!/bin/bash
# After the power cycle: set the AUX input gain to 0 dB using CORRECT 16-bit data writes.
# Field: bits [10:8] of the 16-bit word (high byte's low three bits), 111 = +6 dB, 101 = 0 dB.
#   0x400B: 0x0700 -> 0x0500
#   0x400D: 0x07B3 -> 0x05B3
# Then run one capture to prove the codec still initialises, and read back to see whether the driver
# rewrites the field on its own.
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


def capture(tag):
    o = D / ('aux16_%s.npz' % tag)
    o.unlink(missing_ok=True)
    try:
        replay_trial(str(o), 'room_v1_20261026b', str(D / 'model_recalibrated.json'),
                     np.zeros(16000, np.int16), bypass=False, zero_coeff=True, gain_db=0.0,
                     seconds=0.40, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
        m = json.loads(str(np.load(str(o))['metadata_json']))
        return {'ok': True, 'stop': m.get('stop_reason'), 'pll': m.get('pll_readback')}
    except Exception as exc:
        return {'ok': False, 'error': repr(exc)[:140]}


fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
orig = {reg: read16(fd, reg) for reg in REGS}
print('AUX16 originals %s' % {hex(k): '0x%04X' % v for k, v in orig.items()})
json.dump({'bus': BUS, 'addr': '0x%02X' % ADDR, 'width_bits': 16,
           'originals': {hex(k): '0x%04X' % v for k, v in orig.items()}},
          open('/home/xilinx/adau176x_aux_original_16bit.json', 'w'), ensure_ascii=False, indent=2)
os.close(fd)

print('AUX16 run_before %s' % capture('before'))

fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
for reg in REGS:
    old = read16(fd, reg)
    new = (old & ~0x0700) | (0x05 << 8)
    write16(fd, reg, new)
    print('AUX16 set %s 0x%04X -> 0x%04X readback=0x%04X'
          % (hex(reg), old, new, read16(fd, reg)))
os.close(fd)

print('AUX16 run_after %s' % capture('after'))

fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, I2C_SLAVE, ADDR)
after = {reg: read16(fd, reg) for reg in REGS}
print('AUX16 after_run %s' % {hex(k): '0x%04X' % v for k, v in after.items()})
reset = any(((v >> 8) & 7) == 7 for v in after.values())
print('AUX16_DRIVER_RESETS %s' % reset)
os.close(fd)
PY
