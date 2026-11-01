#!/bin/bash
# Fast button poll: read the status register directly (no overlay reload) for 15 seconds.
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
status = MMIO(ov.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000)
b = Board(D, hp_volume=40)

print('FAST_STATUS base=0x%08X initial=0x%08X' % (status.base_addr, status.read(8) & 0xFFFFFFFF))
b.set_led(0b1111, control)
print('FAST_LED all four on; now press BTN0 for about 1 s (polling for 15 s)')
seen = []
t0 = time.time()
while time.time() - t0 < 15:
    r = b.read_buttons(status)
    bits = tuple(r['btn'])
    if bits != (0, 0, 0, 0) and (not seen or seen[-1][0] != bits):
        seen.append((bits, round(time.time() - t0, 1)))
        print('FAST_BTN %s at %.1fs (status %s)' % (bits, time.time() - t0, r['status']))
    time.sleep(0.05)
b.set_led(0b0000, control)
print('FAST_DONE presses=%s' % (seen if seen else 'none'))
PY
