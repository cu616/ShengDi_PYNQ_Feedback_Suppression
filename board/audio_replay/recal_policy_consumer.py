"""C's orchestration boundary for B's policy; no hardware or new thresholds."""
import copy
import importlib

CONTRACT = 'recal-policy-consumer-v1'
CAUSES = {
    'HARDWARE_ERROR': 'hardware_error',
    'MEASUREMENT_INAPPLICABLE': 'measurement_inapplicable',
    'MODEL_UNQUALIFIED': 'model_rejected',
    'DATA_INSUFFICIENT': 'data_insufficient',
}
EXCITATION_FIELDS = ('kind', 'target_rms_dbfs', 'achieved_rms_dbfs', 'peak', 'sha256', 'frames')


def classify(result):
    """Map B status/actions, retaining the complete unmodified numeric receipt."""
    item = result.get('decision', result)
    status = item.get('status')
    cause = item.get('cause')
    reasons = item.get('reasons') or []
    reason = '; '.join(str(s) for s in reasons) or 'B判定：' + str(status)
    if cause:
        decision = CAUSES.get(cause, 'data_insufficient')
    elif status == 'REJECT_CLIP':
        decision = 'input_overload'
    elif status in ('REJECT_SCALE', 'REJECT_SHAPE', 'FAIL'):
        cause = 'MODEL_UNQUALIFIED'; decision = CAUSES[cause]
    elif status in ('OK', 'DEPLOYABLE_FIT', 'PASS', 'READY_TO_INSTALL'):
        decision = 'valid_pass'
    else:
        # An exhausted excitation plan does not prove a particular hardware fault.
        cause = 'DATA_INSUFFICIENT'; decision = CAUSES[cause]
    return dict(decision=decision, cause=cause, reason=reason,
                policy_contract=CONTRACT, policy_result=copy.deepcopy(result))


def complete_final(result):
    steps = result.get('steps', {})
    return (result.get('decision', {}).get('status') == 'READY_TO_INSTALL'
            and all(steps.get(k, {}).get('status') == v for k, v in (
                ('capture', 'OK'), ('fit', 'DEPLOYABLE_FIT'), ('three_point', 'PASS')))
            and not any(steps[k].get('cause') for k in ('capture', 'fit', 'three_point')))


def consume_reply(reply, phase, *, next_excitation=None, attempt=None):
    """An explicit cause overrides a contradictory pass, including legacy wrappers."""
    cause = reply.get('cause')
    retry = reply.get('decision') == 'retry'
    if cause and not (cause == 'DATA_INSUFFICIENT' and retry):
        return CAUSES.get(cause, 'data_insufficient'), cause, reply.get('reason', str(cause))
    if 'policy_contract' not in reply:
        return reply.get('decision'), None, reply.get('reason')
    if reply['policy_contract'] != CONTRACT or not isinstance(reply.get('policy_result'), dict):
        return 'data_insufficient', 'DATA_INSUFFICIENT', '数值回执版本或内容不完整'
    mapped = classify(reply['policy_result'])
    decision, cause, reason = (mapped[k] for k in ('decision', 'cause', 'reason'))
    if decision == 'valid_pass' and phase == 'validate' and not complete_final(reply['policy_result']):
        return 'data_insufficient', 'DATA_INSUFFICIENT', '采集、拟合、三点验收存在缺项，未启用候选'
    # A retry is authorized only by Consumer.capture's exact presealed action.
    if retry and reply.get('retry_authorized') is True:
        plan = reply['policy_result'].get('decision', {})
        action = plan.get('action', {})
        if (plan.get('status') == 'RAISE_EXCITATION' and plan.get('attempt') == attempt
                and isinstance(next_excitation, dict)
                and all(k in action and next_excitation.get(k) == action[k] for k in EXCITATION_FIELDS)):
            return 'retry', 'DATA_INSUFFICIENT', reply.get('reason', reason)
    return decision, cause, reason


class Consumer:
    def __init__(self, policy=None):
        self.policy = policy or importlib.import_module('feedback.recal_policy')

    def capture(self, reference, microphone, sample_rate_hz, *, attempt,
                next_excitation=None, plan_options=None, **capture_options):
        checked = self.policy.check_capture(reference, microphone, sample_rate_hz, **capture_options)
        return self.capture_result(checked, attempt=attempt, next_excitation=next_excitation,
                                   plan_options=plan_options)

    def capture_result(self, checked, *, attempt, next_excitation=None, plan_options=None):
        if checked['status'] in ('OK', 'REJECT_CLIP'):
            return classify(checked)
        planned = self.policy.plan_excitation(checked, attempt, **(plan_options or {}))
        out = classify(dict(steps=dict(capture=checked), blocked_at='capture', decision=planned))
        action = planned.get('action', {})
        if (planned['status'] == 'RAISE_EXCITATION'
                and type(attempt) is int and 0 <= attempt < self.policy.MAX_ATTEMPTS
                and isinstance(next_excitation, dict)
                and all(k in action and next_excitation.get(k) == action[k] for k in EXCITATION_FIELDS)):
            out.update(decision='retry', retry_authorized=True)
        return out

    def probes(self, H, freqs, coherence, gain_db):
        # Caller persists this result before collecting any cancellation arm.
        return self.policy.select_probe_frequencies(H, freqs, coherence, gain_db)

    def fit(self, coefficients_q20, sample_rate_hz, *, scene_id, training, lag_evidence):
        expected = [dict(capture_id=c['capture_id'], sha256=c['sha256']) for c in training]
        if (not expected or lag_evidence.get('scene_id') != scene_id
                or lag_evidence.get('estimator') != 'estimate_lag'
                or lag_evidence.get('captures') != expected
                or type(lag_evidence.get('lag_frames')) is not int):
            return classify(dict(status='INCONCLUSIVE', cause='DATA_INSUFFICIENT',
                reasons=['缺少绑定本轮训练原件的estimate_lag结果'], metrics={}))
        checked = self.policy.check_fit(coefficients_q20, sample_rate_hz,
                                       expected_peak_tap=lag_evidence['lag_frames'])
        out = classify(checked)
        out['lag_evidence'] = copy.deepcopy(lag_evidence)
        return out

    def three_point(self, points, **options):
        return self.policy.check_three_point(points, **options)

    def final(self, capture, fit, three_point):
        # B allows partial calls; the product must require all three stages itself.
        if capture is None or fit is None:
            return classify(dict(status='INCONCLUSIVE', cause='DATA_INSUFFICIENT',
                reasons=['采集或拟合尚未完成，未启用候选'], metrics={}))
        result = self.policy.decide(capture=capture, fit=fit, three_point=three_point,
                                    require_three_point=True)
        out = classify(result)
        if out['decision'] == 'valid_pass' and not complete_final(result):
            out.update(decision='data_insufficient', cause='DATA_INSUFFICIENT',
                       reason='采集、拟合、三点验收存在缺项，未启用候选')
        return out
