#!/bin/bash
# Read the AUX input gain (8-bit) in the record mixer registers, then set bits[2:0] from 111 to 101.
# Registers 0x400B / 0x400D: [2:0] AUX gain (111 = +6 dB, 101 = 0 dB); [4:3] differential PGA (untouched);
# [7:5] reserved (untouched). Data width is 8 bits - the earlier 16-bit read was a code error.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import fcntl
import json
import os
import time

I2C_SLAVE = 0x0703
BUS = '/dev/i2c-1'
ADDR = 0x3B
REGS = (0x400B, 0x400D)
NEW_LOW3 = 0x05          # 0 dB


def open_bus():
    fd = os.open(BUS, os.O_RDWR)
    fcntl.ioctl(fd, I2C_SLAVE, ADDR)
    return fd


def read8(fd, reg):
    if os.write(fd, reg.to_bytes(2, 'big')) != 2:
        raise IOError('short register-address write')
    data = os.read(fd, 1)
    if len(data) != 1:
        raise IOError('short register-data read')
    return data[0]


def write8(fd, reg, value):
    payload = reg.to_bytes(2, 'big') + bytes([value & 0xFF])
    if os.write(fd, payload) != 3:
        raise IOError('short register write')
    time.sleep(0.002)


fd = open_bus()
before, after = {}, {}
for reg in REGS:
    try:
        v = read8(fd, reg)
        before['0x%04X' % reg] = v
        print('AUX_READ 0x%04X = 0x%02X   low3=%s (%s)'
              % (reg, v, format(v & 7, '03b'), {7: '+6 dB', 5: '0 dB'}.get(v & 7, 'other')))
    except Exception as exc:
        before['0x%04X' % reg] = None
        print('AUX_READ_ERR 0x%04X %r' % (reg, exc))

json.dump({'bus': BUS, 'addr': '0x%02X' % ADDR, 'width_bits': 8, 'originals': before,
           'note': 'correct single-byte snapshot'},
          open('/home/xilinx/adau176x_aux_original_8bit.json', 'w'), ensure_ascii=False, indent=2)
print('AUX_SAVED /home/xilinx/adau176x_aux_original_8bit.json')

if all(v is not None and (v & 7) == 7 for v in before.values()):
    print('AUX_PRECONDITION ok: both read 0x07 in the low three bits, proceeding')
    changed = {}
    for reg in REGS:
        old = before['0x%04X' % reg]
        new = (old & 0xF8) | NEW_LOW3
        try:
            write8(fd, reg, new)
            back = read8(fd, reg)
            changed['0x%04X' % reg] = {'old': old, 'new': new, 'readback': back,
                                       'ok': back == new}
            print('AUX_WRITE 0x%04X 0x%02X -> 0x%02X  readback=0x%02X %s'
                  % (reg, old, new, back, 'OK' if back == new else 'MISMATCH'))
        except Exception as exc:
            changed['0x%04X' % reg] = {'old': old, 'error': repr(exc)}
            print('AUX_WRITE_ERR 0x%04X %r' % (reg, exc))
    after = changed
    json.dump(changed, open('/home/xilinx/adau176x_aux_changed_8bit.json', 'w'),
              ensure_ascii=False, indent=2)
    print('AUX_CHANGED_SAVED /home/xilinx/adau176x_aux_changed_8bit.json')
else:
    print('AUX_PRECONDITION_FAIL not both 0x07 low3; no write performed')
os.close(fd)
PY
