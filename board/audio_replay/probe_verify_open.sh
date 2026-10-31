#!/bin/bash
# Focused probe: run ONE verify arm with the multitone-refit candidate and print the full exception.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import traceback
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
cand = D / 'model_candidate_20250511-105305.rejected.json'
print('candidate exists:', cand.is_file(), 'bytes', cand.stat().st_size if cand.is_file() else 0)
model = json.loads(cand.read_text(encoding='utf-8'))
coef = model.get('coefficients_q20') or model.get('coefficients')
print('coefficients len:', len(coef) if coef else None,
      'min', min(coef) if coef else None, 'max', max(coef) if coef else None)

RATE = 48828.125
n = int(2.0 * RATE)
tone = np.rint(0.15 * np.sin(2 * np.pi * 322.0 * np.arange(n) / RATE) * 32767).astype(np.int16)
out = D / 'probe_verify_open.npz'
try:
    replay_trial(str(out), 'room_v1_20261026b', str(cand), tone, bypass=False, zero_coeff=False,
                 gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                 local_capture_confirmed=True, direct_only=True)
    print('RUN_OK')
except Exception as exc:
    print('RUN_RAISED', type(exc).__name__, repr(exc)[:200])
    traceback.print_exc()
if out.is_file():
    cap = np.load(str(out))
    print('npz keys:', cap.files)
    meta = json.loads(str(cap['metadata_json']))
    print('stop=%s frames=%s' % (meta.get('stop_reason'), meta.get('completed_frames')))
PY
