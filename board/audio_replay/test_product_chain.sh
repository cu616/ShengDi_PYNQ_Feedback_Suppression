#!/bin/bash
# Whole-chain integration of the product entry: prepare -> training -> validation -> install -> run ->
# concurrent abort, with the LED indicator and the switch readback exercised in the same session.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import threading
import time

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)

p.indicate({'state': 'recalibrating'})
print('CHAIN_LED %s' % J(p.indicate({'state': 'recalibrating'})))
print('CHAIN_PREP %s' % J({k: (r := p.perform({'op': 'prepare', 'request_id': 'r1', 'scene_id': 's1'})).get(k)
                           for k in ('ok', 'status', 'prepared')}))

plan = {'seed': 4242, 'level_dbfs': -22.0, 'captures': [{'capture_id': 't1'}]}
tr = p.perform({'op': 'training', 'request_id': 'r2', 'scene_id': 's1', 'plan': plan})
c0 = (tr.get('captures') or [{}])[0]
print('CHAIN_TRAIN %s' % J({k: tr.get(k) for k in ('ok', 'status')} |
                           {'source_sha256': (c0.get('source_sha256') or '')[:16],
                            'seed': c0.get('seed'), 'level': c0.get('level_dbfs'),
                            'valid_frames': c0.get('valid_frames')}))

va = p.perform({'op': 'validation', 'request_id': 'r3', 'scene_id': 's1', 'plan': plan})
c1 = (va.get('captures') or [{}])[0]
same = c0.get('source_sha256') == c1.get('source_sha256')
print('CHAIN_VALID %s' % J({k: va.get(k) for k in ('ok', 'status')} |
                           {'source_sha256': (c1.get('source_sha256') or '')[:16],
                            'seed': c1.get('seed'), 'independent_source': not same}))

ins = p.perform({'op': 'install', 'request_id': 'r4', 'scene_id': 's1',
                 'model_path': cfg['model_path'], 'run_gain_q12': 2303})
print('CHAIN_INSTALL %s' % J({k: ins.get(k) for k in ('ok', 'status', 'applies_at', 'taps')} |
                              {'model_sha256': (ins.get('model_sha256') or '')[:16],
                               'coefficients_sha256': (ins.get('coefficients_sha256') or '')[:16],
                               'hashes_distinct': ins.get('model_sha256') != ins.get('coefficients_sha256')}))

p.indicate({'state': 'quiet'})
run_res = {}


def do_run():
    run_res.update(p.perform({'op': 'run', 'request_id': 'r5', 'scene_id': 's1',
                              'seconds': 12.0, 'gain_q12': 2303, 'bypass': False}))


t = threading.Thread(target=do_run)
t.start()
time.sleep(2.0)
print('CHAIN_POLL_RUNNING %s' % J({k: p.poll().get(k) for k in ('ok', 'effective_mode', 'protected')}))
t0 = time.monotonic()
ab = p.abort()
print('CHAIN_ABORT %s' % J({k: ab.get(k) for k in ('ok', 'muted', 'quiescent', 'elapsed_ms')} |
                           {'abort_call_ms': round((time.monotonic() - t0) * 1000, 1)}))
t.join(timeout=30)
print('CHAIN_RUN_AFTER_ABORT %s' % J({k: run_res.get(k) for k in ('ok', 'status', 'elapsed_seconds')}))
print('CHAIN_FINAL_MODE %s' % p.poll().get('effective_mode'))
PY
