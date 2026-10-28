#!/bin/bash
# Re-run the two checks that need no person against the EXACT delivered hashes:
#   1  mixed bitstream/driver refused before the overlay is downloaded
#   2  silent run still completes and still writes the full identity into status.json
# Plus: the on-board package hashes are printed so the record shows which files ran.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
L=/home/xilinx/jupyter_notebooks/base/audio/audio_live
T=/home/xilinx/jupyter_notebooks/base/audio/audio_mismatch_test

echo "=== package identity on the board ==="
sha256sum $D/replay_trial.py $D/replay_tools.py $D/test_verify_replay_v3.py $D/audio_replay.bit $D/audio_replay.hwh

echo "=== 1. mixed pair refusal ==="
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
    print('MIXED_PAIR accepted (= FAIL)')
except RuntimeError as exc:
    print('MIXED_PAIR refused' if 'does not match this driver' in str(exc) else
          'MIXED_PAIR refused for another reason: ' + str(exc)[:120],
          '(= PASS)' if 'does not match this driver' in str(exc) else '')
PY
rm -rf $T

echo "=== 2. silent run with the delivered driver ==="
cd $D
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json, time
from pathlib import Path
import numpy as np
from replay_trial import replay_trial
DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
out = DIR / ('bringup3_%d.npz' % time.time_ns())
err = None
try:
    replay_trial(str(out), 'room_v1_20261026b', str(DIR / 'rewired_512_20261026.json'),
                 np.zeros(1000, dtype=np.int16), zero_coeff=True, gain_db=-14.0, seconds=1.2,
                 hp_volume=40, speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    err = repr(exc)[:200]
print('BRINGUP3 error:', err)
if out.is_file():
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    print('BRINGUP3 stop=%s frames=%s capture_status=0x%08x bit22=%d package=%s driver=%s '
          'tools=%s bit_exact=%s wide=%s partial=%s'
          % (meta.get('stop_reason'), meta.get('completed_frames'), st, (st >> 22) & 1,
             meta.get('package_version'), str(meta.get('driver_sha256'))[:8],
             str(meta.get('replay_tools_sha256', 'n/a'))[:8],
             (meta.get('verification') or {}).get('bit_exact'),
             (meta.get('verification') or {}).get('wide_residual_frames'),
             (meta.get('verification') or {}).get('wide_residual_count_partial')))
    st_path = out.with_suffix('.status.json')
    if st_path.is_file():
        s = json.loads(st_path.read_text())
        print('STATUS_IDENTITY has_capture_status=%s has_bit22=%s package=%s driver=%s bit=%s hwh=%s model=%s'
              % ('capture_status' in s, 'input_full_scale_seen' in s, s.get('package_version'),
                 str(s.get('driver_sha256'))[:8], str(s.get('bit_sha256'))[:8],
                 str(s.get('hwh_sha256'))[:8], str(s.get('model_sha256'))[:8]))
PY
