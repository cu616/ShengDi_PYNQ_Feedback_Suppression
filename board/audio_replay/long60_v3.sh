#!/bin/bash
# 60-second continuous run on the final candidate (v3 driver + v3 bitstream).
# Configuration is the successful baseline: the PHONE plays the recording through the air, the board
# injects silence, zero coefficients, PL -8 dB, Codec 40, speaker 100 cm side-facing. The point is
# continuity plus a listening record, not a gain result.
# If the input hits full scale the new driver stops immediately with stop_reason="input_clip";
# that is the correct behaviour and has to be reported as such, not worked around.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
echo "LONG60 start (60 s, no injected source; the phone in the room is the source)"
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
out = DIR / ('long60_%d.npz' % time.time_ns())
err = None
t0 = time.time()
try:
    replay_trial(str(out), 'room_v1_20261026b', str(DIR / 'rewired_512_20261026.json'),
                 np.zeros(1000, dtype=np.int16), bypass=False, zero_coeff=True, gain_db=-8.0,
                 seconds=60.0, hp_volume=40, speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    err = repr(exc)[:240]
wall = time.time() - t0
print('LONG60 error:', err, ' wall_s=%.1f' % wall)
if out.is_file():
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    print('LONG60 stop=%s completed=%s capture_status=0x%08x bit22=%d rsat=%s psat=%s gsat=%s msat=%s'
          % (meta.get('stop_reason'), meta.get('completed_frames'), st, (st >> 22) & 1,
             meta.get('residual_saturations'), meta.get('prediction_saturations'),
             meta.get('gain_saturations'), meta.get('mix_saturations')))
    print('LONG60 mic_rms=%s mic_peak=%s full_scale_samples=%s bit_exact=%s wall_s=%.1f'
          % (meta.get('mic_rms_dbfs'), meta.get('mic_peak_dbfs'), meta.get('mic_full_scale_samples'),
             (meta.get('verification') or {}).get('bit_exact'), wall))
    ok = meta.get('stop_reason') == 'completed' and int(meta.get('completed_frames') or 0) >= 2929687
    print('LONG60_VERDICT', 'PASS' if ok else 'NOT COMPLETED (report as is)')
else:
    print('LONG60_VERDICT FAIL (no capture)')
PY
