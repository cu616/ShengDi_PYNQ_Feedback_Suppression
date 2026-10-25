"""Project-only RC0 orchestration. Hardware remains owned by A's frozen driver.

No import-time hardware actions. The v2 continuous entry arms once for 60 s;
its register timeline and tail ring support engineering acceptance only.
"""
import csv
import hashlib
import json
import platform
from pathlib import Path
import uuid
import wave
import zipfile

import numpy as np
from evaluation import VERSION, CONFIG, analyze_npz, sha
from model_comparison import protection_evidence, qhash, flat_trial, export_csv
from room_experiment import gate_metrics, sources, write_json
from tail_metrics import BANDS, TAIL_CONFIG

POLICY = 'c-sprint-rc01-1.0.5'
A_ASSETS = dict(commit='85f4967f242eed61eaa6b74041be931c2f5bc7a0', contract='audio-replay-v2+audio-closed-v2',
    bit_sha256='61bb71aabb824c57191edcea93d1333143cd959c16d43028585913c54a8f61fa',
    hwh_sha256='92b499a39d04de891632a89512bfff49f7482a332344128556b1506529d1b75b',
    max_run_frames=3000000)
DEFAULT_MODEL = dict(name='calibrated_20261024',source_file='models/room_v1/calibrated_20261024.json',
    file_sha256='c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a',
    coefficients_sha256='c9d3b1e658fd2ed8b731904eaa1f2bec62677b732f5bebe1acf34f1d96fa2160',
    validity='same verified calibration scene only; no cross-session fallback')
RATE = 48828.125
PLAN = dict(gain_db=-14., gain_q12=817, hp_volume=40, sample_rate_hz=RATE,
            fixture_id='room_v1_20261021', speech_seconds=8., pair_seconds=2.52, source_seconds=2.50,
            repeats=2, continuous_target_seconds=60., eq='identity',
            gate_drift_db=5., pair_gate_drift_db=1.5,
            fir_observation='forced_source_response', source_rms_dbfs=-24.,
            automatic_gain_escalation=False)
PAIR_FIELDS = ('gain_q12', 'hp_volume', 'sample_rate_hz', 'fixture_id',
               'bit_sha256', 'model_sha256', 'coefficients_sha256',
               'source_pcm16_sha256', 'session_id', 'scene_sha256', 'eq_sha256')
PAIR_FIELDS += ('comparison_id','repeat_id','comparison_first_frame','comparison_end_frame','measurement_kind')


def comparison_source():
    """Same -24 dBFS forcing level, sustained through the saved capture window."""
    x=np.random.default_rng(20261024).normal(size=int(PLAN['source_seconds']*RATE))
    fade=int(.01*RATE)
    x[:fade]*=np.linspace(0,1,fade);x[-fade:]*=np.linspace(1,0,fade)
    x*=10**(PLAN['source_rms_dbfs']/20)/np.sqrt(np.mean(x*x))
    if np.max(abs(x))>.5:raise ValueError('comparison source exceeds fixed headroom')
    return np.rint(x*32768).astype('<i2')


def source_response(path, source, external_source_off_verified):
    """Descriptive forced-response powers, never a stability or howl criterion.

    Retain the tail metric's signal/noise and band floors. A source-on window is
    qualified explicitly; no frame metadata are relabelled as a source-off tail.
    """
    out=dict(valid=False,kind='forced_source_response',reasons=[],first_frame=None,end_frame=None,frames=0,
             rms_dbfs=None,mic_band_dbfs={},minimum_mic_dbfs=max(TAIL_CONFIG['minimum_mic_dbfs'],-37.8+6.),
             minimum_band_mic_dbfs=TAIL_CONFIG['minimum_band_mic_dbfs'],
             scope='same digital forcing, microphone response in saved source-on window; no stability/MSG/ASG')
    try:
        if external_source_off_verified is not True:raise ValueError('external_source_off_unverified')
        with np.load(path,allow_pickle=False) as capture:
            m=json.loads(str(capture['metadata_json'].item()));mic=np.asarray(capture['microphone'],float)
            if ('source_pcm16' not in capture or not np.array_equal(capture['source_pcm16'],source) or
                    m.get('source_pcm16_sha256')!=hashlib.sha256(source.tobytes()).hexdigest()):
                raise ValueError('forcing_source_mismatch')
            if (m.get('source_schedule_verified') is not True or
                    m.get('source_end_frame_exclusive')!=len(source) or m.get('source_frames')!=len(source)):
                raise ValueError('forcing_schedule_unverified')
            first,end,frames=(m.get(k) for k in ('first_frame','completed_frames','frames'))
            if (any(type(v) is not int for v in (first,end,frames)) or end-first!=frames or
                    mic.shape!=(frames,) or not np.isfinite(mic).all() or np.any(abs(mic)>=1) or
                    m.get('dropped_frames',0)):
                raise ValueError('invalid_response_capture')
            rate=float(capture['sample_rate_hz'].item())
            if rate!=RATE:raise ValueError('response_rate_mismatch')
        # Exclude unknown FIR history and the fixed source fade. Both sides use
        # identical global frame indices; a longer run cannot enlarge this ring.
        begin=max(first+512,int(.2*rate));stop=min(end,len(source)-int(.01*rate))
        out.update(first_frame=begin,end_frame=max(begin,stop),frames=max(0,stop-begin))
        block=round(rate*TAIL_CONFIG['block_seconds'])
        if stop-begin<block*TAIL_CONFIG['minimum_blocks']:raise ValueError('response_window_too_short')
        x=mic[begin-first:stop-first].copy();x-=x.mean()
        level=float(20*np.log10(max(np.std(x),1e-12)));out['rms_dbfs']=level
        if level<out['minimum_mic_dbfs']:raise ValueError('response_below_signal_floor')
        blocks=x[:len(x)//block*block].reshape(-1,block)
        if np.any(np.std(blocks,axis=1)<10**(out['minimum_mic_dbfs']/20)):
            raise ValueError('response_blocks_below_signal_floor')
        window=np.hanning(len(x));power=abs(np.fft.rfft(x*window))**2
        freq=np.fft.rfftfreq(len(x),1/rate);scale=2/(len(x)*np.sum(window**2))
        for low,high in BANDS:
            mask=(freq>=low)&(freq<high);energy=float(power[mask].sum()*scale)
            key=f'{low}-{high}'
            if not mask.any() or energy<10**(out['minimum_band_mic_dbfs']/10):
                out['mic_band_dbfs'][key]=None;out['reasons'].append('band_below_signal_floor:'+key)
            else:out['mic_band_dbfs'][key]=float(10*np.log10(energy))
        out['valid']=not out['reasons']
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
        out['reasons'].append(str(exc))
    return out


def validate_preflight(manifest, preflight):
    payload = {k:v for k,v in manifest['hashes'].items() if k!='preflight.json'}
    rows = preflight.get('trials', [])
    required = ('seconds','source_frames','transition_frames','capture_frames','window_frames')
    human = manifest.get('workflow','full')=='human_only'
    if ('preflight.json' not in manifest['hashes'] or preflight.get('all_ok') is not True or
            preflight.get('policy') != POLICY or
            preflight.get('evidence_kind') != 'software_fixture' or
            preflight.get('a_assets') != manifest.get('a_assets') or
            preflight.get('source_commits') != manifest['source_commits'] or
            preflight.get('workflow','full')!=manifest.get('workflow','full') or
            preflight.get('payload_hashes') != payload or len(rows)!=(5 if human else 15) or
            preflight.get('checks',{}).get('real_driver_rejects_equal_source_budget') is not True or
            preflight.get('checks',{}).get('human_scope_preserved' if human else 'continuous_workflow_passed') is not True or
            any(r.get('driver_input_ok') is not True for r in rows) or
            any(r.get('ok') is not True or any(not isinstance(r.get(k),(int,float)) or
                not np.isfinite(r[k]) or r[k]<=0 for k in required) or
                r['window_frames']>r['capture_frames'] for r in rows)):
        raise ValueError('PREFLIGHT_FAIL: missing, failed or stale software preflight')


def check_package(base, require_preflight=True):
    base = Path(base).resolve()
    manifest = json.loads((base/'sprint-manifest.json').read_text(encoding='utf8'))
    if manifest.get('workflow','full') not in ('full','human_only'):
        raise ValueError('unsupported sprint workflow')
    if (manifest['policy'] != POLICY or manifest['plan'] != PLAN or
            manifest['calculation_version'] != VERSION or manifest['detector_config'] != CONFIG or
            manifest.get('default_model') != DEFAULT_MODEL):
        raise ValueError('frozen policy mismatch')
    if (manifest.get('a_assets') != A_ASSETS or manifest['source_commits']['A']!=A_ASSETS['commit'] or
            manifest['hashes'].get('audio_replay.bit')!=A_ASSETS['bit_sha256'] or
            manifest['hashes'].get('audio_replay.hwh')!=A_ASSETS['hwh_sha256']):
        raise ValueError('ASSET_MISMATCH: A commit/contract/bit/hwh binding')
    for name, digest in manifest['hashes'].items():
        path = (base/name).resolve()
        if base not in path.parents or sha(path) != digest:
            raise ValueError('package hash mismatch: '+name)
    from residual_tools import load_candidate
    model, q = load_candidate(base/'model.json', PLAN['fixture_id'], PLAN['hp_volume'], RATE)
    if len(q) != 512 or qhash(q) != manifest['coefficients_sha256']:
        raise ValueError('deployed Q20 mismatch')
    if (sha(base/'model.json')!=DEFAULT_MODEL['file_sha256'] or
            qhash(q)!=DEFAULT_MODEL['coefficients_sha256']):
        raise ValueError('default calibrated model mismatch; no candidate_512 fallback')
    if require_preflight:
        preflight = json.loads((base/'preflight.json').read_text(encoding='utf8'))
        validate_preflight(manifest, preflight)
    return manifest


def pair_check(a, b):
    """One actual FIR switch, no model/EQ/gain/scene changes hidden in a pair."""
    reasons = [k for k in PAIR_FIELDS if a.get(k) is None or a.get(k) != b.get(k)]
    if a.get('bypass') is not True or b.get('bypass') is not False:
        reasons.append('fir_switch')
    if any(x.get('category') not in ('unknown','no_instability_observed_in_window') or x.get('stop_reasons') or
           x.get('protection') is not False or x.get('recovery_ok') is not True or
           (x.get('category')=='unknown' and x.get('analysis',{}).get('reasons')!=['source_or_transition_overlap']) for x in (a,b)):
        reasons.append('validity_or_stop')
    if any(x.get('source_response',{}).get('valid') is not True or
           x.get('measurement_kind')!='forced_source_response' for x in (a,b)):
        reasons.append('source_response_not_validated')
    gates = [x.get('gate_mic_over_ref_db') for x in (a,b)]
    if any(v is None for v in gates) or abs(gates[0]-gates[1]) > PLAN['pair_gate_drift_db']:
        reasons.append('pair_path_drift')
    response=[x.get('source_response',{}) for x in (a,b)]
    levels=[t.get('rms_dbfs') for t in response]
    band_delta={}
    for low,high in BANDS:
        key=f'{low}-{high}';values=[t.get('mic_band_dbfs',{}).get(key) for t in response]
        band_delta[key]=(values[1]-values[0] if not reasons and all(v is not None for v in values) else None)
    return dict(comparison_id=a.get('comparison_id'),repeat_id=a.get('repeat_id'),
                off_capture_id=a.get('capture_id'),on_capture_id=b.get('capture_id'),gain_q12=a.get('gain_q12'),
                configuration_matches=not any(r in PAIR_FIELDS or r=='fir_switch' for r in reasons),
                window_comparison_valid=not reasons, reasons=reasons,
                on_minus_off_tail_rms_db=None,
                on_minus_off_response_rms_db=(levels[1]-levels[0] if not reasons and all(v is not None for v in levels) else None),
                on_minus_off_band_response_db=band_delta,measurement_kind='forced_source_response',
                coverage_scope='saved source-on response windows only; no acoustic stability claim',
                measured_msg_db=None,measured_asg_db=None)


def stop_reasons(analysis, status, error=None):
    flags = analysis.get('event_flags', {})
    reasons = []
    if error: reasons.append('execution_error:'+str(error))
    if analysis.get('category') == 'invalid': reasons.append('invalid_capture')
    if flags.get('protection') is True: reasons.append('protection')
    if flags.get('early_stop') is True: reasons.append('early_stop')
    if any(flags.get(k) is True for k in ('prediction_saturations', 'residual_saturations',
                                         'gain_saturations', 'mix_saturations', 'microphone_clipping')):
        reasons.append('clipping_or_numeric_event')
    if flags.get('instability_growth'): reasons.append('observed_growth')
    if status.get('recovery_ok') is not True: reasons.append('recovery_not_verified')
    if status.get('save_error'): reasons.append('save_error')
    return reasons


def listener_metrics(folder, confirmation):
    """Fixed-gain PCM16 recorder; noise subtraction is power subtraction.

    No calibrated SPL, no AGC correction, no total-RMS speech improvement claim.
    Only statistics and hashes enter the return ZIP; WAVs stay local.
    """
    if confirmation != 'FIXED_SOURCE_FIXED_GAIN_NO_AGC':
        return dict(status='not_tested', reason='fixed_source_and_measurement_gain_not_confirmed')
    levels = {}; rates = set(); durations = set(); hashes = {}
    try:
        for mode in ('off', 'on'):
            for kind in ('speech', 'noise'):
                key = mode+'-'+kind; path = Path(folder)/(key+'.wav')
                with wave.open(str(path), 'rb') as stream:
                    if stream.getnchannels()!=1 or stream.getsampwidth()!=2 or stream.getcomptype()!='NONE':
                        raise ValueError('mono uncompressed PCM16 required: '+key)
                    rate = stream.getframerate(); rates.add(rate)
                    x = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(float)
                if len(x) < rate or np.any(x <= -32768) or np.any(x >= 32767):
                    raise ValueError('short or clipped listener recording: '+key)
                if kind=='speech': durations.add((len(x), rate))
                levels[key] = float(np.mean((x-x.mean())**2)/32768**2)
                hashes[key] = sha(path)
        if len(rates)!=1 or len(durations)!=1: raise ValueError('listener rates/durations differ')
        speech = {m:levels[m+'-speech']-levels[m+'-noise'] for m in ('off','on')}
        snr = {m:10*np.log10(levels[m+'-speech']/max(levels[m+'-noise'], 1e-24)) for m in speech}
        if any(speech[m]<=0 or snr[m]<6 for m in speech):
            raise ValueError('speech power not separated from background by 6 dB')
        return dict(status='passed', relative_speech_change_db=float(10*np.log10(speech['on']/speech['off'])),
                    snr_db=snr, input_sha256=hashes, absolute_spl=None,
                    scope='fixed listener, source and recorder gain; descriptive relative result, no universal quality pass')
    except (OSError, ValueError, wave.Error) as exc:
        return dict(status='not_tested' if isinstance(exc, FileNotFoundError) else 'failed', reason=str(exc),
                    absolute_spl=None)


def collect(folder, state):
    folder = Path(folder)
    # Include evidence created just before a kernel/process interruption, even
    # when the runner never returned to append its normal summary row.
    inventory = []
    for path in sorted(folder.glob('*.npz')):
        entry = dict(file=path.name,sha256=sha(path),metadata=None)
        try:
            with path.open('rb') as stream, np.load(stream,allow_pickle=False) as capture:
                entry['metadata']=json.loads(str(capture['metadata_json'].item()))
        except (OSError,ValueError,KeyError,EOFError,zipfile.BadZipFile) as exc:
            entry['read_error']=str(exc)
        inventory.append(entry)
    state['raw_files']=inventory
    write_json(folder/'summary.json', state)
    # Preserve the existing B-readable model-summary schema. FIR switch pairs
    # remain in fir_pairs: they are not baseline/candidate model comparisons.
    b_rows=[]
    registry=state.get('model_registry')
    for row in state['trials']:
        a=dict(row['analysis']);m=dict(a.get('evaluation_metadata',a.get('original_metadata',{})))
        for key in ('session_id','scene_sha256','comparison_id','repeat_id'):
            if key not in m:m[key]=row.get(key)
        a['evaluation_metadata']=m
        b_rows.append(flat_trial(dict(row,analysis=a),registry))
    write_json(folder/'summary-v3.json',dict(schema_version=3,calculation_version=VERSION,
        summary_revision='3.2.1+sprint-rc0',trials=b_rows,pairs=[],
        fir_switch_pairs=state['fir_pairs'],model_pair_comparison_not_requested=True,msg_db=None,asg_db=None))
    export_csv(folder/'summary-v3.csv',b_rows)
    with (folder/'summary.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        fields = ['id','role','category','protection','recovery_ok','first_frame','completed_frames',
                  'frames','waveform_coverage_fraction','gain_q12','hp_volume','bypass','bit_sha256',
                  'model_sha256','coefficients_sha256','eq_sha256','gate_status','hearing_basis','response_valid','stop_reasons']
        writer = csv.DictWriter(stream, fieldnames=fields);writer.writeheader()
        for row in state['trials']:
            writer.writerow({k:json.dumps(row[k]) if isinstance(row.get(k),(list,dict)) else row.get(k) for k in fields})
    hashes = {str(p.relative_to(folder)).replace('\\','/'):sha(p) for p in folder.rglob('*')
              if p.is_file() and p.suffix not in ('.npz','.wav','.zip','.bit','.hwh') and p.name!='return-manifest.json'}
    write_json(folder/'return-manifest.json', dict(hashes=hashes, raw_audio_included=False))
    target = folder/'return-results.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(list(hashes)+['return-manifest.json']): archive.write(folder/name, name)
    print('RETURN_PACKAGE', str(target.resolve()), flush=True)


def run_sprint(base=None, ask=input, runner=None, validator=check_package, continuous_runner=None):
    base = Path(base or Path(__file__).resolve().parent).resolve()
    folder = base/'results'/('sprint-'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    (folder/'listener').mkdir()
    state = dict(policy=POLICY, calculation_version=VERSION, plan=PLAN, run_id=folder.name,
                 runtime=dict(python=platform.python_version(),numpy=np.__version__,pynq=None),
                 status='preflight', trials=[], fir_pairs=[], msg_db=None, asg_db=None,
                 checks={k:dict(status='not_tested') for k in
                         ('package','real_voice','fir_comparison','listener','continuous_60s','stop_recovery','independent_reproduction')},
                 full_trial_stability='unknown', raw_audio_upload=False)
    previous_gate = None
    try:
        manifest = validator(base)
        human_only=manifest.get('workflow','full')=='human_only'
        state['workflow']=manifest.get('workflow','full')
        state['package_source'] = manifest['source_commits'];state['package_hashes'] = manifest['hashes']
        state['default_model'] = DEFAULT_MODEL
        state['a_assets'] = A_ASSETS
        state['failure_action'] = dict(action='mute_and_stop',automatic_bypass=False,old_session_fallback=False)
        state['model_registry']={manifest['hashes']['model.json']:dict(file='room_v1/calibrated_20261024.json',
            fixture_id=PLAN['fixture_id'],logical_taps=512,role='baseline',
            coefficients_sha256=manifest['coefficients_sha256'],padded_512_sha256=manifest['coefficients_sha256'])}
        state['checks']['package'] = dict(status='passed', level='local_hash_and_compatibility')
        state['checks']['continuous_60s'] = dict(status='not_tested',
            reason=('not scheduled in human session; r4 evidence reviewed separately' if human_only else
                    'await one 60-second arm with this package model/gain/assets; historical bypass record is separate'),
            scope='register timeline plus tail PCM; engineering only')
        state['eq_contribution'] = dict(status='not_tested', reason='identity EQ baseline; no B candidate supplied')
        print('PACKAGE_OK; DEFAULT_MODEL=calibrated_20261024 (strong); '+
              ('HUMAN_SESSION_ONLY_5_TRIALS' if human_only else 'v2 single-arm 60s')+
              '; fixed gain -14 dB / Q12=817, no escalation')
        if ask('确认现场值守、可立即切断音响电源、不戴耳机、允许本地保存音频；输入 READY：').strip()!='READY':
            raise RuntimeError('operator_cancel')
        if ask('确认麦克风/音响/前放与 strong 标定一致，Codec40；输入 SAME_SCENE，变化则停止交B重标定：').strip()!='SAME_SCENE':
            raise RuntimeError('scene_changed_or_unverified')
        layout = ask('一次填写声源-麦克风距离、麦克风/音响位置、听众/测量位置、固定源文件/音量、测量增益与AGC状态：').strip()
        if not layout: raise RuntimeError('layout_missing')
        observation = ask('真人现场讲话且有人耳评价才输入 HUMAN_LIVE_AND_LISTENING；代理/预填/仪表代判输入 PROXY；其他输入记未核实：').strip()
        state['observation_kind'] = ('human_live_and_listening' if observation=='HUMAN_LIVE_AND_LISTENING'
                                     else 'proxy' if observation=='PROXY' else 'unverified')
        if human_only and state['observation_kind']!='human_live_and_listening':
            raise RuntimeError('human_session_requires_live_speech_and_human_listening; no proxy board run')
        state['scene'] = dict(layout=layout, fixture_id=PLAN['fixture_id'], model_sha256=manifest['hashes']['model.json'])
        scene_hash = hashlib.sha256(json.dumps(state['scene'],sort_keys=True).encode()).hexdigest()
        if runner is None:
            import pynq
            state['runtime']['pynq']=getattr(pynq,'__version__','unknown')
            from replay_trial import replay_trial
            runner = replay_trial
        _, tone = sources(); burst=comparison_source();silence = np.zeros(1,dtype='<i2')

        def trial(role, bypass=False, source=None, seconds=8., direct=False, hear=False, gate=None,
                  comparison_id=None,repeat_id=None):
            index = len(state['trials'])+1;path = folder/('%02d-%s.npz'%(index,role))
            pcm = silence if source is None else source
            error = None; metadata = {}
            state['pending_trial']=dict(id=index,role=role,file=path.name,status='prepared_or_running')
            collect(folder,state)
            def start():
                if role=='path-gate':
                    return ask('%02d path-gate 已配置且静音；请停止手机/外部人声并保持安静，本项只播包内定音；START开始：'%index).strip()=='START'
                return ask('%02d %s 已配置且静音。真实人声项此时就位，START才发声；其他输入停止：'%(index,role)).strip()=='START'
            try:
                metadata = runner(path, PLAN['fixture_id'], base/'model.json', pcm,
                    bypass=bypass, gain_db=PLAN['gain_db'], seconds=seconds, hp_volume=PLAN['hp_volume'],
                    direct_only=direct, speaker_confirmed=True, local_capture_confirmed=True, before_start=start)
            except (Exception, KeyboardInterrupt) as exc:
                error = type(exc).__name__+':'+str(exc)
            status_path = path.with_suffix('.status.json')
            status = json.loads(status_path.read_text(encoding='utf8')) if status_path.exists() else {}
            expected = dict(fixture_id=PLAN['fixture_id'],hp_volume=40,bypass=bypass,
                gain_q12=0 if direct else PLAN['gain_q12'], bit_sha256=manifest['hashes']['audio_replay.bit'],
                model_sha256=manifest['hashes']['model.json'],coefficients_sha256=manifest['coefficients_sha256'])
            fir = role in ('fir-off','fir-on')
            evidence = (dict(input_sha256=sha(path),provenance='frozen RC0 scene background floor; operator SOURCE_OFF',
                             metadata={'noise_floor_dbfs':-37.8}) if fir and path.exists() else None)
            analysis = analyze_npz(path,expected=expected,positive_control_valid=gate is not None,
                external_source_active=source is None,
                external_source_off_verified=fir and state.get('external_source_off_verified') is True,
                metadata_evidence=evidence)
            # Recovery/error status is a separate authoritative sidecar from A.
            reasons = stop_reasons(analysis,status,error)
            m = analysis.get('evaluation_metadata',analysis.get('original_metadata',metadata))
            if not isinstance(m,dict):m={}
            m=dict(m)
            original=analysis.get('original_metadata',{})
            for key in ('first_frame','completed_frames','frames'):
                if key in original:m[key]=original[key]
            row = dict(m,id=index,role=role,analysis=analysis,driver_status=status,category=analysis['category'],
                protection=protection_evidence(m)[0],recovery_ok=status.get('recovery_ok'),
                session_id=state['run_id'],scene_sha256=scene_hash,eq_sha256=sha(base/'eq.json'),
                comparison_id=comparison_id,repeat_id=repeat_id,
                gate_mic_over_ref_db=None if gate is None else gate['mic_over_ref_db'],stop_reasons=reasons,
                tail_valid=analysis.get('tail_statistics',{}).get('tail_valid'),
                tail_first_frame=analysis.get('tail_analysis_window',{}).get('first_frame'),
                tail_end_frame=analysis.get('tail_analysis_window',{}).get('end_frame'),
                waveform_coverage_fraction=analysis.get('capture_window',{}).get('waveform_coverage_fraction'))
            row['local_capture'] = path.name;state['trials'].append(row)
            if fir:
                response=source_response(path,pcm,state.get('external_source_off_verified'))
                row.update(source_response=response,response_valid=response['valid'],
                    measurement_kind='forced_source_response',comparison_first_frame=response['first_frame'],
                    comparison_end_frame=response['end_frame'])
            state.pop('pending_trial',None)
            collect(folder,state)
            if reasons: raise RuntimeError(';'.join(reasons))
            if hear:
                hearing_prompt=('扩声可辨且清晰才选CLEAR；仅听见原声选NO_AMPLIFICATION。' if human_only else '')
                code = ask(hearing_prompt+'此项现场听感：CLEAR / DISTORTED / NO_AMPLIFICATION / HOWL / UNKNOWN：').strip()
                row['hearing_reported_code'] = code
                row['hearing_basis'] = state['observation_kind']
                row['hearing_code'] = code if state['observation_kind']=='human_live_and_listening' else 'PROXY'
                if state['observation_kind']=='human_live_and_listening' and code in ('DISTORTED','NO_AMPLIFICATION','HOWL'):
                    check='real_voice' if role=='real-voice' else 'listener'
                    state['checks'][check]=dict(status='failed',basis=state['observation_kind'],
                        reason='human_hearing_stop',hearing_code=code,scope='reported human outcome, not measured onset threshold')
                if code not in ('CLEAR','UNKNOWN','PROXY'):raise RuntimeError('hearing_stop:'+code)
            return row

        def gate():
            nonlocal previous_gate
            row = trial('path-gate',source=tone,seconds=1.02,direct=True)
            value = gate_metrics(folder/row['local_capture'], -37.8, previous_gate)
            row['path_gate'] = value
            row['gate_status'] = 'passed' if value['passed'] else 'failed'
            state['checks']['path_gate'] = dict(status=row['gate_status'], source_on_frames=value['end_frame']-value['first_frame'],
                scope='source-on tone path check; acoustic stability category is separate')
            row['gate_mic_over_ref_db']=value.get('mic_over_ref_db')
            if not value['passed']: raise RuntimeError('path_gate_failed:'+','.join(value['reasons']))
            if previous_gate is None: previous_gate=value['rms_dbfs']
            return value

        # Real microphone use precedes gain-boundary probing; no new gain ladder.
        g = gate()
        trial('real-voice',gate=g,hear=True)
        voice = state['trials'][-1]['hearing_code']
        state['checks']['real_voice'] = dict(status='passed' if voice=='CLEAR' else 'not_tested',
            basis=state['observation_kind'], hearing_code=voice,
            scope='human live speech and human listening required; proxy cannot pass; saved waveform is a tail only')
        print('听众比较使用同一固定录制人声，经外部声源拾音；源/测量设备位置和音量不变，关闭AGC。')
        print('可选测量录音保存到', str((folder/'listener').resolve()),
              '：off-speech.wav/off-noise.wav/on-speech.wav/on-noise.wav；单声道PCM16，每份至少1秒。')
        trial('listener-off',direct=True,hear=False)
        g = gate();trial('listener-on',gate=g,hear=True)
        confirmation = ask('四份听众录音齐全且同源/同增益/无AGC时输入 FIXED_SOURCE_FIXED_GAIN_NO_AGC；否则回车标未测：').strip()
        state['checks']['listener'] = listener_metrics(folder/'listener',confirmation)
        if human_only:
            state['human_listener_report']=ask('填写固定听众位置开/关差别：可辨扩声、清晰度、底噪、音色、失真；不确定写未知：').strip() or 'unknown'
            state['checks']['fir_comparison']=dict(status='not_tested',reason='not scheduled in human session; r4 evidence reviewed separately')
            state['status']='completed_with_unmeasured_requirements'
            return state
        if ask('FIR对照前停止所有外部声源和讲话，确认后输入 SOURCE_OFF：').strip()!='SOURCE_OFF':
            raise RuntimeError('external_source_off_unverified')
        state['external_source_off_verified']=True
        for repeat in range(PLAN['repeats']):
            modes = [True,False] if repeat%2==0 else [False,True]
            rows = {}
            for bypass in modes:
                g = gate();row = trial('fir-off' if bypass else 'fir-on',bypass,burst,PLAN['pair_seconds'],gate=g,
                    comparison_id=state['run_id']+'-fir-'+str(repeat+1),repeat_id=repeat+1)
                rows[bypass] = row
                if row.get('response_valid') is not True:
                    reason='fir_response_insufficient:'+','.join(row['source_response']['reasons'])
                    row['stop_reasons'].append(reason)
                    raise RuntimeError(reason)
            result = pair_check(rows[True],rows[False]);result['repeat']=repeat+1
            state['fir_pairs'].append(result)
            if not result['window_comparison_valid']:raise RuntimeError('pair_not_valid')
        state['checks']['fir_comparison'] = dict(status='passed',effect_claimed=False,
            scope='two same-config forced-source response pairs completed; no stability/MSG/ASG claim')
        gate()
        from sprint_continuous import continuous_trial
        state['pending_trial']=dict(id=15,role='continuous-60s',status='prepared_or_running')
        collect(folder,state)
        path,result=continuous_trial(base,folder,manifest,PLAN,ask,continuous_runner)
        analysis=result.pop('analysis');status=result.pop('driver_status')
        state['checks']['continuous_60s']=result
        m=analysis['evaluation_metadata']
        state['trials'].append(dict(m,id=15,role='continuous-60s',local_capture=path.name,analysis=analysis,
            driver_status=status,category=analysis['category'],recovery_ok=status.get('recovered'),
            protection=analysis['event_flags']['protection'],stop_reasons=result['reasons'],
            session_id=state['run_id'],scene_sha256=scene_hash,eq_sha256=sha(base/'eq.json'),
            waveform_coverage_fraction=analysis['capture_window']['waveform_coverage_fraction']))
        state.pop('pending_trial',None)
        if result['status']!='passed':raise RuntimeError('continuous_not_passed:'+','.join(result['reasons']))
        state['status']='completed_with_unmeasured_requirements'
    except (Exception, KeyboardInterrupt) as exc:
        state['status']='stopped';state['stop_reason']=type(exc).__name__+':'+str(exc)
        state['mandatory_action']='No more trials in this run. Inspect evidence; power off speaker if mute/recovery is uncertain.'
    finally:
        recoveries = [r.get('recovery_ok') for r in state['trials']]
        state['checks']['stop_recovery'] = dict(status='passed' if recoveries and all(v is True for v in recoveries)
                                              else 'failed' if any(v is False for v in recoveries) else 'not_tested',
            unverified_trials=[r['id'] for r in state['trials'] if r.get('recovery_ok') is None],
            scope='A driver sidecar reports per-trial cleanup; emergency/abnormal recovery still requires A acceptance')
        collect(folder,state)
    return state
