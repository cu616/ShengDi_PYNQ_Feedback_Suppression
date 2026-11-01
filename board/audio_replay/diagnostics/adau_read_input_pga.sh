#!/bin/bash
# Read the ADAU1761 input PGA registers (0x400B / 0x400D) over /dev/i2c-1 at 0x3B.
# READ ONLY. Nothing is written. The original values are saved so a later change can be undone.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import fcntl
import json
import os
import struct
import time

I2C_SLAVE = 0x0703
BUS = '/dev/i2c-1'
ADDR = 0x3B
REGS = (0x400B, 0x400D)


def open_bus():
    fd = os.open(BUS, os.O_RDWR)
    fcntl.ioctl(fd, I2C_SLAVE, ADDR)
    return fd


def read16(fd, reg):
    """ADAU1761 read: write the 2-byte register address, then read 2 bytes of data."""
    os.write(fd, struct.pack('>H', reg))
    time.sleep(0.002)
    data = os.read(fd, 2)
    if len(data) != 2:
        raise IOError('short read for 0x%04X: %r' % (reg, data))
    return struct.unpack('>H', data)[0]


out = {}
try:
    fd = open_bus()
except Exception as exc:
    print('I2C_OPEN_FAIL %r' % (exc,))
    raise SystemExit(1)

for reg in REGS:
    try:
        val = read16(fd, reg)
        low3 = val & 0b111
        out['0x%04X' % reg] = {'raw': '0x%04X' % val, 'low3': format(low3, '03b'),
                               'low3_db': {7: '+6 dB', 5: '0 dB'}.get(low3, 'other')}
        print('I2C_READ 0x%04X = 0x%04X  low3=%s (%s)'
              % (reg, val, format(low3, '03b'), out['0x%04X' % reg]['low3_db']))
    except Exception as exc:
        out['0x%04X' % reg] = {'error': repr(exc)}
        print('I2C_READ_ERR 0x%04X %r' % (reg, exc))
os.close(fd)

open('/home/xilinx/adau1761_input_pga_original.json', 'w').write(
    json.dumps({'bus': BUS, 'addr': '0x%02X' % ADDR, 'registers': out,
                'note': 'read-only snapshot taken before any change'}, ensure_ascii=False, indent=2))
print('I2C_SAVED /home/xilinx/adau1761_input_pga_original.json')
print('I2C_SUMMARY %s' % json.dumps(out, ensure_ascii=False))
PY
