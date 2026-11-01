#!/bin/bash
# Which bits move, and in which direction, when each button is pressed?
# Prints every status change for 24 seconds with a fast poll (no overlay reload inside the loop).
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time

from pynq import MMIO, Overlay

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
ov = Overlay(D + '/audio_replay.bit')
status = MMIO(ov.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000)
control = MMIO(ov.ip_dict['audio_control']['phys_addr'], 0x1000)
control.write(0, (control.read(0) & ~0x3C) | 0x3C)      # all four LEDs on as a visual "I am ready" marker
print('BTN_SCAN ready base=0x%08X start=0x%08X' % (status.base_addr, status.read(8) & 0xFFFFFFFF))
last = None
t0 = time.time()
while time.time() - t0 < 24:
    w = status.read(8) & 0xFFFFFFFF
    if w != last:
        print('BTN_SCAN %5.1fs 0x%08X  btn=%s' % (time.time() - t0, w,
                                                  [(w >> (27 + i)) & 1 for i in range(4)]))
        last = w
    time.sleep(0.02)
control.write(0, control.read(0) & ~0x3C)
print('BTN_SCAN done')
PY
