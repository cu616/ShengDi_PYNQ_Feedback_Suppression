#!/bin/bash
# Analyse exactly the three files that tone_arms_v3.sh wrote in ONE round, after proving the round
# is internally consistent. C's 2026-10-27 review, item 4, lists five ways the old version still
# produced a number; each one is now a hard rejection:
#   1 missing identity            -> every identity key must exist, be non-null and be equal
#   2 changed source or gain      -> same source hash, same model, same hp volume, same fixture,
#                                    open at gain 0, bypass and cancel at the same non-zero gain
#   3 conflicting actual length   -> identical array lengths and identical frame accounting
#   4 input at the rail           -> bit22 clear, no full-scale microphone sample in metadata AND
#                                    none recomputed from the samples themselves
#   5 an arm that stopped         -> stop_reason must be "completed", early_stop false,
#                                    completed_frames must equal the requested budget, recovery_ok true
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MANIFEST = DIR / 'tone_round.json'
RATE = 48828.125
RAIL = 2**23 - 1
if not MANIFEST.is_file():
    print('TONE_FAIL no tone_round.json: refusing to pair files by guesswork')
    sys.exit(1)
man = json.loads(MANIFEST.read_text())
TONE = float(man.get('tone_hz') or 322.0)
IDENTITY = ('package_version', 'bit_sha256', 'hwh_sha256', 'driver_sha256', 'replay_tools_sha256',
            'model_sha256', 'source_pcm16_sha256', 'coefficients_sha256', 'fixture_id', 'hp_volume')
WINDOW = ('frames', 'first_frame', 'completed_frames', 'sound_seconds_nominal')

rows, problems = {}, []
for entry in man['files']:
    tag = entry['tag']
    path = Path(entry['path'])
    if not entry.get('exists') or not path.is_file():
        problems.append('%s: file missing (%s)' % (tag, entry.get('error')))
        continue
    data = np.load(str(path))
    rows[tag] = (data, json.loads(str(data['metadata_json'])))

if set(rows) != {'open', 'bypass', 'cancel'}:
    print('TONE_FAIL need open/bypass/cancel, got', sorted(rows), problems)
    sys.exit(1)

# 1 identity: present, non-null, identical
for key in IDENTITY:
    values = {tag: meta.get(key) for tag, (_, meta) in rows.items()}
    if any(v in (None, '') for v in values.values()):
        problems.append('identity missing on %s: %s' % (key, values))
    elif len(set(values.values())) != 1:
        problems.append('identity mismatch on %s: %s' % (key, values))
if rows['open'][1].get('package_version') != 'audio-replay-v3':
    problems.append('package_version is not audio-replay-v3: %s'
                    % rows['open'][1].get('package_version'))

# 2 source and gain discipline
gains = {tag: int(meta.get('gain_q12') or 0) for tag, (_, meta) in rows.items()}
if gains['open'] != 0:
    problems.append('open arm was not run at gain 0: %s' % gains['open'])
if gains['bypass'] == 0 or gains['cancel'] == 0:
    problems.append('bypass/cancel ran at gain 0: %s' % gains)
if gains['bypass'] != gains['cancel']:
    problems.append('bypass and cancel used different gains: %s' % gains)
if not rows['bypass'][1].get('bypass') or rows['cancel'][1].get('bypass') or rows['open'][1].get('bypass'):
    problems.append('bypass flags are not (open False, bypass True, cancel False): %s'
                    % {tag: meta.get('bypass') for tag, (_, meta) in rows.items()})
if any(meta.get('zero_coeff') for _, meta in rows.values()):
    problems.append('an arm ran with zero coefficients; the tone round needs the candidate loaded')

# 3 lengths must agree, in the arrays and in the accounting
lengths = {tag: (len(data['microphone']), len(data['prediction_pcm']), len(data['residual_pcm']))
           for tag, (data, _) in rows.items()}
if len(set(lengths.values())) != 1:
    problems.append('array lengths differ: %s' % lengths)
for key in WINDOW:
    values = {tag: meta.get(key) for tag, (_, meta) in rows.items()}
    if len(set(values.values())) != 1:
        problems.append('window mismatch on %s: %s' % (key, values))

# 4 input must not touch the rail, by metadata and by the samples themselves
for tag, (data, meta) in rows.items():
    if int(meta.get('capture_status') or 0) >> 22 & 1:
        problems.append('%s: input full scale (bit22) set' % tag)
    if int(meta.get('mic_full_scale_samples') or 0):
        problems.append('%s: metadata reports microphone samples at the rail (%s)'
                        % (tag, meta.get('mic_full_scale_samples')))
    mic_int = np.rint(np.asarray(data['microphone'], dtype=np.float64) * 2**23).astype(np.int64)
    at_rail = int(np.count_nonzero((mic_int >= RAIL) | (mic_int <= -2**23)))
    if at_rail:
        problems.append('%s: %d microphone samples at the rail in the capture' % (tag, at_rail))
    for key in ('prediction_saturations', 'gain_saturations', 'mix_saturations',
                'residual_saturations'):
        if int(meta.get(key) or 0):
            problems.append('%s: %s = %s' % (tag, key, meta.get(key)))

# 5 no arm may have stopped early
for tag, (_, meta) in rows.items():
    if meta.get('stop_reason') != 'completed':
        problems.append('%s: stop_reason=%s (an arm that stopped cannot be part of a depth)'
                        % (tag, meta.get('stop_reason')))
    if meta.get('early_stop'):
        problems.append('%s: early_stop is set' % tag)
    budget = int(round(float(meta.get('sound_seconds_nominal') or 0) * RATE))
    if budget and int(meta.get('completed_frames') or 0) != budget:
        problems.append('%s: completed_frames %s != requested %s'
                        % (tag, meta.get('completed_frames'), budget))
    if meta.get('recovery_ok') is False:
        problems.append('%s: recovery_ok false' % tag)

if problems:
    print('TONE_FAIL refusing to compute a depth:')
    for p in problems:
        print('  -', p)
    sys.exit(1)


def level(x, f0, halfwidth=2.0):
    n = len(x)
    spec = np.abs(np.fft.rfft(np.asarray(x, dtype=np.float64) * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    return 20*np.log10(max(float(np.max(spec[np.abs(freqs - f0) <= halfwidth])), 1e-12))


out = {}
for tag, (data, _) in rows.items():
    out[tag] = dict(
        mic=level(np.asarray(data['microphone'], dtype=np.float64) * 2**23, TONE),
        pred=level(np.asarray(data['prediction_pcm']), TONE),
        residual=level(np.asarray(data['residual_pcm']), TONE))
    print('TONE_%s mic@%.0f=%.2f pred@%.0f=%.2f residual@%.0f=%.2f'
          % (tag, TONE, out[tag]['mic'], TONE, out[tag]['pred'], TONE, out[tag]['residual']))

o, b, c = out['open'], out['bypass'], out['cancel']
print('TONE_DEPTH cancel_minus_bypass_residual=%+.2f dB cancel_minus_bypass_mic=%+.2f dB '
      'bypass_minus_open_mic=%+.2f dB (round %s, confirmation: %s)'
      % (b['residual'] - c['residual'], b['mic'] - c['mic'], b['mic'] - o['mic'],
         man.get('round_id'), man.get('operator_confirmation')))
print('TONE_NOTE denominators are the bypass arm; open is a level reference only')
PY
