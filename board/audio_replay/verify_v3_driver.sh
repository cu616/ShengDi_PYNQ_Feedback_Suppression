#!/bin/bash
# Two checks that need no person and make no sound:
#   1  mixed bitstream/driver must be refused BEFORE the overlay is downloaded
#   2  the new driver still completes a normal silent run (no input_clip, evidence saved)
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
L=/home/xilinx/jupyter_notebooks/base/audio/audio_live
T=/home/xilinx/jupyter_notebooks/base/audio/audio_mismatch_test

echo "=== 1. mixed pair refusal (v2 bitstream + v3 driver) ==="
rm -rf $T && mkdir -p $T
cp $D/replay_trial.py $D/replay_tools.py $D/closed_tools.py $D/residual_tools.py $T/
cp $L/audio_replay.bit $L/audio_replay.hwh $T/
cp $D/rewired_512_20261026.json $T/
cd $T && /usr/local/share/pynq-venv/bin/python - <<'PY'
import numpy as np
from replay_trial import replay_trial
try:
    replay_trial('/home/xilinx/jupyter_notebooks/base/audio/audio_mismatch_test/probe.npz',
                 'room_v1_20261026b',
                 '/home/xilinx/jupyter_notebooks/base/audio/audio_mismatch_test/rewired_512_20261026.json',
                 np.zeros(1000, dtype=np.int16), gain_db=-14.0, seconds=1.0, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True)
    print('MIXED_PAIR accepted (= FAIL: it started)')
except RuntimeError as exc:
    text = str(exc)
    if 'does not match this driver' in text:
        print('MIXED_PAIR refused before start (= PASS)')
        print('   message:', text[:110])
    else:
        print('MIXED_PAIR refused for another reason (= UNKNOWN):', text[:140])
except Exception as exc:
    print('MIXED_PAIR other error (= CHECK):', repr(exc)[:140])
PY
rm -rf $T

echo "=== 2. new driver, silent run ==="
cd $D
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json, time
from pathlib import Path
import numpy as np
from replay_trial import replay_trial
DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
out = DIR / ('bringup2_%d.npz' % time.time_ns())
err = None
try:
    replay_trial(str(out), 'room_v1_20261026b', str(DIR / 'rewired_512_20261026.json'),
                 np.zeros(1000, dtype=np.int16), zero_coeff=True, gain_db=-14.0, seconds=1.2,
                 hp_volume=40, speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    err = repr(exc)[:200]
print('BRINGUP2 error:', err)
if out.is_file():
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    print('BRINGUP2 stop=%s frames=%s capture_status=0x%08x bit22=%d input_full_scale_seen=%s '
          'rsat=%s psat=%s bit_exact=%s driver_bit=%s'
          % (meta.get('stop_reason'), meta.get('completed_frames'), st, (st >> 22) & 1,
             meta.get('input_full_scale_seen'), meta.get('residual_saturations'),
             meta.get('prediction_saturations'), (meta.get('verification') or {}).get('bit_exact'),
             str(meta.get('bit_sha256'))[:8]))
else:
    print('BRINGUP2 NO CAPTURE')
PY
