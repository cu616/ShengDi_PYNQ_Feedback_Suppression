#!/bin/bash
# Voice check, run on demand.
#
# Why this exists: the full entry takes about three minutes, so the spoken step would arrive at a
# moment the operator cannot predict. Splitting it means the operator says "ready" and the cue plays
# seconds later. The recalibrated model is already installed and in use, so this only records a voice
# segment through it.
#
# Cue: ascending C5-G5-C6 twice (three rising notes) so it cannot be confused with the 322 Hz tone.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$D" <<'PY'
import json
import sys
import time
from pathlib import Path

import numpy as np

from replay_trial_repair import replay_trial   # 0 dB AUX + relaxed PLL check

D = Path(sys.argv[1])
RATE = 48828.125
FIXTURE = 'room_v1_20261026b'
GAIN_DB = -8.0
HP_VOLUME = 40
VOICE_SECONDS = 30.0
MIN_ABOVE_FLOOR_DB = 10.0
ATTEMPTS = 2
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('voice_check_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)

_sel = Path('/home/xilinx/voice_model.txt')
active = Path(_sel.read_text().strip()) if _sel.is_file() else (D / 'model_recalibrated.json')
if not active.is_file():
    print('VOICE_FAIL no recalibrated model; run recal_entry.sh first')
    sys.exit(1)


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


def cue():
    parts = []
    for _ in range(2):
        for f in (523.25, 783.99, 1046.50):
            parts.append(np.rint(0.25 * np.sin(2 * np.pi * f * np.arange(int(0.16 * RATE)) / RATE)
                                 * 32767).astype(np.int16))
            parts.append(np.zeros(int(0.05 * RATE), np.int16))
        parts.append(np.zeros(int(0.35 * RATE), np.int16))
    return np.concatenate(parts)


# The floor must be measured while the operator is still silent, because it is the reference the voice
# level is compared against. If someone is already talking the "floor" becomes the speaker's own voice
# and nothing can be detected. So: ask for silence, measure, and only cue once it is quiet.
FLOOR_QUIET_DBFS = -33.0
FLOOR_TRIES = 5
floor_db = None
for i in range(FLOOR_TRIES):
    print('VOICE_WAIT  stay silent for a moment - measuring the room floor (%d/%d)'
          % (i + 1, FLOOR_TRIES))
    floor_p = OUT / ('floor_%d.npz' % i)
    try:
        replay_trial(str(floor_p), FIXTURE, str(active), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        floor_db = rms_db(np.load(str(floor_p))['microphone'])
    except Exception as exc:
        print('VOICE_FLOOR_ERR %r' % (exc,))
        time.sleep(1.0)
        continue
    print('VOICE_FLOOR_TRY %d %.2f dBFS (need below %.1f)' % (i + 1, floor_db, FLOOR_QUIET_DBFS))
    if floor_db <= FLOOR_QUIET_DBFS:
        break
    time.sleep(1.0)
if floor_db is None or floor_db > FLOOR_QUIET_DBFS:
    print('VOICE_FAIL  the room is too loud to measure a floor (best %.2f dBFS, need %.1f). '
          'Someone talking, a fan, or the loop ringing. Nothing recorded.'
          % (floor_db if floor_db is not None else float('nan'), FLOOR_QUIET_DBFS))
    sys.exit(1)
print('VOICE_FLOOR_OK %.2f dBFS - now the cue will sound' % floor_db)

results = []
ok = False
for attempt in range(ATTEMPTS):
    p = OUT / ('cue_%d.npz' % attempt)
    try:
        replay_trial(str(p), FIXTURE, str(active), cue(), bypass=True, zero_coeff=False,
                     gain_db=0.0, seconds=2.6, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        print('VOICE_CUE_WARN %r' % (exc,))
    print('VOICE_CUE  >>> three rising notes = speak now (%d/%d) <<<' % (attempt + 1, ATTEMPTS))
    time.sleep(1.5)
    cap = OUT / ('voice_%d.npz' % attempt)
    try:
        replay_trial(str(cap), FIXTURE, str(active), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=False, gain_db=GAIN_DB, seconds=VOICE_SECONDS, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True)
    except Exception as exc:
        print('VOICE_FAIL capture raised %r' % (exc,))
        break
    meta = json.loads(str(np.load(str(cap))['metadata_json']))
    rms = rms_db(np.load(str(cap))['microphone'])
    above = rms - floor_db
    results.append({'attempt': attempt + 1, 'rms_dbfs': rms, 'above_floor_db': above,
                    'stop': meta.get('stop_reason')})
    print('VOICE_RESULT %d rms=%.2f dBFS above_floor=%.2f dB stop=%s'
          % (attempt + 1, rms, above, meta.get('stop_reason')))
    if meta.get('stop_reason') == 'completed' and above >= MIN_ABOVE_FLOOR_DB:
        ok = True
        break

(OUT / 'voice_check.json').write_text(json.dumps(
    {'stamp': STAMP, 'model': active.name, 'floor_dbfs': floor_db,
     'min_above_floor_db': MIN_ABOVE_FLOOR_DB, 'attempts': results,
     'verdict': 'VOICE_USABLE' if ok else 'NO_VOICE'}, ensure_ascii=False, indent=2), encoding='utf-8')
print('VOICE_%s  %s' % ('USABLE' if ok else 'NOT_DETECTED', OUT))
sys.exit(0 if ok else 1)
PY
