#!/bin/bash
# Live read of the switch status bits, so the operator can flip SW0 / SW1 while the numbers are on
# screen. Loads the overlay once, then only reads a register: no audio, nothing else changes.
#   bit25 = SW0 raw pin (unsynchronised, diagnostic)
#   bit24 = SW0 synchronised
#   bit23 = SW1 synchronised
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time

from pynq import MMIO, Overlay

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_switch'
ov = Overlay(D + '/audio_replay.bit')
m = MMIO(ov.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000)
print('READ_READY window=40s  bits: 25=SW0raw 24=SW0sync 23=SW1sync')
last = None
t0 = time.monotonic()
while time.monotonic() - t0 < 40:
    s = m.read(8) & 0xFFFFFFFF
    bits = ((s >> 25) & 1, (s >> 24) & 1, (s >> 23) & 1)
    if bits != last:
        print('CHANGE %5.1fs  SW0raw=%d SW0sync=%d SW1sync=%d  status=0x%08x'
              % (time.monotonic() - t0, bits[0], bits[1], bits[2], s))
        last = bits
    time.sleep(0.2)
print('READ_DONE final bits=%s' % (last,))
PY
