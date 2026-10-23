"""Analytic signals and literal register words, not shared implementation oracles."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'board/audio_replay'))
from evaluation import classify, unpack_counts, window_gate, analyze_npz

FS = 8000


def metadata(n=2400, first=16000):
    return dict(frames=n, first_frame=first, completed_frames=first+n,
                source_frames=8000, source_end_frame_exclusive=8000,
                source_schedule_verified=True, transition_frames=400,
                positive_control_valid=True, prediction_saturations=0,
                residual_saturations=0, gain_saturations=0, mix_saturations=0,
                verification={'bit_exact': True})


def tone(growth=0., n=2400):
    t = np.arange(n)/FS
    # The envelope rises EXACTLY growth dB/sec, independent of FFT/regression.
    return np.rint(2**23 * .01 * 10**(growth*t/20) * np.sin(2*np.pi*1000*t)).astype(np.int64)


class EvaluationTests(unittest.TestCase):
    def test_literal_packed_counts(self):
        self.assertEqual(list(unpack_counts([0x00030002, 5, 7]).values()), [2, 3, 5, 7])
        self.assertEqual(list(unpack_counts([0xffff0000, 0, 0]).values()), [0, 65535, 0, 0])
        for bad in ([0, 0], [-1, 0, 0], [2**32, 0, 0]):
            with self.assertRaises(ValueError):
                unpack_counts(bad)

    def test_source_playing_and_boundary(self):
        m = metadata(500, 0)
        out = classify(m, tone(n=500), FS)
        self.assertFalse(out['window']['pure_tail'])
        self.assertTrue(out['window']['source_active_at_stop'])
        self.assertEqual(out['category'], 'unknown')
        self.assertNotIn('detector', out)
        self.assertFalse(window_gate(metadata(first=8399), FS)['pure_tail'])
        self.assertTrue(window_gate(metadata(first=8400), FS)['pure_tail'])

    def test_planned_end_never_promoted_to_actual(self):
        m = metadata(); del m['source_end_frame_exclusive']
        self.assertEqual(classify(m, tone(), FS)['category'], 'unknown')

    def test_stable_tone_and_decay(self):
        for rise in (0, -40):
            self.assertEqual(classify(metadata(), tone(rise), FS)['category'],
                             'no_instability_observed_in_window')

    def test_speech_surrogate(self):
        # Nonstationary broad noise with a fixed seed has no persistent tonal mode.
        rng = np.random.default_rng(177)
        t = np.arange(2400)/FS
        x = np.rint(2**23*.015*rng.normal(size=2400)*(1+.5*np.sin(2*np.pi*5*t))).astype(np.int64)
        self.assertEqual(classify(metadata(), x, FS)['category'], 'no_instability_observed_in_window')

    def test_exponential_growth(self):
        out = classify(metadata(), tone(60), FS)
        self.assertEqual(out['category'], 'observed_instability')
        e = out['instability_evidence'][0]
        self.assertAlmostEqual(e['slope_db_per_second'], 60, delta=.2)
        self.assertGreaterEqual(e['evidence_first_frame'], 16000)

    def test_growth_and_protection_coexist(self):
        m = metadata(); m['guard_tripped'] = True
        out = classify(m, tone(60), FS)
        self.assertEqual(out['category'], 'observed_instability')
        self.assertTrue(out['event_flags']['protection'])

    def test_clipped_tone_is_not_howl(self):
        x = np.clip(tone()*200, -2**23, 2**23-1)
        out = classify(metadata(), x, FS)
        self.assertEqual(out['category'], 'unknown')
        self.assertTrue(out['event_flags']['microphone_clipping'])
        self.assertFalse(out['event_flags']['instability_growth'])

    def test_bypass_prediction_saturation_only(self):
        m = metadata(); m.update(bypass=True, prediction_saturations=5, guard_tripped=True)
        out = classify(m, tone(), FS)
        self.assertEqual(out['category'], 'protection')
        self.assertFalse(out['event_flags']['instability_growth'])

    def test_noise_floor_and_missing_positive_control(self):
        self.assertEqual(classify(metadata(), np.zeros(2400, dtype=int), FS)['category'], 'unknown')
        m = metadata(); m['positive_control_valid'] = False
        self.assertEqual(classify(m, tone(), FS)['category'], 'unknown')

    def test_gap_alignment_configuration_and_version(self):
        for change in ({'frames': 2399}, {'dropped_frames': 1},
                       {'frame_indices': list(range(16000, 18400, 2))},
                       {'reference_alignment_verified': False}, {'version_valid': False}):
            m = metadata(); m.update(change)
            self.assertEqual(classify(m, tone(), FS)['category'], 'invalid')
        self.assertEqual(classify(metadata(), tone(), FS, {'bit_sha256': 'abc'})['category'], 'invalid')

    def test_short_tail_no_slope(self):
        out = classify(metadata(n=30), tone(n=30), FS)
        self.assertEqual(out['category'], 'unknown')
        self.assertFalse(out['instability_evidence'])

    def test_unrecoverable_old_guard_and_no_confidence(self):
        m = metadata(); m.update(artifact_kind='replay_trial_guard', guard_tripped=True,
                                 prediction_saturations=65535, residual_saturations=5, gain_saturations=7)
        out = classify(m, tone(), FS)
        self.assertIsNone(out['counts']['prediction_saturations'])
        self.assertNotIn('confidence', json.dumps(out))

    def test_invalid_counts_retain_protection_and_missing_file(self):
        m = metadata(); m.update(guard_tripped=True, clip_counts_raw=[-1, 0, 0])
        out = classify(m, tone(), FS)
        self.assertEqual(out['category'], 'invalid')
        self.assertTrue(out['event_flags']['protection'])
        self.assertEqual(analyze_npz(ROOT/'tmp/nonexistent-c-measurement.npz')['category'], 'invalid')

    def test_npz_bad_shape_and_read_only(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            p = Path(d)/'bad.npz'
            np.savez(p, reference=np.zeros(5), microphone=np.zeros(6),
                     prediction_pcm=np.zeros(5, dtype=int), residual_pcm=np.zeros(5, dtype=int),
                     sample_rate_hz=FS, metadata_json=json.dumps(metadata()))
            before = p.read_bytes()
            self.assertEqual(analyze_npz(p)['category'], 'invalid')
            self.assertEqual(before, p.read_bytes())


if __name__ == '__main__':
    unittest.main()
