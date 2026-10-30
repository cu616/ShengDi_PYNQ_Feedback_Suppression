#!/bin/bash
# Four alternating arms with the same injected source, for a listener comparison that does not
# rely on memory: zero / candidate / zero / candidate, two seconds each, minimum possible gap.
# The source is the board's own fixed-seed noise, so every segment is the same content.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
TOKEN=/home/xilinx/OPERATOR_READY
if [ ! -s "$TOKEN" ]; then echo "NO_OPERATOR_CONFIRMATION"; exit 3; fi
CONF=$(cat "$TOKEN"); rm -f "$TOKEN"
echo "OPERATOR_CONFIRMATION: $CONF"
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$CONF" <<'PY'
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
LEVEL_DB = float((DIR / 'stationary_level_db.txt').read_text().strip()) if (DIR / 'stationary_level_db.txt').is_file() else -8.0
CONF = sys.argv[1]
# fixed seed: every segment carries the SAME noise, which is what makes this a fair A/B
rng = np.random.default_rng(4242)
noise = rng.standard_normal(int(2.0 * RATE))
noise = (noise / max(np.max(np.abs(noise)), 1e-9) * (10 ** (LEVEL_DB / 20.0)) * 32767.0)
source = np.rint(noise).astype(np.int16)
rows = []


def run(tag, zero):
    out = DIR / ('alt_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), source, bypass=False, zero_coeff=zero,
                     gain_db=-8.0, seconds=2.4, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True)
    except Exception as exc:
        err = repr(exc)[:160]
    if not out.is_file():
        print('ARM %-8s FAILED %s' % (tag, err))
        return None
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    row = dict(tag=tag, stop=meta.get('stop_reason'), bit22=(st >> 22) & 1,
               frames=int(meta.get('completed_frames') or 0))
    rows.append(row)
    print('ARM %-8s stop=%-11s bit22=%d frames=%d' % (tag, row['stop'], row['bit22'], row['frames']))
    return row


gate = run('gate', True)
if not gate or gate['stop'] != 'completed' or gate['bit22']:
    print('GATE_FAIL: not running the comparison')
    raise SystemExit(0)

# alternate so the two conditions are heard back to back: Z C Z C
print('ALT cue: four 2 s segments, zero/candidate alternating, same noise every time')
for i, zero in enumerate((True, False, True, False)):
    r = run('zero_%d' % i if zero else 'cand_%d' % i, zero)
    if not r or r['stop'] != 'completed' or r['bit22']:
        print('ABORTED at segment %d: it was stopped (stop=%s bit22=%s)'
              % (i, 'n/a' if not r else r['stop'], 'n/a' if not r else r['bit22']))
        raise SystemExit(0)
print('ALT_SUMMARY %d segments, all completed, bit22=0, level=%s dBFS' % (len(rows), LEVEL_DB))
PY
