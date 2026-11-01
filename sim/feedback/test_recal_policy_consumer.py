"""C boundary tests with B's exact policy, plus mapping of B's saved case outputs."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'board/audio_replay'))
from feedback import recal_policy as rp
from recal_policy_consumer import Consumer, classify, consume_reply, CONTRACT


class PolicyConsumerTests(unittest.TestCase):
    def setUp(self):
        self.consumer = Consumer(rp)
        self.capture = dict(status='OK', metrics={}, reasons=[])
        self.fit = dict(status='DEPLOYABLE_FIT', metrics={}, reasons=[])
        self.points = [dict(frequency_hz=f, open_db=0., bypass_db=3., cancel_db=-1.) for f in (322., 1000., 4000.)]
        self.three = rp.check_three_point(self.points)

    def test_final_requires_all_three_checks_and_explicit_true(self):
        with mock.patch.object(rp, 'decide', wraps=rp.decide) as call:
            result = self.consumer.final(self.capture, self.fit, self.three)
        self.assertIs(call.call_args.kwargs['require_three_point'], True)
        self.assertEqual(result['decision'], 'valid_pass')
        self.assertEqual(consume_reply(result, 'validate')[0], 'valid_pass')

    def test_missing_three_point_is_insufficient_not_installable(self):
        result = self.consumer.final(self.capture, self.fit, None)
        self.assertEqual(result['decision'], 'data_insufficient')
        self.assertEqual(result['cause'], 'DATA_INSUFFICIENT')
        self.assertEqual(result['policy_result']['blocked_at'], 'three_point')

    def test_missing_capture_or_fit_is_never_accepted(self):
        for capture, fit in ((None, self.fit), (self.capture, None), (None, None)):
            self.assertEqual(self.consumer.final(capture, fit, self.three)['decision'], 'data_insufficient')

    def test_partial_B_ready_receipt_cannot_bypass_C_completion_guard(self):
        partial = classify(rp.decide(three_point=self.three))
        self.assertEqual(partial['policy_result']['decision']['status'], 'READY_TO_INSTALL')
        self.assertEqual(consume_reply(partial, 'validate')[0], 'data_insufficient')

    def test_four_causes_are_preserved_and_distinct(self):
        wanted = dict(HARDWARE_ERROR='hardware_error', MEASUREMENT_INAPPLICABLE='measurement_inapplicable',
                      MODEL_UNQUALIFIED='model_rejected', DATA_INSUFFICIENT='data_insufficient')
        for cause, outcome in wanted.items():
            with self.subTest(cause=cause):
                raw = dict(status='INCONCLUSIVE', cause=cause, points=[], reasons=['B原文'])
                out = classify(raw)
                self.assertEqual((out['decision'], out['cause']), (outcome, cause))
                self.assertEqual(out['policy_result'], raw)
                self.assertEqual(consume_reply(dict(decision='valid_pass', cause=cause, reason='B原文'), 'validate')[0], outcome)

    def test_real_B_hardware_and_source_checks_keep_their_causes(self):
        for options, expected in ((dict(saturation_counts={'adc':1}), 'hardware_error'),
                                  (dict(source_sha=['a'*64,'b'*64]), 'measurement_inapplicable')):
            out = self.consumer.final(self.capture, self.fit, self.consumer.three_point(self.points, **options))
            self.assertEqual(out['decision'], expected)

    def test_current_lag_is_explicit_and_old_scene_or_capture_is_rejected(self):
        training = [dict(capture_id='t1', sha256='a'*64)]
        lag = dict(estimator='estimate_lag', scene_id='moved', captures=training, lag_frames=128)
        coefficients = [0]*512;coefficients[127] = 1 << 18
        with mock.patch.object(rp, 'check_fit', wraps=rp.check_fit) as call:
            out = self.consumer.fit(coefficients, 48828.125, scene_id='moved', training=training, lag_evidence=lag)
        self.assertEqual(call.call_args.kwargs, dict(expected_peak_tap=128))
        self.assertEqual(out['decision'], 'valid_pass')
        self.assertEqual(out['policy_result']['metrics']['peak_tap_delta'], 0)
        for key, value in (('scene_id','old'), ('captures',[dict(capture_id='old',sha256='a'*64)]),
                           ('estimator','old_model_peak'), ('lag_frames',128.0)):
            wrong = dict(lag);wrong[key] = value
            with mock.patch.object(rp, 'check_fit', wraps=rp.check_fit) as call:
                out = self.consumer.fit(coefficients, 48828.125, scene_id='moved', training=training, lag_evidence=wrong)
            self.assertFalse(call.called);self.assertEqual(out['decision'], 'data_insufficient')

    def test_retry_requires_exact_next_excitation_at_both_boundaries(self):
        checked = dict(status='REJECT_EXCITATION', metrics=dict(ref_rms_dbfs=-30.), next=dict(kind='raise_excitation'))
        action = rp.plan_excitation(checked, 0)['action']
        out = self.consumer.capture_result(checked, attempt=0, next_excitation=action)
        self.assertEqual(out['decision'], 'retry')
        self.assertEqual(consume_reply(out, 'fit', next_excitation=action, attempt=0)[0], 'retry')
        for change in (None, dict(action, sha256='f'*64), dict(action, target_rms_dbfs=-20.)):
            self.assertEqual(self.consumer.capture_result(checked, attempt=0, next_excitation=change)['decision'], 'data_insufficient')
            self.assertEqual(consume_reply(out, 'fit', next_excitation=change, attempt=0)[0], 'data_insufficient')
        self.assertEqual(self.consumer.capture_result(checked, attempt=2, next_excitation=action)['decision'], 'data_insufficient')

    def test_clipping_cannot_trigger_excitation_or_gain_retry(self):
        with mock.patch.object(rp, 'plan_excitation', wraps=rp.plan_excitation) as call:
            out = self.consumer.capture_result(dict(status='REJECT_CLIP', metrics={}, next=dict(kind='lower_input_gain')), attempt=0)
        self.assertFalse(call.called);self.assertEqual(out['decision'], 'input_overload')

    def test_only_open_loop_inputs_go_to_probe_selection(self):
        with mock.patch.object(rp, 'select_probe_frequencies', wraps=rp.select_probe_frequencies) as call:
            result = self.consumer.probes([.1,.2,.3],[322,1000,4000],[.9,.9,.9],-8.)
        self.assertEqual(len(result),3);self.assertFalse(call.call_args.kwargs)
        self.assertEqual(len(call.call_args.args),4)

    def test_eight_saved_B_outputs_map_without_reinterpreting_metrics(self):
        cases = json.loads((ROOT/'report/verification/recalibration-policy-2026-11-01/cases.json').read_text(encoding='utf-8'))['cases']
        wanted = dict(A_old_model_mismatch='model_rejected',B_low_snr_capture='data_insufficient',
            B2_deployed_training_capture_must_pass='valid_pass',C_clipped_capture='input_overload',
            D1_322Hz_positive_boost_single_point='data_insufficient',D2_322Hz_residual_positive_feedback='model_rejected',
            D3_322Hz_no_loop_boost_inapplicable='measurement_inapplicable',E_fifty_cm_relocated='data_insufficient')
        self.assertEqual({c['case'] for c in cases},set(wanted))
        for raw in cases:
            before = copy.deepcopy(raw);out = classify(raw)
            self.assertEqual(out['decision'],wanted[raw['case']]);self.assertEqual(raw,before)

    def test_unknown_causes_or_bad_extension_are_insufficient_and_retained(self):
        out = classify(dict(status='PASS',cause='FUTURE_CAUSE'))
        self.assertEqual(out['decision'],'data_insufficient');self.assertEqual(out['cause'],'FUTURE_CAUSE')
        self.assertEqual(consume_reply(dict(policy_contract=CONTRACT,decision='valid_pass'),'validate')[0],'data_insufficient')


if __name__ == '__main__':
    unittest.main()
