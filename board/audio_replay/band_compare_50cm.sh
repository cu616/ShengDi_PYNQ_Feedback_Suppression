#!/bin/bash
# 50 cm key-band comparison: identical broadband excitation through three arms, compared band by band.
#
# Captain's definition, implemented literally:
#   open   = the feedback path is disconnected, the test source still plays (driver direct_only=True:
#            played[n] = source[n], the gain term is forced to zero)
#   bypass = the loop is closed with the canceller bypassed (played[n] = source[n] + g*mic)
#   cancel = the loop is closed with the candidate model cancelling
#
# After levelling, all three arms use the SAME source samples, gain, duration and analysis window.
# Nothing is re-levelled per arm and nothing is tuned to make the candidate look good.
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

from replay_trial import replay_trial

D = Path(sys.argv[1])
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
GAIN_DB = -8.0
HP_VOLUME = 40
SECONDS = 0.3357
TARGET_MIC_PEAK_DBFS = -12.0
MAX_ADJUST = 6
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('band50_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)
BASE = D / 'rewired_512_20261026.json'
# The candidate is a parameter: comparing a 115 cm model at 50 cm would confound the result, so this
# batch always names the model it is judging.
_sel = Path('/home/xilinx/band_model.txt')
CAND = Path(_sel.read_text().strip()) if _sel.is_file() else (D / 'model_recalibrated.json')
if not CAND.is_file():
    print('BAND_FAIL no candidate model at %s' % CAND)
    sys.exit(1)
print('BAND_CANDIDATE %s' % CAND.name)


def peak_db(a):
    return float(20 * np.log10(max(np.max(np.abs(np.asarray(a, float))), 1e-12)))


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


# ---- floor, three silent captures -------------------------------------------------------------
floors = []
for i in range(3):
    p = OUT / ('floor_%d.npz' % i)
    try:
        replay_trial(str(p), FIXTURE, str(CAND), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        floors.append(rms_db(np.load(str(p))['microphone']))
    except Exception as exc:
        print('BAND_FLOOR_ERR %r' % (exc,))
if len(floors) < 2:
    print('BAND_FAIL floor could not be measured')
    sys.exit(1)
floor_db = float(np.median(floors))
print('BAND_FLOOR %.2f dBFS (median of %s)' % (floor_db, ['%.2f' % v for v in floors]))


def noise(n, fs):
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x -= np.mean(x)
    x = x / (float(np.sqrt(np.mean(x ** 2))) or 1.0)
    pk = float(np.max(np.abs(x)))
    if pk > 0.8:
        x *= 0.8 / pk
    return np.rint(x * fs * 32767.0).astype(np.int16)


# ---- level the broadband stimulus on the OPEN arm only, then freeze ---------------------------
fs_now = 0.05
last_good = None
adjusts = 0
trials = []
while True:
    src = noise(int(SECONDS * RATE) - 5, fs_now)
    p = OUT / ('level_%d.npz' % adjusts)
    p.unlink(missing_ok=True)
    clipped = False
    pk = None
    try:
        replay_trial(str(p), FIXTURE, str(CAND), src, bypass=False, zero_coeff=False,
                     gain_db=GAIN_DB, seconds=SECONDS, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        if 'full scale' in repr(exc) or 'bit22' in repr(exc):
            clipped = True
        else:
            print('BAND_FAIL levelling raised %r' % (exc,))
            sys.exit(1)
    if p.is_file():
        pk = peak_db(np.load(str(p))['microphone'])
        m = json.loads(str(np.load(str(p))['metadata_json']))
        if m.get('stop_reason') != 'completed' or (int(m.get('capture_status') or 0) >> 22) & 1:
            clipped = True
    trials.append({'fs': fs_now, 'mic_peak_dbfs': pk, 'clipped': clipped})
    print('BAND_LEVEL try=%d fs=%.4f mic_peak=%s clipped=%s'
          % (adjusts, fs_now, 'n/a' if pk is None else '%.2f' % pk, clipped))
    if clipped:
        if last_good is not None:
            fs_now = last_good
            break
        if adjusts >= MAX_ADJUST:
            print('BAND_FAIL stimulus clipped at every amplitude')
            sys.exit(1)
        fs_now *= 0.5
        adjusts += 1
        continue
    last_good = fs_now
    if abs(pk - TARGET_MIC_PEAK_DBFS) <= 2.0 or adjusts >= MAX_ADJUST:
        break
    fs_now = min(0.5, fs_now * 1.4)
    adjusts += 1

src = noise(int(SECONDS * RATE) - 5, fs_now)
print('BAND_STIMULUS_FROZEN fs=%.4f mic_peak=%s adjustments=%d (identical for all arms)'
      % (fs_now, '%.2f' % trials[-1]['mic_peak_dbfs'] if trials[-1]['mic_peak_dbfs'] else 'n/a', adjusts))

# ---- three arms, identical source --------------------------------------------------------------
arms = {}
for tag, model, bypass, direct in (('open', CAND, False, True), ('bypass', CAND, True, False),
                                   ('cancel', CAND, False, False)):
    p = OUT / ('arm_%s.npz' % tag)
    p.unlink(missing_ok=True)
    try:
        replay_trial(str(p), FIXTURE, str(model), src, bypass=bypass, zero_coeff=False,
                     gain_db=GAIN_DB, seconds=SECONDS, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct)
    except Exception as exc:
        print('BAND_ARM_STOP %s %r' % (tag, exc)[:130])
        arms[tag] = None
        continue
    cap = np.load(str(p))
    meta = json.loads(str(cap['metadata_json']))
    arms[tag] = {'mic': np.asarray(cap['microphone'], float), 'meta': meta}
    print('BAND_ARM %-6s stop=%-10s sat(p/r/g/m)=%s/%s/%s/%s mic_rms=%.2f dBFS coeff=%s'
          % (tag, meta.get('stop_reason'), meta.get('prediction_saturations'),
             meta.get('residual_saturations'), meta.get('gain_saturations'),
             meta.get('mix_saturations'), rms_db(arms[tag]['mic']),
             str(meta.get('coefficients_sha256') or '')[:12]))

if any(v is None for v in arms.values()):
    print('BAND_FAIL not all three arms completed')
    sys.exit(1)

# ---- 1/3-octave comparison ---------------------------------------------------------------------
n = min(len(arms[t]['mic']) for t in arms)
win = np.hanning(n)
freqs = np.fft.rfftfreq(n, 1 / RATE)
spectra = {}
for t in arms:
    spectra[t] = np.abs(np.fft.rfft(arms[t]['mic'][:n] * win))
centers = [125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
           4000, 5000, 6300, 8000]
rows = []
for fc in centers:
    lo, hi = fc / 2 ** (1 / 6), fc * 2 ** (1 / 6)
    mask = (freqs >= lo) & (freqs < hi)
    if mask.sum() == 0:
        continue
    lv = {t: 10 * np.log10(max(np.mean(spectra[t][mask] ** 2), 1e-30)) for t in arms}
    boost = lv['bypass'] - lv['open']          # what closing the loop adds in this band
    effect = lv['cancel'] - lv['bypass']       # what cancelling changes in this band
    rows.append({'fc_hz': fc, 'open_db': lv['open'], 'bypass_db': lv['bypass'],
                 'cancel_db': lv['cancel'], 'loop_boost_db': boost, 'cancel_effect_db': effect})

print('BAND_TABLE  fc(Hz)  open    bypass  cancel  loop_boost  cancel_effect')
for r in rows:
    print('BAND_ROW %6d  %7.2f %7.2f %7.2f   %+7.2f      %+7.2f'
          % (r['fc_hz'], r['open_db'], r['bypass_db'], r['cancel_db'],
             r['loop_boost_db'], r['cancel_effect_db']))

boosts = [r for r in rows if r['loop_boost_db'] > 1.0]
if boosts:
    best = max(boosts, key=lambda r: r['loop_boost_db'])
    print('BAND_BEST_BOOST fc=%d Hz boost=%+.2f dB cancel_effect=%+.2f dB'
          % (best['fc_hz'], best['loop_boost_db'], best['cancel_effect_db']))
else:
    best = None
    print('BAND_NO_BOOST no 1/3-octave band shows more than 1 dB of loop boost at this level')

summary = {'stamp': STAMP, 'position': 'P4_50cm', 'fixture': FIXTURE, 'gain_db': GAIN_DB,
           'floor_dbfs': floor_db, 'stimulus_fs_frozen': fs_now, 'levelling_trials': trials,
           'arms': {t: {'stop': arms[t]['meta'].get('stop_reason'),
                        'mic_rms_dbfs': rms_db(arms[t]['mic']),
                        'coeff_sha256': arms[t]['meta'].get('coefficients_sha256'),
                        'saturations': {k: arms[t]['meta'].get(k) for k in
                                        ('prediction_saturations', 'residual_saturations',
                                         'gain_saturations', 'mix_saturations')}}
                    for t in arms},
           'bands': rows, 'best_boost_band': best,
           'note': 'open = feedback path disconnected, test source still playing; all arms share one '
                   'frozen excitation and one window'}
(OUT / 'band50.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print('BAND_DONE %s' % OUT)
PY
