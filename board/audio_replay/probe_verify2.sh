#!/bin/bash
# Why did the verify arms fail? Run one arm against the newest candidate and print the full error.
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
cands = sorted(D.glob('model_candidate_*.json'), key=lambda p: p.stat().st_mtime)
cand = cands[-1] if cands else None
print('candidate:', cand.name if cand else 'none')
if cand:
    m = json.loads(cand.read_text(encoding='utf-8'))
    c = m.get('coefficients_q20') or m.get('coefficients') or []
    import numpy as np
    arr = np.asarray(c, dtype=np.float64) / float(1 << 20)
    print('taps=%d  max|h|=%.4f  L1=%.2f' % (len(arr), float(np.max(np.abs(arr))), float(np.sum(np.abs(arr)))))
    RATE = 48828.125
    n = int(2.0 * RATE)
    tone = np.rint(0.15 * np.sin(2 * np.pi * 322.0 * np.arange(n) / RATE) * 32767).astype(np.int16)
    out = D / 'probe_verify_open2.npz'
    out.unlink(missing_ok=True)
    try:
        replay_trial(str(out), 'room_v1_20261026b', str(cand), tone, bypass=False, zero_coeff=False,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
        print('RUN_OK')
    except Exception as exc:
        print('RUN_RAISED', type(exc).__name__, repr(exc)[:220])
    if out.is_file():
        meta = json.loads(str(np.load(str(out))['metadata_json']))
        print('stop=%s frames=%s capture_status=0x%08x'
              % (meta.get('stop_reason'), meta.get('completed_frames'),
                 int(meta.get('capture_status') or 0)))
PY
