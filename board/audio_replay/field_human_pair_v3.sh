#!/bin/bash
# Human-speech two-arm window on the v3 package. Quiet gate -> zero arm -> candidate arm.
#
# Rules this script enforces (C 2026-10-27 review, item 3):
#   * an operator confirmation must exist BEFORE arming; the script never invents one
#     (create /home/xilinx/OPERATOR_READY in the same turn the human says go; it is consumed here);
#   * the QUIET gate runs BEFORE the person is asked to speak, never after;
#   * a failed gate or a protection stop (guard / input_clip) stops the rest of the branch;
#   * the injected source is silence: the person speaking is the source.
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
CONF = sys.argv[1]


def run(tag, zero, seconds, direct_only=False):
    out = DIR / ('human_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), np.zeros(1000, dtype=np.int16),
                     bypass=False, zero_coeff=zero, gain_db=-8.0, seconds=seconds, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True,
                     direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('HUMAN %-5s FAILED %s' % (tag, err))
        return None
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    st = int(meta.get('capture_status') or 0)
    st_path = out.with_suffix('.status.json')
    recovery_ok = None
    if st_path.is_file():
        try:
            recovery_ok = bool(json.loads(st_path.read_text()).get('recovery_ok'))
        except Exception:
            recovery_ok = None
    row = dict(tag=tag, zero=zero, stop=meta.get('stop_reason'),
               frames=int(meta.get('completed_frames') or 0),
               mic=20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
               peak=20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
               fs=int(np.count_nonzero(np.abs(mic) >= 0.999)), bit22=(st >> 22) & 1,
               recovery_ok=recovery_ok,
               rsat=meta.get('residual_saturations'), psat=meta.get('prediction_saturations'),
               gsat=meta.get('gain_saturations'), msat=meta.get('mix_saturations'),
               wide=(meta.get('verification') or {}).get('wide_residual_frames'),
               bitexact=(meta.get('verification') or {}).get('bit_exact'), conf=CONF, path=str(out))
    print('HUMAN %-5s stop=%-11s frames=%6d mic=%6.1f peak=%6.1f fs=%d bit22=%d rsat=%s psat=%s '
          'gsat=%s wide=%s bitexact=%s recovery_ok=%s'
          % (row['tag'], row['stop'], row['frames'], row['mic'], row['peak'], row['fs'],
             row['bit22'], row['rsat'], row['psat'], row['gsat'], row['wide'], row['bitexact'],
             row['recovery_ok']))
    return row


def admissible(row):
    return (row is not None and row['stop'] == 'completed' and row['bit22'] == 0
            and row['fs'] == 0 and row['recovery_ok'] is True)


gate = run('gate', True, 0.6, direct_only=True)
if gate is None or not (-60.0 < gate['peak'] < -6.0):
    print('GATE_FAIL: branch stopped before anyone was asked to speak (peak %s)'
          % ('n/a' if gate is None else '%.1f dBFS' % gate['peak']))
    raise SystemExit(0)

print('HUMAN_PAIR cue: speak the same sentence continuously for about 20 s from now')
a = run('zero', True, 6.0)
if not admissible(a):
    print('BRANCH_STOPPED after the zero arm (stop=%s bit22=%s)'
          % ('n/a' if a is None else a['stop'], 'n/a' if a is None else a['bit22']))
    raise SystemExit(0)
b = run('cand', False, 6.0)
if not admissible(b):
    print('BRANCH_STOPPED after the candidate arm (stop=%s bit22=%s)'
          % ('n/a' if b is None else b['stop'], 'n/a' if b is None else b['bit22']))
    raise SystemExit(0)
print('HUMAN_PAIR_SUMMARY zero_mic=%.1f cand_mic=%.1f delta=%+.1f dB conf=%s'
      % (a['mic'], b['mic'], b['mic'] - a['mic'], CONF))
PY
