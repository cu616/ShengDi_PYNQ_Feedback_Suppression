#!/bin/bash
# Steady-state two-arm window on the v3 package. Gate -> zero arm -> candidate arm.
#
# Rules this script enforces (C 2026-10-27 review, item 3):
#   * an operator confirmation must exist BEFORE arming; the script never invents one
#     (create /home/xilinx/OPERATOR_READY in the same turn the human says go; it is consumed here);
#   * the quiet gate runs FIRST and its failure stops the whole branch;
#   * a protection stop (guard / input_clip) in one arm stops the next arm;
#   * the level is read from /home/xilinx/stationary_level_db.txt (default -8) so a level change is
#     a recorded file, not an edit made on the fly.
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
LEVEL=$(cat /home/xilinx/stationary_level_db.txt 2>/dev/null || echo -8)
echo "STATIONARY level=${LEVEL} dBFS peak"
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$LEVEL" "$CONF" <<'PY'
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
LEVEL = float(sys.argv[1])
CONF = sys.argv[2]


def run(tag, pcm, zero, seconds, direct_only=False):
    out = DIR / ('stat_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), pcm, bypass=False, zero_coeff=zero,
                     gain_db=-8.0, seconds=seconds, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('ARM %-5s FAILED %s' % (tag, err))
        return None
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    st = int(meta.get('capture_status') or 0)
    spec = np.abs(np.fft.rfft(mic * np.hanning(len(mic))))
    f = np.fft.rfftfreq(len(mic), 1.0 / RATE)
    band = (f >= 300) & (f <= 360)
    allb = (f >= 50) & (f <= 20000)
    share = float(np.sum(spec[band]**2) / max(float(np.sum(spec[allb]**2)), 1e-30))
    # recovery_ok is read from the status file: a failed restore forbids any further run.
    st_path = out.with_suffix('.status.json')
    recovery_ok = None
    if st_path.is_file():
        try:
            recovery_ok = bool(json.loads(st_path.read_text()).get('recovery_ok'))
        except Exception:
            recovery_ok = None
    row = dict(tag=tag, stop=meta.get('stop_reason'),
               frames=int(meta.get('completed_frames') or 0),
               mic=20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
               peak=20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
               fs=int(np.count_nonzero(np.abs(mic) >= 0.999)),
               bit22=(st >> 22) & 1, share=share, recovery_ok=recovery_ok,
               rsat=meta.get('residual_saturations'), psat=meta.get('prediction_saturations'),
               gsat=meta.get('gain_saturations'), msat=meta.get('mix_saturations'),
               conf=CONF, path=str(out))
    print('ARM %-5s stop=%-11s frames=%6d mic=%6.1f peak=%6.1f fs=%d bit22=%d share=%.4f '
          'rsat=%s psat=%s recovery_ok=%s'
          % (row['tag'], row['stop'], row['frames'], row['mic'], row['peak'], row['fs'],
             row['bit22'], row['share'], row['rsat'], row['psat'], row['recovery_ok']))
    return row


def admissible(row):
    return (row is not None and row['stop'] == 'completed' and row['bit22'] == 0
            and row['fs'] == 0 and row['recovery_ok'] is True)


gate = run('gate', np.zeros(2000, dtype=np.int16), True, 0.6, direct_only=True)
if gate is None or not (-60.0 < gate['peak'] < -6.0):
    print('GATE_FAIL: branch stopped, no arm was run (peak %s)'
          % ('n/a' if gate is None else '%.1f dBFS' % gate['peak']))
    raise SystemExit(0)

n = int(2.0 * RATE)
rng = np.random.default_rng(4242)
x = rng.standard_normal(n)
x = x / max(np.max(np.abs(x)), 1e-9) * (10 ** (LEVEL / 20))
pcm = np.round(x * 32767).astype(np.int16)

a = run('zero', pcm, True, 2.2)
if not admissible(a):
    print('BRANCH_STOPPED after the zero arm (stop=%s bit22=%s)'
          % ('n/a' if a is None else a['stop'], 'n/a' if a is None else a['bit22']))
    raise SystemExit(0)
b = run('cand', pcm, False, 2.2)
if not admissible(b):
    print('BRANCH_STOPPED after the candidate arm (stop=%s bit22=%s)'
          % ('n/a' if b is None else b['stop'], 'n/a' if b is None else b['bit22']))
    raise SystemExit(0)
print('STATIONARY_SUMMARY share_zero=%.4f share_cand=%.4f delta_db=%+.1f level=%.1f conf=%s'
      % (a['share'], b['share'], 10*np.log10(max(a['share'], 1e-12)) -
         10*np.log10(max(b['share'], 1e-12)), LEVEL, CONF))
PY
