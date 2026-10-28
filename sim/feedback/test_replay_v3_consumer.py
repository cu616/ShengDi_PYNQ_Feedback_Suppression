"""C consumer tests for the approved v3 ABI; no hardware imports or operations."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'board/audio_replay'))
from evaluation import analyze_npz, classify, verify_v3_words
from model_comparison import V3_BIT, V3_IDENTITY, V3_IDENTITY_PROFILES, v3_identity_errors, protection_evidence, flat_trial
from replay_tools import verify_replay as old_verify
from tail_metrics import tail_statistics

spec = importlib.util.spec_from_file_location('itemized_consumer', ROOT/'scripts/review_itemized_20261027.py')
itemized = importlib.util.module_from_spec(spec)
spec.loader.exec_module(itemized)
TEST_TEMP = (ROOT/'tmp/v3-consumer-tests').resolve()
assert TEST_TEMP.is_relative_to(ROOT.resolve())
TEST_TEMP.mkdir(parents=True, exist_ok=True)
FS, LO, HI = 48828.125, -2**23, 2**23-1


def nearest(value, bits):
    v = int(value)
    magnitude = (abs(v) + 2**(bits-1)) // 2**bits
    return -magnitude if v < 0 else magnitude


def limit(value):
    return max(LO, min(HI, int(value)))


def trace(n=1024, first=1024, gain=2048, source=None, bypass=False):
    """Independent scalar datapath: h0=-1, mic=.8FS, two-stage clamps."""
    q = np.zeros(512, dtype=np.int64); q[0] = -(1 << 20)
    source = np.zeros(1, dtype='<i2') if source is None else np.asarray(source, dtype='<i2')
    total = n+first
    raw = np.zeros((total, 4), dtype=np.int64)
    wide = np.zeros(total, dtype=np.int64)
    for i in range(total):
        injected = int(source[i])*256 if i < len(source) else 0
        feedback = limit(nearest(wide[i-2]*gain, 12)) if i >= 2 else 0
        played = limit(injected + feedback)
        predicted = limit(-raw[i-1, 0]) if i else 0
        microphone = int(.8*2**23)
        difference = microphone if bypass else microphone-predicted
        wide[i] = difference
        raw[i] = [played, microphone, predicted, limit(difference)]
    return raw[first:], q, source


def metadata(n, first, q, source, **changes):
    m = dict(fixture_id=itemized.FIXTURE, bit_sha256=V3_BIT,
             driver_evidence_version='a-replay-evidence-v2', replay_abi_version=3,
             sample_rate_hz=FS, gain_q12=2048, hp_volume=40, bypass=False,
             zero_coeff=not bool(np.any(q)), frames=n, first_frame=first, completed_frames=first+n,
             logical_taps=512, loaded_taps=512, coefficient_status=8202,
             capture_status=0x8001, input_full_scale_seen=False,
             clip_counts_raw=[0, 0, 0], prediction_saturations=0, residual_saturations=0,
             gain_saturations=0, mix_saturations=0,
             stop_reason='completed', early_stop=False,
             source_frames=len(source), source_end_frame_exclusive=len(source),
             source_schedule_verified=True, positive_control_valid=True,
             source_pcm16_sha256=hashlib.sha256(np.asarray(source, dtype='<i2').tobytes()).hexdigest(),
             coefficients_sha256=hashlib.sha256(np.asarray(q, dtype='<i4').tobytes()).hexdigest(),
             evidence_kind='synthetic_fixture')
    m.update(V3_IDENTITY); m.update(changes)
    return m


def save(path, raw, q, source, m):
    np.savez_compressed(path, reference=raw[:, 0]/2**23, microphone=raw[:, 1]/2**23,
                        prediction_pcm=raw[:, 2], residual_pcm=raw[:, 3], coefficients_q20=q,
                        source_pcm16=source, sample_rate_hz=FS, metadata_json=json.dumps(m))
    path.with_suffix('.status.json').write_text(json.dumps(dict(m, recovery_ok=True)), encoding='utf-8')


class V3ConsumerTests(unittest.TestCase):
    def test_delivered_and_historical_release_tuples_do_not_mix(self):
        for profile in V3_IDENTITY_PROFILES:
            self.assertEqual(v3_identity_errors(profile), [])
        mixed = dict(V3_IDENTITY, replay_tools_sha256=V3_IDENTITY_PROFILES[1]['replay_tools_sha256'])
        self.assertTrue(v3_identity_errors(mixed))
        raw, q, source = trace()
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as folder:
            path = Path(folder)/'release.npz'
            for profile in V3_IDENTITY_PROFILES:
                save(path, raw, q, source, metadata(len(raw), 1024, q, source, **profile))
                reviewed = itemized.review_capture(path)
                self.assertFalse(any('version_binding' in x for x in reviewed['issues']+reviewed['unknown']))
            save(path, raw, q, source, metadata(len(raw), 1024, q, source, **mixed))
            self.assertIn('v3_version_binding_mismatch:release_tuple', itemized.review_capture(path)['issues'])

    def test_sticky_input_full_scale_rejects_clean_captured_tail(self):
        q, source = np.zeros(512, dtype=np.int64), np.zeros(1, dtype='<i2')
        m = metadata(16384, 50000, q, source, input_full_scale_seen=True, capture_status=0x408001)
        result = classify(m, np.zeros(16384, dtype=np.int64), FS)
        self.assertEqual(result['category'], 'invalid')
        self.assertIn('input_full_scale_seen', result['reasons'])
        self.assertTrue(result['event_flags']['input_full_scale_seen'])

    def test_residual_only_is_diagnostic_while_post_gain_still_protects(self):
        q, source = np.zeros(512, dtype=np.int64), np.zeros(1, dtype='<i2')
        m = metadata(16384, 50000, q, source, clip_counts_raw=[7 << 16, 0, 0], residual_saturations=7)
        result = classify(m, np.zeros(16384, dtype=np.int64), FS)
        self.assertNotEqual(result['category'], 'invalid')
        self.assertFalse(result['event_flags']['protection'])
        self.assertTrue(result['event_flags']['residual_saturations'])
        m['clip_counts_raw'][1] = 1
        self.assertTrue(protection_evidence(m)[0])

    def test_mixed_driver_bit_and_helper_identity_are_rejected(self):
        q, source = np.zeros(512, dtype=np.int64), np.zeros(1, dtype='<i2')
        for change in (dict(bit_sha256=itemized.BIT), dict(replay_tools_sha256='a'*64), dict(replay_abi_version=2)):
            with self.subTest(change=change):
                result = classify(metadata(640, 50000, q, source, **change), np.zeros(640, dtype=np.int64), FS)
                self.assertEqual(result['category'], 'invalid')
        untagged = metadata(640, 50000, q, source, bit_sha256=itemized.BIT)
        for key in ('replay_abi_version', *V3_IDENTITY):
            untagged.pop(key)
        self.assertEqual(classify(untagged, np.zeros(640, dtype=np.int64), FS)['category'], 'invalid')

    def test_wide_output_matches_scalar_trace_and_old_oracle_differs(self):
        raw, q, source = trace()
        checked = verify_v3_words(raw, q, False, 2048, source, 1024)
        self.assertTrue(checked['bit_exact'])
        self.assertEqual(checked['output_first_capture_index'], 514)
        self.assertEqual(checked['output_checked_frames'], 510)
        self.assertGreater(checked['wide_residual_frames'], 0)
        self.assertGreater(old_verify(raw, q, False, 2048, source, 1024)['output_mismatches'], 0)

    def test_post_gain_clamp_precedes_mix(self):
        source = np.full(2048, -13000, dtype='<i2')
        raw, q, source = trace(n=1024, first=512, gain=4096, source=source)
        self.assertTrue(verify_v3_words(raw, q, False, 4096, source, 512)['bit_exact'])

    def test_bypass_multiplies_microphone(self):
        raw, q, source = trace(bypass=True)
        self.assertTrue(verify_v3_words(raw, q, True, 2048, source, 1024)['bit_exact'])
        self.assertEqual(verify_v3_words(raw, q, True, 2048, source, 1024)['wide_residual_frames'], 0)

    def test_negative_rail_does_not_count_as_wide_overflow(self):
        raw = np.zeros((640, 4), dtype=np.int64); raw[:, 1] = raw[:, 3] = LO
        checked = verify_v3_words(raw, np.zeros(512, dtype=np.int64), False, 0, np.zeros(1), 0)
        self.assertTrue(checked['bit_exact'])
        self.assertEqual(checked['wide_residual_frames'], 0)

    def test_observed_prefix_wide_events_survive_replay_exclusion(self):
        raw = np.zeros((640, 4), dtype=np.int64)
        q = np.zeros(512, dtype=np.int64); q[-1] = 1 << 20
        raw[:, 1] = raw[:, 3] = HI-50
        raw[:512, 2], raw[:512, 3] = -256, HI
        checked = verify_v3_words(raw, q, False, 0, np.full(1000, -1), 1000)
        self.assertTrue(checked['bit_exact'])
        self.assertEqual(checked['wide_residual_frames'], 512)

    def test_zero_checked_output_frames_are_not_a_pass(self):
        with self.assertRaisesRegex(ValueError, 'no_v3_output_frames'):
            verify_v3_words(np.zeros((513, 4), dtype=np.int64), np.zeros(512), False, 0, np.zeros(1), 1)

    def test_analyze_npz_dispatches_v3_without_overwriting_original(self):
        raw, q, source = trace()
        m = metadata(len(raw), 1024, q, source)
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'capture.npz'; save(p, raw, q, source, m)
            digest = itemized.sha(p)
            result = analyze_npz(p)
            self.assertNotEqual(result['category'], 'invalid', result['reasons'])
            self.assertTrue(result['evaluation_metadata']['verification']['bit_exact'])
            self.assertEqual(result['original_metadata'], m)
            self.assertEqual(itemized.sha(p), digest)

    def test_itemized_adapter_v3_sticky_and_output_scope(self):
        raw, q, source = trace()
        m = metadata(len(raw), 1024, q, source)
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'capture.npz'; save(p, raw, q, source, m)
            result = itemized.review_capture(p)
            self.assertEqual(result['arithmetic']['output_mismatches'], 0)
            self.assertEqual(result['arithmetic']['output_checked_frames'], 510)
            self.assertFalse(result['event_flags']['protection'])
            self.assertFalse(result['event_flags']['captured_input_clipped'])
            m.update(input_full_scale_seen=True, capture_status=0x408001)
            save(p, raw, q, source, m)
            result = itemized.review_capture(p)
            self.assertIn('input_full_scale_seen', result['issues'])
            self.assertTrue(result['event_flags']['input_clipped'])

    def test_itemized_adapter_requires_v3_identity_binding(self):
        q, source = np.zeros(512, dtype=np.int64), np.zeros(1, dtype='<i2')
        m = metadata(640, 0, q, source)
        del m['driver_sha256']
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'capture.npz'; save(p, np.zeros((640, 4), dtype=np.int64), q, source, m)
            result = itemized.review_capture(p)
            self.assertIn('v3_driver_sha256_missing', result['unknown'])
            self.assertFalse(result['captured_numeric_checks_clear'])

    def test_protocol_failure_keeps_arithmetic_but_blocks_completion(self):
        q, source = np.zeros(512, dtype=np.int64), np.zeros(1, dtype='<i2')
        m = metadata(640, 50000, q, source, capture_status=1 | (1 << 18),
                     stop_reason='fault', early_stop=True)
        self.assertEqual(classify(m, np.zeros(640, dtype=np.int64), FS)['category'], 'invalid')
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'fault.npz'; save(p, np.zeros((640, 4), dtype=np.int64), q, source, m)
            result = itemized.review_capture(p)
            self.assertFalse(result['execution_completed'])
            self.assertIn('v3_config_or_protocol_fault', result['issues'])
            self.assertEqual(result['arithmetic']['output_mismatches'], 0)

    def test_tail_wide_statistics_do_not_call_pre_gain_range_input_clipping(self):
        n, first = 16384, 50000
        t = np.arange(n)/FS
        mic = np.rint(2**23*.25*(np.sin(2*np.pi*500*t)+np.sin(2*np.pi*2000*t)+np.sin(2*np.pi*8400*t))).astype(np.int64)
        residual = 2*mic
        self.assertGreater(np.max(np.abs(residual)), HI)
        m = metadata(n, first, np.zeros(512), np.zeros(1), external_source_off_verified=True)
        result = tail_statistics(mic, residual, m, FS, residual_wide=True)
        self.assertTrue(result['tail_valid'], result['tail_reasons'])
        self.assertEqual(result['residual_semantics'], 'wide25_pre_gain')
        for ratio in result['tail_residual_over_mic_db'].values():
            self.assertAlmostEqual(ratio, 6.020599913, places=7)

    def test_flat_summary_keeps_residual_diagnostic_and_rejects_input_sticky(self):
        n = 16384
        t = np.arange(n)/FS
        mic = np.rint(2**23*.01*(np.sin(2*np.pi*500*t)+np.sin(2*np.pi*2000*t)+np.sin(2*np.pi*8400*t))).astype(np.int64)
        m = metadata(n, 50000, np.zeros(512), np.zeros(1),
                     external_source_off_verified=True, mute_during_observation=False,
                     clip_counts_raw=[8 << 16, 0, 0], residual_saturations=8,
                     verification={'bit_exact': True})
        flags = dict(microphone_clipping=False, prediction_saturations=False,
                     residual_saturations=True, gain_saturations=False, mix_saturations=False)
        analysis = dict(category='unknown', evaluation_metadata=m, event_flags=flags,
                        tail_statistics=tail_statistics(mic, mic, m, FS, residual_wide=True))
        result = flat_trial(dict(analysis=analysis))
        self.assertNotIn('safety_not_validated', result['eligibility_reasons'])
        self.assertFalse(result['effect_eligible'])  # explicitly synthetic, never field evidence
        m.update(input_full_scale_seen=True, capture_status=0x408001)
        result = flat_trial(dict(analysis=analysis))
        self.assertEqual(result['category'], 'invalid')
        self.assertFalse(result['effect_eligible'])


if __name__ == '__main__':
    unittest.main()
