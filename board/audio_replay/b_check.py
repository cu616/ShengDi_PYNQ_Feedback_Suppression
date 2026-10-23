"""A's explicit-level trial runner for B's model-prediction check.

Runs paired trials at gains chosen by B (not by the model envelope), because B's
prediction is that the loop goes unstable at -24 dB with cancellation OFF.
Import never plays audio; only main() does, and only with --run.

Source level is an explicit argument: the package's own model-based source cap
is what made the 2026-10-21 direct playback inaudible, and it cannot be used to
plan an audibility test.

Output: one NPZ per trial plus summary.json, updated after every trial.
"""
import argparse
import hashlib
import json
import math
import sys
import time
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from replay_trial import replay_trial          # noqa: E402
from closed_tools import trial_parameters      # noqa: E402

RATE = 48828.125
MAX_SOURCE_FRAMES = 131072

STAGES = {
    # B's request: at each level run cancellation first, then bypass.
    'bcheck': [('cancel', -32.0, 6.0), ('bypass', -32.0, 6.0),
               ('cancel', -24.0, 6.0), ('bypass', -24.0, 6.0),
               ('cancel', -12.5, 6.0), ('bypass', -12.5, 4.0)],
    # Precondition B asked for: confirm normal speech is actually audible.
    'direct': [('direct', 0.0, 2.5)],
    # ASG ladder on the overlay whose microphone path is verified.
    'replay_ladder': [('cancel', -24.0, 2.05), ('bypass', -24.0, 2.05),
                      ('cancel', -18.0, 2.05), ('bypass', -18.0, 2.05),
                      ('cancel', -12.0, 2.05), ('bypass', -12.0, 2.05),
                      ('cancel', -9.0, 2.05), ('bypass', -9.0, 2.05)],
    # Continuation: bracket the bypass onset and find the cancellation onset.
    'replay_rest': [('bypass', -21.0, 2.05),
                    ('cancel', -12.0, 2.05), ('cancel', -9.0, 2.05),
                    ('cancel', -6.0, 2.05), ('cancel', -3.0, 2.05),
                    ('cancel', 0.0, 2.05)],
    # 1.5 dB refinement around both onsets (bypass first, stops at its onset).
    'fine_bypass': [('bypass', -21.0, 2.05), ('bypass', -19.5, 2.05),
                    ('bypass', -18.0, 2.05)],
    'fine_cancel': [('cancel', -18.0, 2.05), ('cancel', -16.5, 2.05),
                    ('cancel', -15.0, 2.05), ('cancel', -13.5, 2.05),
                    ('cancel', -12.0, 2.05)],
    # B's low reference level, for completeness of the three requested levels.
    'b_levels': [('cancel', -32.0, 2.05), ('bypass', -32.0, 2.05)],
    # Output-path A/B: same -26 dB loop, phone as the only excitation.
    'out_check': [('bypass', -26.0, 2.5)],
    # girl_voice (real speech) injected digitally, ascending per mode.
    'voice_cancel': [('cancel', -27.0, 2.05), ('cancel', -24.0, 2.05), ('cancel', -21.0, 2.05),
                     ('cancel', -18.0, 2.05), ('cancel', -16.5, 2.05), ('cancel', -15.0, 2.05),
                     ('cancel', -13.5, 2.05)],
    # 10 s window at gains just below the measured onsets: does it keep growing?
    'long_window': [('bypass', -18.0, 10.0), ('cancel', -19.5, 10.0)],
    'long_noise': [('cancel', -15.0, 10.0), ('bypass', -21.0, 10.0)],
    'voice_bypass': [('bypass', -27.0, 2.05), ('bypass', -24.0, 2.05), ('bypass', -21.0, 2.05),
                     ('bypass', -19.5, 2.05), ('bypass', -18.0, 2.05)],
}


def prepare(path, peak_dbfs):
    """Left channel, resampled to RATE, faded, scaled to an explicit peak."""
    with wave.open(str(path), 'rb') as stream:
        channels, width, rate, n = (stream.getnchannels(), stream.getsampwidth(),
                                    stream.getframerate(), stream.getnframes())
        if (channels not in (1, 2) or width not in (2, 3, 4) or
                not 8000 <= rate <= 48000 or not 0.5 <= n / rate <= 2.5 or
                stream.getcomptype() != 'NONE'):
            raise ValueError('unsupported source.wav format')
        data = stream.readframes(n)
    if width == 3:
        b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int64)
        pcm = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        pcm = np.where(pcm >= 2**23, pcm - 2**24, pcm)
    else:
        pcm = np.frombuffer(data, dtype='<i%d' % width).astype(np.int64)
    x = pcm.reshape(-1, channels)[:, 0] / float(2**(8 * width - 1))
    if np.max(np.abs(x)) >= 0.999:
        raise ValueError('source recording clipped; do not replay')
    x -= np.mean(x)
    if np.std(x) < 1e-5:
        raise ValueError('source recording is silent')
    count = int(math.floor(n * RATE / rate))
    if count > MAX_SOURCE_FRAMES:
        raise ValueError('source exceeds hardware memory')
    x = np.interp(np.arange(count) * rate / RATE, np.arange(n), x)
    fade = min(int(0.01 * RATE), count // 4)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    peak = int(round((10 ** (peak_dbfs / 20.0)) * 32768))
    scaled = x * peak / np.max(np.abs(x))
    pcm16 = (np.sign(scaled) * np.floor(np.abs(scaled) + .5)).astype('<i2')
    return pcm16, dict(
        wav_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        pcm16_sha256=hashlib.sha256(pcm16.tobytes()).hexdigest(),
        raw_peak_dbfs=float(20 * np.log10(max(float(np.max(np.abs(x))), 1e-12))),
        raw_rms_dbfs=float(20 * np.log10(max(float(np.std(x)), 1e-12))),
        injected_peak_dbfs=20 * math.log10(peak / 32768.0),
        frames=count, rate_hz=RATE, interpretation='explicit level, not model-bound')


def run(args):
    if args.zero_source:
        source = np.zeros(4, '<i2')
        source_info = dict(injected_peak_dbfs=-120.0, frames=len(source),
                            interpretation='silent source; phone is the excitation')
    else:
        source, source_info = prepare(args.source, args.peak_dbfs)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = STAGES[args.stage]
    if args.seconds is not None:
        spec = [(mode, gain, args.seconds) for mode, gain, _ in spec]
    summary = dict(schema_version=1, artifact_kind='b_check', stage=args.stage,
                   source=source_info, source_path=str(args.source), peak_dbfs=args.peak_dbfs,
                   model_path=str(args.model), fixture_id=args.fixture,
                   hp_volume=args.hp_volume, bit_sha256=hashlib.sha256(
                       (HERE / 'audio_replay.bit').read_bytes()).hexdigest(),
                   trials=[], stop_reason=None,
                   interpretation='explicit-gain paired trials; NOT measured MSG/ASG')
    print('B_CHECK_SOURCE', json.dumps(source_info, ensure_ascii=False), flush=True)

    def save():
        tmp = out_dir / 'summary.json.tmp'
        tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(out_dir / 'summary.json')

    save()
    for index, (mode, gain, seconds) in enumerate(spec, 1):
        row = dict(index=index, mode=mode, gain_db_requested=gain, seconds=seconds)
        summary['trials'].append(row)
        save()
        path = out_dir / ('%02d_%s_%+gdb.npz' % (index, mode, gain))
        print('[%d/%d] %s gain=%+.1f dB %gs STARTING' % (index, len(spec), mode, gain, seconds),
              flush=True)
        time.sleep(1.5)
        started = time.monotonic()
        try:
            meta = replay_trial(path, args.fixture, str(args.model), source,
                                bypass=(mode == 'bypass'), zero_coeff=False, gain_db=gain,
                                seconds=seconds, hp_volume=args.hp_volume,
                                speaker_confirmed=True, local_capture_confirmed=True,
                                direct_only=(mode == 'direct'))
            row.update(status='complete', metadata=meta)
        except Exception as exc:                                    # noqa: BLE001
            row.update(status='stopped', error=type(exc).__name__ + ': ' + str(exc))
        row['wall_seconds'] = round(time.monotonic() - started, 3)
        meta = row.get('metadata') or {}
        print('[%d/%d] %s %+.1f dB -> %s in %.2fs | mic_rms=%s mic_peak=%s full_scale=%s '
              'pred_sat=%s res_sat=%s gain_sat=%s mix_sat=%s bit_exact=%s' % (
                  index, len(spec), mode, gain, row['status'], row['wall_seconds'],
                  meta.get('mic_rms_dbfs'), meta.get('mic_peak_dbfs'),
                  meta.get('mic_full_scale_samples'), meta.get('prediction_saturations'),
                  meta.get('residual_saturations'), meta.get('gain_saturations'),
                  meta.get('mix_saturations'), (meta.get('verification') or {}).get('bit_exact')),
              flush=True)
        save()
        if row['status'] != 'complete' and mode in ('cancel', 'direct'):
            summary['stop_reason'] = 'unexpected stop in %s at %+.1f dB' % (mode, gain)
            break
        if row['status'] != 'complete' and mode == 'bypass':
            summary['stop_reason'] = ('bypass did not complete at %+.1f dB (guard or fault); '
                                      'this is the answer for this level' % gain)
            break
    if summary['stop_reason'] is None:
        summary['stop_reason'] = 'all planned trials completed'
    save()
    print('B_CHECK_DONE', str(out_dir / 'summary.json'), flush=True)
    print(json.dumps([[t['index'], t['mode'], t['gain_db_requested'], t['status']]
                      for t in summary['trials']], ensure_ascii=False), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=sorted(STAGES), default='direct')
    parser.add_argument('--source', default=str(HERE / 'source.wav'))
    parser.add_argument('--model', default='/home/xilinx/jupyter_notebooks/base/audio/'
                                           'audio_calibrate/candidate_box_v1_256.json')
    parser.add_argument('--out-dir', default='/home/xilinx/bcheck_results')
    parser.add_argument('--peak-dbfs', type=float, default=-20.0)
    parser.add_argument('--zero-source', action='store_true')
    parser.add_argument('--seconds', type=float, default=None,
                        help='override per-trial seconds so the capture covers the source')
    parser.add_argument('--fixture', default='box_v1_20261016')
    parser.add_argument('--hp-volume', type=int, default=40)
    parser.add_argument('--run', action='store_true', help='required: import alone never plays')
    args = parser.parse_args(argv)
    if not args.run:
        print('DRY_RUN; add --run to play audio')
        return 0
    run(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
