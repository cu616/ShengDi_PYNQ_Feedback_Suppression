"""C runtime boundary; B owns all fit and predictive validation decisions."""
import copy
import hashlib
import json
from pathlib import Path

PROFILE = 'b-heldout-v1'


def product_policy():
    """Seal B's three requested levels and independent sources before any playback."""
    from feedback.excitation import white_noise_pcm16
    attempts = []
    for attempt, level in enumerate((-22.0, -19.3, -16.5)):
        plan = {}
        for phase, count, offset in (('training', 6, 0), ('validation', 2, 100)):
            sources = []
            for segment in range(count):
                seed = 4242 + offset + segment
                pcm, record = white_noise_pcm16(level, 16384, seed=seed, peak_cap=.80)
                if not record['ok']:
                    raise ValueError('B excitation unreachable: %s/%s/%s' % (level, phase, seed))
                sources.append({k: record[k] for k in (
                    'seed', 'frames', 'peak_cap', 'sha256', 'rms_db_actual', 'peak_linear', 'reachable_db')})
            plan[phase] = dict(excitation='white_noise', rms_dbfs=level, frames=16384,
                               segments=count, peak_cap=.80, sources=sources)
        assert not ({s['sha256'] for s in plan['training']['sources']}
                    & {s['sha256'] for s in plan['validation']['sources']})
        attempts.append(plan)
    return dict(runtime_profile=PROFILE, algorithm_module='recal_runtime',
                validation_kind='heldout_prediction', input_mode='cue_input',
                compute_timeout_seconds=30, io_timeout_seconds=30, quiet_seconds=2,
                run_seconds=30, cue=True, attempts=attempts,
                phase_gain_q12={k: [0, 1631] for k in ('prepare','cue','cue_input','input','training','validation')},
                indicator_encoding='led4')


def speech_health(request):
    """Integrity/headroom only; a human window has no excitation coherence criterion."""
    import numpy as np
    import recal_algorithm as b
    result = {k: request[k] for k in ('contract', 'request_id', 'scene_id')}
    result.update(decision='data_insufficient', cause='DATA_INSUFFICIENT',
                  reason='讲话检查数据不足', evidence=dict(kind='input_integrity_only', speech_recognition=False))
    entries = request.get('input') or []
    if not entries:
        return result
    metrics = []
    for entry in entries:
        if hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest() != entry['sha256']:
            result.update(decision='hardware_error', cause='HARDWARE_ERROR', reason='讲话原件身份改变')
            return result
        cap = b.load_capture(entry);mic = cap['mic'];md = cap['metadata']
        if (mic.ndim != 1 or len(mic) < b.MIN_VALID_FRAMES or not np.isfinite(mic).all()
                or md.get('dropped_frames') not in (None, 0)):
            return result
        overloaded = bool(np.any(np.abs(mic) >= b.NEAR_FULL_SCALE)
                          or md.get('input_overflow_bit22') or md.get('bit22')
                          or md.get('input_full_scale_seen'))
        metrics.append(dict(capture_id=entry['capture_id'], frames=len(mic), input_overload=overloaded))
        if overloaded:
            result.update(decision='input_overload', cause=None, reason='输入过载，停止讲话后重新标定')
            return result
        if not np.any(mic):
            result['reason'] = '未检测到有效输入，请按提示讲话后重新标定'
            return result
    result.update(decision='valid_pass', cause=None, reason='输入完整且未满幅；未作语音识别或抑制判断')
    result['evidence']['metrics'] = metrics
    return result


def evaluate(request):
    import recal_algorithm as b
    import numpy as np
    try:
        if request['phase'] == 'speech':
            return speech_health(request)
        entries=request.get('validation' if request['phase']=='validate' else
                            'training' if request['phase']=='fit' else 'input') or []
        if request['phase']=='validate' and len(entries)<b.MIN_VALIDATION_CAPTURES:
            return dict(**{k:request[k] for k in ('contract','request_id','scene_id')},
                decision='data_insufficient',cause='DATA_INSUFFICIENT',reason='独立验证少于B规定的两段')
        for entry in entries:
            if hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
                return dict(**{k:request[k] for k in ('contract','request_id','scene_id')},
                    decision='hardware_error',cause='HARDWARE_ERROR',reason='计算前原件身份改变')
            cap=b.load_capture(entry);md=cap['metadata']
            if (md.get('input_full_scale_seen') or (int(md.get('capture_status') or 0)>>22)&1
                    or np.any(np.abs(cap['mic'])>=b.NEAR_FULL_SCALE)):
                return dict(**{k:request[k] for k in ('contract','request_id','scene_id')},
                    decision='input_overload',cause=None,reason='原始驱动记录输入满幅，未启用候选')
            if md.get('stop_reason') not in (None,'completed') or md.get('early_stop'):
                return dict(**{k:request[k] for k in ('contract','request_id','scene_id')},
                    decision='data_insufficient',cause='DATA_INSUFFICIENT',reason='原始采集未正常完成')
        out = b.evaluate(request)
        wrapped = copy.deepcopy(out)
        wrapped['b_algorithm_reply'] = out
        wrapped['algorithm_contract'] = 'recalibration-algorithm-v1'
        wrapped['validation_kind'] = 'heldout_prediction'
        if out['decision'] == 'model_rejected': wrapped['cause'] = 'MODEL_UNQUALIFIED'
        elif out['decision'] == 'data_insufficient': wrapped['cause'] = 'DATA_INSUFFICIENT'
        if out['decision'] == 'retry' and request['phase'] not in ('input','fit'):
            wrapped.update(decision='data_insufficient',cause='DATA_INSUFFICIENT',reason='该阶段不允许自动重试')
        if request['phase'] == 'validate' and out['decision'] == 'valid_pass':
            evidence = out.get('evidence', {})
            if (evidence.get('policy') != 'recalibration-algorithm-v1'
                    or evidence.get('not_asg') is not True or not evidence.get('meaning')):
                wrapped.update(decision='data_insufficient',cause='DATA_INSUFFICIENT',reason='独立预测验证的口径缺失')
        return wrapped
    except Exception as exc:
        return dict(**{k: request.get(k) for k in ('contract','request_id','scene_id')},
                    decision='data_insufficient',cause='DATA_INSUFFICIENT',reason='适配数据不足：'+str(exc))
