"""One new-layout decision, using the existing A runners and C measurements.

Historical evidence workflow only. The resident consumer entry is recal_entry.sh.

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

POLICY = 'c-new-layout-1.5.0'
RATE = 48828.125
FIXTURE = 'room_v1_20261026b'
A_COMMIT = '2928a4a9de2e360d9aeedce435b452b860baf189'
BIT = '61bb71aabb824c57191edcea93d1333143cd959c16d43028585913c54a8f61fa'
HWH = '92b499a39d04de891632a89512bfff49f7482a332344128556b1506529d1b75b'
ZERO = qhash(np.zeros(512, dtype=np.int64))
SCENE_COMMIT = '52ee4e4a5d34fff9f0c82ae46d7dd5449ee99d00'
REPAIRED_CAPTURE_MANIFEST = '1a4196c27730e4ceec678fc2d6debc755212790b494716b45d9e887769bfcfaa'
REPAIRED_CAPTURE_SET = '46aad2acf0557698281d67fdac5724daad9e246f1225c4114093d52abd0036da'
OBSOLETE_B_COMMIT = '8a027578be68d79eece4837c4fb3b5ffb65a7a7a'
MIC_PEAK_LIMIT_DBFS = -6.
PLAN = dict(baseline_seconds=9.5,baseline_gain_db=-8.,baseline_initial_distance_cm=5.,
            baseline_distance_variant_range_cm=[15.,30.],candidate_pair_repeats=2,
            source_seconds=2.50, pair_seconds=2.52, repeats=2,
            speech_seconds=8., continuous_seconds=60., gate_seconds=1.02,
            gate_hz=1000., positive_control='relative-tone-projection-v1',
            positive_minimum_contrast_db=10., positive_noise_offset_bins=list(range(8,16)),
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
    human_pair=candidate.get('profile')=='human_pair'
    runtime=candidate.get('profile') in ('runtime_scan','human_pair')
    optional_B={'injection_rms_dbfs','b_injection_range_dbfs'} if runtime else set()
    for key in set(template())-optional_B:
        require(key in candidate and candidate[key] is not None, 'B:'+key)
    require(candidate.get('profile') in ('forced_response','runtime_scan','human_pair'), 'B:unknown_profile')
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
    require(number(scene.get('talker_to_microphone_cm')) and (5 if human_pair else 15)<=scene['talker_to_microphone_cm']<=30,
            'A:qualified_talker_distance' if human_pair else 'A:talker_distance_15_to_30cm_after_repair')
    for key in set(SCENE_FIELDS[1:-1])-optional_A:
        value=scene.get(key)
        require(bool(value) and 'unknown' not in str(value).lower() and '未知' not in str(value), 'A:unknown:'+key)
    if human_pair:
        require(scene.get('source_kind')=='human_live' and bool(scene.get('talker_id')) and bool(scene.get('phrase')), 'A:human_source_facts')
    elif runtime:
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
    elif not human_pair:
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
    if manifest.get('workflow')=='success_first':return _check_reproduction(base,manifest)
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
        '手机用自身扬声器对麦克风播放，不直接接LINE_IN；每次从文件0秒重放同一8秒片段。'
        '输入 FIELD_READY|讲话距离cm|手机录音文件名|播放音量档位|手机相对麦克风位置；其他输入取消：')
    answer=ask(prompt).strip().split('|')
    if len(answer)!=5 or answer[0]!='FIELD_READY' or any(not v.strip() for v in answer[1:]):
        raise RuntimeError('field_scene_cancelled_or_fixed_source_missing')
    try:distance=float(answer[1])
    except ValueError:raise RuntimeError('invalid_talker_distance')
    scene.update(verified_by_A=True,control_and_cue_approved_by_A=True,
        talker_to_microphone_cm=distance,
        field_confirmation='FIELD_READY',fixed_speech_source=dict(file=answer[2].strip(),playback_level=answer[3].strip(),phone_position=answer[4].strip(),route='phone_speaker_to_microphone',start_seconds=0.,segment_seconds=PLAN['speech_seconds']))
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


def relative_positive_control(path, background_path, baseline=None):
    """Detect the registered tone against equal-window spectral background.

    This is a path-presence test, not a model or full-band SNR test. The floor
    is conservative across the quiet target, quiet neighbours and concurrent
    neighbours. Broadband RMS and tonal dominance are descriptive only.
    """
    out=dict(passed=False,method=PLAN['positive_control'],reasons=[],
        capture_sha256=sha(path),background_sha256=sha(background_path),
        minimum_contrast_db=PLAN['positive_minimum_contrast_db'],drift_db=None,
        scope='1 kHz path presence only; no broadband model, MSG or ASG qualification')
    try:
        arrays=[]
        for file in (path,background_path):
            with np.load(file,allow_pickle=False) as z:
                m=json.loads(str(z['metadata_json'].item()))
                x=np.asarray(z['microphone'],float);y=np.asarray(z['reference'],float)
                first,end,count=(m.get(k) for k in ('first_frame','completed_frames','frames'))
                if (any(type(v) is not int or v<0 for v in (first,end,count)) or end-first!=count or
                    x.shape!=(count,) or y.shape!=x.shape or not np.isfinite(x).all() or
                    not np.isfinite(y).all() or m.get('dropped_frames',0)):
                    raise ValueError('invalid_positive_time_axis')
                arrays.append((m,x,y))
        (m,x,y),(q,bg,bgref)=arrays
        if m.get('source_schedule_verified') is not True or m.get('source_end_frame_exclusive')!=int(RATE):
            raise ValueError('positive_source_schedule_unverified')
        begin=max(m['first_frame'],q['first_frame'],int(.02*RATE))
        end=min(m['completed_frames'],q['completed_frames'],int(RATE)-int(.01*RATE))
        if end-begin<2048:raise ValueError('positive_common_window_too_short')
        x=x[begin-m['first_frame']:end-m['first_frame']]
        y=y[begin-m['first_frame']:end-m['first_frame']]
        bg=bg[begin-q['first_frame']:end-q['first_frame']]
        bgref=bgref[begin-q['first_frame']:end-q['first_frame']]
        if np.any(bgref):raise ValueError('quiet_reference_not_zero')
        t=np.arange(begin,end)/RATE
        def power(v,hz):
            basis=np.column_stack((np.sin(2*np.pi*hz*t),np.cos(2*np.pi*hz*t),np.ones(len(t))))
            fit=basis[:,:2]@np.linalg.lstsq(basis,v,rcond=None)[0][:2]
            return float(np.mean(fit*fit))
        db=lambda p:10*math.log10(max(p,1e-24))
        hz=PLAN['gate_hz'];step=RATE/len(x)
        offsets=[sign*k for sign in (-1,1) for k in PLAN['positive_noise_offset_bins']]
        neighbour_hz=[hz+k*step for k in offsets]
        total=power(x,hz);quiet_target=power(bg,hz);reference=power(y,hz)
        ref_fraction=reference/max(float(np.var(y)),1e-24)
        if reference<=1e-20 or ref_fraction<.99:raise ValueError('actual_reference_tone_missing')
        quiet_local=float(np.mean([power(bg,f) for f in neighbour_hz]))
        concurrent_local=float(np.mean([power(x,f) for f in neighbour_hz]))
        floor=max(quiet_target,quiet_local,concurrent_local,1e-24)
        contrast=db(total)-db(floor)
        transfer=db(total)-db(reference)
        drift=None if baseline is None else transfer-baseline['mic_over_ref_db']
        out.update(first_frame=begin,end_frame=end,frames=len(x),nominal_bin_width_hz=step,
            neighbour_hz=neighbour_hz,rms_dbfs=db(float(np.var(x))),
            background_rms_dbfs=db(float(np.var(bg))),tonal_fraction=total/max(float(np.var(x)),1e-24),
            reference_rms_dbfs=db(float(np.var(y))),reference_tonal_fraction=ref_fraction,
            tone_rms_dbfs=db(total),reference_tone_rms_dbfs=db(reference),mic_over_ref_db=transfer,
            tone_power=total,quiet_tone_power=quiet_target,quiet_neighbour_mean_power=quiet_local,
            concurrent_neighbour_mean_power=concurrent_local,noise_power_used=floor,
            detection_contrast_db=contrast,drift_db=drift,operational_drift_limit_db=5.,
            contrast_definition='tone projection / max(quiet target, quiet neighbour mean, concurrent neighbour mean); equal duration and projection normalization',
            signal_snr_estimate_db=db((total-floor)/floor) if total>floor else None,
            snr_assumptions='conditional estimate only: locally representative, stationary uncorrelated noise; contrast is not itself pure-signal SNR')
        if contrast<PLAN['positive_minimum_contrast_db']:out['reasons'].append('positive_tone_below_relative_floor')
        if drift is not None and abs(drift)>5.:out['reasons'].append('positive_transfer_drift_exceeds_5_db')
        out['passed']=not out['reasons']
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:out['reasons'].append(str(exc))
    return out


def microphone_headroom(path, require_full_capture=False, require_input_response=False):
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
                peak_dbfs=20*math.log10(max(peak,1e-12)),peak_amplitude=peak,
                rms_dbfs=20*math.log10(max(float(np.std(x)),1e-12)))
            if require_full_capture and not full:raise ValueError('precheck_not_fully_captured')
            out['input_varies']=bool(np.ptp(x)>0)
            out['passed']=bool(peak<10**(MIC_PEAK_LIMIT_DBFS/20))
            if not out['passed']:out['reason']='microphone_peak_at_or_above_minus6; lower source or move talker away before a new batch'
            if require_input_response and not out['input_varies']:
                out['passed']=False;out['reason']='input_no_variation_during_requested_speech'
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
    if state.get('workflow')=='success_first':
        state['baseline_result'],state['candidate_result']=reproduction_results(state)
    state['pairs']=result_pairs(state)
    state['runtime_pairs']=runtime_pairs(state)
    state['scan_summary']=scan_summary(state)
    state['inventory']=[]
    for path in sorted(folder.glob('*.npz')):
        item=dict(file=path.name,sha256=sha(path),included=not any(k in path.name for k in ('human','listener')))
        if state.get('workflow')=='success_first':item['board_path']=str(path.resolve())
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


class TrialStopped(RuntimeError):
    def __init__(self,row):
        self.row=row
        super().__init__(';'.join(row['stop_reasons']))


def _make_trial(base,folder,state,context,ask,runner):
    silence=np.zeros(1,dtype='<i2')
    def trial(role,mode='matched',pcm=None,direct=False,repeat=0,seconds=None,positive=False,is_precheck=False,gain_db=None):
        c=context['candidate'];scene=context['scene'];model_path=Path(context['model_path'])
        binding_sha=context['binding_sha256']
        if not is_precheck:
            pre=trial('mic-precheck-'+role,'zero',direct=True,seconds=PLAN['microphone_check_seconds'],is_precheck=True)
            state['last_input_precheck']=dict(capture_id=pre.get('capture_id'),target_role=role,headroom=pre['microphone_headroom'])
            if 'human' in role or 'listener' in role:
                print('输入预检通过；现在停止讲话/暂停手机，等正式提示音结束再开始。',flush=True)
        pcm=silence if pcm is None else pcm
        seconds=PLAN['pair_seconds'] if seconds is None else seconds
        path=folder/('%02d-%s-%s.npz'%(len(state['trials'])+1,role,mode))
        zero=mode=='zero' or direct;error=None
        trial_gain=c['gain_db'] if gain_db is None else gain_db
        trial_gain_q12=int(math.floor(4096*10**(trial_gain/20)+.5))
        state['pending_trial']=dict(file=path.name,role=role,mode=mode)
        write_json(folder/'summary.json',state)
        def start():
            if (folder/'STOP').exists(): return False
            if is_precheck:
                if 'human' in role or 'listener' in role:
                    action=('实际真人用正式响度说最响部分，不播放手机；' if context.get('live_human') else '用正式响度说最响部分/播放固定片段；')
                    return ask(role+' 输出为零，只检查麦克风输入。'+action+'输入MIC_READY并保持到采集结束，其他取消：').strip()=='MIC_READY'
                return True
            if role in ('quiet','positive','positive-post','background','response','runtime-scan'):
                print(role+' 已配置且静音；执行已登记的机器步骤，外源须保持停止。',flush=True)
                return True
            return ask(role+' 已配置且静音；先停止讲话/暂停手机，START继续，其他取消。真人/外源只在实际听到短提示音结束后开始：').strip()=='START'
        try:
            runner(path,FIXTURE,model_path,pcm,gain_db=trial_gain,seconds=seconds,hp_volume=40,
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
        if m.get('source_schedule_verified') is not True or m.get('source_end_frame_exclusive')!=len(pcm) or m.get('source_frames')!=len(pcm):
            reasons.append('actual_digital_source_schedule_mismatch')
        coeff=m.get('coefficient_status',0)
        if type(coeff) is not int or (coeff>>4)&65535!=512 or coeff&14!=10: reasons.append('loader_readback_invalid')
        headroom=microphone_headroom(path,require_full_capture=is_precheck,require_input_response=is_precheck and human and context.get('live_human',False))
        if not headroom['passed']:reasons.append('microphone_headroom_failed:'+str(headroom['reason']))
        row=dict(m,role=role,mode=mode,repeat=repeat,file=path.name,analysis=a,driver_status=status,
            gain_db_requested=trial_gain,microphone_headroom=headroom,is_input_precheck=is_precheck,
            measurement_valid=not reasons,stop_reasons=reasons,scene_sha256=hashlib.sha256(encoded(scene)).hexdigest(),
            binding_sha256=binding_sha,hwh_sha256=HWH,
            condition_id=context.get('condition_id'),actual_talker_distance_cm=scene.get('talker_to_microphone_cm'),
            requested_seconds=seconds,scene_snapshot=dict(scene),prompt_sequence=len(state.get('prompt_log',[])),
            loaded_identity_basis='A loader count/status plus sent Q20 and captured arithmetic; not coefficient-memory hash readback')
        state['trials'].append(row);state.pop('pending_trial',None)
        collect(folder,state)
        if reasons: raise TrialStopped(row)
        return row
    return trial


def _check_reproduction(base,manifest):
    if manifest.get('policy')!=POLICY or manifest.get('plan')!=PLAN:raise ValueError('package policy/plan mismatch')
    candidate_issues=[];optional=set(manifest['candidate_optional_files'])
    for name,digest in manifest['hashes'].items():
        path=(base/name).resolve()
        if base.resolve() not in path.parents:raise ValueError('unsafe package path')
        ok=path.exists() and sha(path)==digest
        if not ok:
            if name in optional:candidate_issues.append('candidate_payload:'+name)
            else:raise ValueError('package hash mismatch:'+name)
    if sha(base/'audio_replay.bit')!=BIT or sha(base/'audio_replay.hwh')!=HWH:raise ValueError('A bit/hwh mismatch')
    if notebook_code_hash(base/'layout.ipynb')!=manifest['notebook_code_sha256']:raise ValueError('notebook code mismatch')
    model,q=load_candidate(base/'baseline-model.json',FIXTURE,40,RATE)
    if len(q)!=512 or sha(base/'baseline-model.json')!=manifest['baseline_transport_sha256']:raise ValueError('baseline transport identity')
    return dict(ready=False,ready_for_field=True,missing=['A:actual_human_configuration'],candidate_issues=candidate_issues,hardware_access=False)


def _human_scene_errors(scene):
    errors=[]
    for key,value in dict(fixture_id=FIXTURE,hp_volume=40,sample_rate_hz=RATE,speaker_to_microphone_cm=100,
        speaker_orientation='side-facing the microphone',plate_and_cotton_unchanged=True,
        verified_by_A=True,control_and_cue_approved_by_A=True,source_kind='human_live').items():
        if scene.get(key)!=value:errors.append('A:'+key)
    for key in ('talker_id','phrase','listener_position','microphone_preamp_gain','speaker_volume_knob'):
        if not scene.get(key):errors.append('A:'+key)
    if -8 not in scene.get('a_allowed_gains_db',[]):errors.append('A:baseline_gain')
    if not number(scene.get('talker_to_microphone_cm')) or not 5<=scene['talker_to_microphone_cm']<=30:errors.append('A:distance')
    return errors


def reproduction_results(state):
    repeats=state.get('baseline_repeats',[])
    positive=lambda r:r.get('measurement_valid') and r.get('sound_heard')=='HEARD' and r.get('verdict')=='AMPLIFIED_CLEAR'
    qualified=state.get('input_response_confirmed') and state.get('path_pre',{}).get('confirmed')
    usable=qualified and len(repeats)==2 and all(positive(r) for r in repeats)
    original_refused=bool(state.get('original_input_refused'))
    if usable:
        reproduction=('changed_distance_usable' if original_refused else 'recorded_settings_reproduced' if
            state.get('historical_similarity')=='SAME' else 'current_conditions_usable_history_comparison_unknown')
    else:reproduction='original_input_refused' if original_refused and not repeats else 'not_reproduced' if len(repeats)==2 else 'incomplete'
    baseline=dict(usable='supported' if usable else 'not_supported' if qualified and len(repeats)==2 else 'unknown',
        reproduction=reproduction,original_input_refused=original_refused,repeats=repeats,
        historical_similarity=state.get('historical_similarity','UNKNOWN'),
        continuous=state.get('human_continuous'),historical_feedback_retained=True,
        scope='current zero-FIR -8dB human use; reports, counters and saved windows, not calibrated SPL or whole-run acoustic proof',
        history_unknowns=['Historical microphone/contact state is not inferred from later faults', 'Exact historical source level may remain unknown'])
    comparisons=state.get('candidate_comparisons',[]);codes=[r.get('verdict') for r in comparisons]
    comparable=bool(usable and len(comparisons)==2 and all(r.get('pair_valid') and r.get('voice_comparable')=='COMPARABLE' for r in comparisons))
    post=state.get('path_post',{});pre=state.get('path_pre',{})
    if not post.get('confirmed'):comparable=False
    drift=None
    if pre.get('relative',{}).get('passed') and post.get('relative',{}).get('passed'):
        drift=post['relative']['mic_over_ref_db']-pre['relative']['mic_over_ref_db']
        if abs(drift)>1.5:comparable=False
    outcome=('qualitative_improvement_reported' if comparable and all(c=='IMPROVED' for c in codes) else
        'no_improvement_reported' if comparable and all(c in ('SIMILAR','WORSE') for c in codes) else
        'mixed_or_unknown' if comparisons else 'not_tested')
    attempted=[r for r in state.get('trials',[]) if r['role']=='human-candidate']
    if any(not r['measurement_valid'] for r in attempted):outcome='execution_failed_effect_unknown'
    elif attempted and len(comparisons)<2:outcome='incomplete_effect_unknown'
    candidate=dict(improvement=outcome,comparisons=comparisons,conditions_comparable=comparable,
        unavailable_reasons=state.get('candidate_unavailable',[]),tone_transfer_drift_db=drift,
        tone_transfer_repeatability='observed' if drift is not None else 'unknown',msg_db=None,asg_db=None,
        scope='same-gain zero/candidate human comparisons; voice is uncalibrated, no precise dB benefit')
    return baseline,candidate


def _run_reproduction(base,ask,runner,live_runner):
    folder=base/'results'/('reproduction-'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    print('STOP_FILE',str((folder/'STOP').resolve()),'；短项开始前检查，60秒由驱动轮询；异常优先断音响电源或中断内核。',flush=True)
    state=dict(policy=POLICY,workflow='success_first',calculation_version=VERSION,detector_config=CONFIG,plan=PLAN,
        run_id=folder.name,board_result_dir=str(folder.resolve()),status='prepared',trials=[],pairs=[],conditions=[],prompt_log=[],msg_db=None,asg_db=None,
        grades=dict(execution='not_started',measurement='unknown',algorithm_difference='unknown',listener_effect='not_tested',continuous_operation='not_tested'),
        execution_origin='injected_runner_not_field_evidence' if runner is not None else 'A_operator_board',
        listener_measurement=dict(status='not_tested',reason='No fixed recorder gain; AGC unknown; qualitative reports separate'),
        baseline_repeats=[],candidate_comparisons=[],historical_listener_feedback=[])
    def human(prompt):
        answer=ask(prompt).strip()
        state['prompt_log'].append(dict(sequence=len(state['prompt_log'])+1,prompt=prompt,answer=answer,
            requirement='actual human action/report; never an automatically supplied field fact'))
        write_json(folder/'summary.json',state)
        return answer
    try:
        manifest=json.loads((base/'layout-manifest.json').read_text(encoding='utf8'));checked=check(base)
        history=json.loads((base/'a-historical-usable-point.json').read_text(encoding='utf8'))
        state['historical_listener_feedback']=history['confirmations']
        scene=json.loads((base/'scene-input.json').read_text(encoding='utf8'))
        answer=human('历史零系数工作点复现：确认当前可靠接线、不恢复不良接触；1米侧对/板棉/Codec40/前放及旋钮不变、听众20cm、单人值守无耳机可断电。手机暂停，只用真人；先在输出静音下检查历史约5cm。标记同一讲话人和同一句话；历史相似性不明写UNKNOWN。输入 REPRO_READY|讲话人标识|固定句子|SAME或UNKNOWN；其他取消：').split('|')
        if len(answer)!=4 or answer[0]!='REPRO_READY' or not all(answer[1:3]) or answer[3] not in ('SAME','UNKNOWN'):raise RuntimeError('reproduction_configuration_cancelled')
        scene.update(talker_to_microphone_cm=5.,talker_id=answer[1],phrase=answer[2],source_kind='human_live',
            verified_by_A=True,control_and_cue_approved_by_A=True,historical_similarity=answer[3],
            fixed_speech_source=dict(kind='human_live',talker_id=answer[1],phrase=answer[2]))
        errors=_human_scene_errors(scene)
        if errors:raise ValueError('BASELINE_CONFIGURATION '+json.dumps(errors))
        state['historical_similarity']=answer[3]
        c=dict(gain_db=-8.,model_sha256=sha(base/'baseline-model.json'))
        _,q=load_candidate(base/'baseline-model.json',FIXTURE,40,RATE);c['coefficients_sha256']=qhash(q)
        binding=dict(workflow='success_first',baseline=dict(c,actual_coefficients_sha256=ZERO,zero_coeff=True,
            transport_file_role='parser/loader transport only; no fitted coefficients used'),scene=dict(scene),package_hashes=manifest['hashes'])
        binding['binding_sha256']=hashlib.sha256(encoded(binding)).hexdigest()
        state['binding']=binding;write_json(folder/'run-binding.json',binding)
        shutil.copy2(base/'baseline-model.json',folder/'model.json')
        context=dict(candidate=c,scene=scene,model_path=base/'baseline-model.json',binding_sha256=binding['binding_sha256'],
            live_human=True,condition_id='recorded-distance-5cm')
        state['conditions'].append(dict(condition_id=context['condition_id'],scene=dict(scene)))
        if runner is None:
            from replay_trial import replay_trial
            runner=replay_trial
        trial=_make_trial(base,folder,state,context,human,runner)
        silence=np.zeros(1,dtype='<i2');tone,_,cue=sources(None)
        quiet_input=trial('input-quiet','zero',direct=True,seconds=.30,is_precheck=True)
        try:voice_input=trial('human-input-original','zero',direct=True,seconds=.30,is_precheck=True)
        except TrialStopped as exc:
            row=exc.row
            clipping_only_invalid=(row['analysis']['event_flags'].get('microphone_clipping') is True and
                set(row['analysis']['reasons'])<= {'source_end_unverified','microphone_full_scale_in_capture'})
            allowed=all(r.startswith('microphone_headroom_failed:microphone_peak_at_or_above_minus6') or
                r=='early_stop_or_clipping' or (r.startswith('invalid_capture:') and clipping_only_invalid)
                for r in row['stop_reasons'])
            if not (allowed and row['microphone_headroom'].get('input_varies') and not row['analysis']['event_flags'].get('early_stop')):raise
            state['original_input_refused']=dict(file=row['file'],reason=row['stop_reasons'],scene=dict(scene))
            response=human('历史5cm输入不合格，输出已停止并留证；不闭环硬试。只允许改变讲话距离一次，其他设置/声量不变。输入 DISTANCE|15至30内实际cm；其他结束并保留原条件拒绝：').split('|')
            if len(response)!=2 or response[0]!='DISTANCE':raise RuntimeError('original_input_refused_no_distance_variant')
            distance=float(response[1])
            if not 15<=distance<=30:raise RuntimeError('distance_variant_out_of_range')
            context['scene']=dict(scene,talker_to_microphone_cm=distance);scene=context['scene']
            context['condition_id']='changed-distance';context['binding_sha256']=hashlib.sha256(encoded(dict(binding=binding,scene=scene))).hexdigest()
            state['conditions'].append(dict(condition_id=context['condition_id'],scene=dict(scene)))
            voice_input=trial('human-input-distance','zero',direct=True,seconds=.30,is_precheck=True)
        print('输入对照',json.dumps(dict(quiet=quiet_input['microphone_headroom'].get('rms_dbfs'),speech=voice_input['microphone_headroom'].get('rms_dbfs'),
            absolute_peak=voice_input['microphone_headroom']['peak_dbfs']),ensure_ascii=False),flush=True)
        if human('刚才实际说话/暂停时麦克风读数有响应？INPUT_RESPONDS / NO_RESPONSE / UNKNOWN：')!='INPUT_RESPONDS':raise RuntimeError('microphone_response_unknown')
        state['input_response_confirmed']=True
        state['input_response_prompt_sequence']=len(state['prompt_log'])
        def path_check(post=False):
            if human('停止真人讲话并实际暂停手机/其他声源，房间安静后输入 SOURCES_STOPPED；其他取消：')!='SOURCES_STOPPED':raise RuntimeError('sources_not_confirmed_stopped')
            source_prompt_sequence=len(state['prompt_log'])
            quiet=trial('quiet','zero',direct=True,seconds=1.02)
            active=trial('positive-post' if post else 'positive','zero',direct=True,pcm=tone,seconds=1.02)
            relative=relative_positive_control(folder/active['file'],folder/quiet['file'])
            legacy=gate_metrics(folder/active['file'],positive_background(folder/quiet['file'])['rms_dbfs'])
            if any(r!='positive_tone_below_relative_floor' for r in relative['reasons']):
                raise RuntimeError('path_reference_or_observation_invalid')
            heard=human('刚才登记的测试音是否实际由指定音响发出（不是手机或电脑）？TONE_HEARD / NOT_HEARD / UNKNOWN：')
            result=dict(confirmed=heard=='TONE_HEARD' and state['input_response_confirmed'],output_report=heard,
                source_prompt_sequence=source_prompt_sequence,output_prompt_sequence=len(state['prompt_log']),
                actual_reference_verified=True,input_response_confirmed=True,relative=relative,legacy=legacy,
                scope='separately verified live input and actual loudspeaker output; 1kHz estimate may remain unknown')
            state['path_post' if post else 'path_pre']=result;collect(folder,state)
            if not result['confirmed']:raise RuntimeError('actual_output_route_unknown')
        path_check()
        for repeat in (1,2):
            trial('human-baseline-off','zero',pcm=cue,direct=True,seconds=PLAN['baseline_seconds'],repeat=repeat,positive=True)
            on=trial('human-baseline-on','zero',pcm=cue,seconds=PLAN['baseline_seconds'],repeat=repeat,positive=True)
            heard=human('本次真人实际听到声音？HEARD / NOT_HEARD / UNKNOWN（原声和扩声来源区分，提示音不计）：')
            verdict=human('相对本轮输出静音，同一真人同句：更容易听清且清晰、无持续鸣叫/明显失真才选 AMPLIFIED_CLEAR；否则 CLEAR_NO_IMPROVEMENT / UNCLEAR / DISTORTED / HOWL / UNKNOWN：')
            words=human('记录本次听众原话：')
            state['baseline_repeats'].append(dict(repeat=repeat,capture_id=on['capture_id'],measurement_valid=on['measurement_valid'],sound_heard=heard,verdict=verdict,listener_words=words,scene=dict(scene)))
            collect(folder,state)
            if verdict in ('DISTORTED','HOWL'):raise RuntimeError('baseline_human_safety_stop:'+verdict)
        usable,_=reproduction_results(state)
        if usable['usable']!='supported':
            state['candidate_unavailable']=['baseline_not_reproduced; no automatic parameter exploration'];state['status']='completed_with_negative_or_unknown_baseline'
            return state
        trial('human-precheck-continuous','zero',direct=True,seconds=.30,is_precheck=True)
        for name in ('audio_replay.bit','audio_replay.hwh'):shutil.copy2(base/name,folder/name)
        if live_runner is None:
            from live_run import live_run
            live_runner=live_run
        continuous=folder/'human-continuous.npz';error=None
        try:
            live_runner(continuous,FIXTURE,context['model_path'],gain_db=-8.,seconds=60.,hp_volume=40,bypass=False,zero_coeff=True,
                speaker_confirmed=True,local_capture_confirmed=True,stop_file=str(folder/'STOP'),
                before_start=lambda:human('60秒真人使用已配置且仍静音。先暂停讲话，START确认后开始正常讲话至程序结束；精确语音起点未测。其他取消：')=='START')
        except (Exception,KeyboardInterrupt) as exc:error=type(exc).__name__+':'+str(exc)
        continuous_manifest=dict(hashes={'model.json':c['model_sha256'],'audio_replay.bit':BIT,'audio_replay.hwh':HWH},coefficients_sha256=ZERO)
        report=continuous_with_headroom(continuous,continuous_manifest,dict(fixture_id=FIXTURE,gain_q12=int(math.floor(4096*10**(-8/20)+.5)),hp_volume=40,continuous_target_seconds=60.,zero_coeff=True),error,model_path=context['model_path'])
        state['human_continuous']=dict(report=report,source_kind='live_human',voice_onset='operator START boundary; precise onset unmeasured',raw_audio_local_only=True)
        if report['status']!='passed':raise RuntimeError('human_continuous_stopped:'+','.join(report['reasons']))
        state['human_continuous']['verdict']=human('本段实际真人持续使用：CLEAR_THROUGHOUT / DEGRADED / DISTORTED / HOWL / PARTIAL / UNKNOWN：')
        state['human_continuous']['listener_words']=human('记录持续使用原话及未覆盖情况：')
        if state['human_continuous']['verdict'] in ('DISTORTED','HOWL','DEGRADED'):raise RuntimeError('human_continuous_use_failed')
        candidate_errors=list(checked['candidate_issues']);candidate=None
        if not candidate_errors:
            candidate=json.loads((base/'candidate-input.json').read_text(encoding='utf8'))
            candidate_errors+=prerequisites(candidate,scene,base/'candidate-unbound.json')
            if candidate.get('profile')!='human_pair' or candidate.get('gain_db')!=-8.:candidate_errors.append('candidate_working_point_must_remain_minus8')
        state['candidate_unavailable']=candidate_errors
        if candidate_errors:
            state['status']='completed_baseline_candidate_unavailable';return state
        state['candidate_binding']=dict(candidate=candidate,scene=dict(scene))
        context.update(candidate=candidate,model_path=base/'candidate-unbound.json',binding_sha256=hashlib.sha256(encoded(state['candidate_binding'])).hexdigest())
        shutil.copy2(base/'candidate-unbound.json',folder/'candidate-model.json')
        for repeat,order in ((1,('zero','matched')),(2,('matched','zero'))):
            rows={}
            for mode in order:rows[mode]=trial('human-candidate',mode,pcm=cue,seconds=PLAN['baseline_seconds'],repeat=repeat,positive=True)
            comparison=human('本对零系数/候选真人同句：IMPROVED / SIMILAR / WORSE / DISTORTED / HOWL / UNKNOWN：')
            comparable=human('本对同一讲话人、同句、位置与相近声量是否保持？COMPARABLE / NOT_COMPARABLE / UNKNOWN：')
            valid=all(r['measurement_valid'] for r in rows.values()) and rows['zero']['scene_sha256']==rows['matched']['scene_sha256'] and rows['zero']['gain_q12']==rows['matched']['gain_q12']
            state['candidate_comparisons'].append(dict(repeat=repeat,pair_valid=valid,voice_comparable=comparable,verdict=comparison,
                listener_words=human('记录本对听众原话：'),captures={k:v['capture_id'] for k,v in rows.items()},gain_db=-8.,scope='uncalibrated live human; qualitative and numerical events separately'))
            if comparison in ('DISTORTED','HOWL'):raise RuntimeError('candidate_human_safety_stop')
        path_check(post=True)
        state['status']='completed'
    except (Exception,KeyboardInterrupt) as exc:
        state['status']='stopped';state['stop_reason']=type(exc).__name__+':'+str(exc)
    finally:
        baseline,candidate=reproduction_results(state)
        state['baseline_result']=baseline;state['candidate_result']=candidate
        state['grades'].update(execution=state['status'],measurement='independent_observations_retained',
            listener_effect=baseline['usable'],algorithm_difference=candidate['improvement'],
            continuous_operation=('supported_human_use' if state.get('human_continuous',{}).get('verdict')=='CLEAR_THROUGHOUT' and state.get('human_continuous',{}).get('report',{}).get('status')=='passed' else
                'human_use_unknown_or_failed' if state.get('human_continuous') else 'not_tested'))
        collect(folder,state)
    return state


def run(base=None, ask=input, runner=None, live_runner=None):
    base=Path(base or Path(__file__).resolve().parent).resolve()
    if json.loads((base/'layout-manifest.json').read_text(encoding='utf8')).get('workflow')=='success_first':
        return _run_reproduction(base,ask,runner,live_runner)
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
        context=dict(candidate=c,scene=scene,model_path=base/'model.json',binding_sha256=binding['binding_sha256'])
        trial=_make_trial(base,folder,state,context,ask,runner)
        # Current-scene positive control uses current background; no old -37.8 floor.
        quiet=trial('quiet',direct=True,seconds=1.02)
        background_control=positive_background(folder/quiet['file'])
        floor=background_control['rms_dbfs']
        gate=trial('positive',direct=True,pcm=tone,seconds=1.02)
        control=(relative_positive_control(folder/gate['file'],folder/quiet['file']) if runtime else
                 gate_metrics(folder/gate['file'],floor))
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
            positive_detection_method=control.get('method','legacy_tonal_dominance'),
            relative_tone_control=control if runtime else None,
            reason='No new injection level or pure-SNR cutoff invented; runtime/listening proceed independently' if runtime else None)
        if runtime:
            for i,scan_gain in enumerate(c['scan_gains_db']):
                order=('zero','matched') if i%2==0 else ('matched','zero')
                for mode in order:trial('runtime-scan',mode,repeat=1,positive=True,gain_db=scan_gain)
            scan_gain=gain
            for mode in ('matched','zero'):trial('runtime-scan',mode,repeat=2,positive=True,gain_db=scan_gain)
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
        after=(relative_positive_control(folder/post['file'],folder/quiet['file'],control) if runtime else
               gate_metrics(folder/post['file'],floor,control['rms_dbfs']))
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
            print('每项8秒；提示音结束后从文件0秒重放已登记同一片段，文件/音量/位置不变。只记录听众定性比较，定量预置未测。',flush=True)
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


def _review_reproduction(archive,state,output,return_sha):
    issues=[];binding=state.get('binding');raw_checked=[];voice_metadata=[]
    if not binding:
        result=dict(policy=POLICY,workflow='success_first',return_sha256=return_sha,raw_quality_control=dict(status='no_board_records',issues=[]),
            baseline_result=reproduction_results(state)[0],candidate_result=reproduction_results(state)[1],
            historical_listener_feedback=state.get('historical_listener_feedback'),execution_origin=state.get('execution_origin'),
            field_effect_claims_allowed=False,stop_reason=state.get('stop_reason'),prompt_log=state.get('prompt_log',[]))
        write_json(output,result);return result
    if hashlib.sha256(archive.read('model.json')).hexdigest()!=binding['baseline']['model_sha256']:issues.append('baseline_transport_hash')
    if hashlib.sha256(encoded({k:v for k,v in binding.items() if k!='binding_sha256'})).hexdigest()!=binding['binding_sha256']:issues.append('baseline_binding_hash')
    inventory={r['file']:r for r in state.get('inventory',[])}
    with tempfile.TemporaryDirectory(prefix='c-reproduction-intake-',dir=Path(output).resolve().parent) as d:
        temp=Path(d)
        for name in archive.namelist():
            if Path(name).name!=name:raise ValueError('unsafe return path')
            if name.endswith('.json') or name.endswith('.npz'):(temp/name).write_bytes(archive.read(name))
        for row in state['trials']:
            name=row['file'];item=inventory.get(name,{})
            if item.get('metadata') and any(item['metadata'].get(k)!=row.get(k) for k in
                    ('capture_id','first_frame','completed_frames','frames','zero_coeff','coefficients_sha256','model_sha256','gain_q12')):
                issues.append('metadata_disagrees:'+name)
            if row.get('measurement_valid'):
                status=row.get('driver_status',{})
                if status.get('recovery_ok') is not True or status.get('save_error') or status.get('cleanup_errors'):issues.append('status_disagrees:'+name)
                zero=row['role']!='human-candidate' or row.get('mode')=='zero'
                expected_hash=ZERO if zero else state.get('candidate_binding',{}).get('candidate',{}).get('coefficients_sha256')
                audible=row['role'] in ('human-baseline-on','human-candidate')
                expected_gain=int(math.floor(4096*10**(-8/20)+.5)) if audible else 0
                if (row.get('coefficients_sha256')!=expected_hash or row.get('zero_coeff')!=zero or row.get('gain_q12')!=expected_gain or
                    row.get('hp_volume')!=40 or row.get('bit_sha256')!=BIT or row.get('fixture_id')!=FIXTURE or
                    row.get('completed_frames')!=int(row['requested_seconds']*RATE) or row.get('source_schedule_verified') is not True or
                    row.get('source_end_frame_exclusive')!=row.get('source_frames')):
                    issues.append('identity_or_budget:'+name)
            if 'human' in name or 'listener' in name:
                if name in archive.namelist():issues.append('unexpected_human_pcm:'+name)
                voice_metadata.append(name);continue
            if name not in archive.namelist():issues.append('raw_missing:'+name);continue
            path=temp/name
            if sha(path)!=item.get('sha256'):issues.append('inventory_hash:'+name);continue
            expected={k:row.get(k) for k in ('fixture_id','hp_volume','sample_rate_hz','bit_sha256','model_sha256','gain_q12','zero_coeff','coefficients_sha256')}
            a=analyze_npz(path,expected=expected,positive_control_valid=False,external_source_active=False,external_source_off_verified=True)
            headroom=microphone_headroom(path,require_full_capture=row.get('is_input_precheck',False))
            if row.get('measurement_valid') and (a['category']=='invalid' or not headroom['passed']):issues.append('raw_recalculation:'+name)
            if (temp/name.replace('.npz','.status.json')).exists():
                status=json.loads((temp/name.replace('.npz','.status.json')).read_text(encoding='utf8'))
                if status!=row['driver_status']:issues.append('status_file:'+name)
            raw_checked.append(name)
        for which,positive_role in (('path_pre','positive'),('path_post','positive-post')):
            declared=state.get(which)
            if not declared:continue
            active=next((r for r in state['trials'] if r['role']==positive_role and not r['is_input_precheck']),None)
            quiet=next((r for r in reversed(state['trials'][:state['trials'].index(active)]) if r['role']=='quiet'),None) if active else None
            if active and quiet:
                actual=relative_positive_control(temp/active['file'],temp/quiet['file'])
                if actual['passed']!=declared['relative']['passed'] or (actual.get('detection_contrast_db') is not None and
                    abs(actual['detection_contrast_db']-declared['relative']['detection_contrast_db'])>1e-7):issues.append('path_recalculation:'+which)
            else:issues.append('path_raw_missing:'+which)
        continuous=state.get('human_continuous')
        if continuous:
            status_name='human-continuous.status.json'
            if status_name not in archive.namelist():issues.append('continuous_status_missing')
            else:
                status=json.loads(archive.read(status_name))
                if status!=continuous['report']['driver_status']:issues.append('continuous_status_disagrees')
                if continuous['report']['status']=='passed' and (not all(status.get(k) is True for k in ('recovered','mute_ok','disarm_ok')) or
                    status.get('zero_coeff') is not True or status.get('coefficients_sha256')!=ZERO or
                    status.get('frames_completed')!=int(60*RATE) or any(status.get('counts',{}).values())):
                    issues.append('continuous_zero_use_identity_or_counts')
    answers={r['sequence']:r['answer'] for r in state.get('prompt_log',[])}
    by_id={r.get('capture_id'):r for r in state['trials']}
    for item in state.get('baseline_repeats',[]):
        row=by_id.get(item['capture_id'],{})
        if row.get('role')!='human-baseline-on' or row.get('measurement_valid')!=item['measurement_valid']:issues.append('baseline_capture_reference')
    for item in state.get('candidate_comparisons',[]):
        rows={k:by_id.get(v,{}) for k,v in item['captures'].items()}
        valid=(set(rows)=={'zero','matched'} and all(r.get('measurement_valid') for r in rows.values()) and
            rows['zero'].get('scene_sha256')==rows['matched'].get('scene_sha256') and rows['zero'].get('gain_q12')==rows['matched'].get('gain_q12'))
        if bool(valid)!=item['pair_valid']:issues.append('candidate_pair_reference')
    if state.get('input_response_confirmed') and answers.get(state.get('input_response_prompt_sequence'))!='INPUT_RESPONDS':issues.append('input_confirmation_missing')
    for which in ('path_pre','path_post'):
        item=state.get(which,{})
        if item.get('confirmed') and (answers.get(item.get('output_prompt_sequence'))!='TONE_HEARD' or
            answers.get(item.get('source_prompt_sequence'))!='SOURCES_STOPPED'):
            issues.append('human_path_confirmation_missing:'+which)
    baseline,candidate=reproduction_results(state)
    if baseline!=state.get('baseline_result'):issues.append('baseline_summary_disagrees')
    if candidate!=state.get('candidate_result'):issues.append('candidate_summary_disagrees')
    reported_baseline=baseline;reported_candidate=candidate
    if issues:
        baseline=dict(baseline,usable='unknown',quality='blocked_pending_quality_fix')
        candidate=dict(candidate,improvement='unknown',quality='blocked_pending_quality_fix')
    result=dict(policy=POLICY,workflow='success_first',return_sha256=return_sha,
        raw_quality_control=dict(status='completed_available_records' if not issues else 'discrepancies',issues=issues,
            independent_raw_files=raw_checked,voice_metadata_only=voice_metadata,
            limitation='Raw human PCM remains local; voice statistics/continuous waveform verification are board-side only, not independent acoustic revalidation'),
        baseline_result=baseline,candidate_result=candidate,reported_baseline_result=reported_baseline,reported_candidate_result=reported_candidate,
        field_effect_claims_allowed=not issues and state.get('execution_origin')=='A_operator_board',
        board_result_dir=state.get('board_result_dir'),trials=state['trials'],historical_listener_feedback=state.get('historical_listener_feedback'),
        conditions=state.get('conditions'),original_input_refused=state.get('original_input_refused'),
        path_pre=state.get('path_pre'),path_post=state.get('path_post'),human_continuous=state.get('human_continuous'),
        prompt_log=state.get('prompt_log'),execution_origin=state.get('execution_origin'),stop_reason=state.get('stop_reason'),msg_db=None,asg_db=None)
    write_json(output,result);return result


def review(path, output):
    """C's one return intake, with all omissions carried to B together."""
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('return-manifest.json'))
        for name,digest in manifest['hashes'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest: raise ValueError('return hash:'+name)
        state=json.loads(z.read('summary.json'))
        if state['policy']!=POLICY: raise ValueError('return policy')
        if state.get('workflow')=='success_first':return _review_reproduction(z,state,output,sha(path))
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
                if quiet and positive:
                    floor=positive_background(temp/quiet['file'])['rms_dbfs']
                    runtime=candidate.get('profile')=='runtime_scan'
                    state['positive_control']=(relative_positive_control(temp/positive['file'],temp/quiet['file']) if runtime else
                        gate_metrics(temp/positive['file'],floor))
                    if post:
                        state['positive_post']=(relative_positive_control(temp/post['file'],temp/quiet['file'],state['positive_control']) if runtime else
                            gate_metrics(temp/post['file'],floor,state['positive_control']['rms_dbfs']))
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
            positive_control=state.get('positive_control'),positive_post=state.get('positive_post'),
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
    if a.action=='review' and result.get('workflow')=='success_first':return 2 if result['raw_quality_control']['issues'] else 0
    return 0 if result.get('ready',result.get('status')=='completed' or a.action=='review') else 2


if __name__=='__main__': raise SystemExit(main())
