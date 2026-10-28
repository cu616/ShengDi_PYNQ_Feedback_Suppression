#!/bin/bash
# SUPERSEDED by field_human_pair_v3.sh (2026-10-28): that script gates the branch, requires an operator
# confirmation token and stops after a protection event. This file is kept only for the
# 2026-10-27 evidence trail and must not be used for new runs.
# SUPERSEDED by field_human_pair_v3.sh (2026-10-28): that script gates the branch, requires an operator
# confirmation token and stops after a protection event. This file is kept only for the
# 2026-10-27 evidence trail and must not be used for new runs.
# One human-speech arm on the v3 (wide-residual) package.
# Usage: bash field_human_v3.sh <zero|cand>
# The injected source is SILENT (the person is the source), so the DAC carries only gain(residual).
# Prints the gate, the arm, and the post-checks that decide whether the trial is admissible:
#   capture_status bit22 (input full scale), microphone full-scale samples, all four saturation
#   counters, stop reason, and the arithmetic check (wide residual count + bit-exactness).
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
ARM=zero
DIR=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $DIR || exit 1
echo "HUMAN_ARM $ARM  (speak one sentence now; window ~6 s)"
/usr/local/share/pynq-venv/bin/python - "$ARM" <<'PY'
import json
import sys
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MODEL = DIR / 'rewired_512_20261026.json'
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
arm = sys.argv[1]
zero = arm == 'zero'


def run(tag, pcm, seconds, zero_coeff, direct_only):
    out = DIR / ('human_%s_%s_%d.npz' % (tag, arm, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), pcm, bypass=False, zero_coeff=zero_coeff,
                     gain_db=-8.0, seconds=seconds, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('HUMAN %-5s FAILED %s' % (tag, err), flush=True)
        return None
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    st = int(meta.get('capture_status') or 0)
    ver = meta.get('verification') or {}
    row = dict(tag=tag, stop=meta.get('stop_reason'), frames=meta.get('completed_frames'),
               mic_rms=20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
               mic_peak=20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
               full_scale=int(np.count_nonzero(np.abs(mic) >= 0.999)),
               bit22=(st >> 22) & 1, bit21=(st >> 21) & 1, bit20=(st >> 20) & 1,
               bit19=(st >> 19) & 1, bit18=(st >> 18) & 1,
               rsat=meta.get('residual_saturations'), psat=meta.get('prediction_saturations'),
               gsat=meta.get('gain_saturations'), msat=meta.get('mix_saturations'),
               wide=ver.get('wide_residual_frames'), bitexact=ver.get('bit_exact'),
               src_ok=meta.get('source_schedule_verified'), path=str(out))
    print('HUMAN %-5s stop=%-9s frames=%6d mic=%6.1f peak=%6.1f fs=%d bit22=%d rsat=%d psat=%d '
          'gsat=%d msat=%d wide=%s bitexact=%s'
          % (row['tag'], row['stop'], int(row['frames'] or 0), row['mic_rms'], row['mic_peak'],
             row['full_scale'], row['bit22'], row['rsat'], row['psat'], row['gsat'], row['msat'],
             row['wide'], row['bitexact']), flush=True)
    return row


# Gate: zero output, short, so the room state is recorded for this arm.
gate = run('gate', np.zeros(2000, dtype=np.int16), 0.6, True, True)
print('HUMAN_ARM %s : start speaking now, keep going for 30 s' % arm, flush=True)
row = run('speech', np.zeros(1000, dtype=np.int16), 6.0, zero, False)
if row:
    ok = (row['full_scale'] == 0 and row['bit22'] == 0 and row['stop'] == 'completed')
    print('HUMAN_VERDICT %s : admissible=%s (needs fs=0, bit22=0, completed; mic peak %.1f dBFS)'
          % (arm, ok, row['mic_peak']), flush=True)
PY
