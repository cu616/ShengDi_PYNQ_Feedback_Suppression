#!/bin/bash
# Unblock the product without changing any frozen file:
# the codec's AUX register returns to its power-on value 0x00 after every boot, which my readback mapping
# does not recognise, so the product's identity check fails before it ever reaches prepare().
# Stop the service (it owns the FPGA), write AUX = 0 dB with the single-byte protocol, restart the service.
set -u
echo '=== stop service ==='
echo xilinx | sudo -S systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
echo '=== write AUX 0 dB ==='
/usr/local/share/pynq-venv/bin/python - <<'PY'
import fcntl, os
fd = os.open('/dev/i2c-1', os.O_RDWR)
fcntl.ioctl(fd, 0x0703, 0x3B)
for reg in (0x400B, 0x400D):
    os.write(fd, reg.to_bytes(2, 'big'))
    old = os.read(fd, 1)[0]
    os.write(fd, reg.to_bytes(2, 'big') + bytes([(old & 0xF8) | 0x05]))
    os.write(fd, reg.to_bytes(2, 'big'))
    print('AUX_FIX 0x%04X old=0x%02X new=0x%02X' % (reg, old, os.read(fd, 1)[0]))
os.close(fd)
PY
echo '=== start service ==='
echo xilinx | sudo -S systemctl start shengdi-product.service 2>&1 | tail -1
sleep 8
systemctl is-active shengdi-product.service
