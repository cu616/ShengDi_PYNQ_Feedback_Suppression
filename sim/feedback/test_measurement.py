"""Offline monitor checks with analytically specified signals and file fixtures."""
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'board/audio_closed'))
from measurement import GrowthMonitor, MonitorConfig, load_capture, replay  # noqa: E402

RATE = 16000.0


def tone(seconds=2, rate=RATE, frequency=500, dbfs=-30):
    t = np.arange(round(seconds * rate)) / rate
    return np.rint(2**23 * 10**(dbfs / 20) * np.sin(2 * np.pi * frequency * t)).astype(np.int32)


def rising(rate=RATE, speed=20, onset=.25):
    t = np.arange(round(2 * rate)) / rate
    amplitude = 10 ** ((-60 + speed * np.maximum(t - onset, 0)) / 20)
    return np.rint(2**23 * amplitude * np.cos(2 * np.pi * 913.7 * t)).astype(np.int32)


class MonitorTests(unittest.TestCase):
    def test_stable_tone_noise_and_silence_do_not_alarm(self):
        rng = np.random.default_rng(29)
        for signal in (tone(), np.zeros(32000, dtype=np.int32),
                       np.rint(rng.normal(0, 1000, 32000)).astype(np.int32)):
            with self.subTest(peak=int(abs(signal).max())):
                result = replay(signal, RATE)
                self.assertEqual(result['verdict'], 'no_growth_detected')
                self.assertIsNone(result['first_suspected_howl'])
                self.assertTrue(result['coverage']['complete'])

    def test_rise_detected_with_bounded_delay_and_frequency(self):
        result = replay(rising(), RATE)
        self.assertEqual(result['verdict'], 'suspected_howl')
        alarm = result['first_suspected_howl']
        self.assertGreaterEqual(alarm['time_seconds'], .25)
        self.assertLessEqual(alarm['time_seconds'] - .25, 1.25)
        self.assertLess(abs(alarm['peak_hz'] - 913.7), RATE / 1024)
        self.assertGreater(alarm['rise_db'], 3)
        self.assertGreater(alarm['slope_db_per_second'], 6)
        self.assertTrue(result['offline_only'])

    def test_window_results_are_invariant_to_packet_size(self):
        signal = rising()
        expected = replay(signal, RATE, chunk_frames=4096)
        for size in (17, 511, len(signal)):
            with self.subTest(chunk=size):
                self.assertEqual(replay(signal, RATE, chunk_frames=size), expected)

    def test_actual_project_sample_rate(self):
        result = replay(rising(rate=48828.125), 48828.125)
        self.assertEqual(result['verdict'], 'suspected_howl')
        self.assertLess(result['first_suspected_howl']['time_seconds'], 1.5)

    def test_short_burst_does_not_become_growth(self):
        signal = np.zeros(32000, dtype=np.int32)
        signal[10000:11280] = tone(.08, dbfs=-10)
        self.assertEqual(replay(signal, RATE)['verdict'], 'no_growth_detected')

    def test_out_of_band_rise_does_not_create_an_in_band_alarm(self):
        t = np.arange(32000) / RATE
        signal = np.rint(2**23 * 10**((-60 + 20 * t) / 20) *
                         np.sin(2 * np.pi * 100 * t)).astype(np.int32)
        config = replace(MonitorConfig(), low_hz=300, high_hz=3000)
        result = replay(signal, RATE, config=config)
        self.assertEqual(result['verdict'], 'no_growth_detected')
        self.assertGreaterEqual(result['analysis']['monitored_first_bin_hz'], 300)

    def test_missing_middle_resets_history_and_cannot_imply_stability(self):
        first = tone(.6, dbfs=-60)
        second = tone(1, dbfs=-10)
        indices = np.r_[np.arange(len(first)), 16000 + np.arange(len(second))]
        result = replay(np.r_[first, second], RATE, frame_indices=indices, total_frames=32000)
        self.assertEqual(result['verdict'], 'insufficient_data')
        self.assertEqual(result['coverage']['missing_intervals'], [[9600, 16000]])
        self.assertIsNone(result['first_suspected_howl'])
        after = [row for row in result['trace'] if row['first_frame'] >= 16000]
        self.assertFalse(after[0]['history_ready'])
        self.assertFalse(any(row['first_frame'] < 16000 < row['end_frame'] for row in result['trace']))

    def test_tail_and_short_complete_record_are_insufficient(self):
        signal = tone(.336)
        tail = replay(signal, RATE, first_frame=32000 - len(signal), total_frames=32000)
        self.assertEqual(tail['verdict'], 'insufficient_data')
        self.assertAlmostEqual(tail['coverage']['fraction'], .168)
        self.assertEqual(tail['coverage']['missing_intervals'], [[0, 26624]])
        short = replay(signal, RATE)
        self.assertTrue(short['coverage']['complete'])
        self.assertFalse(short['coverage']['sufficient_contiguous_history'])
        self.assertEqual(short['verdict'], 'insufficient_data')

    def test_input_and_spectral_coverage_are_distinct(self):
        result = replay(np.zeros(1123, dtype=np.int32), RATE)
        self.assertTrue(result['coverage']['complete'])
        self.assertEqual(result['coverage']['spectral_intervals'], [[0, 1024]])
        self.assertEqual(result['coverage']['spectral_unanalyzed_intervals'], [[1024, 1123]])

    def test_full_scale_event_is_not_a_howl_claim(self):
        signal = np.zeros(100, dtype=np.int32)
        signal[20:22] = [2**23 - 1, -2**23]
        result = replay(signal, RATE, chunk_frames=13)
        self.assertEqual(result['verdict'], 'full_scale')
        self.assertEqual(result['full_scale_samples'], 2)
        self.assertEqual(result['events'][0]['frame'], 20)
        self.assertIsNone(result['first_suspected_howl'])

    def test_positive_warning_survives_later_missing_data(self):
        signal = rising()
        result = replay(signal, RATE, total_frames=40000)
        self.assertEqual(result['verdict'], 'suspected_howl')
        self.assertFalse(result['coverage']['complete'])
        self.assertEqual(result['coverage']['missing_intervals'], [[32000, 40000]])

    def test_bad_pcm_order_and_extent_are_rejected(self):
        for signal in ([2**23], [-2**23 - 1], [float('nan')], [[1, 2]], []):
            with self.subTest(signal=signal), self.assertRaises(ValueError):
                replay(signal, RATE)
        for indices in ([0, 0], [2, 1], [-1, 0]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                replay(np.array([1, 2]), RATE, frame_indices=np.array(indices))
        monitor = GrowthMonitor(RATE)
        monitor.push(np.zeros(100, dtype=np.int32), 0)
        with self.assertRaises(ValueError):
            monitor.push(np.zeros(10, dtype=np.int32), 99)
        with self.assertRaises(ValueError):
            monitor.finish(99)
        monitor.finish(100)
        with self.assertRaises(ValueError):
            monitor.push(np.zeros(10, dtype=np.int32), 100)

    def test_config_validation(self):
        for change in (dict(hop_seconds=0), dict(window_seconds=.001, hop_seconds=.016),
                       dict(minimum_rise_db=-1), dict(minimum_fit_r2=1.1),
                       dict(low_hz=9000), dict(frequency_tolerance_bins=-1),
                       dict(growth_seconds=float('inf'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                GrowthMonitor(RATE, replace(MonitorConfig(), **change))
        with self.assertRaises(ValueError):
            GrowthMonitor(float('nan'))

    def test_empty_stream_has_zero_coverage(self):
        result = GrowthMonitor(RATE).finish(100)
        self.assertEqual(result['verdict'], 'insufficient_data')
        self.assertEqual(result['coverage']['fraction'], 0)
        self.assertEqual(result['coverage']['missing_intervals'], [[0, 100]])


class ReplayFileTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def capture(self, signal=None, **metadata):
        signal = tone() if signal is None else signal
        path = self.folder / 'capture.npz'
        np.savez_compressed(path, residual_pcm=signal, microphone=signal / 2**23,
                            sample_rate_hz=RATE,
                            metadata_json=json.dumps(dict(frames=len(signal), **metadata)))
        return path

    def test_normalized_pcm_and_tail_metadata_round_trip(self):
        original = tone(.336)
        path = self.capture(original, first_frame=26624, completed_frames=32000)
        signal, rate, extent, _ = load_capture(path, 'microphone')
        np.testing.assert_array_equal(signal, original)
        self.assertEqual(rate, RATE)
        result = replay(signal, rate, **extent)
        self.assertEqual(result['coverage']['missing_intervals'], [[0, 26624]])

    def test_dropped_frames_without_positions_are_rejected(self):
        with self.assertRaises(ValueError):
            load_capture(self.capture(dropped_frames=1))

    def test_explicit_frame_positions_preserve_missing_coverage(self):
        path = self.folder / 'indexed.npz'
        indices = np.r_[np.arange(8000), np.arange(16000, 24000)]
        np.savez_compressed(path, residual_pcm=tone(1), frame_indices=indices,
                            sample_rate_hz=RATE,
                            metadata_json=json.dumps(dict(completed_frames=24000, dropped_frames=8000)))
        signal, rate, extent, _ = load_capture(path)
        result = replay(signal, rate, **extent)
        self.assertEqual(result['coverage']['missing_intervals'], [[8000, 16000]])
        self.assertEqual(result['verdict'], 'insufficient_data')

    def test_cli_reads_without_playback_and_refuses_overwrite(self):
        capture = self.capture()
        digest = hashlib.sha256(capture.read_bytes()).hexdigest()
        output, trace = self.folder / 'result.json', self.folder / 'trace.csv'
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/replay-audio.py'),
                   '--input', str(capture), '--output', str(output), '--trace', str(trace)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(result['verdict'], 'no_growth_detected')
        self.assertEqual(result['input_sha256'], digest)
        with trace.open(newline='', encoding='utf-8-sig') as stream:
            self.assertTrue(list(csv.DictReader(stream)))
        old_output = output.read_bytes()
        again = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(output.read_bytes(), old_output)
        self.assertEqual(hashlib.sha256(capture.read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
