#!/bin/bash
# Segments A and C of B's 86061a7 comparison design, at the agreed working point.
# MODE comes from /home/xilinx/ac_mode.txt: "tone" (default) or "speech", so the two parts can be
# cued separately. Segment B (g = -3, deliberately made to howl) is NOT here on purpose.
#
#   tone   : quiet gate -> 322 Hz three-point (open / bypass / cancel), writes tone_round.json
#   speech : quiet gate -> speech arms, three takes per arm (zero, then candidate)
#
# Rules enforced: operator token required (never created here); gate first; a protection stop or a
# failed recovery ends the branch; bit22 is re-read at every arm; the stop reason is recorded
# verbatim, and "stopped by input full scale" is never written as "howling detected".
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
MODE=$(cat /home/xilinx/ac_mode.txt 2>/dev/null || echo tone)
echo "OPERATOR_CONFIRMATION: $CONF"
echo "AC_MODE: $MODE"
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
RATE = 48828.125
GAIN_DB = -8.0
CONF = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else 'tone'
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
        print('RUN %-12s FAILED %s' % (tag, err))
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
               psat=meta.get('prediction_saturations'),
               wide=(meta.get('verification') or {}).get('wide_residual_frames'),
               bitexact=(meta.get('verification') or {}).get('bit_exact'), path=str(out))
    rows.append(row)
    print('RUN %-12s stop=%-11s frames=%6d mic=%6.1f peak=%6.1f fs=%d bit22=%d rsat=%s wide=%s rec=%s'
          % (row['tag'], row['stop'], row['frames'], row['mic'], row['peak'], row['fs'], row['bit22'],
             row['rsat'], row['wide'], row['recovery_ok']))
    return row


def ok(row):
    return (row is not None and row['stop'] == 'completed' and row['bit22'] == 0
            and row['fs'] == 0 and row['recovery_ok'] is True)


gate = run('gate', np.zeros(2000, dtype=np.int16), True, False, 0.6, direct_only=True)
if not gate or not (-60.0 < gate['peak'] < -6.0):
    print('GATE_FAIL: nothing else runs (peak %s)' % ('n/a' if not gate else '%.1f' % gate['peak']))
    raise SystemExit(0)

if MODE == 'tone':
    n = int(2.0 * RATE)
    t = np.arange(n) / RATE
    tone = np.round(0.15 * np.sin(2 * np.pi * 322.0 * t) * 32767).astype(np.int16)
    files = []
    for tag, bypass, direct in (('open', False, True), ('bypass', True, False),
                                ('cancel', False, False)):
        r = run('tone_' + tag, tone, False, bypass, 2.2, direct_only=direct)
        if not ok(r):
            print('BRANCH_STOPPED in the tone round at %s' % tag)
            raise SystemExit(0)
        files.append(dict(tag=tag, path=r['path'], exists=True, error=None))
    manifest = dict(round_id=time.time_ns(), tone_hz=322.0, amplitude_fs=0.15,
                    operator_confirmation=CONF, created=time.time(), files=files)
    (DIR / 'tone_round.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('TONE_ROUND_WRITTEN', DIR / 'tone_round.json')
    raise SystemExit(0)

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
    print('  %-16s mic=%6.1f peak=%6.1f' % (r['tag'], r['mic'], r['peak']))
PY
echo "SEGMENT_B not run: needs an explicit authorisation, a person at the amplifier switch and a hard 2 s cap"
