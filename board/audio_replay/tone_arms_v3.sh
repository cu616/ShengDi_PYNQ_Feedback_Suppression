#!/bin/bash
# Steady-state three-point tone measurement at one frequency, with a SAME-ROUND manifest.
# C's 2026-10-27 review (item 4) requires the analysis to pair files that provably come from the
# same round and to check identity, window and input validity before computing anything.
# This script writes <package>/tone_round.json listing exactly the three files it produced;
# tone_analyze.sh refuses to pair anything else.
#
#   open   : digital gain forced to 0 -> the acoustic path alone (no loop)
#   bypass : loop closed, candidate coefficients loaded but NOT subtracted
#   cancel : loop closed, candidate subtraction active
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
TONE_HZ = 322.0
AMP = 0.15
ROUND = time.time_ns()
CONF = sys.argv[1]
n = int(2.0 * RATE)
t = np.arange(n) / RATE
pcm = np.round(AMP * np.sin(2*np.pi*TONE_HZ*t) * 32767).astype(np.int16)
entries = []


def run(tag, bypass, direct_only):
    out = DIR / ('tone_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), pcm, bypass=bypass, zero_coeff=False,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    ok = out.is_file()
    print('TONE %-6s %s' % (tag, err or ('ok' if ok else 'no capture')))
    entries.append(dict(tag=tag, path=str(out), error=err, exists=ok))
    return ok


# Stop at the FIRST failing arm: a round with a missing arm cannot produce a depth, so there is no
# point in running the rest (C 2026-10-28: a failed first item must not be followed by more runs).
for tag, bypass, direct_only in (('open', False, True), ('bypass', True, False),
                                 ('cancel', False, False)):
    if not run(tag, bypass, direct_only):
        print('TONE_ROUND_ABORTED at %s: not running the remaining arms' % tag)
        break

manifest = dict(round_id=ROUND, tone_hz=TONE_HZ, amplitude_fs=AMP, operator_confirmation=CONF,
                created=time.time(), files=entries)
(DIR / 'tone_round.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('TONE_ROUND_WRITTEN', DIR / 'tone_round.json', 'round', ROUND)
PY
