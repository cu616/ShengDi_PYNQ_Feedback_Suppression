#!/bin/bash
# Steady, unhurried physical check: all four LEDs on for 20 seconds while the buttons are polled.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time

from pynq import MMIO, Overlay

from hw_api import Board

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
ov = Overlay(D + '/audio_replay.bit')
control = MMIO(ov.ip_dict['audio_control']['phys_addr'], 0x1000)
b = Board(D, hp_volume=40)

b.set_led(0b1111, control)
print('STEADY_LED all four requested on; readback=%s'
      % b.set_led(0b1111, control).get('readback_control'))
seen = []
t0 = time.time()
while time.time() - t0 < 20:
    r = b.read_buttons()
    bits = tuple(r.get('btn') or ())
    if bits and bits != (0, 0, 0, 0):
        if not seen or seen[-1] != bits:
            seen.append(bits)
            print('STEADY_BTN %s at %.1fs' % (bits, time.time() - t0))
    time.sleep(0.15)
b.set_led(0b0000, control)
print('STEADY_DONE patterns_seen=%s' % (seen if seen else 'none'))
PY
