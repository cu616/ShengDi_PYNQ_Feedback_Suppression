#!/bin/bash
# Physical check of the LEDs and BTN0 on the I/O build.
# Scenario: LED 1010 (5 s) -> LED 0101 (5 s) -> LED 0000, and the buttons are polled throughout.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time

from pynq import MMIO, Overlay

from hw_api import Board

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
ov = Overlay(D + '/audio_replay.bit')
control = MMIO(ov.ip_dict['audio_control']['phys_addr'], 0x1000)
b = Board(D, hp_volume=40)

for mask, hold in ((0b1010, 5.0), (0b0101, 5.0)):
    r = b.set_led(mask, control)
    print('PHYS_LED requested=%s issued=%s readback=%s'
          % (format(mask, '04b'), r.get('issued'), r.get('readback_control')))
    t0 = time.time()
    seen = set()
    while time.time() - t0 < hold:
        btn = b.read_buttons()
        if btn.get('btn'):
            seen.add(tuple(btn['btn']))
        time.sleep(0.2)
    if seen:
        print('PHYS_BUTTONS seen during LED %s: %s' % (format(mask, '04b'), sorted(seen)))
b.set_led(0, control)
print('PHYS_LED requested=0000 issued=True')
btn = b.read_buttons()
print('PHYS_BUTTONS final=%s' % json.dumps(btn.get('btn')))
PY
