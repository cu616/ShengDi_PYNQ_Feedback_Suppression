"""Local test of the tone-round guard (no board, no audio).

Run: python -X utf8 board/audio_replay/test_tone_round_guard.py

Builds one good synthetic round - including the status.json sidecar - then breaks it in each way C
listed, and asserts the guard rejects every broken one and accepts only the good one. Rejection
samples are derived on copies, so no audible trial is ever needed to prove them.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tone_round_guard import load_round, validate, three_point  # noqa: E402

SCRATCH = HERE / '._tone_guard'
SCRATCH.mkdir(exist_ok=True)
RATE = 48828.125
N = 4096
SRC = 1000
results = []


def case(name, ok, detail=""):
    print("%-58s %s %s" % (name, "OK" if ok else "FAIL", detail))
    results.append(ok)


def make_arm(tag, *, bit22=0, stop='completed', gain=1631, bypass=False, zero=False,
             length=N, mic_rail=False, saturations=0, identity_override=None, window_shift=0,
             source=None, sidecar_override=None, frames_override=None, completed_override=None):
    t = np.arange(length) / RATE
    mic = 0.15 * np.sin(2 * np.pi * 322.0 * t)
    if mic_rail:
        mic = mic.copy()
        mic[10] = 1.0
    completed = SRC + window_shift + length
    meta = dict(
        package_version='audio-replay-v3',
        bit_sha256='b' * 64, hwh_sha256='h' * 64, driver_sha256='d' * 64,
        replay_tools_sha256='r' * 64, model_sha256='m' * 64, source_pcm16_sha256='s' * 64,
        coefficients_sha256='c' * 64, fixture_id='room_v1_20261026b', hp_volume=40,
        gain_q12=gain, bypass=bypass, zero_coeff=zero, capture_status=(1 << 22) if bit22 else 1,
        mic_full_scale_samples=1 if mic_rail else 0, stop_reason=stop, early_stop=stop != 'completed',
        frames=length if frames_override is None else frames_override,
        first_frame=SRC + window_shift,
        completed_frames=completed if completed_override is None else completed_override,
        sound_seconds_nominal=completed / RATE, recovery_ok=True,
        prediction_saturations=saturations, gain_saturations=0, mix_saturations=0,
        residual_saturations=0)
    if identity_override:
        meta.update(identity_override)
    src = np.zeros(SRC, dtype=np.int16) if source is None else np.asarray(source, dtype=np.int16)
    meta['source_pcm16_sha256'] = __import__('hashlib').sha256(src.tobytes()).hexdigest()
    path = SCRATCH / ('%s_%d.npz' % (tag, np.random.randint(1, 10**9)))
    np.savez_compressed(path, microphone=mic, prediction_pcm=np.zeros(length),
                        residual_pcm=np.zeros(length), source_pcm16=src,
                        metadata_json=json.dumps(meta))
    side = dict(recovery_ok=True, cleanup_errors=[], save_error=None, stop_reason='completed')
    if sidecar_override:
        side.update(sidecar_override)
    path.with_suffix('.status.json').write_text(json.dumps(side), encoding='utf-8')
    return tag, path


def build(name, **overrides):
    common = overrides.pop('identity_override_all', None)
    files = []
    for tag, base in (('open', dict(gain=0, bypass=False)),
                      ('bypass', dict(gain=1631, bypass=True)),
                      ('cancel', dict(gain=1631, bypass=False))):
        kwargs = dict(base)
        kwargs.update(overrides.get(tag, {}))
        if common:
            kwargs['identity_override'] = common
        t, path = make_arm(tag, **kwargs)
        files.append(dict(tag=t, path=str(path), exists=True, error=None))
    man = SCRATCH / (name + '.json')
    man.write_text(json.dumps(dict(round_id=1, tone_hz=322.0, amplitude_fs=0.15,
                                   operator_confirmation='test', files=files)), encoding='utf-8')
    return man


def expect_reject(name, man, needle):
    try:
        _, rows = load_round(man)
        problems = validate(rows)
    except ValueError as exc:
        problems = [str(exc)]
    hit = any(needle in p for p in problems)
    case(name, hit, '' if hit else ('got %s' % problems[:2]))


def expect_accept(name, man):
    _, rows = load_round(man)
    problems = validate(rows)
    if problems:
        case(name, False, 'unexpected: %s' % problems[:2])
        return
    tp = three_point(rows, 322.0)
    case(name, True, 'cd=%.2f boost=%.2f diff=%.2f overshoot=%.2f [%s]'
         % (tp['cd_322_db'], tp['loop_boost_db'], tp['acoustic_difference_db'],
            tp['overshoot_db'], tp['units']))


expect_accept('good round is accepted', build('good'))

# C 2026-10-28: a 0.25 full-scale tone must read -12.04 dBFS, not +48.16
from tone_round_guard import level_dbfs  # noqa: E402
_t = np.arange(N) / RATE
_quarter = 0.25 * np.sin(2 * np.pi * 322.0 * _t) * 2**23
_read = level_dbfs(_quarter, 322.0)
case('0.25 full-scale tone reads -12.04 dBFS',
     abs(_read + 12.04) < 0.15, 'read %.2f' % _read)

# the five original bad-input classes
expect_reject('1 missing identity is rejected',
              build('noident', cancel={'identity_override': {'driver_sha256': None}}),
              'identity missing')
expect_reject('2a different gain between arms is rejected',
              build('gain2', cancel={'gain': 2048}), 'different gains')
expect_reject('2b bypass flag wrong is rejected',
              build('flag2', open={'bypass': True}), 'bypass flags')
expect_reject('2c open arm not at gain 0 is rejected',
              build('gain0', open={'gain': 1000}), 'open arm was not run at gain 0')
expect_reject('3 different array length is rejected',
              build('len3', cancel={'length': N - 100}), 'array lengths differ')
expect_reject('3b different window accounting is rejected',
              build('win3', cancel={'window_shift': 7}), 'window mismatch')
expect_reject('4a bit22 set is rejected',
              build('rail4', bypass={'bit22': 1}), 'bit22')
expect_reject('4b microphone sample at the rail is rejected',
              build('rail4b', cancel={'mic_rail': True}), 'at the rail')
expect_reject('4c saturations are rejected',
              build('sat4', cancel={'saturations': 3}), 'prediction_saturations')
expect_reject('5a stopped arm is rejected',
              build('stop5', bypass={'stop': 'input_clip'}), 'stop_reason')
expect_reject('5b early_stop is rejected',
              build('stop5b', cancel={'stop': 'guard'}), 'early_stop')

# C 2026-10-28 gap 3a: the ACTUAL source array changes while the claimed hash stays the same
expect_reject('3a changed source array is rejected',
              build('src3a', cancel={'source': np.ones(SRC, dtype=np.int16)}), 'source arrays differ')

# C 2026-10-28 gap 3b: all three arms share one wrong frame count
expect_reject('3b shared wrong frame count is rejected',
              build('frames3b', open={'frames_override': N - 1},
                    bypass={'frames_override': N - 1}, cancel={'frames_override': N - 1}),
              'actual array length')

# C 2026-10-28 gap 3c: the sidecar says the recovery failed
expect_reject('3c failing recovery sidecar is rejected',
              build('side3c', cancel={'sidecar_override': {'recovery_ok': False}}),
              'sidecar recovery_ok')
expect_reject('3d missing sidecar is rejected',
              build('side3d', bypass={'sidecar_override': {'cleanup_errors': ['x']}}),
              'cleanup_errors')

for path in SCRATCH.glob('*'):
    try:
        path.unlink()
    except OSError:
        pass
try:
    SCRATCH.rmdir()
except OSError:
    pass

print("TONE_ROUND_GUARD_TEST %s (%d checks)" % ("PASS" if all(results) else "FAIL", len(results)))
sys.exit(0 if all(results) else 1)
