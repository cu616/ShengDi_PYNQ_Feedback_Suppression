#!/bin/bash
# One continuous take for the video: the codec starts MUTED, the audio path is armed for N seconds,
# then the codec is muted again by the driver. A single recording therefore covers
# "silence -> path on -> silence" with the real sound of the real configuration, which is exactly
# what a02 needs. Nothing here is staged and no threshold is relaxed for the camera.
#
# MODE comes from /home/xilinx/demo_mode.txt:
#   a02  20 s, zero coefficients, gain -8 dB   (real person speaking; ordinary amplification)
#   a05  60 s, zero coefficients, gain -8 dB   (continuous-run shot)
#
# Cue lines carry a wall-clock offset so the editor can line the take up with the recording, and so
# the person knows when to start and stop without anyone touching the board mid-shot.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
TOKEN=/home/xilinx/OPERATOR_READY
if [ ! -s "$TOKEN" ]; then
  echo "NO_OPERATOR_CONFIRMATION: refusing to arm (create $TOKEN first)"
  exit 3
fi
CONF=$(cat "$TOKEN"); rm -f "$TOKEN"
MODE=$(cat /home/xilinx/demo_mode.txt 2>/dev/null || echo a02)
echo "OPERATOR_CONFIRMATION: $CONF"
echo "DEMO_MODE: $MODE"
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$CONF" "$MODE" <<'PY'
import json
import sys
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MODEL = DIR / 'rewired_512_20261026.json'
FIXTURE = 'room_v1_20261026b'
CONF = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else 'a02'
SECONDS = {'a02': 20.0, 'a05': 60.0}.get(MODE)
if SECONDS is None:
    print('DEMO_FAIL unknown mode %r' % MODE)
    raise SystemExit(2)
T0 = time.monotonic()


def cue(text):
    print('CUE %7.2fs %s' % (time.monotonic() - T0, text))


def take(tag, seconds, zero, direct_only=False):
    out = DIR / ('demo_%s_%d.npz' % (tag, time.time_ns()))
    cue('arm %s (path goes live now)' % tag)
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), np.zeros(1000, dtype=np.int16), bypass=False,
                     zero_coeff=zero, gain_db=-8.0, seconds=seconds, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    cue('muted again (%s)' % tag)
    if not out.is_file():
        print('DEMO_FAIL %s produced no capture: %s' % (tag, err))
        return None
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    mic = np.asarray(np.load(str(out))['microphone'], dtype=np.float64)
    rec = dict(tag=tag, stop=meta.get('stop_reason'), bit22=(st >> 22) & 1,
               frames=int(meta.get('completed_frames') or 0),
               mic=20 * np.log10(max(float(np.sqrt(np.mean(mic ** 2))), 1e-12)),
               peak=20 * np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
               path=str(out))
    print('DEMO_RUN %-4s stop=%-11s frames=%7d mic=%6.1f peak=%6.1f bit22=%d'
          % (rec['tag'], rec['stop'], rec['frames'], rec['mic'], rec['peak'], rec['bit22']))
    return rec


# Pre-check, not part of the take: the same quiet gate the field scripts use, so a bad room level is
# caught before the camera rolls. It produces no sound.
gate = take('gate', 0.6, True, direct_only=True)
if not gate or gate['stop'] != 'completed' or gate['bit22'] or not (-60.0 < gate['peak'] < -6.0):
    print('DEMO_FAIL gate: peak %s -- fix the room before filming'
          % ('n/a' if not gate else '%.1f dBFS' % gate['peak']))
    raise SystemExit(0)
cue('gate ok, rolling: speak naturally when you are ready')

rec = take(MODE, SECONDS, True)
print('DEMO_SUMMARY %s' % json.dumps(rec, ensure_ascii=False))
if rec and (rec['stop'] != 'completed' or rec['bit22']):
    print('DEMO_NOTE the take stopped early (stop=%s bit22=%s); keep the file as a failed take, '
          'do not present it as a success' % (rec['stop'], rec['bit22']))
PY
