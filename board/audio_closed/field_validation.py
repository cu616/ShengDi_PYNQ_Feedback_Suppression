"""A-owned, bounded field A/B runner. Import does not access hardware or play audio."""
import hashlib
import json
from pathlib import Path
import time
import uuid

import numpy as np


def model_gain_plan(model_path, fixture_id='box_v1_20261016', hp_volume=40,
                    sample_rate=48828.125, start_db=-30.0, step_db=3.0,
                    max_pairs=8, margin_db=6.0):
    """Return a conservative model-based test ceiling and levels.

    The small-gain bound uses sum(abs(h)); it is only an estimate for the
    identified open-loop path, not a measured closed-loop stability limit.
    """
    model_path = Path(model_path)
    model = json.loads(model_path.read_text(encoding='utf-8'))
    expected = dict(taps=256, lag_first=1, coefficient_format='signed24_fraction20',
                    training_source='board', fixture_id=fixture_id,
                    hp_volume=hp_volume, sample_rate_hz=sample_rate)
    for key, value in expected.items():
        if model.get(key) != value:
            raise ValueError('candidate mismatch: ' + key)
    h = np.asarray(model.get('coefficients'), dtype=np.float64)
    q = np.asarray(model.get('coefficients_q20'))
    if h.shape != (256,) or q.shape != (256,) or q.dtype.kind not in 'iu' or not np.isfinite(h).all():
        raise ValueError('invalid 256-tap candidate')
    q_expected = np.sign(h) * np.floor(np.abs(h) * 2**20 + .5)
    if not np.array_equal(q, q_expected):
        raise ValueError('candidate float/Q20 coefficients disagree')
    l1 = float(np.sum(np.abs(h)))
    if not np.isfinite(l1) or l1 <= 0:
        raise ValueError('candidate has no usable path energy')
    bound_db = float(-20.0 * np.log10(l1))
    ceiling_db = bound_db - margin_db
    # The first useful step is 6 dB above the already completed, inaudible -36 dB check.
    levels = []
    for i in range(max_pairs):
        gain = start_db + step_db * i
        if gain > ceiling_db + 1e-9:
            break
        levels.append(round(gain, 3))
    return dict(model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                taps=256, l1_norm=l1, estimated_small_gain_limit_db=bound_db,
                operating_ceiling_db=ceiling_db, margin_db=margin_db,
                gain_levels_db=levels,
                interpretation='candidate-based conservative range estimate only; NOT measured MSG/ASG')


def load_setup(setup_path, fixture_id='box_v1_20261016'):
    """Require a completed, operator-verified scene record before any sound."""
    setup = json.loads(Path(setup_path).read_text(encoding='utf-8'))
    if (setup.get('schema_version') != 1 or setup.get('fixture_id') != fixture_id or
            setup.get('calibration_match_original') is not True or
            setup.get('operator_verified') is not True or
            setup.get('codec_hp_volume') != 40 or setup.get('sample_rate_hz') != 48828.125):
        raise ValueError('complete field_setup.json and confirm original calibration fixture')
    if (setup.get('wiring', {}).get('channel_mapping_verified') is not True or
            setup.get('speaker', {}).get('external_volume_control_verified') is not True):
        raise ValueError('verify audio channel mapping and speaker volume control in field_setup.json')
    required = [
        ('wiring', 'max4466_supply_v'),
        ('wiring', 'max4466_gain_setting'), ('box', 'dimensions_cm'),
        ('box', 'lid_state'), ('microphone', 'position_xyz_cm'),
        ('microphone', 'orientation'), ('speaker', 'position_xyz_cm'),
        ('speaker', 'orientation'), ('normal_speech_source', 'position_xyz_cm'),
        ('normal_speech_source', 'orientation'),
        ('normal_speech_source', 'playback_volume_setting'),
        ('normal_speech_source', 'loop_or_clip_id'), ('operator_notes', None),
    ]
    for section, key in required:
        value = setup.get(section) if key is None else setup.get(section, {}).get(key)
        if value is None or value == '' or value == []:
            raise ValueError('field_setup.json missing ' + section + ('.' + key if key else ''))
    return setup


def run_field_validation(fixture_id='box_v1_20261016',
                         model_path='../audio_calibrate/candidate_box_v1_256.json',
                         setup_path='field_setup.json',
                         output_root='field_results', ask=input, runner=None):
    """At each selected gain run bypass then cancel, changing bypass only."""
    run_start = time.monotonic()
    folder = Path(output_root) / ('field_' + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    state = dict(schema_version=1, run_id=folder.name, status='preflight', fixture_id=fixture_id,
                 setup_path=str(setup_path), trials=[], pairs=[],
                 interpretation='paired listening/range exploration; NOT measured MSG/ASG')

    def save():
        state['wall_elapsed_seconds'] = time.monotonic() - run_start
        state['sound_seconds_completed'] = sum(
            row.get('metadata', {}).get('sound_seconds_nominal', 0.0)
            for row in state['trials'])
        temp = folder / 'summary.json.tmp'
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(folder / 'summary.json')

    save()
    try:
        if runner is None:
            from closed_trial import closed_trial
            runner = closed_trial
        import closed_batch
        setup = load_setup(setup_path, fixture_id=fixture_id)
        setup_hash = hashlib.sha256(Path(setup_path).read_bytes()).hexdigest()
        model_path = Path(model_path).resolve()
        plan = model_gain_plan(model_path, fixture_id=fixture_id)
        state.update(setup=setup, setup_sha256=setup_hash, plan=plan,
                     model_sha256=plan['model_sha256'], seconds_per_trial=2.0,
                     hp_volume=40, source='fixed phone speech',
                     planned_max_sound_seconds=4.0 * len(plan['gain_levels_db']))
        if not plan['gain_levels_db']:
            raise RuntimeError('model-derived safe range does not reach -30 dB; no playback authorized by this plan')
        print('本地模型估算（不是稳定阈值）：', json.dumps(plan, ensure_ascii=False))
        save()
        if ask('现场确认：配置与原标定夹具一致、固定语音源已就绪、音响可立即断电且本地采样已同意；输入 READY：').strip().upper() != 'READY':
            state.update(status='cancelled', stop_reason='operator_cancel_before_ready')
            return state
        if ask('确认使用以上范围并开始；其余输入取消：').strip().upper() != 'START':
            state.update(status='cancelled', stop_reason='operator_cancel_before_start')
            return state

        bit_path = Path(__file__).resolve().with_name('audio_closed.bit')
        bit_hash = hashlib.sha256(bit_path.read_bytes()).hexdigest()
        state.update(status='running', bit_sha256=bit_hash)
        save()
        for gain in plan['gain_levels_db']:
            pair = []
            pair_row = dict(gain_db_requested=gain, status='running')
            state['pairs'].append(pair_row)
            for bypass in (True, False):
                mode = 'bypass' if bypass else 'cancel'
                index = len(state['trials']) + 1
                file_path = folder / ('%02d_%s_%+gdb.npz' % (index, mode, gain))
                row = dict(index=index, gain_db_requested=gain, mode=mode, file=file_path.name)
                state['trials'].append(row)
                save()

                def ready():
                    print('[%d/%d] %s at %+.1f dB; configured and muted.' %
                          (index, 2 * len(plan['gain_levels_db']), mode, gain))
                    return ask('准备听时输入 START，其他输入停止：').strip().upper() == 'START'

                result = runner(file_path, fixture_id, str(model_path), bypass=bypass,
                                zero_coeff=False, gain_db=gain, seconds=2.0, hp_volume=40,
                                speaker_confirmed=True, local_capture_confirmed=True,
                                before_start=ready)
                row['metadata'] = result
                issue = closed_batch.rejection(result)
                if (result.get('bypass') is not bypass or result.get('bit_sha256') != bit_hash or
                        result.get('model_sha256') != plan['model_sha256']):
                    issue = 'artifact_or_mode_mismatch'
                if pair and any(pair[0].get(k) != result.get(k) for k in closed_batch.MATCH_KEYS):
                    issue = 'pair_configuration_mismatch'
                row['status'] = 'complete' if issue is None else 'failed'
                row['digital_issue'] = issue
                save()
                if issue:
                    pair_row.update(status='stopped', stop_reason=issue)
                    raise RuntimeError(issue)
                pair.append(result)
                answer = ask('听感：0无声且安静 / 1清楚人声且安静 / 2杂音 / 3尖叫或增长 / 4结束未静 / q停止：').strip().lower()
                hearing_map = {'0': 'inaudible', '1': 'speech', '2': 'noise',
                               '3': 'howl_or_growth', '4': 'not_quiet', 'q': 'operator_stop'}
                row['hearing'] = hearing_map.get(answer, 'invalid_hearing_code')
                save()
                if answer not in ('0', '1'):
                    pair_row.update(status='stopped', stop_reason=hearing_map.get(answer, 'invalid_hearing_code'))
                    state.update(status='stopped', stop_reason=pair_row['stop_reason'])
                    save()
                    print('停止整批；若声音仍持续，立即切断音响电源。')
                    return state
            pair_row.update(status='complete', configuration_matches=True,
                            bypass_hearing=state['trials'][-2]['hearing'],
                            cancel_hearing=state['trials'][-1]['hearing'])
            save()
    except (Exception, KeyboardInterrupt) as exc:
        state.update(status='stopped', stop_reason=type(exc).__name__ + ': ' + str(exc))
        if state['pairs'] and state['pairs'][-1].get('status') == 'running':
            state['pairs'][-1].update(status='incomplete', stop_reason=state['stop_reason'])
    finally:
        if state['status'] == 'running':
            state['status'] = 'completed'
        save()
        print('结果：', str(folder / 'summary.json'))
        print('原始NPZ留在板卡；本摘要不含音频。MSG/ASG未自动测量。')
    return state
