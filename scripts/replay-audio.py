"""Offline replay and controlled validation; never emits audio or controls a board."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'board/audio_closed'))
from measurement import MonitorConfig, load_capture, replay  # noqa: E402


def pcm(signal):
    return np.clip(np.rint(np.asarray(signal) * 2**23), -2**23, 2**23 - 1).astype(np.int32)


def controlled_cases():
    """Labels follow explicitly specified input construction, not detector output."""
    rate = 16000.0
    frames = int(2 * rate)
    t = np.arange(frames) / rate
    tone = pcm(0.03 * np.sin(2 * np.pi * 437.5 * t))
    yield 'steady_tone', tone, rate, {}, 'no_growth_detected', None
    rng = np.random.default_rng(616)
    yield 'broadband_noise', pcm(rng.normal(0, .005, frames)), rate, {}, 'no_growth_detected', None
    envelope = np.maximum(0, np.sin(2 * np.pi * 3 * t)) ** 2
    phase = 2 * np.pi * np.cumsum(145 + 8 * np.sin(2 * np.pi * 2 * t)) / rate
    voice = sum((1 - .1 * k) * np.sin((k + 1) * phase) for k in range(5)) * .012 * envelope
    yield 'voiced_proxy_not_real_speech', pcm(voice), rate, {}, 'no_growth_detected', None
    burst = np.where((t >= .7) & (t < .78), .3 * np.sin(2 * np.pi * 437.5 * t), 0)
    yield 'short_tonal_burst', pcm(burst), rate, {}, 'no_growth_detected', None
    yield 'quick_fade_then_steady', pcm(np.minimum(t / .08, 1) * .03 *
                                      np.sin(2 * np.pi * 437.5 * t)), rate, {}, 'no_growth_detected', None
    for name, frequency, speed in [('growth_slow', 437.5, 8),
                                   ('growth_off_bin', 915.3, 24),
                                   ('growth_high_frequency', 7000, 24)]:
        onset = .25
        amplitude = 10 ** ((-60 + speed * np.maximum(t - onset, 0)) / 20)
        yield name, pcm(amplitude * np.sin(2 * np.pi * frequency * t)), rate, {}, 'suspected_howl', onset
    full_scale = tone.copy()
    full_scale[int(rate):int(rate * 1.05)] = 2**23 - 1
    yield 'full_scale_protection', full_scale, rate, {}, 'full_scale', None
    indices = np.r_[np.arange(int(rate * .8)), np.arange(int(rate), frames)]
    yield 'missing_middle', tone[indices], rate, dict(frame_indices=indices, total_frames=frames), 'insufficient_data', None
    count = 5376  # .336 seconds at this fixture rate: cannot establish growth history.
    yield 'tail_only', tone[-count:], rate, dict(first_frame=frames - count, total_frames=frames), 'insufficient_data', None

    # Independent expectation: a causal pure-delay loop with gain 3*.5 > 1
    # grows to clipping; matching cancellation removes that feedback path.
    sys.path.insert(0, str(ROOT / 'src'))
    from feedback.closed_loop_sim import simulate
    room = np.zeros(16); room[3] = .5
    h = np.zeros(256, dtype=np.int64); h[2] = 1 << 19
    source = np.random.default_rng(7).normal(0, 1e-4, 12000)
    for bypass in (False, True):
        result = simulate(room, source, h, 12288, bypass=bypass, keep_signal=True)
        yield ('model_loop_bypass' if bypass else 'model_loop_cancel'), result['played'], 8000.0, {}, (
            'full_scale' if bypass else 'no_growth_detected'), None


def run_demo(config=None):
    results, trace = [], []
    for name, signal, rate, options, expected, onset in controlled_cases():
        result = replay(signal, rate, config=config, **options)
        for row in result.pop('trace'):
            trace.append(dict(case=name, **row))
        passed = result['verdict'] == expected
        alarm = result['first_suspected_howl']
        delay = None
        if onset is not None:
            delay = alarm['time_seconds'] - onset if alarm else None
            passed = passed and delay is not None and 0 <= delay <= 1.25
        results.append(dict(name=name, expected_verdict=expected,
                            construction='Known controlled signal; growth onset explicitly set' if onset is not None
                            else 'Known controlled signal or pure-delay loop with analytic gain condition',
                            growth_onset_seconds=onset, alarm_delay_seconds=delay,
                            passed=bool(passed), result=result))
    return dict(schema_version=1, artifact_kind='controlled_replay_validation',
                hardware_executed=False, cases=results,
                passed=sum(case['passed'] for case in results), total=len(results),
                interpretation='Controlled fixtures only; not real-speech error rates or measured MSG/ASG'), trace


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input', type=Path, help='existing project NPZ; read-only')
    source.add_argument('--demo', action='store_true', help='controlled signals and model-loop replay')
    parser.add_argument('--channel', choices=('residual', 'prediction', 'microphone', 'reference'), default='residual')
    parser.add_argument('--config', type=Path, help='optional JSON object of MonitorConfig overrides')
    parser.add_argument('--output', type=Path, required=True, help='NEW result JSON path')
    parser.add_argument('--trace', type=Path, help='optional NEW per-window CSV path')
    args = parser.parse_args(argv)
    targets = [args.output] + ([args.trace] if args.trace else [])
    if len({path.resolve() for path in targets}) != len(targets):
        parser.error('output and trace must be different paths')
    if any(path.exists() for path in targets):
        parser.error('choose new output paths; existing files are never overwritten')
    try:
        overrides = json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
        config = MonitorConfig(**overrides)
        if args.demo:
            report, trace = run_demo(config)
        else:
            signal, rate, extent, metadata = load_capture(args.input, args.channel)
            report = replay(signal, rate, config=config, **extent)
            trace = [dict(case='input', **row) for row in report.pop('trace')]
            report.update(artifact_kind='offline_capture_replay',
                          input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                          channel=args.channel,
                          coverage_basis='Declared NPZ frame metadata; not independently measured transport coverage',
                          capture_id=metadata.get('capture_id'),
                          fixture_id=metadata.get('fixture_id'))
        encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        for path in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(encoded)
        if args.trace:
            fields = ['case', 'first_frame', 'end_frame', 'time_seconds', 'peak_hz',
                      'rms_dbfs', 'dc_fs', 'tonal_dbfs', 'tonal_fraction', 'history_ready',
                      'growth_candidate', 'rise_db', 'slope_db_per_second', 'fit_r2', 'peak_bin']
            with args.trace.open('x', newline='', encoding='utf-8-sig') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader(); writer.writerows(trace)
        if args.demo:
            print('CONTROLLED_REPLAY: %d/%d passed' % (report['passed'], report['total']))
            for case in report['cases']:
                print('%s: %s; expected=%s; delay=%s' % (
                    case['name'], case['result']['verdict'], case['expected_verdict'], case['alarm_delay_seconds']))
            return 0 if report['passed'] == report['total'] else 1
        print('OFFLINE_REPLAY: %s; declared coverage=%.4f; events=%d' % (
            report['verdict'], report['coverage']['fraction'], len(report['events'])))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    sys.exit(main())
