#!/bin/bash
# One live-use validation: 115 cm, canceller ON, digital gain -5 dB, 30 s of real speech.
#
# Purpose (captain): decide whether -5 dB is a usable candidate working point under these conditions.
# It is NOT a confirmation of "+3 dB stable gain", and no gain is raised if anything misbehaves.
#
# Everything is printed before the cue sounds, so the operator can see that the model, the gain and
# the quantised value are what was intended.
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
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
GAIN_DB = -5.0
EXPECTED_Q12 = 2303
HP_VOLUME = 40
SECONDS = 30.0
CUE_FS = 0.08
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('live115_g5_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)

model = D / 'model_recalibrated.json'
if not model.is_file():
    print('LIVE_FAIL model_recalibrated.json missing')
    sys.exit(1)
print('LIVE_MODEL %s' % model.name)
print('LIVE_GEOMETRY speaker-mic 115 cm, talker 35 cm, Codec %d' % HP_VOLUME)
print('LIVE_GAIN gain_db=%.1f  expected_gain_q12=%d' % (GAIN_DB, EXPECTED_Q12))


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


def peak_db(a):
    return float(20 * np.log10(max(np.max(np.abs(np.asarray(a, float))), 1e-12)))


# floor first, so the operator is silent while it is measured
floors = []
for i in range(2):
    p = OUT / ('floor_%d.npz' % i)
    try:
        replay_trial(str(p), FIXTURE, str(model), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        floors.append(rms_db(np.load(str(p))['microphone']))
    except Exception as exc:
        print('LIVE_FLOOR_ERR %r' % (exc,))
floor_db = float(np.median(floors)) if floors else None
print('LIVE_FLOOR %s dBFS' % ('n/a' if floor_db is None else '%.2f' % floor_db))

parts = []
for _ in range(2):
    for f in (523.25, 783.99, 1046.50):
        parts.append(np.rint(CUE_FS * np.sin(2 * np.pi * f * np.arange(int(0.16 * RATE)) / RATE)
                             * 32767).astype(np.int16))
        parts.append(np.zeros(int(0.05 * RATE), np.int16))
    parts.append(np.zeros(int(0.35 * RATE), np.int16))
cue = np.concatenate(parts)
cp = OUT / 'cue.npz'
cp.unlink(missing_ok=True)
try:
    replay_trial(str(cp), FIXTURE, str(model), cue, bypass=True, zero_coeff=False, gain_db=0.0,
                 seconds=2.6, hp_volume=HP_VOLUME, speaker_confirmed=True,
                 local_capture_confirmed=True, direct_only=True)
    print('LIVE_CUE ok mic_peak=%.2f dBFS' % peak_db(np.load(str(cp))['microphone']))
except Exception as exc:
    print('LIVE_CUE_WARN %r' % (exc,))

print('LIVE_CAN_SPEAK  >>> three rising notes just sounded: talk normally for 30 s <<<')
time.sleep(1.5)
cap = OUT / 'live.npz'
cap.unlink(missing_ok=True)
try:
    replay_trial(str(cap), FIXTURE, str(model), np.zeros(16000, np.int16), bypass=False,
                 zero_coeff=False, gain_db=GAIN_DB, seconds=SECONDS, hp_volume=HP_VOLUME,
                 speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    print('LIVE_STOPPED %r' % (exc,))
    (OUT / 'live115.json').write_text(json.dumps(
        {'stamp': STAMP, 'gain_db': GAIN_DB, 'model': model.name, 'result': 'stopped',
         'error': repr(exc)[:200]}, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.exit(1)

meta = json.loads(str(np.load(str(cap))['metadata_json']))
mic = np.asarray(np.load(str(cap))['microphone'], float)
rec = {'stamp': STAMP, 'gain_db': GAIN_DB, 'model': model.name,
       'gain_q12_readback': meta.get('gain_q12'), 'stop': meta.get('stop_reason'),
       'capture_status': int(meta.get('capture_status') or 0),
       'bit22': int(meta.get('capture_status') or 0) >> 22 & 1,
       'mic_rms_dbfs': rms_db(mic), 'mic_peak_dbfs': peak_db(mic),
       'above_floor_db': (rms_db(mic) - floor_db) if floor_db else None,
       'saturations': {k: meta.get(k) for k in ('prediction_saturations', 'residual_saturations',
                                               'gain_saturations', 'mix_saturations')},
       'coeff_sha256': meta.get('coefficients_sha256')}
print('LIVE_RESULT %s' % json.dumps(rec, ensure_ascii=False))
ok = (rec['stop'] == 'completed' and rec['bit22'] == 0
      and all((v or 0) == 0 for v in rec['saturations'].values()))
rec['verdict'] = 'USABLE' if ok else 'NOT_USABLE'
print('LIVE_%s  gain_db=%.1f q12=%s' % (rec['verdict'], GAIN_DB, rec['gain_q12_readback']))
(OUT / 'live115.json').write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')
sys.exit(0 if ok else 1)
PY
