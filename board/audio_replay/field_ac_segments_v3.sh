#!/bin/bash
# Segments A and C of B's 86061a7 comparison design, at the agreed working point.
# Segment B (g = -3, deliberately made to howl) is NOT in this script: it needs an explicit
# authorisation, a person at the amplifier switch and a hard 2 s cap.
#
#   A (safe level, g = -8 dB): 322 Hz three-point, then speech 3 takes per arm
#   C (speech arms, same g):   same sentence, same distance, three takes per arm
#
# Rules enforced here (C 2026-10-27 item 3 + B 86061a7 pitfalls):
#   * operator confirmation token required; the script never creates one
#   * the quiet gate comes FIRST; a failed gate ends everything
#   * a protection stop or a failed recovery ends the branch immediately
#   * bit22 is re-measured at every arm, not only at the start
#   * the bypass arm's microphone runs 4.76 dB hotter, so bypass is recorded separately when it rails
#   * the stop reason is recorded verbatim; "stopped by input full scale" is not "howling detected"
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
GAIN_DB = -8.0
CONF = sys.argv[1]
rows = []


def run(tag, pcm, zero, bypass, seconds, direct_only=False):
    out = DIR / ('ac_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), pcm, bypass=bypass, zero_coeff=zero,
                     gain_db=GAIN_DB, seconds=seconds, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('RUN %-10s FAILED %s' % (tag, err))
        return None
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    st = int(meta.get('capture_status') or 0)
    sp = out.with_suffix('.status.json')
    rec = None
    if sp.is_file():
        try:
            rec = bool(json.loads(sp.read_text()).get('recovery_ok'))
        except Exception:
            rec = None
    row = dict(tag=tag, stop=meta.get('stop_reason'), frames=int(meta.get('completed_frames') or 0),
               mic=20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
               peak=20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
               fs=int(np.count_nonzero(np.abs(mic) >= 0.999)), bit22=(st >> 22) & 1,
               recovery_ok=rec, rsat=meta.get('residual_saturations'),
               psat=meta.get('prediction_saturations'), wide=(meta.get('verification') or {}).get('wide_residual_frames'),
               bitexact=(meta.get('verification') or {}).get('bit_exact'), path=str(out))
    rows.append(row)
    print('RUN %-10s stop=%-11s frames=%6d mic=%6.1f peak=%6.1f fs=%d bit22=%d rsat=%s wide=%s rec=%s'
          % (row['tag'], row['stop'], row['frames'], row['mic'], row['peak'], row['fs'], row['bit22'],
             row['rsat'], row['wide'], row['recovery_ok']))
    return row


def ok(row):
    return (row is not None and row['stop'] == 'completed' and row['bit22'] == 0
            and row['fs'] == 0 and row['recovery_ok'] is True)


gate = run('gate', np.zeros(2000, dtype=np.int16), True, False, 0.6, direct_only=True)
if not gate or not (-60.0 < gate['peak'] < -6.0):
    print('GATE_FAIL: nothing else runs')
    raise SystemExit(0)

# ---- A: 322 Hz three-point (open / bypass / cancel), one round --------------------------------
n = int(2.0 * RATE)
t = np.arange(n) / RATE
tone = np.round(0.15 * np.sin(2 * np.pi * 322.0 * t) * 32767).astype(np.int16)
round_files = []
for tag, zero, bypass, direct in (('open', False, False, True), ('bypass', False, True, False),
                                  ('cancel', False, False, False)):
    r = run('tone_' + tag, tone, zero, bypass, 2.2, direct_only=direct)
    if not ok(r):
        print('BRANCH_STOPPED in the tone round at %s' % tag)
        raise SystemExit(0)
    round_files.append(dict(tag=tag, path=r['path'], exists=True, error=None))

manifest = dict(round_id=time.time_ns(), tone_hz=322.0, amplitude_fs=0.15,
                operator_confirmation=CONF, created=time.time(), files=round_files)
(DIR / 'tone_round.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('TONE_ROUND_WRITTEN', DIR / 'tone_round.json')

# ---- C: speech arms, three takes each, same sentence and distance -----------------------------
print('SPEECH cue: same sentence, three takes per arm, keep the level steady')
for arm, zero in (('zero', True), ('cand', False)):
    for take in range(3):
        r = run('speech_%s_%d' % (arm, take), np.zeros(1000, dtype=np.int16), zero, False, 10.0)
        if not ok(r):
            print('BRANCH_STOPPED in the speech arms at %s take %d (stop=%s bit22=%s)'
                  % (arm, take, 'n/a' if r is None else r['stop'],
                     'n/a' if r is None else r['bit22']))
            raise SystemExit(0)

print('AC_SUMMARY %d runs, all completed with bit22=0' % len(rows))
for r in rows:
    print('  %-12s mic=%6.1f peak=%6.1f' % (r['tag'], r['mic'], r['peak']))
PY
echo "SEGMENT_B not run: needs an explicit authorisation, a person at the amplifier switch and a hard 2 s cap"
