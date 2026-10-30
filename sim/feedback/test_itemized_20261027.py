"""Targeted numeric/coverage regressions for the 2026-10-27 field review.

Fixtures reproduce boundaries and reported census counts, not missing human PCM.
"""
import hashlib
import importlib.util
import json
import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEST_TEMP = (ROOT/'tmp/itemized-20261027-tests').resolve()
assert TEST_TEMP.is_relative_to(ROOT.resolve())
TEST_TEMP.mkdir(parents=True, exist_ok=True)
SPEC = importlib.util.spec_from_file_location('itemized_review', ROOT/'scripts/review_itemized_20261027.py')
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


def fixture(path, mic, first=0, q=None, pred=None, counts=(0, 0, 0), source=None, **changes):
    mic = np.asarray(mic, dtype=np.int64)
    n = len(mic)
    q = np.zeros(512, dtype=np.int64) if q is None else np.asarray(q, dtype=np.int64)
    pred = np.zeros(n, dtype=np.int64) if pred is None else np.asarray(pred, dtype=np.int64)
    residual = np.clip(mic-pred, review.MINIMUM, review.MAXIMUM)
    source = np.zeros(1, dtype='<i2') if source is None else np.asarray(source, dtype='<i2')
    indices = np.arange(first, first+n)
    injection = np.zeros(n, dtype=np.int64)
    active = indices < len(source)
    injection[active] = source[indices[active]].astype(np.int64)*256
    reference = np.clip(injection + np.r_[0, 0, review.rounded_shift(residual[:-2]*1631, 12)], review.MINIMUM, review.MAXIMUM)
    meta = dict(fixture_id=review.FIXTURE, bit_sha256=review.BIT, hp_volume=40,
                sample_rate_hz=48828.125, gain_q12=1631, zero_coeff=not np.any(q),
                bypass=False, frames=n, first_frame=first, completed_frames=first+n,
                logical_taps=512, loaded_taps=512, coefficient_status=8202,
                stop_reason='completed', clip_counts_raw=list(counts),
                source_schedule_verified=True, source_end_frame_exclusive=len(source),
                source_pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest(),
                coefficients_sha256=hashlib.sha256(q.astype('<i4').tobytes()).hexdigest())
    meta.update(review.unpack_counts(list(counts)))
    meta.update(changes)
    np.savez_compressed(path, microphone=mic/review.SCALE, reference=reference/review.SCALE,
                        prediction_pcm=pred, residual_pcm=residual, coefficients_q20=q,
                        source_pcm16=source, sample_rate_hz=48828.125,
                        metadata_json=json.dumps(meta))
    path.with_suffix('.status.json').write_text(json.dumps(dict(meta, recovery_ok=True)), encoding='utf-8')


class ItemizedReviewTests(unittest.TestCase):
    def test_signed24_legal_rails_are_not_arithmetic_overflow(self):
        x = np.array([-8388609, -8388608, -8388607, 8388606, 8388607, 8388608])
        self.assertEqual(review.outside_pcm(x).tolist(), [True, False, False, False, False, True])

    def test_gain_negative_half_rounds_away_from_zero(self):
        product = np.array([-6145, -6144, -2049, -2048, -2047, 2047, 2048, 6144])
        # Independent hand-rounded Q12 boundaries, matching RTL magnitude rounding.
        self.assertEqual(review.rounded_shift(product, 12).tolist(), [-2, -2, -1, -1, 0, 0, 1, 2])

    def test_counter_word_preserves_both_16_and_full_32_bit_fields(self):
        self.assertEqual(list(review.unpack_counts([0x00080000, 70000, 131073]).values()), [0, 8, 70000, 131073])
        self.assertEqual(review.unpack_counts([0xffff0000, 0, 0])['residual_saturations'], 65535)

    def test_invalid_counter_keeps_independent_input_observation(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'bad-count.npz'
            mic = np.zeros(1024, dtype=np.int64); mic[-1] = review.MINIMUM
            fixture(p, mic, clip_counts_raw=[-1, 0, 0])
            r = review.review_capture(p)
            self.assertIn('raw_counter_words_invalid', r['issues'])
            self.assertIsNone(r['event_flags']['protection'])
            self.assertEqual(r['measurement']['microphone_negative_rail_samples'], 1)
            self.assertTrue(r['event_flags']['input_clipped'])

    def test_spectral_power_obeys_parseval_and_band_share_identity(self):
        rng = np.random.default_rng(4242)
        n, fs = 16384, 48828.125
        x = .1 + .03*rng.normal(size=n) + .08*np.sin(2*np.pi*328*np.arange(n)/fs)
        m = review.power_metrics(x, fs)
        w = np.hanning(n)
        independent = np.sum(((x-x.mean())*w)**2)/np.sum(w*w)
        self.assertAlmostEqual(m['spectral_total_power'], independent, places=14)
        self.assertAlmostEqual(m['band_300_360_dbfs'], m['spectral_total_dbfs'] + 10*np.log10(m['band_share']), places=12)
        self.assertNotEqual(m['rms_including_dc_dbfs'], m['centered_rms_dbfs'])

    def test_summary_numbers_are_consistency_only(self):
        share_drop = 10*np.log10(.2281/.0476)
        self.assertAlmostEqual(share_drop, 6.8052, places=4)
        self.assertAlmostEqual(share_drop + 3.3, 10.1052, places=4)
        self.assertAlmostEqual(10*np.log10(.713/.008), 19.5, places=3)

    def test_reported_zero_rail_census_does_not_become_good_baseline(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'zero.npz'
            mic = np.zeros(16384, dtype=np.int64)
            mic[9772:9772+2197] = review.MAXIMUM
            mic[9772+2197:9772+2197+1162] = review.MINIMUM
            fixture(p, mic, first=447483)
            result = review.review_capture(p)
            self.assertEqual(result['measurement']['microphone_rail_samples'], 3359)
            self.assertEqual(result['residual_event']['observed_residual_overflows'], 0)
            self.assertFalse(result['captured_numeric_checks_clear'])
            self.assertFalse(result['event_flags']['protection'])
            self.assertIn('captured_microphone_clipping', result['issues'])

    def test_eight_rail_samples_alone_do_not_prove_eight_overflows(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'legal.npz'
            mic = np.zeros(16384, dtype=np.int64)
            mic[16353:16361] = review.MAXIMUM
            fixture(p, mic, first=98334)
            r = review.review_capture(p)
            self.assertEqual(r['residual_event']['observed_residual_overflows'], 0)
            self.assertIsNone(r['residual_event']['first_in_capture_global_frame'])

    def test_reported_candidate_extent_and_event_census_keeps_scope(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'candidate-shape.npz'
            mic, pred = np.zeros(16384, dtype=np.int64), np.zeros(16384, dtype=np.int64)
            mic[16353:16361], pred[16353:16361] = review.MAXIMUM-100, -200
            fixture(p, mic, first=98334, pred=pred, counts=(8 << 16, 0, 0), stop_reason='guard')
            r = review.review_capture(p)
            e = r['residual_event']
            self.assertEqual(e['observed_residual_overflows'], 8)
            self.assertEqual(e['first_in_capture_global_frame'], 114687)
            self.assertTrue(e['observed_count_equals_unsaturated_final_counter'])
            self.assertTrue(e['full_run_first_event'].startswith('unknown'))
            self.assertTrue(r['event_flags']['protection'])
            self.assertIsNone(e['frequency_of_first_event_hz'])

    def test_tail_history_is_excluded_from_local_predictor_replay(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'history.npz'
            q = np.zeros(512, dtype=np.int64); q[0] = 1
            pred = np.zeros(1024, dtype=np.int64); pred[0] = 17
            fixture(p, np.zeros(1024), first=50000, q=q, pred=pred)
            r = review.review_capture(p)
            self.assertEqual(r['arithmetic']['history_excluded_frames'], 512)
            self.assertEqual(r['arithmetic']['prediction_mismatches'], 0)
            self.assertEqual(r['arithmetic']['prediction_evaluated_frames'], 512)

    def test_identity_bad_extent_and_status_disagreement_cannot_pass(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'identity.npz'
            fixture(p, np.zeros(1024), coefficients_sha256='wrong', completed_frames=2000, loaded_taps=256)
            side = p.with_suffix('.status.json')
            status = json.loads(side.read_text(encoding='utf-8')); status['residual_saturations'] = 8
            side.write_text(json.dumps(status), encoding='utf-8')
            r = review.review_capture(p)
            self.assertFalse(r['captured_numeric_checks_clear'])
            for reason in ('actual_q20_identity_mismatch', 'actual_capture_extent_missing_or_inconsistent',
                           'status_metadata_mismatch:residual_saturations', 'decoded_counter_mismatch:residual_saturations',
                           'loaded_taps_mismatch'):
                self.assertIn(reason, r['issues'])

    def test_clean_tail_does_not_certify_full_run_adc(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'clean-tail.npz'
            fixture(p, np.zeros(1024), first=2928663)
            r = review.review_capture(p)
            self.assertTrue(r['captured_numeric_checks_clear'])
            self.assertFalse(r['whole_run_adc_headroom_verified'])
            self.assertEqual(r['actual_interval']['missing_waveform_intervals'], [[0, 2928663]])

    def test_source_on_and_transition_windows_are_not_mixed(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'source-window.npz'
            source = np.full(97656, 32, dtype='<i2')
            fixture(p, np.zeros(16384), first=91037, source=source)
            r = review.review_capture(p)
            on = r['interval_measurements']['source_on']
            tail = r['interval_measurements']['source_off_after_50ms']
            self.assertEqual((on['first_frame'], on['end_frame'], on['microphone']['frames']), (91037, 97656, 6619))
            self.assertEqual((tail['first_frame'], tail['end_frame']), (100098, 107421))
            self.assertEqual(r['arithmetic']['output_mismatches'], 0)

    def test_aligned_nonstationary_source_pair_and_mismatch_rejection(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'pair.npz'
            fixture(p, np.zeros(1024))
            a = review.review_capture(p)
            a['source_has_nonzero_samples'] = True
            a['source_pcm16_sha256'] = 'same-known-digital-segment'
            b = copy.deepcopy(a)
            b['identity']['actual_q20_sha256'] = review.CANDIDATE
            t = np.arange(16384)/48828.125
            envelope = np.linspace(.01, .1, len(t))
            a['measurement'] = review.power_metrics(envelope*(np.sin(2*np.pi*328*t)+np.sin(2*np.pi*800*t)), 48828.125)
            b['measurement'] = review.power_metrics(envelope*(.3*np.sin(2*np.pi*328*t)+np.sin(2*np.pi*800*t)), 48828.125)
            delta = review.source_pairs([a, b])[0]['windows']['whole_capture']
            self.assertAlmostEqual(delta['absolute_band_drop_db'], delta['share_drop_db']+delta['spectral_total_drop_db'], places=10)
            b['source_pcm16_sha256'] = 'different-segment'
            self.assertEqual(review.source_pairs([a, b]), [])


def probe_b_analyzer(path):
    """Run the same boundary contract against a specified B revision, read-only."""
    import inspect
    spec = importlib.util.spec_from_file_location('B_analyzer_under_review', path)
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    new_api = 'model_label' in inspect.signature(analyzer.analyze).parameters

    def call(p):
        with np.errstate(divide='ignore', invalid='ignore'):
            return analyzer.analyze(p, None, None, None) if new_api else analyzer.analyze(p)

    def primary(r):
        return r['primary_capture_only'] if new_api else r['overflow']

    def overflow(r):
        return primary(r)['overflow_in_valid_window' if new_api else 'samples_over']

    def maximum_output(r):
        return r['post_gain']['max_abs'] if new_api else r['output']['max_abs_after_gain']

    def rejected(r):
        return (r.get('valid') is False or bool(r.get('issues')) or
                r.get('attribution', {}).get('allowed') is False)

    results = []
    with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
        p = Path(d)/'negative-rail.npz'
        fixture(p, np.full(1024, review.MINIMUM))
        r = call(p)
        results.append(dict(case='legal_negative_rail', expected=0,
                            observed=overflow(r), passed=overflow(r) == 0))
        p = Path(d)/'negative-half.npz'
        fixture(p, np.full(1024, -2048), gain_q12=1)
        r = call(p)
        results.append(dict(case='negative_Q12_half', expected=1/review.SCALE,
                            observed=maximum_output(r),
                            passed=maximum_output(r) == 1/review.SCALE))
        p = Path(d)/'unknown-prefix.npz'
        q = np.zeros(512, dtype=np.int64); q[0], q[-1] = -2**19, 2**19
        fixture(p, np.full(1024, int(.95*review.SCALE)), first=447483, q=q)
        r = call(p)
        results.append(dict(case='unknown_FIR_prefix', expected=0,
                            observed=overflow(r), passed=overflow(r) == 0))
        for name, change in (('Q20_hash_mismatch', dict(coefficients_sha256='incorrect')),
                             ('inconsistent_extent', dict(completed_frames=2000))):
            p = Path(d)/(name+'.npz')
            fixture(p, np.zeros(1024), **change)
            try:
                r = call(p)
                # Rejection or an explicit invalid result is acceptable. This check
                # does not promote an unknown new output schema to a passing result.
                invalid = rejected(r)
                results.append(dict(case=name, passed=invalid,
                                    observed='explicit invalid' if invalid else 'ordinary result without invalid marker'))
            except (ValueError, RuntimeError, SystemExit) as exc:
                results.append(dict(case=name,
                                    passed=not isinstance(exc, SystemExit) or exc.code == 2,
                                    observed=type(exc).__name__))
        if new_api:
            for name, level in (('positive_float_one_must_not_sign_wrap', 1.0),
                                ('out_of_range_normalized_float_must_be_invalid', 2.0)):
                p = Path(d)/(name+'.npz')
                fixture(p, np.ones(1024, dtype=np.int64))
                with np.load(p, allow_pickle=False) as cap:
                    fields = {key: cap[key] for key in cap.files}
                fields['microphone'] = np.full(1024, level)
                fields['residual_pcm'] = np.full(1024, review.MAXIMUM, dtype=np.int64)
                np.savez_compressed(p, **fields)
                try:
                    r = call(p)
                    if level == 1.0:
                        observed = primary(r)['max_wide']
                        ok = abs(observed-review.MAXIMUM/review.SCALE) < .5/review.SCALE
                    else:
                        observed = r['attribution']
                        ok = rejected(r)
                    results.append(dict(case=name, passed=bool(ok), observed=observed))
                except (ValueError, RuntimeError, SystemExit) as exc:
                    results.append(dict(case=name,
                                        passed=not isinstance(exc, SystemExit) or exc.code == 2,
                                        observed=type(exc).__name__))
            p = Path(d)/'prefix-headroom.npz'
            q = np.zeros(512, dtype=np.int64); q[0] = 1 << 20
            reference = np.zeros(1024, dtype=np.int64); reference[100:108] = -200
            pred = np.r_[0, reference[:-1]]
            mic = np.ones(1024, dtype=np.int64); mic[101:109] = review.MAXIMUM-100
            fixture(p, mic, q=q, pred=pred, first=50000, counts=(8 << 16, 0, 0))
            with np.load(p, allow_pickle=False) as cap:
                fields = {key: cap[key] for key in cap.files}
            fields['reference'] = reference/review.SCALE
            np.savez_compressed(p, **fields)
            r = call(p)
            expected = float(-20*np.log10(1/review.SCALE))
            # A whole-capture peak may remain, but cannot substitute for a metric
            # explicitly claimed to exclude the unscored prefix.
            measured = primary(r).get('valid_window_headroom_db', primary(r)['headroom_db'])
            results.append(dict(case='valid_window_headroom_excludes_prefix', expected=expected,
                                observed=measured, passed=abs(measured-expected) < 1e-8))
    return dict(script=str(path), script_sha256=review.sha(path),
                fixtures='synthetic boundaries, not recovered A speech PCM', cases=results)


if __name__ == '__main__':
    import sys
    if '--b-script' in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--b-script', type=Path, required=True)
        parser.add_argument('--out', type=Path, required=True)
        args = parser.parse_args()
        result = probe_b_analyzer(args.b_script)
        with args.out.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print('B_BOUNDARY_REVIEW', args.out, sum(x['passed'] for x in result['cases']), '/', len(result['cases']))
        raise SystemExit(0 if all(x['passed'] for x in result['cases']) else 2)
    unittest.main()
