#!/bin/bash
# 115 cm field acceptance chain: button -> cue -> capture -> install -> live run -> switch -> stop.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)
scene = '115cm-' + time.strftime('%H%M%S')
run_dir = '/home/xilinx/jupyter_notebooks/base/audio/audio_io/fieldwin/' + scene

# 1. button starts recalibration
print('FW115_PRESS_BTN0 now (long press ~1.5 s); polling 15 s')
t0, ev = time.time(), None
while time.time() - t0 < 15:
    for e in p.poll().get('events') or []:
        if e.get('kind') == 'recalibrate':
            ev = e
    if ev:
        break
    time.sleep(0.05)
print('FW115_BUTTON %s' % J(ev or {'kind': None}))
p.indicate({'state': 'recalibrating'})

prep = p.perform({'op': 'prepare', 'request_id': 'b0', 'scene_id': scene, 'run_dir': run_dir})
print('FW115_PREP %s' % J({k: prep.get(k) for k in ('ok', 'status')}))

p.indicate({'state': 'speak'})
ci = p.perform({'op': 'input', 'cue': True, 'request_id': 'b1', 'scene_id': scene,
                'run_dir': run_dir, 'seconds': 2.4})
ir = ci.get('input_ready') or {}
print('FW115_CUE %s' % J({'ok': ci.get('ok'), 'cue_end': ir.get('cue_end_frame'),
                          'valid_first': ir.get('valid_first_frame')}))

plan = {'peak_cap': 0.80, 'seed': 4242, 'validation_seed': 4243,
        'training': [{'seed': 4242, 'frames': 16384} for _ in range(6)],
        'validation': [{'seed': 4243, 'frames': 16384} for _ in range(2)]}
for op in ('training', 'validation'):
    r = p.perform({'op': op, 'request_id': 'b-' + op, 'scene_id': scene, 'run_dir': run_dir, 'plan': plan})
    caps = r.get('captures') or []
    print('FW115_%s %s' % (op.upper(), J({'ok': r.get('ok'), 'level': r.get('level_accepted_dbfs'),
                                          'n': len(caps), 'bit22': [c.get('bit22') for c in caps]})))

ins = p.perform({'op': 'install', 'request_id': 'b2', 'scene_id': scene, 'run_dir': run_dir,
                 'model_path': cfg['model_path'], 'run_gain_q12': 2303})
print('FW115_INSTALL %s' % J({k: ins.get(k) for k in ('ok', 'status', 'loaded_count', 'run_gain_q12')}))

p.indicate({'state': 'ready'})
print('FW115_SPEAK_NOW talk continuously for 30 s; FLIP_SW0 comes mid-run')
t0 = time.time()
mode0 = mode1 = None
p._write_control(arm=False, bypass=False, gain_q12=2303, allow_armed=True)
p._write_control(arm=True, allow_armed=True)
import math
import numpy as np
from pathlib import Path
cap = Path(run_dir) / 'live.npz'
cap.parent.mkdir(parents=True, exist_ok=True)
src = np.zeros(16, np.int16)
flipped = False
try:
    p._driver().replay_trial(str(cap), scene, str(p.model_path), src, bypass=False, zero_coeff=False,
                             gain_db=20 * math.log10(2303 / 4096.0), seconds=30.0,
                             hp_volume=p.hp_volume, speaker_confirmed=True,
                             local_capture_confirmed=True, direct_only=False,
                             reuse_overlay=False, restore_stock=False)
    meta = p._meta(np.load(str(cap)))
finally:
    p._write_control(arm=False, allow_armed=True)
    p.mute()
st = int(meta.get('capture_status') or 0)
print('FW115_RUN %s' % J({'stop': meta.get('stop_reason'), 'bit22': (st >> 22) & 1,
                          'pred': meta.get('prediction_saturations'),
                          'res': meta.get('residual_saturations'),
                          'gain': meta.get('gain_saturations')}))

print('FW115_PRESS_BTN3 now (stop); polling 12 s')
t0, ev = time.time(), None
while time.time() - t0 < 12:
    for e in p.poll().get('events') or []:
        if e.get('kind') == 'cancel':
            ev = e
    if ev:
        break
    time.sleep(0.05)
print('FW115_BTN3 %s' % J(ev or {'kind': None}))
p.mute()
print('FW115_DONE scene=%s mode_after=%s' % (scene, p.effective_mode()))
PY
