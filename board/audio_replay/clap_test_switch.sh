#!/bin/bash
# Input full-scale stop check (captain 2026-10-28 key protection, C check item 2).
# direct_only sets the digital gain to 0, so nothing is played: this only listens to the microphone.
# A hand clap 2-3 cm from the microphone is the only way to drive the ADC to full scale on this
# hardware (the PS cannot drive the ADC directly).
# Expected: stop_reason="input_clip", capture_status bit22=1, evidence saved, codec muted,
# stock overlay restored (recovery_ok true).
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
cd $D || exit 1
echo "CLAP_TEST window 3 s, no output, start clapping now"
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
out = DIR / ('sw_clap_%d.npz' % time.time_ns())
err = None
try:
    replay_trial(str(out), 'room_v1_20261026b', str(DIR / 'rewired_512_20261026.json'),
                 np.zeros(1000, dtype=np.int16), bypass=False, zero_coeff=True, gain_db=-8.0,
                 seconds=3.0, hp_volume=40, speaker_confirmed=True,
                 local_capture_confirmed=True, direct_only=True)
except Exception as exc:
    err = repr(exc)[:220]

print('CLAP error:', err)
status_path = out.with_suffix('.status.json')
if out.is_file():
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    print('CLAP stop=%s frames=%s capture_status=0x%08x bit22=%d input_full_scale_seen=%s '
          'mic_peak_dbfs=%.1f mic_full_scale_samples=%s'
          % (meta.get('stop_reason'), meta.get('completed_frames'), st, (st >> 22) & 1,
             meta.get('input_full_scale_seen'), float(meta.get('mic_peak_dbfs') or -999),
             meta.get('mic_full_scale_samples')))
    ok = (meta.get('stop_reason') == 'input_clip' and (st >> 22) & 1 == 1)
    print('CLAP_VERDICT', 'PASS' if ok else 'FAIL (expected stop_reason=input_clip and bit22=1)')
else:
    print('CLAP_VERDICT FAIL (no capture)')
if status_path.is_file():
    st_json = json.loads(status_path.read_text())
    print('CLAP_RECOVERY recovery_ok=%s cleanup_errors=%s stop_reason=%s'
          % (st_json.get('recovery_ok'), st_json.get('cleanup_errors'), st_json.get('stop_reason')))
else:
    print('CLAP_RECOVERY status.json missing')
PY
