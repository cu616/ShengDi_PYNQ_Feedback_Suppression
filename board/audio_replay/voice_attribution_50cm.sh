#!/bin/bash
# Real-person check at speaker-mic 50 cm with the talker at 20 cm, plus attribution of any bit22.
#
# Captain's requirement: bit22 only means "input full scale". To say whether it comes from the direct
# voice or from the feedback return, the same voice must be captured twice: once with the feedback path
# disconnected (open) and once with the loop closed (cancel).
#
# The cue is deliberately quiet (0.08 FS) so that the cue itself cannot be the thing that clips.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$D" <<'PY'
import json
import sys
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path(sys.argv[1])
RATE = 48828.125
FIXTURE = 'room_v1_20261026b'
GAIN_DB = -8.0
HP_VOLUME = 40
CUE_FS = 0.08
SECONDS = 20.0
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('voice50_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)

sel = Path('/home/xilinx/voice_model.txt')
model = Path(sel.read_text().strip()) if sel.is_file() else (D / 'model_recalibrated.json')
print('VOICE_MODEL %s' % model.name)


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


def peak_db(a):
    return float(20 * np.log10(max(np.max(np.abs(np.asarray(a, float))), 1e-12)))


def cue():
    parts = []
    for _ in range(2):
        for f in (523.25, 783.99, 1046.50):
            parts.append(np.rint(CUE_FS * np.sin(2 * np.pi * f * np.arange(int(0.16 * RATE)) / RATE)
                                 * 32767).astype(np.int16))
            parts.append(np.zeros(int(0.05 * RATE), np.int16))
        parts.append(np.zeros(int(0.35 * RATE), np.int16))
    return np.concatenate(parts)


# floor first, while the talker is still silent
floors = []
for i in range(3):
    p = OUT / ('floor_%d.npz' % i)
    try:
        replay_trial(str(p), FIXTURE, str(model), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        floors.append(rms_db(np.load(str(p))['microphone']))
    except Exception as exc:
        print('VOICE_FLOOR_ERR %r' % (exc,))
floor_db = float(np.median(floors)) if floors else None
print('VOICE_FLOOR %s dBFS' % ('n/a' if floor_db is None else '%.2f' % floor_db))
if floor_db is None or floor_db > -33.0:
    print('VOICE_FAIL room too loud to start (floor %s)' % floor_db)
    sys.exit(1)

# cue once, quietly
cp = OUT / 'cue.npz'
cp.unlink(missing_ok=True)
try:
    replay_trial(str(cp), FIXTURE, str(model), cue(), bypass=True, zero_coeff=False,
                 gain_db=0.0, seconds=2.6, hp_volume=HP_VOLUME, speaker_confirmed=True,
                 local_capture_confirmed=True, direct_only=True)
    cm = json.loads(str(np.load(str(cp))['metadata_json']))
    cpeak = peak_db(np.load(str(cp))['microphone'])
    print('VOICE_CUE_OK mic_peak=%.2f dBFS stop=%s' % (cpeak, cm.get('stop_reason')))
except Exception as exc:
    print('VOICE_CUE_CLIPPED %r  (the cue itself does not fit the input at this distance)' % (exc,))

results = []
print('VOICE_CAN_SPEAK  >>> three rising notes just sounded: talk normally for 20 s <<<')
time.sleep(1.5)

# A: feedback path disconnected, the source is silent, only the room and the voice
pA = OUT / 'open.npz'
pA.unlink(missing_ok=True)
try:
    replay_trial(str(pA), FIXTURE, str(model), np.zeros(16000, np.int16), bypass=False,
                 zero_coeff=False, gain_db=GAIN_DB, seconds=SECONDS, hp_volume=HP_VOLUME,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    mA = json.loads(str(np.load(str(pA))['metadata_json']))
    results.append({'arm': 'open (no feedback return)', 'stop': mA.get('stop_reason'),
                    'bit22': int(mA.get('capture_status') or 0) >> 22 & 1,
                    'mic_rms_dbfs': rms_db(np.load(str(pA))['microphone']),
                    'mic_peak_dbfs': peak_db(np.load(str(pA))['microphone'])})
except Exception as exc:
    results.append({'arm': 'open (no feedback return)', 'stop': 'raised', 'error': repr(exc)[:120]})
print('VOICE_ARM_OPEN %s' % results[-1])

# B: loop closed with the canceller
pB = OUT / 'cancel.npz'
pB.unlink(missing_ok=True)
try:
    replay_trial(str(pB), FIXTURE, str(model), np.zeros(16000, np.int16), bypass=False,
                 zero_coeff=False, gain_db=GAIN_DB, seconds=SECONDS, hp_volume=HP_VOLUME,
                 speaker_confirmed=True, local_capture_confirmed=True)
    mB = json.loads(str(np.load(str(pB))['metadata_json']))
    results.append({'arm': 'cancel (loop closed)', 'stop': mB.get('stop_reason'),
                    'bit22': int(mB.get('capture_status') or 0) >> 22 & 1,
                    'mic_rms_dbfs': rms_db(np.load(str(pB))['microphone']),
                    'mic_peak_dbfs': peak_db(np.load(str(pB))['microphone'])})
except Exception as exc:
    results.append({'arm': 'cancel (loop closed)', 'stop': 'raised', 'error': repr(exc)[:120]})
print('VOICE_ARM_CANCEL %s' % results[-1])

# attribution
att = 'inconclusive'
if len(results) == 2 and 'bit22' in results[0] and 'bit22' in results[1]:
    o, c = results[0]['bit22'], results[1]['bit22']
    if o == 1 and c == 1:
        att = 'direct voice alone trips the input (open arm also saturated)'
    elif o == 0 and c == 1:
        att = 'the feedback return trips the input (open arm clean, closed loop saturated)'
    else:
        att = 'neither arm saturated'
print('VOICE_ATTRIBUTION %s' % att)
(OUT / 'voice50.json').write_text(json.dumps(
    {'stamp': STAMP, 'model': model.name, 'floor_dbfs': floor_db, 'cue_fs': CUE_FS,
     'arms': results, 'attribution': att,
     'setup': 'speaker-mic 50 cm, talker-mic 20 cm, gain -8 dB, Codec 40'},
    ensure_ascii=False, indent=2), encoding='utf-8')
print('VOICE_DONE %s' % OUT)
PY
