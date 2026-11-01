#!/bin/bash
# Measured capabilities receipt for the v2 adapter.
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
out = {'caps': p.capabilities(), 'identity_before': p.identity()}
out['prepare'] = {k: (r := p.perform({'op': 'prepare', 'request_id': 'rc', 'scene_id': 's-receipt'})).get(k)
                  for k in ('ok', 'status', 'prepared')}
out['mute'] = p.mute()
out['poll'] = {k: p.poll().get(k) for k in ('ok', 'protected', 'effective_mode', 'saturation')}
out['identity_after'] = p.identity()
print('RECEIPT_JSON ' + json.dumps(out, ensure_ascii=False))
PY
