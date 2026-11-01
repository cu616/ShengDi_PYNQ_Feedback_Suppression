#!/bin/bash
# Button and switch acceptance at 115 cm, with the LED acting as the "do this now" signal.
#   1111 -> long-press BTN0        0001 -> acknowledged
#   0100 -> flip SW0 up            (waits for status[24])
#   1000 -> press BTN3             (waits for the cancel event)
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import math
import time
from pathlib import Path

import numpy as np

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)
scene = '115cm-bt-' + time.strftime('%H%M%S')
run_dir = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_io/fieldwin') / scene
run_dir.mkdir(parents=True, exist_ok=True)
p.perform({'op': 'prepare', 'request_id': 'p0', 'scene_id': scene, 'run_dir': str(run_dir)})

def wait_event(kind, timeout, pattern):
    p._write_control(led=pattern, allow_armed=True)
    t0, hit = time.time(), None
    while time.time() - t0 < timeout:
        for e in p.poll().get('events') or []:
            if e.get('kind') == kind:
                hit = e
        if hit:
            break
        time.sleep(0.05)
    return hit

btn = wait_event('recalibrate', 40, 0b1111)
print('BT_LED_BTN0 %s' % J(btn or {'kind': None}))
p._write_control(led=0b0001, allow_armed=True)

def live(tag, bypass, seconds=20.0):
    cap = run_dir / (tag + '.npz')
    p._write_control(arm=False, bypass=bypass, gain_q12=2303, allow_armed=True)
    p._write_control(arm=True, allow_armed=True)
    try:
        p._driver().replay_trial(str(cap), p.fixture, str(p.model_path), np.zeros(16, np.int16),
                                 bypass=bypass, zero_coeff=False,
                                 gain_db=20 * math.log10(2303 / 4096.0), seconds=seconds,
                                 hp_volume=p.hp_volume, speaker_confirmed=True,
                                 local_capture_confirmed=True, direct_only=False,
                                 reuse_overlay=False, restore_stock=False)
        meta = p._meta(np.load(str(cap)))
    finally:
        p._write_control(arm=False, allow_armed=True)
        p.mute()
    mic = np.asarray(np.load(str(cap))['microphone'], float)
    st = int(meta.get('capture_status') or 0)
    return {'tag': tag, 'bypass': bypass, 'stop': meta.get('stop_reason'),
            'mic_dbfs': round(float(20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12))), 2),
            'sw0': (st >> 24) & 1, 'bit22': (st >> 22) & 1,
            'sat': [meta.get('prediction_saturations'), meta.get('residual_saturations'),
                    meta.get('gain_saturations')]}

a = live('sw0_down', bypass=False)
print('BT_RUN_A %s' % J(a))

p._write_control(led=0b0100, allow_armed=True)
t0, up = time.time(), False
while time.time() - t0 < 40:
    if (p._status_word() >> 24) & 1:
        up = True
        break
    time.sleep(0.05)
print('BT_SW0_FLIPPED %s' % up)

b = live('sw0_up', bypass=True)
print('BT_RUN_B %s' % J(b))

t0, hit = time.time(), None
p._write_control(led=0b1000, allow_armed=True)
while time.time() - t0 < 40:
    for e in p.poll().get('events') or []:
        if e.get('kind') == 'cancel':
            hit = e
    if hit:
        break
    time.sleep(0.05)
print('BT_BTN3 %s' % J(hit or {'kind': None}))
p.mute()
print('BT_DONE bt0=%s sw0=%s btn3=%s' % (bool(btn), up, bool(hit)))
PY
