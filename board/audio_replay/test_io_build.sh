#!/bin/bash
# Verify the I/O-integrated bitstream: buttons readable, LEDs writable, audio still works.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json

from pynq import MMIO, Overlay

from hw_api import Board

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
ov = Overlay(D + '/audio_replay.bit')
print('IO_OVERLAY ips=%d' % len(ov.ip_dict))
control = MMIO(ov.ip_dict['audio_control']['phys_addr'], 0x1000)

b = Board(D, hp_volume=40)
b.model = b.dir / 'model_recalibrated.json'
if not b.model.is_file():
    import shutil
    shutil.copy2('/home/xilinx/jupyter_notebooks/base/audio/audio_switch/model_recalibrated.json', b.model)

print('IO_CAPABILITIES %s' % json.dumps(b.capabilities(), ensure_ascii=False)[:160])
print('IO_AUX %s' % json.dumps(b.get_aux_gain_db(), ensure_ascii=False)[:120])
init = b.init_and_mute()
print('IO_INIT %s' % json.dumps({k: init.get(k) for k in ('ok', 'stop_reason', 'frames', 'full_scale_samples')}, ensure_ascii=False))

btn = b.read_buttons()
print('IO_BUTTONS %s' % json.dumps({k: btn.get(k) for k in ('ok', 'btn', 'any_pressed')}, ensure_ascii=False))

for mask in (0b0000, 0b1010, 0b1111, 0b0000):
    r = b.set_led(mask, control)
    print('IO_LED mask=%s -> %s' % (format(mask, '04b'), json.dumps({k: r.get(k) for k in ('ok', 'led')}, ensure_ascii=False)))

sw = b.read_switches()
print('IO_SWITCHES %s' % json.dumps({k: sw.get(k) for k in ('ok', 'sw0_up', 'sw1_up')}, ensure_ascii=False))
PY
