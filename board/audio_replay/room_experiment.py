"""Bounded current-room comparison. Import never accesses hardware."""
import hashlib
import json
from pathlib import Path
import uuid
import zipfile

import numpy as np
from evaluation import VERSION, analyze_npz, sha
from model_comparison import flat_trial, pair_models, export_csv, load_registry, SUMMARY_REVISION

RATE = 48828.125
POLICY = 'c-room-policy-1.0.0'
PLAN = dict(fixture_id='room_v1_20261021', hp_volume=40,
            gains_db=[-9., -6., -3., 0.], repeats=2,
            seconds=2.1, source_seconds=1.87, source_rms_dbfs=-24.,
            gate_hz=1000., gate_peak_dbfs=-20., gate_seconds=1.02,
            gate_source_seconds=1., gate_drift_db=1.5, gate_noise_margin_db=6.,
            transition_frames=2442, speech_seconds=3., speech_gain_db=-9.,
            purpose='current-session 256/512 same-gain comparison; no measured MSG/ASG',
            online_microphone_clip_protection=False)


def write_json(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    temp.replace(path)


def sources():
    n=int(PLAN['source_seconds']*RATE)
    x=np.random.default_rng(20261024).normal(size=n)
    fade=int(.01*RATE)
    x[:fade]*=np.linspace(0,1,fade); x[-fade:]*=np.linspace(1,0,fade)
    x*=10**(PLAN['source_rms_dbfs']/20)/np.sqrt(np.mean(x*x))
    if np.max(np.abs(x))>.5:raise ValueError('source peak exceeds fixed headroom')
    burst=np.rint(x*32768).astype('<i2')
    t=np.arange(int(PLAN['gate_source_seconds']*RATE))/RATE
    tone=np.sin(2*np.pi*PLAN['gate_hz']*t)*10**(PLAN['gate_peak_dbfs']/20)
    tone[:fade]*=np.linspace(0,1,fade);tone[-fade:]*=np.linspace(1,0,fade)
    return burst,np.rint(tone*32768).astype('<i2')


def check_room_package(base):
    base=Path(base);m=json.loads((base/'experiment-manifest.json').read_text(encoding='utf8'))
    if m.get('status')!='ready' or m.get('measurement_policy_version')!=POLICY or m.get('calculation_version')!=VERSION:
        raise ValueError('ROOM_PACKAGE_NOT_READY')
    if m.get('plan')!=PLAN:raise ValueError('frozen room plan mismatch')
    for name,digest in m['hashes'].items():
        p=(base/name).resolve()
        if base.resolve() not in p.parents or sha(p)!=digest:raise ValueError('frozen asset mismatch: '+name)
    nb=json.loads((base/'experiment.ipynb').read_text(encoding='utf8'))
    code=[''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code']
    if hashlib.sha256(json.dumps(code,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()!=m['notebook_code_sha256']:
        raise ValueError('Notebook code mismatch')
    scene=json.loads((base/'scene.json').read_text(encoding='utf8'))
    if scene.get('fixture_id')!=PLAN['fixture_id'] or scene.get('hp_volume')!=40 or scene.get('matches_calibration') is not True:
        raise ValueError('room scene mismatch')
    registry=load_registry(base/'models')
    if {v['role'] for v in registry.values()}!={'baseline','candidate'}:raise ValueError('room model pair missing')
    return m,scene


def pcm_from_capture(path):
    with np.load(path,allow_pickle=False) as z:
        mic=np.rint(z['microphone']*2**23).astype(np.int64)
        ref=np.array(z['reference'])*2**23
        meta=json.loads(str(z['metadata_json'].item()))
    if mic.ndim!=1 or ref.shape!=mic.shape:raise ValueError('capture shape mismatch')
    return mic,ref,meta


def gate_metrics(path,noise_floor_dbfs,baseline_dbfs=None):
    mic,ref,m=pcm_from_capture(path)
    first=m['first_frame'];end=min(m['completed_frames'],m['source_end_frame_exclusive']-int(.01*RATE))
    begin=max(first,int(.02*RATE));lo=begin-first;hi=max(lo,end-first)
    x=mic[lo:hi].astype(float)/2**23;y=ref[lo:hi]/2**23
    result=dict(passed=False,baseline_dbfs=baseline_dbfs,capture_sha256=sha(path),
                first_frame=begin,end_frame=end,reasons=[])
    if len(x)<2048:result['reasons'].append('gate_source_on_window_too_short');return result
    t=np.arange(begin,end)/RATE
    basis=np.column_stack((np.sin(2*np.pi*PLAN['gate_hz']*t),np.cos(2*np.pi*PLAN['gate_hz']*t),np.ones(len(t))))
    coeff=np.linalg.lstsq(basis,x,rcond=None)[0]
    fitted=basis[:,:2]@coeff[:2]
    level=float(20*np.log10(max(np.std(x),1e-12)))
    tonal_fraction=float(np.mean(fitted*fitted)/max(np.var(x),1e-24))
    drift=None if baseline_dbfs is None else level-baseline_dbfs
    result.update(rms_dbfs=level,tonal_fraction=tonal_fraction,drift_db=drift,
                  reference_rms_dbfs=float(20*np.log10(max(np.std(y),1e-12))))
    if level<float(noise_floor_dbfs)+PLAN['gate_noise_margin_db']:result['reasons'].append('gate_at_noise_floor')
    if level>-3:result['reasons'].append('gate_level_too_high')
    if tonal_fraction<.8:result['reasons'].append('gate_tone_not_observed')
    if np.any((mic==-2**23)|(mic==2**23-1)):result['reasons'].append('gate_microphone_full_scale')
    if drift is not None and abs(drift)>PLAN['gate_drift_db']:result['reasons'].append('gate_drift_exceeds_1p5_db')
    result['passed']=not result['reasons'];return result


def active_statistics(path,noise_floor_dbfs):
    mic,_,m=pcm_from_capture(path)
    # Exclude unknown FIR history at the ring boundary and the fixed source fade.
    first=m['first_frame'];begin=first+512
    end=min(m['completed_frames'],m['source_end_frame_exclusive']-int(.01*RATE))
    x=mic[max(0,begin-first):max(0,end-first)]/2**23
    level=None if not len(x) else float(20*np.log10(max(np.std(x),1e-12)))
    return dict(first_frame=begin,end_frame=end,frames=len(x),mic_rms_dbfs=level,
                valid=bool(len(x)>=2048 and level>=noise_floor_dbfs+6.))


def collect_room(base,folder,state):
    registry=load_registry(base/'models') if (base/'models/manifest.json').is_file() else None
    for row in state['trials']:
        if row['trial_role']=='closed_model' and row.get('post_gate',{}).get('passed') is not True:
            a=row.get('analysis')
            if a:
                a['category']='invalid';a['reasons'].append('post_trial_gate_not_confirmed')
                a.get('evaluation_metadata',{})['positive_control_valid']=False
        row.update(flat_trial(row,registry))
    state['model_pairs']=pair_models(state['trials'])
    state['schema_version']=3;state['calculation_version']=VERSION;state['summary_revision']=SUMMARY_REVISION
    state['raw_files']=[dict(file=p.name,sha256=sha(p),board_path=str(p.resolve())) for p in sorted(folder.glob('*.npz'))]
    write_json(folder/'summary.json',state);export_csv(folder/'summary.csv',state['trials'])
    packet=folder/'return-results.zip'
    with zipfile.ZipFile(packet,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.iterdir()):
            if p.suffix in ('.json','.csv','.txt'):z.write(p,p.name)
        # Exact model bytes let B verify the current-session model identities.
        for p in sorted((base/'models').rglob('*.json')):z.write(p,'models/'+str(p.relative_to(base/'models')).replace('\\','/'))
    return packet


def run_room(base=None,ask=input,runner=None,validator=check_room_package):
    base=Path(base or Path(__file__).resolve().parent)
    folder=base/'results'/('room-'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    state=dict(run_id=folder.name,measurement_policy_version=POLICY,status='preflight',
               trials=[],plan=PLAN,msg_db=None,asg_db=None,amplifier_reset_required=False,
               normal_mic_amplification_demonstrated=False,model_pairs=[],
               evidence_kind='software_fixture' if runner is not None else 'board_recording')
    row=None;gate_baseline=None;last_closed=None
    def save():write_json(folder/'summary.json',state)
    def call(role,model_role,gain,pcm,seconds,comparison=None,repeat=None,gate=None):
        nonlocal row,last_closed
        validator(base)
        index=len(state['trials'])+1;path=folder/('%02d-%s-%s.npz'%(index,role,model_role))
        model_path=base/manifest['model_files'][model_role]
        row=dict(index=index,file=path.name,trial_role=role,mode='speech-bypass' if model_role=='bypass' else role,
                 status='preparing',amplifier_gate=gate)
        state['trials'].append(row);save()
        direct=role=='amplifier_gate';speech=role=='speech';bypass=model_role=='bypass' or direct
        def ready():
            if direct:return True  # READY explicitly authorizes these bounded open-loop gates.
            text='正常讲话，至提示结束' if speech else '手机和人员静音'
            return ask('%s %s %.1f dB，已装载且静音；%s。START开始，其他停止：'%(role,model_role,gain,text)).strip().upper()=='START'
        try:
            row['metadata']=runner(path,scene['fixture_id'],str(model_path),pcm,bypass=bypass,
                zero_coeff=False,direct_only=direct,gain_db=gain,seconds=seconds,hp_volume=40,
                speaker_confirmed=True,local_capture_confirmed=True,before_start=ready)
        finally:
            if path.is_file():
                context=dict(scene_sha256=sha(base/'scene.json'),session_id=state['run_id'],
                             measurement_policy_version=POLICY,trial_role=role,
                             mute_applied=True,mute_during_observation=False,
                             external_source_off_verified=not speech,external_source_active=speech,
                             noise_floor_dbfs=scene['noise_floor_dbfs'])
                if comparison is not None:context.update(comparison_id=comparison,repeat_id=repeat)
                if gate is not None:context['positive_control_valid']=gate['passed']
                evidence=dict(input_sha256=sha(path),provenance='C frozen room policy; prior gate '+str(gate.get('capture_sha256') if gate else None),metadata=context)
                q=json.loads(model_path.read_text(encoding='utf8'))['coefficients_q20'];q=np.pad(q,(0,512-len(q))).astype('<i4')
                expected=dict(model_sha256=sha(model_path),bit_sha256=manifest['hashes']['audio_replay.bit'],
                              coefficients_sha256=hashlib.sha256(q.tobytes()).hexdigest(),fixture_id=scene['fixture_id'],
                              hp_volume=40,sample_rate_hz=RATE,bypass=bypass,
                              gain_q12=0 if direct else int(np.floor(4096*10**(gain/20)+.5)),
                              source_pcm16_sha256=hashlib.sha256(pcm.astype('<i2').tobytes()).hexdigest(),
                              driver_evidence_version='a-replay-evidence-v2')
                row['analysis']=analyze_npz(path,expected=expected,metadata_evidence=evidence,
                    external_source_active=speech,analysis_interval='source_off_tail' if role=='closed_model' else None)
                flags=row['analysis']['event_flags']
                if flags.get('microphone_clipping') or flags.get('protection'):
                    state['amplifier_reset_required']=True
                row['status']='captured'
            side=path.with_suffix('.status.json')
            if side.is_file():row['driver_status']=json.loads(side.read_text(encoding='utf8'))
            save()
        if not path.is_file():raise RuntimeError('capture_missing')
        a=row['analysis'];flags=a['event_flags']
        if flags.get('microphone_clipping'):
            state['amplifier_reset_required']=True;raise RuntimeError('microphone_full_scale; new gate required before any next trial')
        if row.get('driver_status',{}).get('recovery_ok') is not True:raise RuntimeError('recovery_not_confirmed')
        if flags.get('protection') or flags.get('instability_growth') or any(flags.get(k) for k in ('prediction_saturations','residual_saturations','gain_saturations','mix_saturations')):
            state['amplifier_reset_required']=True;raise RuntimeError('level_or_growth_event; batch stopped')
        if a['category']=='invalid':raise RuntimeError('capture_invalid:'+','.join(a['reasons']))
        if a.get('evaluation_metadata',{}).get('verification',{}).get('bit_exact') is not True:raise RuntimeError('arithmetic_not_verified')
        if role=='closed_model':
            row['active_source_statistics']=active_statistics(path,scene['noise_floor_dbfs'])
            if not row['active_source_statistics']['valid']:
                a['category']='invalid';a['reasons'].append('active_source_not_observed')
                raise RuntimeError('active_source_not_observed; no stability conclusion')
            if not a.get('tail_statistics',{}).get('tail_valid'):
                a['category']='unknown';a['reasons'].append('tail_not_qualified; no stability claim')
        if not direct:
            answer=ask('已恢复静音：1清楚/可接受，0无声，2失真，3尖叫，4未静，q停止：').strip()
            row['hearing_code']=answer;save()
            if answer!='1':
                a['category']='invalid';a['reasons'].append('operator_hearing:'+answer)
                raise RuntimeError('operator_hearing:'+answer)
        if role=='closed_model':last_closed=row
        return row
    def gate():
        nonlocal last_closed
        r=call('amplifier_gate','candidate',0.,tone,PLAN['gate_seconds'])
        g=gate_metrics(folder/r['file'],scene['noise_floor_dbfs'],gate_baseline)
        if last_closed is not None:
            last_closed['post_gate']=g
            last_closed['analysis']['evaluation_metadata']['positive_control_valid']=g['passed']
            if not g['passed']:
                last_closed['analysis']['category']='invalid'
                last_closed['analysis']['reasons'].append('post_trial_gate_failed')
            last_closed=None
        r['amplifier_gate']=g;save()
        if not g['passed']:raise RuntimeError('amplifier_gate_failed:'+','.join(g['reasons']))
        return g
    try:
        save();manifest,scene=validator(base);state.update(versions=manifest,scene=scene)
        burst=np.load(base/'burst.npy',allow_pickle=False);tone=np.load(base/'gate.npy',allow_pickle=False)
        if burst.dtype!=np.dtype('<i2') or tone.dtype!=np.dtype('<i2'):raise ValueError('frozen source dtype mismatch')
        print('房间0.5 m、音响1只、Codec40；手机静音。每项门禁直放1.02秒；闭环最长2.1秒，需START。')
        print('有人值守并可立即断音响电源。麦克风满幅检查覆盖保存窗口；没有全程ADC在线保护。')
        action=ask('确认现场已恢复正常、允许本地保存：RUN固定模型比较；SPEECH仅外部讲话；其他退出：').strip().upper()
        state['requested_action']=action
        if action not in ('RUN','SPEECH'):
            state.update(status='cancelled',stop_reason='operator_cancel_before_audio');return state
        if runner is None:
            from replay_trial import replay_trial
            runner=replay_trial
        g=gate();gate_baseline=g['rms_dbfs'];state['gate_baseline_dbfs']=gate_baseline;gate()
        state['status']='running'
        if action=='RUN':
            for gain in PLAN['gains_db']:
                q=int(np.floor(4096*10**(gain/20)+.5))
                for repeat in range(PLAN['repeats']):
                    roles=('candidate','baseline') if repeat==0 else ('baseline','candidate')
                    identity='%s-q%d-r%d'%(state['run_id'],q,repeat+1)
                    for role in roles:
                        g=gate()
                        call('closed_model',role,gain,burst,PLAN['seconds'],identity,repeat+1,g)
        # This is a functional speech acceptance, separate from the model comparison.
        for role in ('candidate','bypass'):
            g=gate();call('speech',role,PLAN['speech_gain_db'],np.zeros(1,dtype='<i2'),PLAN['speech_seconds'],gate=g)
        state.update(status='completed',stop_reason='completed',functional_hearing_accepted=True,
                     normal_mic_amplification_demonstrated=state['evidence_kind']=='board_recording')
    except (Exception,KeyboardInterrupt) as exc:
        state.update(status='stopped',stop_reason=type(exc).__name__+': '+str(exc))
        if row is not None:row['error']=state['stop_reason']
    finally:
        state['resume_policy']='no automatic audio resume; a new run requires fresh initial gates'
        state['executed_counts']={role:sum(r['trial_role']==role for r in state['trials'])
                                  for role in ('amplifier_gate','closed_model','speech')}
        state['planned_model_trials']=16 if state.get('requested_action')=='RUN' else 0
        state['unexecuted_model_trials']=max(0,state['planned_model_trials']-state['executed_counts']['closed_model'])
        try:
            packet=collect_room(base,folder,state);print('RETURN_ONE_FILE',str(packet.resolve()))
        except (OSError,ValueError) as exc:
            print('RESULT_SAVE_FAILED',str(exc),'BOARD_RESULTS_DIRECTORY',str(folder.resolve()))
    return state
