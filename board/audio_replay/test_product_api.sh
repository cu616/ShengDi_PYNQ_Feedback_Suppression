#!/bin/bash
# Contract self-test for recal-product-v1 on real hardware.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}

p = create_product(cfg)
print('PROD_CAP %s' % json.dumps(p.capabilities(), ensure_ascii=False)[:300])
print('PROD_ID %s' % json.dumps(p.identity(), ensure_ascii=False)[:300])
print('PROD_POLL %s' % json.dumps(p.poll(), ensure_ascii=False)[:300])
print('PROD_INDICATE %s' % json.dumps(p.indicate({'state': 'ready'}), ensure_ascii=False))
print('PROD_INDICATE_IDLE %s' % json.dumps(p.indicate({'pattern': '0000'}), ensure_ascii=False))
print('PROD_MUTE %s' % json.dumps(p.mute(), ensure_ascii=False))
print('PROD_ABORT %s' % json.dumps(p.abort(), ensure_ascii=False))

prep = p.perform({'op': 'prepare', 'request_id': 'r1', 'scene_id': 's1'})
print('PROD_PREPARE %s' % json.dumps({k: prep.get(k) for k in ('ok', 'status', 'prepared')}, ensure_ascii=False))

inp = p.perform({'op': 'input', 'request_id': 'r2', 'scene_id': 's1',
                 'plan': {'captures': [{'seconds': 1.5, 'capture_id': 'i1',
                                        'content_kind': 'onboard_excitation'}]}})
print('PROD_INPUT %s' % json.dumps({'ok': inp.get('ok'), 'status': inp.get('status'),
                                    'valid_first_frame': inp.get('valid_first_frame'),
                                    'capture': (inp.get('captures') or [{}])[0]}, ensure_ascii=False)[:400])
print('PROD_FINAL_MUTE %s' % json.dumps(p.mute(), ensure_ascii=False))
PY
