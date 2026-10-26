"""One new-layout decision, using the existing A runners and C measurements.

No board imports until required candidate/site identities have been bound.
Independent arms remain separate; gains are frozen and capped, with no MSG interpolation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile

import numpy as np
from evaluation import analyze_npz, sha, VERSION, CONFIG
from listener_metrics import listener_metrics
from model_comparison import qhash
from residual_tools import load_candidate
from room_experiment import gate_metrics, write_json
from sprint_continuous import driver_request

POLICY = 'c-new-layout-1.2.0'
RATE = 48828.125
FIXTURE = 'room_v1_20261026'
A_COMMIT = '2928a4a9de2e360d9aeedce435b452b860baf189'
BIT = '61bb71aabb824c57191edcea93d1333143cd959c16d43028585913c54a8f61fa'
HWH = '92b499a39d04de891632a89512bfff49f7482a332344128556b1506529d1b75b'
ZERO = qhash(np.zeros(512, dtype=np.int64))
SCENE_COMMIT = '52ee4e4a5d34fff9f0c82ae46d7dd5449ee99d00'
REPAIRED_CAPTURE_MANIFEST = '1a4196c27730e4ceec678fc2d6debc755212790b494716b45d9e887769bfcfaa'
REPAIRED_CAPTURE_SET = '46aad2acf0557698281d67fdac5724daad9e246f1225c4114093d52abd0036da'
OBSOLETE_B_COMMIT = '8a027578be68d79eece4837c4fb3b5ffb65a7a7a'
MIC_PEAK_LIMIT_DBFS = -6.
PLAN = dict(source_seconds=2.50, pair_seconds=2.52, repeats=2,
            speech_seconds=8., continuous_seconds=60., gate_seconds=1.02,
            microphone_check_seconds=.30,microphone_peak_limit_dbfs=MIC_PEAK_LIMIT_DBFS,
            gain_search='bounded_registered_scan_only', automatic_extension=False,
            runtime_scan_gains_db=[-14,-12,-10,-8,-6],eq='identity', capture='independent final rings')
SCENE_FIELDS = ('talker_to_microphone_cm', 'listener_position', 'microphone_preamp_gain',
                'speaker_volume_knob', 'fixed_speech_source', 'recorder_gain', 'agc_disabled')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf8')


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def notebook_code_hash(path):
    notebook=json.loads(Path(path).read_text(encoding='utf8'))
    codes=[''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type']=='code']
    return hashlib.sha256(encoded(codes)).hexdigest()


def template():
    return dict(policy=POLICY, fixture_id=FIXTURE, b_commit=None, model_sha256=None,
        coefficients_sha256=None, hp_volume=40, sample_rate_hz=RATE, lag_first=1,
        forward_schedule_frames=2, deployment_evidence=None, original_timeline_holdout=None,
        diagnostic_alignment=None, input_manifest_sha256=None, gain_db=None,
        b_allowed_gains_db=None, injection_rms_dbfs=None, b_injection_range_dbfs=None,
        gain_and_injection_basis=None, bands=None,
        # Each band needs low_hz/high_hz/minimum_signal_snr_db/basis. No default threshold.
        prediction_and_failure_actions=None, profile='forced_response', scan_gains_db=[],wire_repair_binding=None)


def scene_template():
    return dict(fixture_id=FIXTURE, verified_by_A=False, hp_volume=40, sample_rate_hz=RATE,
        speaker_to_microphone_cm=100, speaker_orientation='side-facing the microphone',
        plate_and_cotton_unchanged=None, a_allowed_gains_db=None,
        a_injection_range_dbfs=None, a_limits_basis=None, control_and_cue_approved_by_A=False,
        **{key: None for key in SCENE_FIELDS})


def prerequisites(candidate, scene, model=None):
    """Return all missing/mismatched inputs together, before any board action."""
    errors = []
    def require(ok, reason):
        if not ok: errors.append(reason)
    runtime=candidate.get('profile')=='runtime_scan'
    optional_B={'injection_rms_dbfs','b_injection_range_dbfs'} if runtime else set()
    for key in set(template())-optional_B:
        require(key in candidate and candidate[key] is not None, 'B:'+key)
    require(candidate.get('profile') in ('forced_response','runtime_scan'), 'B:unknown_profile')
    for key, value in dict(policy=POLICY, fixture_id=FIXTURE, hp_volume=40,
                           sample_rate_hz=RATE, lag_first=1, forward_schedule_frames=2).items():
        require(candidate.get(key)==value, 'B:incompatible:'+key)
    for key in ('b_commit','model_sha256','coefficients_sha256','input_manifest_sha256'):
        value=candidate.get(key)
        require(isinstance(value,str) and len(value)==(40 if key=='b_commit' else 64)
                and all(c in '0123456789abcdef' for c in value), 'B:identity:'+key)
    for key in ('deployment_evidence','original_timeline_holdout','diagnostic_alignment',
                'gain_and_injection_basis','prediction_and_failure_actions'):
        require(bool(candidate.get(key)), 'B:evidence:'+key)
    repair=candidate.get('wire_repair_binding') or {}
    require(candidate.get('b_commit')!=OBSOLETE_B_COMMIT,'B:pre_repair_candidate_not_qualified')
    for key,value in dict(capture_manifest_sha256=REPAIRED_CAPTURE_MANIFEST,
        capture_set_sha256=REPAIRED_CAPTURE_SET,wire_state='repaired',
        model_sha256=candidate.get('model_sha256'),coefficients_sha256=candidate.get('coefficients_sha256'),
        b_commit=candidate.get('b_commit')).items():
        require(repair.get(key)==value and value is not None,'B:wire_repair_binding:'+key)
    require(bool(repair.get('basis_ref')),'B:wire_repair_binding:basis_ref')
    optional_A={'fixed_speech_source','recorder_gain','agc_disabled','a_injection_range_dbfs'} if runtime else set()
    for key in set(scene_template())-optional_A:
        require(key in scene and scene[key] is not None, 'A:'+key)
    required_A=dict(fixture_id=FIXTURE, verified_by_A=True, hp_volume=40,
                          sample_rate_hz=RATE, speaker_to_microphone_cm=100,
                          speaker_orientation='side-facing the microphone',
                          plate_and_cotton_unchanged=True, control_and_cue_approved_by_A=True)
    if not runtime: required_A['agc_disabled']=True
    for key,value in required_A.items():
        require(scene.get(key)==value, 'A:unverified:'+key)
    require(number(scene.get('talker_to_microphone_cm')) and 15<=scene['talker_to_microphone_cm']<=30,
            'A:talker_distance_15_to_30cm_after_repair')
    for key in set(SCENE_FIELDS[1:-1])-optional_A:
        value=scene.get(key)
        require(bool(value) and 'unknown' not in str(value).lower() and '未知' not in str(value), 'A:unknown:'+key)
    if runtime:
        source=scene.get('fixed_speech_source')
        require(isinstance(source,dict) and all(bool(source.get(k)) for k in ('file','playback_level','phone_position'))
                and source.get('route')=='phone_speaker_to_microphone','A:fixed_phone_source_facts')
    gain=candidate.get('gain_db'); level=candidate.get('injection_rms_dbfs')
    require(number(gain) and -60<=gain<=18.06179973983887, 'gain:driver_range')
    for owner, gains in (('B',candidate.get('b_allowed_gains_db')),('A',scene.get('a_allowed_gains_db'))):
        require(isinstance(gains,list) and bool(gains) and all(number(g) for g in gains)
                and number(gain) and gain in gains, owner+':gain_not_supported')
    if not runtime:
        require(number(level) and -90<=level<=-6, 'injection:PCM_headroom')
        for owner,bounds in (('B',candidate.get('b_injection_range_dbfs')),('A',scene.get('a_injection_range_dbfs'))):
            require(isinstance(bounds,list) and len(bounds)==2 and all(number(v) for v in bounds)
                    and number(level) and bounds[0]<=level<=bounds[1], owner+':injection_not_supported')
    else:
        scan=candidate.get('scan_gains_db')
        require(isinstance(scan,list) and bool(scan) and scan==sorted(set(scan)) and scan[0]==-14
                and candidate.get('gain_db') in scan and all(g in PLAN['runtime_scan_gains_db'] for g in scan), 'C:runtime_scan_limits')
        for owner,gains in (('B',candidate.get('b_allowed_gains_db')),('A',scene.get('a_allowed_gains_db'))):
            require(isinstance(gains,list) and isinstance(scan,list) and all(g in gains for g in scan),owner+':scan_gain_not_supported')
    bands=candidate.get('bands')
    require(isinstance(bands,list) and bool(bands), 'B:bands_missing')
    if isinstance(bands,list):
        for i, band in enumerate(bands):
            ok=isinstance(band,dict) and all(number(band.get(k)) for k in
                (('low_hz','high_hz') if runtime else ('low_hz','high_hz','minimum_signal_snr_db')))
            require(ok and 0<band['low_hz']<band['high_hz']<RATE/2 and bool(band.get('basis')),
                    'B:band:'+str(i))
    if model is not None:
        try:
            _,q=load_candidate(model,FIXTURE,40,RATE)
            require(len(q)==512 and bool(np.any(q)), 'B:model_must_be_nonzero_512')
            require(sha(model)==candidate.get('model_sha256'), 'B:model_file_hash')
            require(qhash(q)==candidate.get('coefficients_sha256'), 'B:Q20_hash')
        except (ValueError,KeyError,TypeError,OSError) as exc: errors.append('B:model:'+str(exc))
    else: errors.append('B:model_file_missing')
    return sorted(set(errors))


def check(base):
    base=Path(base)
    manifest=json.loads((base/'layout-manifest.json').read_text(encoding='utf8'))
    if manifest.get('policy')!=POLICY or manifest.get('plan')!=PLAN:
        raise ValueError('package policy/plan mismatch')
    for name,digest in manifest['hashes'].items():
        path=(base/name).resolve()
        if base.resolve() not in path.parents or sha(path)!=digest:
            raise ValueError('package hash mismatch:'+name)
    if manifest['hashes'].get('audio_replay.bit')!=BIT or manifest['hashes'].get('audio_replay.hwh')!=HWH:
        raise ValueError('A bit/hwh mismatch')
    if notebook_code_hash(base/'layout.ipynb')!=manifest.get('notebook_code_sha256'):
        raise ValueError('notebook code mismatch')
    binding=base/'run-binding.json'
    if not binding.exists():
        candidate=json.loads((base/'candidate-input.json').read_text(encoding='utf8'))
        scene=json.loads((base/'scene-input.json').read_text(encoding='utf8'))
        model=base/'candidate-unbound.json'
        return dict(ready=False,missing=prerequisites(candidate,scene,model if model.exists() else None)+
                    ['C:frozen_run_binding_missing'],hardware_access=False)
    data=json.loads(binding.read_text(encoding='utf8'))
    errors=prerequisites(data['candidate'],data['scene'],base/'model.json')
    if data.get('package_hashes')!=manifest['hashes']: errors.append('binding:stale_payload')
    if data.get('binding_sha256')!=hashlib.sha256(encoded({k:v for k,v in data.items() if k!='binding_sha256'})).hexdigest():
        errors.append('binding:hash')
    return dict(ready=not errors,missing=errors,binding=data,hardware_access=False)


def bind(base, model, candidate, scene):
    base=Path(base)
    check(base)
    candidate=json.loads(Path(candidate).read_text(encoding='utf8'))
    scene=json.loads(Path(scene).read_text(encoding='utf8'))
    errors=prerequisites(candidate,scene,model)
    if errors: raise ValueError('BINDING_INCOMPLETE '+json.dumps(errors,ensure_ascii=False))
    if (base/'run-binding.json').exists() or (base/'model.json').exists():
        raise ValueError('bind a fresh extraction; do not overwrite a frozen model')
    manifest=json.loads((base/'layout-manifest.json').read_text(encoding='utf8'))
    tone,burst,cue=sources(candidate.get('injection_rms_dbfs') if candidate.get('profile')!='runtime_scan' else None)
    controls=[]
    for source,seconds in ((tone,1.02),(burst,PLAN['pair_seconds']),(cue,PLAN['speech_seconds'])):
        controls.append(driver_request(base,'replay_trial',base/'compatibility-probe.npz',FIXTURE,model,source,
            gain_db=candidate['gain_db'],seconds=seconds,hp_volume=40,
            speaker_confirmed=True,local_capture_confirmed=True))
    controls.append(driver_request(base,'live_run',base/'compatibility-live.npz',FIXTURE,model,
        gain_db=candidate['gain_db'],seconds=60.,hp_volume=40,
        speaker_confirmed=True,local_capture_confirmed=True))
    shutil.copy2(model,base/'model.json')
    data=dict(candidate=candidate,scene=scene,package_hashes=manifest['hashes'],driver_validation=controls)
    data['binding_sha256']=hashlib.sha256(encoded(data)).hexdigest()
    write_json(base/'run-binding.json',data)
    return check(base)


def sources(level):
    t=np.arange(int(RATE))/RATE
    tone=np.rint(32768*10**(-20/20)*np.sin(2*np.pi*1000*t)).astype('<i2')
    fade=int(.01*RATE)
    if level is None:
        burst=np.zeros(1,dtype='<i2')
    else:
        noise=np.random.default_rng(20261026).normal(size=int(PLAN['source_seconds']*RATE))
        noise[:fade]*=np.linspace(0,1,fade); noise[-fade:]*=np.linspace(1,0,fade)
        noise*=10**(level/20)/np.std(noise)
        if np.max(abs(noise))>.5: raise ValueError('B injection exceeds frozen PCM peak headroom')
        burst=np.rint(noise*32768).astype('<i2')
    # An audible source cue proves playback has started; no pre-arm countdown.
    cue=tone[:int(.15*RATE)].copy()
    cue[:fade]=np.rint(cue[:fade]*np.linspace(0,1,fade))
    cue[-fade:]=np.rint(cue[-fade:]*np.linspace(1,0,fade))
    return tone,burst,cue


def bind_at_field(base, ask):
    """Bind only A's current facts locally; no extra B response or board API."""
    base=Path(base);checked=check(base)
    if checked['ready']: return checked,False
    c=json.loads((base/'candidate-input.json').read_text(encoding='utf8'))
    scene=json.loads((base/'scene-input.json').read_text(encoding='utf8'))
    if c.get('profile')!='runtime_scan': return checked,False
    if any(e.startswith('B:') or e.startswith('C:runtime_scan') for e in checked['missing']):
        return checked,False
    # A single explicit factual confirmation, not silence, authorises this bounded batch.
    print('现场预填',json.dumps(scene,ensure_ascii=False),flush=True)
    prompt=('一次现场核实：麦克风线已修好，一米侧对/金属板隔音棉/Codec40/音响最大/前放出厂未动；默认讲话25cm，听众距音响20cm。'
        '确认单人控板、无耳机、可断音响电源、准许本地存音频，起始外部声源停止且房间安静；'
        '按包内离散档位且不超过-6dB；每项前麦克风峰值必须严格低于-6dBFS。'
        '手机用自身扬声器对麦克风播放，不直接接LINE_IN。'
        '输入 FIELD_READY|讲话距离cm|手机录音文件名|播放音量档位|手机相对麦克风位置；其他输入取消：')
    answer=ask(prompt).strip().split('|')
    if len(answer)!=5 or answer[0]!='FIELD_READY' or any(not v.strip() for v in answer[1:]):
        raise RuntimeError('field_scene_cancelled_or_fixed_source_missing')
    try:distance=float(answer[1])
    except ValueError:raise RuntimeError('invalid_talker_distance')
    scene.update(verified_by_A=True,control_and_cue_approved_by_A=True,
        talker_to_microphone_cm=distance,
        field_confirmation='FIELD_READY',fixed_speech_source=dict(file=answer[2].strip(),playback_level=answer[3].strip(),phone_position=answer[4].strip(),route='phone_speaker_to_microphone'))
    # Validate all remaining identities before writing any active model.
    errors=prerequisites(c,scene,base/'candidate-unbound.json')
    if errors: raise ValueError('BINDING_INCOMPLETE '+json.dumps(errors,ensure_ascii=False))
    scene_path=base/'field-scene.json';write_json(scene_path,scene)
    return bind(base,base/'candidate-unbound.json',base/'candidate-input.json',scene_path),True


def spectrum(path, bands, source_on=False):
    """Common global window; retain raw timeline and actual played reference."""
    with np.load(path,allow_pickle=False) as z:
        m=json.loads(str(z['metadata_json'].item()))
        first,end,frames=(m.get(k) for k in ('first_frame','completed_frames','frames'))
        x=np.asarray(z['microphone'],float);ref=np.asarray(z['reference'],float)
        if (any(type(v) is not int for v in (first,end,frames)) or end-first!=frames or
            x.shape!=(frames,) or ref.shape!=x.shape or not np.isfinite(x).all() or
            not np.isfinite(ref).all() or m.get('dropped_frames',0)):
            raise ValueError('invalid segment timeline')
        begin=max(first+512,int(.2*RATE))
        # Identical window for background and source, without joining independent arms.
        stop=min(end,int(PLAN['source_seconds']*RATE)-int(.01*RATE))
        if source_on and (m.get('source_schedule_verified') is not True or
                          m.get('source_end_frame_exclusive')!=int(PLAN['source_seconds']*RATE)):
            raise ValueError('unverified source time axis')
        x=x[begin-first:stop-first];ref=ref[begin-first:stop-first]
        if len(x)<4096: raise ValueError('insufficient common source-on window')
        w=np.hanning(len(x));f=np.fft.rfftfreq(len(x),1/RATE)
        power=2*abs(np.fft.rfft((x-x.mean())*w))**2/(len(x)*np.sum(w*w))
        values={f"{b['low_hz']}-{b['high_hz']}":float(power[(f>=b['low_hz'])&(f<b['high_hz'])].sum()) for b in bands}
        return dict(first_frame=begin,end_frame=stop,frames=len(x),band_power=values,
            reference_rms_dbfs=20*math.log10(max(float(np.std(ref)),1e-12)),
            microphone_rms_dbfs=20*math.log10(max(float(np.std(x)),1e-12)),
            reference_scope='actual mixed DAC words, not requested injection alone',
            alignment='raw global trial frame; lag_first=1, forward=2 once; no segment shifts')


def snr_bands(active, background, bands):
    out={}
    for band in bands:
        key=f"{band['low_hz']}-{band['high_hz']}"
        total=active['band_power'][key];noise=background['band_power'][key]
        signal=total-noise
        value=10*math.log10(signal/noise) if signal>0 and noise>0 else None
        valid=value is not None and value>=band['minimum_signal_snr_db']
        out[key]=dict(valid=valid,total_power=total,background_power=noise,signal_power=signal,
            signal_snr_db=value,minimum_signal_snr_db=band['minimum_signal_snr_db'],basis=band['basis'],
            reason=None if valid else 'insufficient_band_SNR_or_background',
            assumptions='same mode/gain/band/window; stationary uncorrelated background; not a deterministic bound')
    return out


def positive_background(path):
    """Use exactly the positive tone's global window, excluding its final fade."""
    with np.load(path,allow_pickle=False) as capture:
        m=json.loads(str(capture['metadata_json'].item()))
        first=m['first_frame'];end=m['completed_frames']
        begin=max(first,int(.02*RATE));stop=min(end,int(RATE)-int(.01*RATE))
        x=np.asarray(capture['microphone'],float)[begin-first:stop-first]
        if len(x)<2048 or not np.isfinite(x).all():raise ValueError('positive background window invalid')
        return dict(rms_dbfs=20*math.log10(max(float(np.std(x)),1e-12)),
            first_frame=begin,end_frame=stop,frames=len(x))


def microphone_headroom(path, require_full_capture=False):
    """ADC absolute peak, including DC. Strict threshold; never an anti-howl result."""
    out=dict(passed=False,peak_dbfs=None,limit_dbfs=MIC_PEAK_LIMIT_DBFS,
        first_frame=None,end_frame=None,frames=0,full_capture=False,reason=None,
        scope='observed input samples only; precheck is representative, not a whole-future-run guarantee')
    try:
        with np.load(path,allow_pickle=False) as capture:
            m=json.loads(str(capture['metadata_json'].item()));x=np.asarray(capture['microphone'],float)
            first,end,count=(m.get(k) for k in ('first_frame','completed_frames','frames'))
            if m.get('driver_evidence_version')=='a-continuous-v1':
                end=m.get('frames_completed')
                count=end-first if type(end) is int and type(first) is int else None
            if (any(type(v) is not int or v<0 for v in (first,end,count)) or end-first!=count or
                x.shape!=(count,) or not count or not np.isfinite(x).all() or np.any(x < -1) or np.any(x>=1)
                or m.get('dropped_frames',0)):raise ValueError('invalid_headroom_capture')
            full=first==0 and count==end
            peak=float(np.max(np.abs(x)))
            out.update(first_frame=first,end_frame=end,frames=count,full_capture=full,
                peak_dbfs=20*math.log10(max(peak,1e-12)),peak_amplitude=peak)
            if require_full_capture and not full:raise ValueError('precheck_not_fully_captured')
            out['passed']=bool(peak<10**(MIC_PEAK_LIMIT_DBFS/20))
            if not out['passed']:out['reason']='microphone_peak_at_or_above_minus6; lower source or move talker away before a new batch'
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:out['reason']=str(exc)
    return out


def continuous_with_headroom(path, manifest, plan, error=None, model_path=None):
    from sprint_continuous import review_continuous
    report=review_continuous(path,manifest,plan,error,model_path=model_path)
    report['microphone_headroom']=microphone_headroom(path)
    if not report['microphone_headroom']['passed']:
        report['status']='failed';report['reasons'].append('microphone_headroom_failed_in_saved_tail')
    return report


def paired(rows):
    pairs=[]
    for repeat in (1,2):
        modes={r['mode']:r for r in rows if r['role']=='response' and r['repeat']==repeat}
        if set(modes)!= {'zero','matched'}: continue
        a,b=modes['zero'],modes['matched'];reasons=[]
        for key in ('gain_q12','hp_volume','fixture_id','sample_rate_hz','bit_sha256','model_sha256',
                    'source_pcm16_sha256','scene_sha256','binding_sha256'):
            if a.get(key)!=b.get(key): reasons.append(key)
        if a.get('coefficients_sha256')!=ZERO or b.get('coefficients_sha256')==ZERO: reasons.append('loaded_modes')
        for key in ('first_frame','end_frame','frames'):
            if a.get('spectrum',{}).get(key)!=b.get('spectrum',{}).get(key): reasons.append('window:'+key)
        if not all(r.get('measurement_valid') for r in (a,b)): reasons.append('invalid_capture')
        delta={}
        for key, av in a.get('snr_bands',{}).items():
            bv=b.get('snr_bands',{}).get(key,{})
            ok=not reasons and av['valid'] and bv.get('valid') is True
            delta[key]=dict(valid=ok,matched_minus_zero_response_db=(10*math.log10(bv['signal_power']/av['signal_power']) if ok else None),
                reason=None if ok else 'pair_or_band_invalid')
        pairs.append(dict(repeat=repeat,zero_capture_id=a.get('capture_id'),matched_capture_id=b.get('capture_id'),
            configuration_valid=not reasons,reasons=reasons,bands=delta,
            measured_gain_q12=a.get('gain_q12'),duration_seconds=PLAN['pair_seconds'],
            scope='background-subtracted forced response in saved windows; no MSG/ASG',msg_db=None,asg_db=None))
    return pairs


def result_pairs(state):
    pairs=paired(state['trials'])
    post=state.get('positive_post',{})
    matched_control=post.get('passed') and abs(post.get('drift_db',math.inf))<=1.5
    if not matched_control:
        for pair in pairs:
            pair['configuration_valid']=False;pair['reasons'].append('comparison_control_unverified_or_drift_over_1.5dB')
            for band in pair['bands'].values():
                band.update(valid=False,matched_minus_zero_response_db=None,reason='comparison_control_unverified_or_drift_over_1.5dB')
    return pairs


def runtime_pairs(state):
    groups={}
    for row in state['trials']:
        if row['role']=='runtime-scan':
            groups.setdefault((row['gain_db_requested'],row['repeat']),{})[row['mode']]=row
    pairs=[]
    post=state.get('positive_post',{})
    control_ok=bool(post.get('passed') and abs(post.get('drift_db',math.inf))<=1.5)
    for (gain,repeat),modes in sorted(groups.items()):
        reasons=[]
        if set(modes)!= {'zero','matched'}:reasons.append('incomplete_pair')
        a,b=modes.get('zero',{}),modes.get('matched',{})
        if not control_ok:reasons.append('post_control_unverified_or_drift')
        for key in ('gain_q12','hp_volume','sample_rate_hz','fixture_id','bit_sha256','hwh_sha256',
                    'model_sha256','scene_sha256','binding_sha256','source_pcm16_sha256','completed_frames','first_frame'):
            if not a.get(key) or a.get(key)!=b.get(key):reasons.append('pair:'+key)
        if a.get('coefficients_sha256')!=ZERO or b.get('coefficients_sha256') in (None,ZERO):reasons.append('loaded_modes')
        if not all(r.get('measurement_valid') for r in (a,b)):reasons.append('invalid_or_stopped_arm')
        levels=[r.get('analysis',{}).get('window_rms_dbfs') for r in (a,b)]
        pairs.append(dict(gain_db_requested=gain,gain_q12=a.get('gain_q12'),repeat=repeat,
            configuration_valid=not reasons,reasons=reasons,
            zero_capture_id=a.get('capture_id'),matched_capture_id=b.get('capture_id'),
            categories={mode:r.get('analysis',{}).get('category','unknown') for mode,r in modes.items()},
            counts={mode:r.get('analysis',{}).get('counts') for mode,r in modes.items()},
            event_flags={mode:r.get('analysis',{}).get('event_flags') for mode,r in modes.items()},
            matched_minus_zero_window_mic_rms_db=(levels[1]-levels[0] if not reasons and all(number(v) for v in levels) else None),
            level_difference_scope='saved microphone window only; no stability margin or ASG inference',
            scope='same-condition closed-loop operation; no added injection; growth only in saved window',
            full_trial_stability='unknown',msg_db=None,asg_db=None))
    return pairs


def scan_summary(state):
    result={}
    for mode in ('zero','matched'):
        rows=[r for r in state['trials'] if r['role']=='runtime-scan' and r['mode']==mode]
        result[mode]=dict(points=[dict(gain_db_requested=r['gain_db_requested'],gain_q12=r.get('gain_q12'),
            completed_frames=r.get('completed_frames'),requested_seconds=PLAN['pair_seconds'],
            category=r['analysis']['category'],counts=r['analysis'].get('counts'),
            event_flags=r['analysis'].get('event_flags'),capture_window=r['analysis'].get('capture_window'),
            measurement_valid=r['measurement_valid'],stop_reasons=r['stop_reasons']) for r in rows],
            largest_completed_gain_db=max((r['gain_db_requested'] for r in rows if r['measurement_valid']),default=None),
            upper_limit_reason='registered discrete A/B gain list or earlier stop; never interpolate',
            acoustic_boundary='unknown',msg_db=None,asg_db=None)
    return result


def collect(folder, state):
    """Runs only after the A call has returned/stopped; never delays protection."""
    state['pairs']=result_pairs(state)
    state['runtime_pairs']=runtime_pairs(state)
    state['scan_summary']=scan_summary(state)
    state['inventory']=[]
    for path in sorted(folder.glob('*.npz')):
        item=dict(file=path.name,sha256=sha(path),included=not any(k in path.name for k in ('human','listener')))
        try:
            with np.load(path,allow_pickle=False) as z: item['metadata']=json.loads(str(z['metadata_json'].item()))
        except (OSError,ValueError,KeyError,EOFError,zipfile.BadZipFile) as exc: item['error']=str(exc)
        state['inventory'].append(item)
    write_json(folder/'summary.json',state)
    names=[p.name for p in folder.iterdir() if p.is_file() and p.suffix=='.json' and p.name!='return-manifest.json']
    names += [i['file'] for i in state['inventory'] if i['included']]
    hashes={name:sha(folder/name) for name in sorted(names)}
    write_json(folder/'return-manifest.json',dict(policy=POLICY,hashes=hashes,human_audio_included=False))
    with zipfile.ZipFile(folder/'return-results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in list(hashes)+['return-manifest.json']: z.write(folder/name,name)
    print('RETURN_PACKAGE',str((folder/'return-results.zip').resolve()),flush=True)


def run(base=None, ask=input, runner=None, live_runner=None):
    base=Path(base or Path(__file__).resolve().parent).resolve()
    folder=base/'results'/('layout-'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    (folder/'listener').mkdir()
    state=dict(policy=POLICY,calculation_version=VERSION,detector_config=CONFIG,plan=PLAN,
        run_id=folder.name,status='prepared',trials=[],pairs=[],msg_db=None,asg_db=None,
        grades=dict(execution='not_started',measurement='unknown',algorithm_difference='unknown',
                    listener_effect='not_tested',continuous_operation='not_tested'),
        layout_benefit='not_measured; layout fixed, FIR contribution only',whole_run_acoustics='unknown',
        listener_measurement=dict(status='not_tested',quantitative_disabled=True,
            reason='A=52ee4e4: no fixed readable recorder gain; AGC unknown/not controllable',absolute_spl=None),
        effect_conclusion='not_established; repaired-scene matching model plus valid paired field results required')
    try:
        checked,field_confirmed=bind_at_field(base,ask)
        if not checked['ready']: raise ValueError('BINDING_INCOMPLETE '+json.dumps(checked['missing'],ensure_ascii=False))
        binding=checked['binding'];c=binding['candidate'];scene=binding['scene']
        state['binding']=binding;write_json(folder/'run-binding.json',binding)
        shutil.copy2(base/'model.json',folder/'model.json')
        gain=c['gain_db'];gain_q12=int(math.floor(4096*10**(gain/20)+.5))
        runtime=c.get('profile')=='runtime_scan'
        state['profile']=c.get('profile','forced_response')
        tone,burst,cue=sources(None if runtime else c['injection_rms_dbfs']);silence=np.zeros(1,dtype='<i2')
        if not field_confirmed and ask('一次确认：A现场独占控制、scene事实未变、可断音响电源、无耳机、准许本地存音频；READY继续：').strip()!='READY':
            raise RuntimeError('operator_cancel')
        if runner is None:
            from replay_trial import replay_trial
            runner=replay_trial
        def trial(role,mode='matched',pcm=None,direct=False,repeat=0,seconds=None,positive=False,is_precheck=False):
            if not is_precheck:
                pre=trial('mic-precheck-'+role,'zero',direct=True,seconds=PLAN['microphone_check_seconds'],is_precheck=True)
                state['last_input_precheck']=dict(capture_id=pre.get('capture_id'),target_role=role,headroom=pre['microphone_headroom'])
                if 'human' in role or 'listener' in role:
                    print('输入预检通过；现在停止讲话/暂停手机，等正式提示音结束再开始。',flush=True)
            pcm=silence if pcm is None else pcm
            seconds=PLAN['pair_seconds'] if seconds is None else seconds
            path=folder/('%02d-%s-%s.npz'%(len(state['trials'])+1,role,mode))
            zero=mode=='zero' or direct;error=None
            trial_gain=scan_gain if role=='runtime-scan' else gain
            trial_gain_q12=int(math.floor(4096*10**(trial_gain/20)+.5))
            state['pending_trial']=dict(file=path.name,role=role,mode=mode)
            write_json(folder/'summary.json',state)
            def start():
                if (folder/'STOP').exists(): return False
                if is_precheck:
                    if 'human' in role or 'listener' in role:
                        return ask(role+' 输出为零，只检查麦克风输入。用正式响度说最响部分/播放固定片段；输入MIC_READY并保持到采集结束，其他取消：').strip()=='MIC_READY'
                    return True
                if role in ('quiet','positive','positive-post','background','response','runtime-scan'):
                    print(role+' 已配置且静音；按 READY 授权批次继续。',flush=True)
                    return True
                return ask(role+' 已配置且静音；先停止讲话/暂停手机，START继续，其他取消。真人/外源只在实际听到短提示音结束后开始：').strip()=='START'
            try:
                runner(path,FIXTURE,base/'model.json',pcm,gain_db=trial_gain,seconds=seconds,hp_volume=40,
                    bypass=False,zero_coeff=zero,direct_only=direct,speaker_confirmed=True,
                    local_capture_confirmed=True,before_start=start)
            except (Exception,KeyboardInterrupt) as exc: error=type(exc).__name__+':'+str(exc)
            side=path.with_suffix('.status.json')
            status=json.loads(side.read_text(encoding='utf8')) if side.exists() else {}
            expected=dict(fixture_id=FIXTURE,hp_volume=40,sample_rate_hz=RATE,bypass=False,zero_coeff=zero,
                gain_q12=0 if direct else trial_gain_q12,bit_sha256=BIT,model_sha256=c['model_sha256'],
                coefficients_sha256=ZERO if zero else c['coefficients_sha256'],logical_taps=512,loaded_taps=512)
            human='human' in role or 'listener' in role
            a=analyze_npz(path,expected=expected,positive_control_valid=positive,
                external_source_active=human,external_source_off_verified=not human)
            m=a.get('original_metadata',{})
            reasons=[];flags=a.get('event_flags',{})
            if error: reasons.append(error)
            if a['category']=='invalid': reasons.append('invalid_capture:'+','.join(a['reasons']))
            if flags.get('protection') or any(flags.get(k) for k in ('prediction_saturations','residual_saturations','gain_saturations','mix_saturations')):
                reasons.append('protection_or_numeric_event; acoustic_cause_unknown')
            if flags.get('early_stop') or flags.get('microphone_clipping'): reasons.append('early_stop_or_clipping')
            if m.get('completed_frames')!=int(seconds*RATE):reasons.append('actual_run_duration_incomplete')
            if flags.get('instability_growth'): reasons.append('observed_growth_in_valid_window')
            if status.get('recovery_ok') is not True or status.get('cleanup_errors'): reasons.append('cleanup_unverified')
            if status.get('save_error') or status.get('salvage_errors'): reasons.append('evidence_save_or_salvage_failed')
            if a.get('evaluation_metadata',{}).get('verification',{}).get('bit_exact') is not True: reasons.append('actual_reference_arithmetic_unverified')
            if m.get('source_pcm16_sha256')!=hashlib.sha256(pcm.astype('<i2').tobytes()).hexdigest(): reasons.append('actual_source_mismatch')
            coeff=m.get('coefficient_status',0)
            if type(coeff) is not int or (coeff>>4)&65535!=512 or coeff&14!=10: reasons.append('loader_readback_invalid')
            headroom=microphone_headroom(path,require_full_capture=is_precheck)
            if not headroom['passed']:reasons.append('microphone_headroom_failed:'+str(headroom['reason']))
            row=dict(m,role=role,mode=mode,repeat=repeat,file=path.name,analysis=a,driver_status=status,
                gain_db_requested=trial_gain,microphone_headroom=headroom,is_input_precheck=is_precheck,
                measurement_valid=not reasons,stop_reasons=reasons,scene_sha256=hashlib.sha256(encoded(scene)).hexdigest(),
                binding_sha256=binding['binding_sha256'],hwh_sha256=HWH,
                loaded_identity_basis='A loader count/status plus sent Q20 and captured arithmetic; not coefficient-memory hash readback')
            state['trials'].append(row);state.pop('pending_trial',None)
            collect(folder,state)
            if reasons: raise RuntimeError(';'.join(reasons))
            return row
        # Current-scene positive control uses current background; no old -37.8 floor.
        quiet=trial('quiet',direct=True,seconds=1.02)
        background_control=positive_background(folder/quiet['file'])
        floor=background_control['rms_dbfs']
        gate=trial('positive',direct=True,pcm=tone,seconds=1.02)
        control=gate_metrics(folder/gate['file'],floor)
        state['positive_control']=control
        if not control['passed']: raise RuntimeError('positive_control_failed:'+','.join(control['reasons']))
        difference=control['rms_dbfs']-floor
        state['signal_noise_conditions']=dict(positive_total_dbfs=control['rms_dbfs'],background_dbfs=floor,
            total_to_background_db=difference,
            signal_snr_db=10*math.log10(10**(difference/10)-1) if difference>0 else None,
            background_window=background_control,
            positive_window={key:control[key] for key in ('first_frame','end_frame')},
            scope='same gain=0 direct positive tone/background; no broadband model qualification',
            frequency_estimation='not_tested' if runtime else 'conditional_on_each_band',
            no_extra_injection=runtime,coherence_required_for_B_frequency_estimate=.8,
            reason='No new injection level or pure-SNR cutoff invented; runtime/listening proceed independently' if runtime else None)
        if runtime:
            for i,scan_gain in enumerate(c['scan_gains_db']):
                order=('zero','matched') if i%2==0 else ('matched','zero')
                for mode in order:trial('runtime-scan',mode,repeat=1,positive=True)
            scan_gain=gain
            for mode in ('matched','zero'):trial('runtime-scan',mode,repeat=2,positive=True)
        else:
            # Balanced, repeated matched/zero forced response; local SNR failure never stops the batch.
            for repeat,order in ((1,('zero','matched')),(2,('matched','zero'))):
                for mode in order:
                    background=trial('background',mode,repeat=repeat,positive=True)
                    response=trial('response',mode,pcm=burst,repeat=repeat,positive=True)
                    response['spectrum']=spectrum(folder/response['file'],c['bands'],True)
                    background['spectrum']=spectrum(folder/background['file'],c['bands'])
                    response['snr_bands']=snr_bands(response['spectrum'],background['spectrum'],c['bands'])
        post=trial('positive-post',direct=True,pcm=tone,seconds=1.02)
        after=gate_metrics(folder/post['file'],floor,control['rms_dbfs'])
        state['positive_post']=after
        if not after['passed']: raise RuntimeError('positive_post_failed')
        state['grades']['algorithm_difference']='descriptive_pairs_available'
        if runtime:
            state['human_switch']=dict(scope='same speaker/phrase and gain at corrected talker distance; qualitative only',
                talker_to_microphone_cm=scene['talker_to_microphone_cm'],gain_db=gain,trials=[])
            for mode in ('zero','matched'):
                voice=trial('human-'+mode,mode,pcm=cue,seconds=PLAN['speech_seconds'],positive=True)
                voice['sound_heard']=ask(mode+' 真人讲话实际听到声音？HEARD / NOT_HEARD / UNKNOWN（提示音不计）：').strip()
                state['human_switch']['trials'].append(dict(mode=mode,capture_id=voice.get('capture_id'),sound_heard=voice['sound_heard']))
            comparison=ask('比较零系数/匹配模型真人同句：IMPROVED / SIMILAR / WORSE / DISTORTED / HOWL / UNKNOWN：').strip()
            state['human_switch']['comparison_report']=comparison or 'UNKNOWN'
            if comparison in ('WORSE','DISTORTED','HOWL'):raise RuntimeError('human_comparison_stop:'+comparison)
        else:
            voice=trial('human',pcm=cue,seconds=PLAN['speech_seconds'],positive=True)
            voice['sound_heard']=ask('真人讲话实际听到声音？HEARD / NOT_HEARD / UNKNOWN（提示音不计）：').strip()
        if ask(('听众/已登记的手机固定片段、音量与位置按scene就位；' if runtime else '听众/固定人声源按scene就位；')+
               'LISTENER继续；其他输入将听众记未测：').strip()=='LISTENER':
            print('每项8秒；提示音结束后播放已登记同一手机录音，文件/音量/位置不变。只记录听众定性比较，定量预置未测。',flush=True)
            trial('listener-off',pcm=cue,direct=True,seconds=PLAN['speech_seconds'],positive=True)
            trial('listener-on',pcm=cue,seconds=PLAN['speech_seconds'],positive=True)
            code=ask('相对刚才系统静音：DISTINGUISHABLE / NO_AMPLIFICATION / DISTORTED / UNKNOWN：').strip()
            state['listener_report']=dict(code=code,details=ask('一次填写：固定听众位置的清晰度、底噪、音色、失真；未知写未知：').strip())
            state['grades']['listener_effect']=('supported_by_human_report' if code=='DISTINGUISHABLE' else
                'failed' if code in ('NO_AMPLIFICATION','DISTORTED') else 'unknown')
        # Sustained use is evaluated at this candidate/work point; old engineering tests are not repeated.
        if state['grades']['listener_effect']=='supported_by_human_report':
            trial('mic-precheck-continuous','zero',direct=True,seconds=PLAN['microphone_check_seconds'],is_precheck=True)
            for name in ('audio_replay.bit','audio_replay.hwh'): shutil.copy2(base/name,folder/name)
            if live_runner is None:
                from live_run import live_run
                live_runner=live_run
            path=folder/'continuous.npz';stop=folder/'STOP'
            print('CONTINUOUS_STOP_FILE',str(stop),flush=True)
            try:
                live_runner(path,FIXTURE,base/'model.json',gain_db=gain,seconds=60.,hp_volume=40,
                    bypass=False,zero_coeff=False,speaker_confirmed=True,local_capture_confirmed=True,
                    stop_file=str(stop),before_start=lambda:ask('持续60秒，外源关闭、保持安静；START开始，其它取消：').strip()=='START')
            except (Exception,KeyboardInterrupt) as exc: state['continuous_error']=type(exc).__name__+':'+str(exc)
            manifest=dict(hashes={'model.json':c['model_sha256'],'audio_replay.bit':BIT,'audio_replay.hwh':HWH},
                          coefficients_sha256=c['coefficients_sha256'])
            report=continuous_with_headroom(path,manifest,dict(fixture_id=FIXTURE,gain_q12=gain_q12,hp_volume=40,
                continuous_target_seconds=60.),state.get('continuous_error'),model_path=base/'model.json')
            state['continuous']=report
            state['grades']['continuous_operation']='engineering_completed' if report['status']=='passed' else report['status']
            if report['status']!='passed': raise RuntimeError('continuous_stopped:'+','.join(report['reasons']))
        state['grades']['execution']='completed'
        state['status']='completed'
    except (Exception,KeyboardInterrupt) as exc:
        state['status']='stopped';state['grades']['execution']='stopped'
        state['stop_reason']=type(exc).__name__+':'+str(exc)
    finally:
        state['pairs']=result_pairs(state)
        valid=[b['valid'] for p in state['pairs'] for b in p['bands'].values()]
        rp=runtime_pairs(state)
        operation_valid=any(p['configuration_valid'] for p in rp)
        state['grades']['measurement']='valid_runtime_pairs_available' if operation_valid else 'valid_bands_available' if any(valid) else 'unknown_or_invalid'
        state['grades']['algorithm_difference']='bounded_runtime_comparison_available' if operation_valid else 'valid_window_differences_available' if any(valid) else 'unknown'
        state['running_observations']=[dict(mode=r['mode'],repeat=r['repeat'],role=r['role'],
            gain_q12=r.get('gain_q12'),completed_frames=r.get('completed_frames'),
            category=r['analysis']['category'],event_flags=r['analysis'].get('event_flags'),
            counts=r['analysis'].get('counts'),scope=r['analysis'].get('capture_window'),
            stop_reasons=r['stop_reasons']) for r in state['trials'] if r['role'] in ('background','response','runtime-scan')]
        state['algorithm_effect']='unknown; response deltas, protection, human effect and sustained run reported separately'
        collect(folder,state)
    return state


def review(path, output):
    """C's one return intake, with all omissions carried to B together."""
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('return-manifest.json'))
        for name,digest in manifest['hashes'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest: raise ValueError('return hash:'+name)
        state=json.loads(z.read('summary.json'))
        if state['policy']!=POLICY: raise ValueError('return policy')
        qc=[]
        binding=state.get('binding')
        if binding:
            candidate=binding['candidate']
            output=Path(output)
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='c-layout-intake-',dir=output.parent) as directory:
                temp=Path(directory)
                for item in state['inventory']:
                    if not item['included']: continue
                    name=item['file']
                    if Path(name).name!=name or name not in manifest['hashes']:
                        qc.append('raw_missing_or_unsafe:'+name);continue
                    data=z.read(name)
                    if hashlib.sha256(data).hexdigest()!=item['sha256']:
                        qc.append('inventory_hash:'+name);continue
                    (temp/name).write_bytes(data)
                for name in manifest['hashes']:
                    if name.endswith('.status.json') or name=='model.json':
                        if Path(name).name!=name:raise ValueError('unsafe return metadata path')
                        (temp/name).write_bytes(z.read(name))
                for row in state['trials']:
                    raw=temp/row['file']
                    if not raw.exists() and ('human' in row['file'] or 'listener' in row['file']):continue
                    if not raw.exists():
                        qc.append('raw_missing:'+row['file']);row['measurement_valid']=False;continue
                    expected={key:row.get(key) for key in ('fixture_id','hp_volume','sample_rate_hz',
                        'bit_sha256','model_sha256','gain_q12','zero_coeff','coefficients_sha256')}
                    analysis=analyze_npz(raw,expected=expected,positive_control_valid=True,external_source_off_verified=True)
                    headroom=microphone_headroom(raw,require_full_capture=row.get('is_input_precheck',False))
                    if headroom['passed']!=row.get('microphone_headroom',{}).get('passed'):
                        qc.append('input_headroom_summary_mismatch:'+row['file'])
                    row['microphone_headroom']=headroom
                    if not headroom['passed']:
                        row['measurement_valid']=False
                    if row['measurement_valid'] and (analysis['category']=='invalid' or
                        analysis.get('evaluation_metadata',{}).get('verification',{}).get('bit_exact') is not True):
                        qc.append('raw_revalidation:'+row['file']);row['measurement_valid']=False
                    if row['role']=='runtime-scan':row['analysis']=analysis
                    if row['measurement_valid'] and row['role'] in ('background','response'):
                        row['spectrum']=spectrum(raw,candidate['bands'],row['role']=='response')
                for row in state['trials']:
                    if row['role']!='response' or not row['measurement_valid']: continue
                    background=next((r for r in state['trials'] if r['role']=='background' and
                        r['mode']==row['mode'] and r['repeat']==row['repeat'] and r['measurement_valid']),None)
                    if background is None:
                        qc.append('background_missing:'+row['file']);row['measurement_valid']=False
                    else:row['snr_bands']=snr_bands(row['spectrum'],background['spectrum'],candidate['bands'])
                quiet=next((r for r in state['trials'] if r['role']=='quiet' and r['measurement_valid']),None)
                positive=next((r for r in state['trials'] if r['role']=='positive' and r['measurement_valid']),None)
                post=next((r for r in state['trials'] if r['role']=='positive-post' and r['measurement_valid']),None)
                if quiet and positive and post:
                    floor=positive_background(temp/quiet['file'])['rms_dbfs']
                    state['positive_control']=gate_metrics(temp/positive['file'],floor)
                    state['positive_post']=gate_metrics(temp/post['file'],floor,state['positive_control']['rms_dbfs'])
                if state.get('continuous'):
                    if sha(temp/'model.json')!=candidate['model_sha256']:raise ValueError('return model identity')
                    model_manifest=dict(hashes={'model.json':candidate['model_sha256'],'audio_replay.bit':BIT,
                        'audio_replay.hwh':HWH},coefficients_sha256=candidate['coefficients_sha256'])
                    plan=dict(fixture_id=FIXTURE,gain_q12=int(math.floor(4096*10**(candidate['gain_db']/20)+.5)),
                        hp_volume=40,continuous_target_seconds=60.)
                    state['continuous']=continuous_with_headroom(temp/'continuous.npz',model_manifest,plan,
                        state.get('continuous_error'),model_path=temp/'model.json')
        pairs=result_pairs(state)
        # Round only for cross-machine comparison, never for stored numerical results.
        def rounded(value):
            if isinstance(value,float):return round(value,8)
            if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
            if isinstance(value,list):return [rounded(v) for v in value]
            return value
        if rounded(pairs)!=rounded(state['pairs']):qc.append('paired_summary_differs_on_raw_recalculation')
        run_pairs=runtime_pairs(state)
        if rounded(run_pairs)!=rounded(state.get('runtime_pairs',[])):qc.append('runtime_pairs_differ_on_raw_recalculation')
        missing=[dict(file=r['file'],reasons=r['stop_reasons']) for r in state['trials'] if r['stop_reasons']]
        report=dict(policy=POLICY,return_sha256=sha(path),grades=state['grades'],pairs=pairs,
            raw_quality_control=dict(status='completed' if not qc else 'discrepancies',issues=qc),
            runtime_pairs=run_pairs,scan_summary=scan_summary(state),
            signal_noise_conditions=state.get('signal_noise_conditions'),
            uncertainties=missing,stop_reason=state.get('stop_reason'),binding=state.get('binding'),
            running_observations=state.get('running_observations'),
            raw_nonhuman_files=[i for i in state['inventory'] if i['included']],
            listener=state.get('listener_report'),listener_measurement=state.get('listener_measurement'),
            human_switch=state.get('human_switch'),
            continuous=state.get('continuous'),whole_run_acoustics='unknown',msg_db=None,asg_db=None)
        write_json(output,report)
        return report


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('check','bind','run','review'))
    p.add_argument('--base',type=Path,default=Path(__file__).resolve().parent)
    for key in ('model','candidate','scene','return-zip','output'): p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    if a.action=='bind':
        if not all((a.model,a.candidate,a.scene)): p.error('bind needs --model --candidate --scene')
        result=bind(a.base,a.model,a.candidate,a.scene)
    elif a.action=='run': result=run(a.base)
    elif a.action=='review':
        if not a.return_zip or not a.output: p.error('review needs --return-zip --output')
        result=review(a.return_zip,a.output)
    else: result=check(a.base)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0 if result.get('ready',result.get('status')=='completed' or a.action=='review') else 2


if __name__=='__main__': raise SystemExit(main())
