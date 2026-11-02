#!/bin/bash
# Bypass the product state machine (and its stage timeout) to hear live amplification directly.
# The product service owns the FPGA while it runs, so it must be stopped first and restarted after.
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export PYTHONUNBUFFERED=1
echo '=== stop service ==='
echo xilinx | sudo -S systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np

from hw_api import create_product

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
p = create_product({'package_dir': D, 'fixture': 'room_v1_20261026b', 'hp_volume': 40,
                    'aux_db': 0.0, 'model_path': D + '/model_recalibrated.json',
                    'run_dir_root': D + '/bypass_runs'})
J = lambda d: json.dumps(d, ensure_ascii=False)

print('BYPASS_PREP %s' % J({k: (r := p.perform({'op': 'prepare', 'request_id': 'b0', 'scene_id': 'bypass'})).get(k)
                            for k in ('ok', 'status')}))
print('BYPASS_SPEAK_NOW talk continuously for 30 s')
r = p.perform({'op': 'run', 'request_id': 'b1', 'scene_id': 'bypass',
               'seconds': 30.0, 'gain_q12': 2303, 'bypass': False})
print('BYPASS_RUN %s' % J({k: r.get(k) for k in ('ok', 'status', 'effective_mode', 'audio_frames',
                                                 'elapsed_seconds', 'wall_seconds')}))
runs = sorted(Path(D + '/bypass_runs').glob('run_*.npz'))
if runs:
    with np.load(str(runs[-1])) as c:
        mic = np.asarray(c['microphone'], float)
        ref = np.asarray(c['reference'], float)
        db = lambda a: float(20 * np.log10(max(np.sqrt(np.mean(a ** 2)), 1e-12)))
        print('BYPASS_LEVEL ref=%.2f dBFS mic=%.2f dBFS full_scale=%d'
              % (db(ref), db(mic), int((np.abs(mic) >= 0.999).sum())))
    print('BYPASS_FILE %s' % runs[-1])
p.mute()
PY
echo '=== start service ==='
echo xilinx | sudo -S systemctl start shengdi-product.service 2>&1 | tail -1
sleep 5
systemctl is-active shengdi-product.service
