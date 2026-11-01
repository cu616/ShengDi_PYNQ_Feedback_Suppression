#!/bin/bash
# Live amplification through the product entry: no injection, the voice comes from the microphone.
# Evidence that the DAC is driven: the played signal must be far above the (zero) injection.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json

import numpy as np

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)
db = lambda a: float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))

print('LIVE_PREP %s' % J({k: (r := p.perform({'op': 'prepare', 'request_id': 'r0', 'scene_id': 'live'})).get(k)
                          for k in ('ok', 'status', 'prepared')}))
print('LIVE_WARM %s' % J(p.warm_up()))

res = p.perform({'op': 'run', 'request_id': 'r1', 'scene_id': 'live',
                 'seconds': 30.0, 'gain_q12': 2303, 'bypass': False})
print('LIVE_RUN %s' % J({k: res.get(k) for k in ('ok', 'status', 'effective_mode', 'elapsed_seconds')}))

runs = sorted((p.run_root).glob('run_*.npz'))
if runs:
    with np.load(str(runs[-1])) as c:
        keys = list(c.keys())
        mic = np.asarray(c['microphone'], float)
        inj = np.asarray(c['source_pcm16'], float) if 'source_pcm16' in c else np.zeros(1)
        played = np.asarray(c['played'], float) if 'played' in c else None
        meta = json.loads(str(c['metadata_json']))
    print('LIVE_KEYS %s' % keys)
    print('LIVE_LEVEL mic=%.2f dBFS injection=%.2f dBFS' % (db(np.clip(mic, -1, 1)), db(inj / 32768.0)))
    if played is not None:
        print('LIVE_PLAYED %.2f dBFS  played_minus_mic=%+.2f dB'
              % (db(np.clip(played, -1, 1)), db(np.clip(played, -1, 1)) - db(np.clip(mic, -1, 1))))
    st = int(meta.get('capture_status') or 0)
    print('LIVE_STATUS bit22=%d pred=%s res=%s gain=%s stop=%s'
          % ((st >> 22) & 1, meta.get('prediction_saturations'), meta.get('residual_saturations'),
             meta.get('gain_saturations'), meta.get('stop_reason')))
print('LIVE_POLL %s' % J({k: p.poll().get(k) for k in ('protected', 'saturation', 'effective_mode')}))
p.mute()
PY
