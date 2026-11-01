#!/bin/bash
# Field window step 1+2: cue+input in one call (needs a talker), then the encapsulated 6+2 plan.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json',
       'run_dir_root': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/fieldwin'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)
scene = 'fw-' + time.strftime('%H%M%S')
run_dir = '/home/xilinx/jupyter_notebooks/base/audio/audio_io/fieldwin/' + scene

prep = p.perform({'op': 'prepare', 'request_id': 'w0', 'scene_id': scene, 'run_dir': run_dir})
print('FW_PREP %s' % J({k: prep.get(k) for k in ('ok', 'status', 'prepared')}))

p.indicate({'state': 'speak'})
ci = p.perform({'op': 'input', 'cue': True, 'request_id': 'w1', 'scene_id': scene,
                'run_dir': run_dir, 'seconds': 2.4})
ir = ci.get('input_ready') or {}
print('FW_CUEINPUT %s' % J({'ok': ci.get('ok'), 'status': ci.get('status'),
                            'input_ready': {k: ir.get(k) for k in ('capture_id', 'cue_end_frame',
                                                                   'valid_first_frame', 'status')}}))

plan = {'peak_cap': 0.80, 'seed': 4242, 'validation_seed': 4243,
        'training': [{'seed': 4242, 'frames': 16384} for _ in range(6)],
        'validation': [{'seed': 4243, 'frames': 16384} for _ in range(2)]}
for op in ('training', 'validation'):
    t0 = time.monotonic()
    r = p.perform({'op': op, 'request_id': 'w-' + op, 'scene_id': scene,
                   'run_dir': run_dir, 'plan': plan})
    caps = r.get('captures') or []
    print('FW_%s %s' % (op.upper(), J({'ok': r.get('ok'), 'status': r.get('status'),
                                       'level': r.get('level_accepted_dbfs'),
                                       'n': len(caps),
                                       'valid': [c.get('valid_frames') for c in caps],
                                       'bit22': [c.get('bit22') for c in caps],
                                       'wall_s': round(time.monotonic() - t0, 1)})))
    if caps:
        print('FW_%s_SRC %s' % (op.upper(), J([(c.get('capture_id'), (c.get('source_sha256') or '')[:12])
                                               for c in caps])))
p.mute()
print('FW_DONE scene=%s dir=%s' % (scene, run_dir))
PY
