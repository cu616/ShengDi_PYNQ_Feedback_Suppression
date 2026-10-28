#!/bin/bash
# Analyse exactly the three files that tone_arms_v3.sh wrote in ONE round, after checking that the
# round is internally consistent. C's 2026-10-27 review, item 4:
#   * pair by an explicit same-round manifest, never by globbing whatever files exist;
#   * verify identity (bit / hwh / driver / model hashes), window (frames, first_frame, duration)
#     and input validity (bit22 clear, no full-scale microphone samples, no saturations) for all three;
#   * refuse to print a number when any of that fails.
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
if not MANIFEST.is_file():
    print('TONE_FAIL no tone_round.json: refusing to pair files by guesswork')
    sys.exit(1)
man = json.loads(MANIFEST.read_text())
TONE = float(man.get('tone_hz') or 322.0)
IDENTITY_KEYS = ('bit_sha256', 'hwh_sha256', 'driver_sha256', 'model_sha256', 'package_version')
WINDOW_KEYS = ('frames', 'first_frame', 'sound_seconds_nominal')

rows, problems = {}, []
for entry in man['files']:
    tag = entry['tag']
    path = Path(entry['path'])
    if not entry.get('exists') or not path.is_file():
        problems.append('%s: file missing (%s)' % (tag, entry.get('error')))
        continue
    data = np.load(str(path))
    rows[tag] = (data, json.loads(str(data['metadata_json'])))

if len(rows) != 3:
    print('TONE_FAIL need open/bypass/cancel, got', sorted(rows), problems)
    sys.exit(1)

for key in IDENTITY_KEYS:
    values = {tag: meta.get(key) for tag, (_, meta) in rows.items()}
    if len(set(values.values())) != 1:
        problems.append('identity mismatch on %s: %s' % (key, values))
for key in WINDOW_KEYS:
    values = {tag: meta.get(key) for tag, (_, meta) in rows.items()}
    if len(set(values.values())) != 1:
        problems.append('window mismatch on %s: %s' % (key, values))
for tag, (_, meta) in rows.items():
    if int(meta.get('capture_status') or 0) >> 22 & 1:
        problems.append('%s: input full scale (bit22) set' % tag)
    if int(meta.get('mic_full_scale_samples') or 0):
        problems.append('%s: microphone samples at the rail (%s)'
                        % (tag, meta.get('mic_full_scale_samples')))
    for key in ('prediction_saturations', 'gain_saturations', 'mix_saturations'):
        if int(meta.get(key) or 0):
            problems.append('%s: %s = %s' % (tag, key, meta.get(key)))

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
