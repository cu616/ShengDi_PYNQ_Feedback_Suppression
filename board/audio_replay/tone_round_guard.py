"""Tone-round guard and three-point analysis, importable so it can be tested without a board.

The bash entry point (tone_analyze.sh) is a thin wrapper around this module, so the checks that
guard a real round are the same checks that are unit-tested off-board.

C 2026-10-28 added three gaps on top of the five bad-input classes:
  1 the gate can still let the branch continue after a protection stop (fixed in the scripts, not
    here: the gate is now accepted only if it also satisfies the full per-arm predicate)
  2 a tone arm that tripped protection but still wrote an NPZ was not treated as a stop
    (fixed in the scripts; this module additionally refuses such a round)
  3 this module still missed: an actual change in the source ARRAY, a shared WRONG frame count,
    and a failing recovery sidecar (status.json)
"""
import hashlib
import json
from pathlib import Path

import numpy as np

RATE = 48828.125
RAIL_POS, RAIL_NEG = 2**23 - 1, -2**23
IDENTITY = ('package_version', 'bit_sha256', 'hwh_sha256', 'driver_sha256', 'replay_tools_sha256',
            'model_sha256', 'source_pcm16_sha256', 'coefficients_sha256', 'fixture_id', 'hp_volume')
WINDOW = ('frames', 'first_frame', 'completed_frames', 'sound_seconds_nominal')


def _sidecar(path):
    """status.json written next to the npz; the authoritative place for recovery facts."""
    p = Path(path).with_suffix('.status.json')
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_round(manifest_path):
    """Return (manifest, {tag: (arrays, metadata, sidecar)}). Raises ValueError with the reason."""
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
        rows[tag] = (data, json.loads(str(data['metadata_json'])), _sidecar(f))
    if set(rows) != {'open', 'bypass', 'cancel'}:
        raise ValueError('need open/bypass/cancel, got %s' % sorted(rows))
    return man, rows


def _array_sha(arr):
    return hashlib.sha256(np.asarray(arr).tobytes()).hexdigest()


def validate(rows):
    """Return a list of problems; empty means the round is usable."""
    problems = []

    # --- identity: present, non-null, identical -----------------------------------------------
    for key in IDENTITY:
        values = {tag: meta.get(key) for tag, (_, meta, _) in rows.items()}
        if any(v in (None, '') for v in values.values()):
            problems.append('identity missing on %s: %s' % (key, values))
        elif len(set(values.values())) != 1:
            problems.append('identity mismatch on %s: %s' % (key, values))
    if rows['open'][1].get('package_version') != 'audio-replay-v3':
        problems.append('package_version is not audio-replay-v3: %s'
                        % rows['open'][1].get('package_version'))

    # --- the ACTUAL source array, not just its claimed hash (C 2026-10-28 gap 3a) --------------
    src_len, src_sha = {}, {}
    for tag, (data, meta, _) in rows.items():
        if 'source_pcm16' not in data.files:
            problems.append('%s: capture has no source_pcm16 array' % tag)
            continue
        arr = np.asarray(data['source_pcm16'])
        src_len[tag], src_sha[tag] = len(arr), _array_sha(arr)
        if _array_sha(arr) != meta.get('source_pcm16_sha256'):
            problems.append('%s: source array hash does not match its own metadata' % tag)
    if src_len and (len(set(src_len.values())) != 1 or len(set(src_sha.values())) != 1):
        problems.append('source arrays differ between arms: len %s sha %s'
                        % (src_len, {k: v[:8] for k, v in src_sha.items()}))

    # --- gain and arm flags -------------------------------------------------------------------
    gains = {tag: int(meta.get('gain_q12') or 0) for tag, (_, meta, _) in rows.items()}
    if gains['open'] != 0:
        problems.append('open arm was not run at gain 0: %s' % gains['open'])
    if gains['bypass'] == 0 or gains['cancel'] == 0:
        problems.append('bypass/cancel ran at gain 0: %s' % gains)
    if gains['bypass'] != gains['cancel']:
        problems.append('bypass and cancel used different gains: %s' % gains)
    flags = {tag: bool(meta.get('bypass')) for tag, (_, meta, _) in rows.items()}
    if flags != {'open': False, 'bypass': True, 'cancel': False}:
        problems.append('bypass flags are not (open False, bypass True, cancel False): %s' % flags)
    if any(meta.get('zero_coeff') for _, meta, _ in rows.values()):
        problems.append('an arm ran with zero coefficients; the tone round needs the candidate loaded')

    # --- lengths, and the frame accounting against the ARRAYS (C 2026-10-28 gap 3b) -----------
    lengths = {tag: (len(data['microphone']), len(data['prediction_pcm']), len(data['residual_pcm']))
               for tag, (data, _, _) in rows.items()}
    if len(set(lengths.values())) != 1:
        problems.append('array lengths differ: %s' % lengths)
    for tag, (data, meta, _) in rows.items():
        n = len(data['microphone'])
        if int(meta.get('frames') or -1) != n:
            problems.append('%s: metadata frames %s != actual array length %d'
                            % (tag, meta.get('frames'), n))
        ff, cf = meta.get('first_frame'), meta.get('completed_frames')
        if ff is not None and cf is not None and int(ff) + n != int(cf):
            problems.append('%s: first_frame %s + %d != completed_frames %s' % (tag, ff, n, cf))
        budget = int(round(float(meta.get('sound_seconds_nominal') or 0) * RATE))
        if budget and int(cf or 0) != budget:
            problems.append('%s: completed_frames %s != requested %s' % (tag, cf, budget))
    for key in WINDOW:
        values = {tag: meta.get(key) for tag, (_, meta, _) in rows.items()}
        if len(set(values.values())) != 1:
            problems.append('window mismatch on %s: %s' % (key, values))

    # --- the injected-source window must be identical across arms -----------------------------
    windows = {}
    for tag, (data, meta, _) in rows.items():
        n = len(data['microphone'])
        ff = int(meta.get('first_frame') or 0)
        src_n = src_len.get(tag, 0)
        # frames that actually carried injection inside this capture
        injected = max(0, min(n, src_n - ff))
        windows[tag] = (ff, src_n, injected)
    if len(set(windows.values())) != 1:
        problems.append('injected-source window differs between arms: %s' % windows)

    # --- input at the rail -------------------------------------------------------------------
    for tag, (data, meta, _) in rows.items():
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

    # --- no arm may have stopped, and the recovery sidecar must agree (gap 3c) ---------------
    for tag, (_, meta, side) in rows.items():
        if meta.get('stop_reason') != 'completed':
            problems.append('%s: stop_reason=%s (an arm that stopped cannot be part of a depth)'
                            % (tag, meta.get('stop_reason')))
        if meta.get('early_stop'):
            problems.append('%s: early_stop is set' % tag)
        if meta.get('recovery_ok') is False:
            problems.append('%s: metadata says recovery_ok false' % tag)
        if side is None:
            problems.append('%s: no status.json sidecar next to the capture' % tag)
            continue
        if side.get('recovery_ok') is not True:
            problems.append('%s: sidecar recovery_ok=%s' % (tag, side.get('recovery_ok')))
        if side.get('cleanup_errors'):
            problems.append('%s: sidecar cleanup_errors=%s' % (tag, side.get('cleanup_errors')))
        if side.get('save_error'):
            problems.append('%s: sidecar save_error=%s' % (tag, side.get('save_error')))
        if side.get('stop_reason') != 'completed':
            problems.append('%s: sidecar stop_reason=%s' % (tag, side.get('stop_reason')))
    return problems


def level_dbfs(x, f0, halfwidth=2.0):
    """Level in dBFS. All three signals are 24-bit PCM after the *2**23 normalisation below, so the
    three numbers and their differences are in the same unit (C 2026-10-28: units must be stated)."""
    x = np.asarray(x, dtype=np.float64) / 2**23
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / RATE)
    band = np.abs(freqs - f0) <= halfwidth
    return 20 * np.log10(max(float(np.max(spec[band])), 1e-12))


def three_point(rows, tone_hz):
    """The three quantities B 86061a7 defined, in dBFS, with names that match the report."""
    out = {}
    for tag, (data, _, _) in rows.items():
        out[tag] = dict(
            mic=level_dbfs(np.asarray(data['microphone'], dtype=np.float64) * 2**23, tone_hz),
            pred=level_dbfs(np.asarray(data['prediction_pcm'], dtype=np.float64), tone_hz),
            residual=level_dbfs(np.asarray(data['residual_pcm'], dtype=np.float64), tone_hz))
    o, b, c = out['open'], out['bypass'], out['cancel']
    return dict(levels_dbfs=out,
                units='dBFS re 24-bit full scale, all three signals',
                cd_322_db=b['residual'] - c['residual'],
                loop_boost_db=b['mic'] - o['mic'],
                acoustic_difference_db=b['mic'] - c['mic'],
                overshoot_db=(b['mic'] - c['mic']) - (b['mic'] - o['mic']),
                names={'cd_322_db': 'residual depth (model fit, NOT benefit)',
                       'loop_boost_db': 'audible-benefit scale = what the loop adds and a canceller '
                                        'can at most recover',
                       'acoustic_difference_db': 'loop_boost + overshoot, NOT benefit',
                       'overshoot_db': 'cancel goes below the no-loop path by this much'})
