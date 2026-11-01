#!/bin/bash
# Verify C's four fixes on hardware: metadata accessor, JSON install, cancel gate, audio vs wall timing.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import threading

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)

p.perform({'op': 'prepare', 'request_id': 'r0', 'scene_id': 'fixcheck'})

# 3. pre-set cancel must not reach the driver
ev = threading.Event()
ev.set()
c = p.perform({'op': 'training', 'request_id': 'r1', 'scene_id': 'fixcheck',
               'plan': {'training': [{'seed': 4242}]}}, ev)
print('FIX_CANCEL %s' % J({k: c.get(k) for k in ('ok', 'status', 'reason', 'never_armed_again')}))

# 2. install parses the JSON model and verifies the load
ins = p.perform({'op': 'install', 'request_id': 'r2', 'scene_id': 'fixcheck',
                 'model_path': cfg['model_path'], 'run_gain_q12': 2303})
print('FIX_INSTALL %s' % J({k: ins.get(k) for k in ('ok', 'status', 'reason', 'loaded_count', 'taps',
                                                     'run_gain_q12', 'applies_at')} |
                            {'model': (ins.get('model_sha256') or '')[:16],
                             'coeff': (ins.get('coefficients_sha256') or '')[:16],
                             'reported': (ins.get('reported_coefficients_sha256') or '')[:16],
                             'identity_gain_q12': (ins.get('identity') or {}).get('gain_q12')}))

# 4. audio time from frames, wall time separately
r = p.perform({'op': 'run', 'request_id': 'r3', 'scene_id': 'fixcheck',
               'seconds': 3.0, 'gain_q12': 2303})
print('FIX_RUN %s' % J({k: r.get(k) for k in ('ok', 'status', 'audio_frames', 'elapsed_seconds',
                                               'wall_seconds')}))
PY
