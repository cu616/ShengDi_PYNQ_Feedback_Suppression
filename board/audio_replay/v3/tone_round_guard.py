"""Tone-round guard and three-point analysis, importable so it can be tested without a board.

The bash entry point (tone_analyze.sh) is a thin wrapper around this module. Keeping the checks
here means C's five bad-input classes can be exercised with synthetic captures instead of only
being read in a script.

C 2026-10-27 item 4, the five classes that must be rejected:
  1 missing identity
  2 changed source or gain
  3 conflicting actual length
  4 input at the rail
  5 an arm that stopped
"""
import json
from pathlib import Path

import numpy as np

RATE = 48828.125
RAIL_POS, RAIL_NEG = 2**23 - 1, -2**23
IDENTITY = ('package_version', 'bit_sha256', 'hwh_sha256', 'driver_sha256', 'replay_tools_sha256',
            'model_sha256', 'source_pcm16_sha256', 'coefficients_sha256', 'fixture_id', 'hp_volume')
WINDOW = ('frames', 'first_frame', 'completed_frames', 'sound_seconds_nominal')


def load_round(manifest_path):
    """Return (manifest, {tag: (arrays, metadata)}) or raise ValueError with the reason."""
    path = Path(manifest_path)
    if not path.is_file():
        raise ValueError('no tone_round.json: refusing to pair files by guesswork')
    man = json.loads(path.read_text())
    rows = {}
    for entry in man.get('files', []):
        tag = entry.get('tag')
        f = Path(entry.get('path', ''))
        if not entry.get('exists') or not f.is_file():
            raise ValueError('%s: file missing (%s)' % (tag, entry.get('error')))
        data = np.load(str(f))
        rows[tag] = (data, json.loads(str(data['metadata_json'])))
    if set(rows) != {'open', 'bypass', 'cancel'}:
        raise ValueError('need open/bypass/cancel, got %s' % sorted(rows))
    return man, rows


def validate(rows):
    """Return a list of problems; empty means the round is usable."""
    problems = []
    for key in IDENTITY:
        values = {tag: meta.get(key) for tag, (_, meta) in rows.items()}
        if any(v in (None, '') for v in values.values()):
            problems.append('identity missing on %s: %s' % (key, values))
        elif len(set(values.values())) != 1:
            problems.append('identity mismatch on %s: %s' % (key, values))
    if rows['open'][1].get('package_version') != 'audio-replay-v3':
        problems.append('package_version is not audio-replay-v3: %s'
                        % rows['open'][1].get('package_version'))

    gains = {tag: int(meta.get('gain_q12') or 0) for tag, (_, meta) in rows.items()}
    if gains['open'] != 0:
        problems.append('open arm was not run at gain 0: %s' % gains['open'])
    if gains['bypass'] == 0 or gains['cancel'] == 0:
        problems.append('bypass/cancel ran at gain 0: %s' % gains)
    if gains['bypass'] != gains['cancel']:
        problems.append('bypass and cancel used different gains: %s' % gains)
    flags = {tag: bool(meta.get('bypass')) for tag, (_, meta) in rows.items()}
    if flags != {'open': False, 'bypass': True, 'cancel': False}:
        problems.append('bypass flags are not (open False, bypass True, cancel False): %s' % flags)
    if any(meta.get('zero_coeff') for _, meta in rows.values()):
        problems.append('an arm ran with zero coefficients; the tone round needs the candidate loaded')

    lengths = {tag: (len(data['microphone']), len(data['prediction_pcm']), len(data['residual_pcm']))
               for tag, (data, _) in rows.items()}
    if len(set(lengths.values())) != 1:
        problems.append('array lengths differ: %s' % lengths)
    for key in WINDOW:
        values = {tag: meta.get(key) for tag, (_, meta) in rows.items()}
        if len(set(values.values())) != 1:
            problems.append('window mismatch on %s: %s' % (key, values))

    for tag, (data, meta) in rows.items():
        if int(meta.get('capture_status') or 0) >> 22 & 1:
            problems.append('%s: input full scale (bit22) set' % tag)
        if int(meta.get('mic_full_scale_samples') or 0):
            problems.append('%s: metadata reports microphone samples at the rail (%s)'
                            % (tag, meta.get('mic_full_scale_samples')))
        mic_int = np.rint(np.asarray(data['microphone'], dtype=np.float64) * 2**23).astype(np.int64)
        at_rail = int(np.count_nonzero((mic_int >= RAIL_POS) | (mic_int <= RAIL_NEG)))
        if at_rail:
            problems.append('%s: %d microphone samples at the rail in the capture' % (tag, at_rail))
        for key in ('prediction_saturations', 'gain_saturations', 'mix_saturations',
                    'residual_saturations'):
            if int(meta.get(key) or 0):
                problems.append('%s: %s = %s' % (tag, key, meta.get(key)))

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
    return problems


def level(x, f0, halfwidth=2.0):
    x = np.asarray(x, dtype=np.float64)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / RATE)
    return 20 * np.log10(max(float(np.max(spec[np.abs(freqs - f0) <= halfwidth])), 1e-12))


def three_point(rows, tone_hz):
    out = {}
    for tag, (data, _) in rows.items():
        out[tag] = dict(mic=level(np.asarray(data['microphone']) * 2**23, tone_hz),
                        pred=level(np.asarray(data['prediction_pcm']), tone_hz),
                        residual=level(np.asarray(data['residual_pcm']), tone_hz))
    o, b, c = out['open'], out['bypass'], out['cancel']
    return dict(levels=out,
                cd_322_db=b['residual'] - c['residual'],
                loop_boost_db=b['mic'] - o['mic'],
                acoustic_difference_db=b['mic'] - c['mic'],
                overshoot_db=(b['mic'] - c['mic']) - (b['mic'] - o['mic']))
