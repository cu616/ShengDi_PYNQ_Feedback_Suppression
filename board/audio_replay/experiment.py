"""C fixed experiment entry. All device actions stay in A's replay_trial.

Historical evidence workflow only. The resident consumer entry is recal_entry.sh.

Import has no side effects. A completed integration manifest is mandatory before
even importing PYNQ. Results are checkpointed and zipped on every exit path.
"""
import csv
import hashlib
import json
from pathlib import Path
import uuid
import zipfile
import numpy as np
from evaluation import VERSION, CONFIG, analyze_npz, sha
from model_comparison import SUMMARY_VERSION, SUMMARY_REVISION, flat_trial, pair_models, load_registry, export_csv, BIT_CAPACITIES

HERE = Path(__file__).resolve().parent
PLAN = dict(gains_db=[-26., -24.], repeats=2, digital_seconds=1.4,
            source_seconds=1., source_peak_dbfs=-42., speech_seconds=2.,
            speech_gain_db=-26., hp_volume=40, transition_seconds=.05,
            positive_control_min_dbfs=-45., positive_control_max_dbfs=-3.,
            positive_control_drift_db=6., maximum_lag_change_frames=1,
            purpose='same-gain bypass/cancel comparison in closed box; then external speech audibility',
            independent_variable='bypass only within each pair',
            msg_asg_policy='not computed; these points do not establish replicated thresholds')


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
    temp.replace(path)


def check_package(base=HERE):
    base = Path(base)
    m = json.loads((base/'experiment-manifest.json').read_text(encoding='utf8'))
    if m.get('status') != 'ready':
        raise ValueError('PACKAGE_INCOMPLETE: ' + '; '.join(m.get('missing', [])))
    for name, expected in m['hashes'].items():
        if sha(base/name) != expected:
            raise ValueError('frozen file changed: '+name)
    notebook = json.loads((base/'experiment.ipynb').read_text(encoding='utf8'))
    code = [''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code']
    digest = hashlib.sha256(json.dumps(code, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    if digest != m['notebook_code_sha256']:
        raise ValueError('Notebook code changed')
    if m['calculation_version'] != VERSION or m['plan'] != PLAN or m['detector_config'] != CONFIG:
        raise ValueError('calculation/plan mismatch')
    scene = json.loads((base/'scene.json').read_text(encoding='utf8'))
    if scene.get('operator_verified') is not True or scene.get('fixture_id') != 'box_v1_20261016':
        raise ValueError('scene not confirmed for frozen box plan')
    return m, scene


def source_pcm():
    # Deterministic broadband burst; fixed amplitude in both modes and all gains.
    rng = np.random.default_rng(20261023)
    n = int(48828.125*PLAN['source_seconds'])
    x = rng.normal(size=n)
    fade = int(.01*48828.125)
    x[:fade] *= np.linspace(0, 1, fade); x[-fade:] *= np.linspace(1, 0, fade)
    return np.rint(x/np.max(np.abs(x))*np.floor(32768*10**(PLAN['source_peak_dbfs']/20))).astype('<i2')


def positive_control(path):
    """Use a source-ON direct capture to reject standby and gross path changes."""
    with np.load(path, allow_pickle=False) as z:
        mic, ref = np.array(z['microphone']), np.array(z['reference'])
    rms = float(20*np.log10(max(float(np.std(mic)), 1e-12)))
    # Independent direct dot products; no alignment with an assumed fixed lag.
    mic, ref = mic-mic.mean(), ref-ref.mean()
    scores = [float(np.dot(ref[:-lag] if lag else ref, mic[lag:]) /
                    max(np.linalg.norm(ref[:-lag] if lag else ref)*np.linalg.norm(mic[lag:]), 1e-20))
              for lag in range(min(512, len(mic)//2))]
    lag = int(np.argmax(np.abs(scores)))
    return dict(rms_dbfs=rms, delay_frames=lag, correlation=abs(scores[lag]),
                passed=(PLAN['positive_control_min_dbfs'] <= rms <= PLAN['positive_control_max_dbfs']
                        and abs(scores[lag]) >= .1))


def collect(folder, state):
    folder = Path(folder)
    state['raw_files'] = [dict(file=p.name, sha256=sha(p), board_path=str(p.resolve()))
                          for p in sorted(folder.glob('*.npz'))]
    state['return_policy'] = 'statistics only; raw NPZ stays at listed board paths'
    state['schema_version']=SUMMARY_VERSION
    state['summary_revision']=SUMMARY_REVISION
    registry_path=Path(__file__).resolve().parent/'models'
    registry=load_registry(registry_path) if (registry_path/'manifest.json').is_file() else None
    for row in state['trials']:
        row.update(flat_trial(row,registry))
    state['model_pairs']=pair_models(state['trials'])
    write_json(folder/'summary.json', state)
    export_csv(folder/'summary.csv',state['trials'])
    out = folder/'return-results.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.iterdir()):
            if p.suffix in ('.json', '.csv', '.txt'):
                z.write(p, p.name)
    return out


def run_package(base=HERE, ask=input, runner=None, validator=check_package):
    base = Path(base)
    folder = base/'results'/('run-'+uuid.uuid4().hex[:12]); folder.mkdir(parents=True)
    state = dict(schema_version=1, calculation_version=VERSION, run_id=folder.name,
                 status='preflight', trials=[], pairs=[], plan=PLAN, detector_config=CONFIG,
                 msg_db=None, asg_db=None, normal_mic_amplification_demonstrated=False)
    row = None
    def save(): write_json(folder/'summary.json', state)
    def trial(mode, gain, pcm, seconds, direct=False, speech=False):
        nonlocal row
        index = len(state['trials'])+1
        path = folder/('%02d-%s.npz' % (index, mode))
        row = dict(index=index, mode=mode, gain_db=gain, file=path.name, status='preparing')
        state['trials'].append(row); save()
        # Check every frozen asset before each call, including the model.
        validator(base)
        def ready():
            print('%02d %s: 配置就绪、静音。%s；本项 %.2f 秒。' %
                  (index, mode, '输入 START 后正常说话，持续至结束' if speech else '手机和人员保持静音', seconds))
            ok = ask('START 开始；其他输入停止整批：').strip().upper() == 'START'
            if ok: row['status']='audio_authorized'; save()
            return ok
        try:
            meta = runner(path, scene['fixture_id'], str(base/'model.json'), pcm,
                          bypass=mode.endswith('bypass'), direct_only=direct,
                          zero_coeff=False, gain_db=gain, seconds=seconds, hp_volume=40,
                          speaker_confirmed=True, local_capture_confirmed=True, before_start=ready)
            row['metadata'] = meta
        finally:
            if path.is_file():
                expected = dict(model_sha256=manifest['hashes']['model.json'],
                                bit_sha256=manifest['hashes']['audio_replay.bit'],
                                hp_volume=40, sample_rate_hz=48828.125, fixture_id=scene['fixture_id'],
                                bypass=mode.endswith('bypass'),
                                gain_q12=(0 if direct else int(np.floor(4096*10**(gain/20)+.5))),
                                source_pcm16_sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
                                driver_evidence_version='a-replay-evidence-v2')
                if coefficient_hash is not None:
                    expected['coefficients_sha256'] = coefficient_hash
                row['analysis'] = analyze_npz(path, expected=expected, external_source_active=speech,
                                              external_source_off_verified=not speech)
                row['status'] = 'captured'
            status_path = path.with_suffix('.status.json')
            if status_path.is_file(): row['driver_status'] = json.loads(status_path.read_text(encoding='utf8'))
            save()
        if not path.is_file(): raise RuntimeError('driver_returned_without_capture')
        if row.get('driver_status',{}).get('recovery_ok') is not True:
            raise RuntimeError('restoration_not_confirmed')
        a = row['analysis']
        if a['category']=='invalid' or a['event_flags'].get('protection') or a['event_flags'].get('instability_growth'):
            raise RuntimeError('measurement_stop:'+a['category'])
        if any(v for k,v in a['event_flags'].items() if k.endswith('saturations') or k=='microphone_clipping'):
            raise RuntimeError('numerical_or_level_event')
        if row['metadata'].get('verification',{}).get('bit_exact') is not True:
            raise RuntimeError('arithmetic_not_verified')
        answer = ask('已结束并恢复静音。1 清楚/可接受；0 无声；2 失真；3 增长尖叫；4 未静；q 停止：').strip()
        row['hearing_code']=answer; save()
        if answer!='1': raise RuntimeError('operator_hearing:'+answer)
        if speech:
            # External speech has no verified source-off boundary. Keep it out of
            # the tail classifier even though the injected digital source is zero.
            row['analysis'] = dict(category='unknown', calculation_version=VERSION,
                                   reasons=['external_speech_active; functional_acceptance_only'], event_flags=a['event_flags'])
        return row
    try:
        save()
        manifest, scene = validator(base)
        model = json.loads((base/'model.json').read_text(encoding='utf8')) if (base/'model.json').exists() else {}
        q = model.get('coefficients_q20')
        if q is not None and len(q)==256 and manifest.get('hashes',{}).get('audio_replay.bit') in BIT_CAPACITIES:
            q=np.pad(np.asarray(q,dtype='<i4'),(0,256))
        coefficient_hash = (hashlib.sha256(np.asarray(q,dtype='<i4').tobytes()).hexdigest() if q is not None else None)
        state['versions'] = manifest
        state['scene'] = scene
        if runner is None:
            from replay_trial import replay_trial
            runner = replay_trial
        print('最多18项，数字试次共19.36秒，外部讲话4秒；逐项START，全程有人值守。')
        if ask('确认箱体关盖、两音响在线且可断电、手机静音、允许板上保存，输入 READY：').strip().upper()!='READY':
            state['status']='cancelled'; return state
        pcm = source_pcm()
        state['status']='running'
        for gain in PLAN['gains_db']:
            for repeat in range(PLAN['repeats']):
                pre = trial('control-before-bypass', gain, pcm, 1.02, direct=True)
                before = positive_control(folder/pre['file']); pre['positive_control'] = before
                if not before['passed']: raise RuntimeError('positive_control_before_failed')
                modes = ('cancel','bypass') if repeat==0 else ('bypass','cancel')
                pair = [trial(mode, gain, pcm, PLAN['digital_seconds']) for mode in modes]
                post = trial('control-after-bypass', gain, pcm, 1.02, direct=True)
                after = positive_control(folder/post['file']); post['positive_control'] = after
                controls_ok = (after['passed'] and abs(after['rms_dbfs']-before['rms_dbfs'])<=PLAN['positive_control_drift_db']
                               and abs(after['delay_frames']-before['delay_frames'])<=PLAN['maximum_lag_change_frames'])
                if not controls_ok: raise RuntimeError('positive_control_drift_or_delay')
                keys = ('bit_sha256','model_sha256','coefficients_sha256','source_pcm16_sha256',
                        'gain_q12','hp_volume','sample_rate_hz','completed_frames','fixture_id')
                comparable = all(pair[0]['metadata'].get(k) is not None and
                                 pair[0]['metadata'].get(k)==pair[1]['metadata'].get(k) for k in keys)
                for r in pair:
                    r['analysis'] = analyze_npz(folder/r['file'], positive_control_valid=controls_ok,
                                               external_source_off_verified=True)
                state['pairs'].append(dict(gain_db=gain, repeat=repeat+1, comparable=comparable,
                                           trials=[r['index'] for r in pair], positive_controls_valid=controls_ok,
                                           asg_db=None))
                save()
                if not comparable: raise RuntimeError('pair_configuration_mismatch')
                if any(r['analysis']['category']=='unknown' for r in pair):
                    raise RuntimeError('tail_evidence_insufficient; do not escalate; C reviews saved packet')
        # Functional input acceptance after digital comparisons; no digital excitation.
        zero_source = np.zeros(1,dtype='<i2')
        for mode in ('speech-cancel','speech-bypass'):
            trial(mode, PLAN['speech_gain_db'], zero_source, PLAN['speech_seconds'], speech=True)
        state.update(status='completed', normal_mic_amplification_demonstrated=True)
    except (Exception, KeyboardInterrupt) as exc:
        state.update(status='stopped', stop_reason=type(exc).__name__+': '+str(exc))
        if row is not None: row['error']=state['stop_reason']
    finally:
        state['resume_policy']='never resume audio automatically; collect existing results, fix cause, create new run'
        try:
            out = collect(folder, state)
            print('RETURN_ONE_FILE', str(out.resolve()))
        except OSError as exc:
            # A driver owns actual recovery. Do not hide it with a second failing save.
            print('RESULT_SAVE_FAILED', str(exc), 'BOARD_RESULTS_DIRECTORY', str(folder.resolve()))
    return state


if __name__ == '__main__':
    run_package()
