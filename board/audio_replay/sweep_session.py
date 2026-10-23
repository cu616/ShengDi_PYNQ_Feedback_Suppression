"""Bounded multigain field batch. Import never opens board devices."""
import hashlib
import json
import time
import uuid
from pathlib import Path
import numpy as np
from replay_session import HERE, check_package, load_scene
from replay_tools import prepare_source, RATE
from residual_tools import load_candidate
from sweep_plan import make_plan, sha


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
    temp.replace(path)


def prepare_sweep():
    """Silent planning; returns a plan only when a useful multi-point range exists."""
    folder = HERE/'replay_results'/('sweep_'+uuid.uuid4().hex[:12])
    folder.mkdir(parents=True)
    state = dict(schema_version=1, artifact_kind='replay_sweep', status='planning',
                 trials=[], pairs=[], sound_seconds_completed=0., stage='package')
    path = folder/'summary.json'
    write_json(path, state)
    try:
        check_package()
        setup = HERE.parent/'audio_closed/field_setup.json'
        state['stage'] = 'scene'
        state['setup'] = load_scene(setup)
        state['setup_sha256'] = sha(setup)
        state['stage'] = 'silent_analysis'
        state['plan'] = make_plan(HERE.parent/'audio_calibrate')
        state['status'] = 'planned'
        state['stage'] = 'await_recording'
        write_json(path, state)
        print('可测档位：' + ', '.join(str(p['gain_db'])+' dB' for p in state['plan']['points']), flush=True)
        print('每档先抵消、后旁路；出现异常停止升档。录2秒时总发声上限约 %.1f 秒。' %
              ((1+2*len(state['plan']['points']))*2.4), flush=True)
        print('静默选档完成。现在才进入第2格录音。', flush=True)
        return path
    except (Exception, KeyboardInterrupt) as exc:
        state.update(status='stopped', stop_reason=type(exc).__name__+': '+str(exc))
        write_json(path, state)
        print('未授权发声：'+state['stop_reason']+'\n返回：'+str(path), flush=True)
        return None


def run_sweep(plan_path, ask=input):
    if plan_path is None:
        raise ValueError('第1格没有生成可用多档计划；不要录音或播放，返回该格的summary.json')
    path = Path(plan_path)
    state = json.loads(path.read_text(encoding='utf8'))
    if state['status'] != 'planned':
        raise ValueError('这个批次已开始或已结束，不覆盖结果；返回已有summary.json')
    folder = path.parent
    start = time.monotonic()
    row = None

    def save():
        state['wall_elapsed_seconds'] = time.monotonic()-start
        write_json(path, state)

    try:
        check_package()
        setup = HERE.parent/'audio_closed/field_setup.json'
        if sha(setup) != state['setup_sha256']:
            raise ValueError('选档后现场配置变动，停止')
        data = HERE.parent/'audio_calibrate'
        for name, facts in state['plan']['files'].items():
            if sha(data/name) != facts['sha256']:
                raise ValueError('选档后标定文件变动：'+name)
        model_path = data/'candidate_box_v1_256.json'
        _, q = load_candidate(model_path, state['setup']['fixture_id'], 40, RATE)
        state['stage'] = 'source'
        pcm, source = prepare_source(HERE/'source.wav', q, 0)
        limit = int(np.floor(state['plan']['source_peak_limit']*32768))
        scale = min(1., limit/max(1, int(np.max(np.abs(pcm.astype(np.int64))))))
        pcm = (np.sign(pcm)*np.floor(np.abs(pcm.astype(float))*scale)).astype('<i2')
        if np.max(np.abs(pcm.astype(np.int64))) < 8:
            raise ValueError('处理后语音幅度不足，停止')
        source.update(pcm16_sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
                      source_peak_dbfs=float(20*np.log10(np.max(np.abs(pcm.astype(float)))/32768)))
        source.pop('loop_bound', None)
        source['level_basis'] = 'common peak limit for every planned gain and both modes; see plan'
        seconds = len(pcm)/RATE+.4
        points = state['plan']['points']
        total = 1+2*len(points)
        state.update(source=source, seconds_per_trial=seconds, planned_max_sound_seconds=total*seconds,
                     normal_mic_amplification_demonstrated=False,
                     interpretation='prerecorded digital-source feedback sweep; no measured ASG',
                     capture_scope='last 16384 frames, primarily source-off tail; internal saturation counters cover entire trial',
                     stage='confirmation')
        save()
        print('手机停止外放；最多%d项，每项%.2f秒，总发声最多%.2f秒。' % (total, seconds, total*seconds), flush=True)
        if ask('夹具未动、音响可立即断电、同意本地录音保存，输入 READY：').strip().upper() != 'READY':
            state.update(status='cancelled', stop_reason='operator_cancel')
            return state
        from replay_trial import replay_trial
        state['status'] = 'running'
        schedule = [('direct', points[0], True)]
        for point in points:
            schedule.extend([('cancel', point, False), ('bypass', point, True)])
        previous = None
        for index, (mode, point, bypass) in enumerate(schedule, 1):
            direct = mode == 'direct'
            row = dict(index=index, mode=mode, gain_db=point['gain_db'], status='preparing')
            state['trials'].append(row)
            state['stage'] = '%d:%s' % (index, mode)
            save()

            def ready():
                print('[%d/%d] %s %s：配置完成，静音中。' %
                      (index, total, mode, 'g=0' if direct else str(point['gain_db'])+' dB'), flush=True)
                if ask('输入 START 后立即播放并采样 %.2f 秒；其他输入结束：' % seconds).strip().upper() != 'START':
                    return False
                row['status'] = 'audio_authorized'
                save()
                return True

            meta = replay_trial(folder/('%02d_%s.npz' % (index, mode)),
                                state['setup']['fixture_id'], str(model_path), pcm,
                                bypass=bypass, direct_only=direct, gain_db=point['gain_db'],
                                seconds=seconds, hp_volume=40, speaker_confirmed=True,
                                local_capture_confirmed=True, before_start=ready)
            row.update(metadata=meta, status='complete')
            state['sound_seconds_completed'] += meta['sound_seconds_nominal']
            save()
            answer = ask('已静音。听感：0无声 / 1语音清楚且结束安静 / 2杂音失真 / 3啸叫增长 / 4结束仍响：').strip()
            row['hearing_code'] = answer
            if direct:
                state['direct_playback_heard'] = answer == '1'
            bad = (not meta.get('verification', {}).get('bit_exact') or any(meta.get(k, 0) for k in
                   ('prediction_saturations', 'residual_saturations', 'gain_saturations', 'mix_saturations', 'mic_full_scale_samples')))
            if (meta['gain_q12'] != (0 if direct else point['gain_q12']) or meta['bypass'] != bypass or
                    meta['model_sha256'] != state['plan']['files'][model_path.name]['sha256'] or
                    meta['source_pcm16_sha256'] != source['pcm16_sha256'] or meta['hp_volume'] != 40):
                bad = True
            if mode == 'cancel':
                previous = row
            if mode == 'bypass':
                keys = ('bit_sha256', 'model_sha256', 'coefficients_sha256', 'source_pcm16_sha256',
                        'gain_q12', 'hp_volume', 'sample_rate_hz', 'completed_frames', 'fixture_id')
                matches = previous is not None and all(previous['metadata'].get(k) == meta.get(k) for k in keys)
                state['pairs'].append(dict(gain_db=point['gain_db'], gain_q12=point['gain_q12'],
                    cancel_trial=previous['index'] if previous else None, bypass_trial=index,
                    configuration_matches=matches, cancel_hearing=previous['hearing_code'] if previous else None,
                    bypass_hearing=answer, conclusion=('本档抵消正常、旁路听到啸叫增长；单次定性差异，需复现'
                    if matches and not bad and answer=='3' else '见两项听感与数字检查；未量化ASG')))
                bad = bad or not matches
            save()
            if bad or answer != '1':
                state.update(status='stopped', stop_reason='digital_or_saturation_fault' if bad else mode+':hearing_'+answer,
                             conclusion='停止后续升档；已完成配对和异常记录保留，不自动重试')
                return state
        state.update(status='completed', conclusion='已测全部档位未找到旁路失稳阈值；未测得MSG/ASG')
    except (Exception, KeyboardInterrupt) as exc:
        state.update(status='stopped', stop_reason=type(exc).__name__+': '+str(exc))
        if row is not None and row['status'] != 'complete':
            state['sound_seconds_unknown_for_failed_trial'] = row['status'] == 'audio_authorized'
            row['status'] = 'interrupted_or_failed'
        print('停止阶段：'+state['stage']+'；'+state['stop_reason'], flush=True)
    finally:
        save()
        print('结束，只返回：'+str(path)+'\nWAV/NPZ保留板卡。', flush=True)
    return state
