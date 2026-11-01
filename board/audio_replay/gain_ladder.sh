#!/bin/bash
# Bounded gain ladder: -8, -5, -2, 0 dB, bypass and cancel, at ONE fixed geometry.
#
# Captain's rules implemented:
#   * the same frozen source and a fixed 10 s observation for every level and both modes;
#   * "no protection tripped" is recorded as one condition, NOT as proof of stability;
#   * the first level where a mode trips protection or shows clear regeneration stops THAT mode -
#     the failing level is not hit again;
#   * the last step is 2 dB, and the actual quantised gain is recorded (Q4.12 rounding);
#   * nothing here is called MSG/ASG: the result is a boundary interval per mode.
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
HP_VOLUME = 40
SECONDS = 2.6   # the driver caps the source at 131072 samples (2.68 s) and the capture
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('ladder_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)

sel = Path('/home/xilinx/voice_model.txt')
model = Path(sel.read_text().strip()) if sel.is_file() else (D / 'model_recalibrated.json')
print('LADDER_MODEL %s' % model.name)
print('LADDER_GEOMETRY speaker-mic 115 cm (operator must confirm before this runs)')

LEVELS = [-8.0, -5.0, -2.0, 0.0]
SRC_FS = 0.10          # fixed source amplitude for every level and both modes


def q12(g_db):
    return int(round(4096 * 10 ** (g_db / 20.0)))


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


def peak_db(a):
    return float(20 * np.log10(max(np.max(np.abs(np.asarray(a, float))), 1e-12)))


def tonality_db(mic):
    """Largest 1/3-octave band over the band median: a crude 'narrowband growth' indicator."""
    n = len(mic)
    win = np.hanning(n)
    spec = np.abs(np.fft.rfft(mic * win)) ** 2
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    bands = []
    for fc in (125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150):
        m = (freqs >= fc / 2 ** (1 / 6)) & (freqs < fc * 2 ** (1 / 6))
        if m.any():
            bands.append(10 * np.log10(max(np.mean(spec[m]), 1e-30)))
    if not bands:
        return 0.0
    return float(max(bands) - float(np.median(bands)))


rng = np.random.default_rng(4242)
n = int(SECONDS * RATE) - 5
x = rng.standard_normal(n)
x -= x.mean()
x = x / (np.sqrt(np.mean(x ** 2)) or 1.0) * SRC_FS
src = np.rint(x * 32767).astype(np.int16)
print('LADDER_SOURCE fs=%.3f rms=%.2f dBFS peak=%.2f dBFS frozen for every level'
      % (SRC_FS, rms_db(src / 32768.0), peak_db(src / 32768.0)))

results = []
stopped = {'bypass': None, 'cancel': None}
for g_db in LEVELS:
    for mode in ('bypass', 'cancel'):
        if stopped[mode] is not None:
            results.append({'gain_db': g_db, 'mode': mode, 'status': 'skipped: %s' % stopped[mode]})
            continue
        p = OUT / ('g%+05.1f_%s.npz' % (g_db, mode))
        p.unlink(missing_ok=True)
        rec = {'gain_db': g_db, 'q12': q12(g_db), 'mode': mode}
        try:
            replay_trial(str(p), FIXTURE, str(model), src, bypass=(mode == 'bypass'), zero_coeff=False,
                         gain_db=g_db, seconds=SECONDS, hp_volume=HP_VOLUME, speaker_confirmed=True,
                         local_capture_confirmed=True, direct_only=False)
        except Exception as exc:
            rec.update({'status': 'stopped', 'error': repr(exc)[:120]})
            stopped[mode] = 'first anomaly at %.1f dB' % g_db
            print('LADDER_RESULT %s' % rec)
            results.append(rec)
            continue
        cap = np.load(str(p))
        meta = json.loads(str(cap['metadata_json']))
        mic = np.asarray(cap['microphone'], float)
        rec.update({'status': 'completed', 'stop': meta.get('stop_reason'),
                    'capture_status': int(meta.get('capture_status') or 0),
                    'mic_rms_dbfs': rms_db(mic), 'mic_peak_dbfs': peak_db(mic),
                    'bit22': int(meta.get('capture_status') or 0) >> 22 & 1,
                    'saturations': {k: meta.get(k) for k in
                                    ('prediction_saturations', 'residual_saturations',
                                     'gain_saturations', 'mix_saturations')},
                    'tonality_db': tonality_db(mic)})
        if rec['bit22'] or meta.get('stop_reason') != 'completed' or rec['tonality_db'] > 12.0:
            rec['status'] = 'anomaly'
            stopped[mode] = 'first anomaly at %.1f dB' % g_db
        print('LADDER_RESULT %s' % json.dumps(rec, ensure_ascii=False))

summary = {'stamp': STAMP, 'model': model.name, 'geometry': 'speaker-mic 115 cm',
           'source': {'fs': SRC_FS, 'rms_dbfs': rms_db(src / 32768.0)},
           'levels': LEVELS, 'results': results, 'stopped': stopped,
           'note': 'boundary interval per mode, not MSG/ASG; 3 dB steps cannot resolve a precise limit',
           'deviation': 'the captain asked for a 10 s observation, but the driver caps the source at 131072 samples (2.68 s) and the capture is the last 16384 frames, so each level runs 2.6 s with the source active through the whole capture window'}
(OUT / 'ladder.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
for mode in ('bypass', 'cancel'):
    ok = [r['gain_db'] for r in results if r.get('mode') == mode and r.get('status') == 'completed']
    print('LADDER_BOUNDARY %s highest_completed=%s first_anomaly=%s'
          % (mode, max(ok) if ok else 'none', stopped[mode] or 'none reached'))
print('LADDER_DONE %s' % OUT)
PY
