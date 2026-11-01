#!/bin/bash
# Can the codec accept I2C writes at all? Write back the SAME value and verify the readback.
# If a no-op write does not stick, the codec is not accepting writes (power/clock/reset problem).
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import fcntl
import os
import time

BUS, ADDR = '/dev/i2c-1', 0x3B


def read16(fd, reg):
    os.write(fd, reg.to_bytes(2, 'big'))
    time.sleep(0.002)
    d = os.read(fd, 2)
    return int.from_bytes(d, 'big') if len(d) == 2 else None


def write16(fd, reg, value):
    n = os.write(fd, reg.to_bytes(2, 'big') + value.to_bytes(2, 'big'))
    time.sleep(0.003)
    return n


fd = os.open(BUS, os.O_RDWR)
fcntl.ioctl(fd, 0x0703, ADDR)
for reg in (0x400B, 0x400D, 0x4000):
    before = read16(fd, reg)
    n = write16(fd, reg, before if before is not None else 0)
    after = read16(fd, reg)
    print('I2C_WRITE_TEST reg=0x%04X before=0x%04X wrote=%d bytes after=0x%04X %s'
          % (reg, before or 0, n, after or 0, 'STICKS' if before == after else 'NO_CHANGE_OR_DIFF'))
os.close(fd)

print('I2C_NOTE a write that does not change anything but still returns 3 bytes only proves the bus '
      'accepted the transfer, not that the codec latched it')
PY
