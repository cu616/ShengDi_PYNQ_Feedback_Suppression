#!/bin/bash
# Two clearly separated phases so the operator knows exactly what to watch and when.
#   PHASE A (10 s)  all four user LEDs on   -> watch LD0-LD3
#   PHASE B (10 s)  LEDs off, buttons polled -> press BTN0
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time

from pynq import MMIO, Overlay

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
ov = Overlay(D + '/audio_replay.bit')
control = MMIO(ov.ip_dict['audio_control']['phys_addr'], 0x1000)
status = MMIO(ov.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000)

def set_led(mask):
    cur = control.read(0) & 0xFFFFFFFF
    control.write(0, (cur & ~0x3C) | ((mask & 0xF) << 2))
    return (control.read(0) >> 2) & 0xF

print('PHASE_A start: LEDs on for 10 s')
print('PHASE_A led_readback=%s' % format(set_led(0b1111), '04b'))
time.sleep(10)
set_led(0b0000)
print('PHASE_A end: LEDs off')

print('PHASE_B start: LEDs off, press BTN0 for 10 s')
seen = []
t0 = time.time()
while time.time() - t0 < 10:
    w = status.read(8) & 0xFFFFFFFF
    bits = tuple((w >> (27 + i)) & 1 for i in range(4))
    if bits != (0, 0, 0, 0) and (not seen or seen[-1] != bits):
        seen.append(bits)
        print('PHASE_B btn=%s at %.1fs' % (bits, time.time() - t0))
    time.sleep(0.02)
print('PHASE_B done presses=%s' % (seen if seen else 'none'))
PY
