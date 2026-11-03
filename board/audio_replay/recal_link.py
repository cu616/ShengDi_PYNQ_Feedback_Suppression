"""C protocol transport and maintenance check; never imports a board driver."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import threading
import uuid

CAPTURE_PLAN_CONTRACT='recal-capture-plan-v1'


class CapturePlanError(ValueError):
    def __init__(self,index,check):
        self.index=index;self.check=check
        super().__init__('capture plan segment %s: %s'%(index,check))


def perform_capture_plan(hardware, request, cancel):
    """C calling layer; A supplies replay_capture_plan and all actual hardware I/O."""
    import numpy as np
    result={k:request[k] for k in ('contract','request_id','scene_id','op')}
    result.update(ok=False,status='error',failed_index=None,failed_check=None,captures=[])
    old_op=hardware._current_op
    try:
        if cancel.is_set():raise ValueError('cancelled')
        driver=hardware._driver()
        if (getattr(driver,'CAPTURE_PLAN_API',None)!=CAPTURE_PLAN_CONTRACT
                or not callable(getattr(driver,'replay_capture_plan',None))):
            raise ValueError('capture_plan_driver_unavailable')
        plan=request['plan'];items=plan['captures'];outputs=[];sources=[]
        if request['op'] not in ('training','validation') or not items:raise ValueError('capture_plan_shape')
        levels=plan.get('levels',[plan.get('level_dbfs')])
        if len(levels)!=1:raise ValueError('capture_plan_requires_one_approved_level')
        hardware.run_dir=request['run_dir']
        for index,item in enumerate(items):
            result['failed_index']=index
            if int(item.get('frames',16384))!=16384:raise ValueError('window_frames')
            seed=int(item.get('seed',plan['seed']));level=float(item.get('level_dbfs',levels[0]))
            source=hardware._make_stimulus(seed=seed,level_dbfs=level)
            if source is None:raise ValueError('stimulus_unreachable')
            if len(source)!=16386:raise ValueError('source_frames')
            path,cid=hardware._capture_path(request['scene_id'],request['op'],index)
            start=index*16388
            outputs.append(dict(capture_id=item.get('capture_id',cid),output_path=str(path),
                first_frame=start+4,end_frame=start+16388,valid_frames=16382,
                source_first_frame=start,source_end_frame=start+16386,seed=seed,level_dbfs=level))
            sources.extend((source,np.zeros(2,dtype=np.int16)))
        source=np.concatenate(sources)[:-2]
        result['failed_index']=None
        if len(source)>131072:raise ValueError('source_ram_capacity')
        # Bind an explicit calibration-only copy, never relabel the original model or PCM.
        original=Path(hardware.model_path);model=json.loads(original.read_text(encoding='utf-8'))
        result['source_model_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
        model['fixture_id']=request['scene_id'];bound=Path(request['run_dir'])/'batch-source-model.json'
        with bound.open('xb') as stream:stream.write(json.dumps(model,ensure_ascii=False).encode())
        if cancel.is_set():raise ValueError('cancelled')
        result['failed_index']=None;hardware._current_op=request['op'];hardware._op_hold+=1
        try:
            raw=driver.replay_capture_plan(outputs,request['scene_id'],str(bound),source,
                request_id=request['request_id'],scene_id=request['scene_id'],op=request['op'],
                hp_volume=hardware.hp_volume,gain_q12=0,direct_only=True,zero_coeff=True,
                speaker_confirmed=True,local_capture_confirmed=True,restore_stock=False,
                before_start=lambda:hardware._arm_baseline(cancel),cancel_event=cancel)
        finally:hardware._op_hold-=1
        if raw.get('contract')!=CAPTURE_PLAN_CONTRACT or any(raw.get(k)!=request[k] for k in ('request_id','scene_id','op')):
            raise ValueError('capture_plan_envelope')
        result.update({k:raw.get(k) for k in ('ok','status','captures','failed_index','failed_check','reason','input_clip')})
        result['batch']=dict(raw.get('batch',{}),contract=raw['contract'])
        result['planned_windows']=outputs;result['planned_source_sha256']=hashlib.sha256(source.tobytes()).hexdigest()
        result['calibration_model_sha256']=hashlib.sha256(bound.read_bytes()).hexdigest()
        for index,item in enumerate(result.get('captures') or []):
            try:item['sha256']=hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
            except (OSError,KeyError,TypeError) as exc:raise CapturePlanError(index,'capture_file: '+str(exc))
        hardware._scene_frames+=16384*len(result.get('captures') or [])
        if result.get('ok') is True and result.get('status')=='completed':
            check_capture_plan(request,result)
            result['capture_plan_check']=dict(ok=True,segments=len(result['captures']))
    except Exception as exc:
        result.update(ok=False,status='error',failed_check=result.get('failed_check') or str(exc),reason=str(exc))
        if isinstance(exc,CapturePlanError):result.update(failed_index=exc.index,failed_check=exc.check)
        result['capture_plan_check']=dict(ok=False,reason=str(exc))
    finally:
        hardware._current_op=old_op
        result['identity']=hardware.identity()
    return result


def check_capture_plan(request, reply):
    """Reject a partial/mixed/overwritten batch before fitting any segment."""
    import numpy as np
    from replay_tools import verify_replay
    def reject(index,check):raise CapturePlanError(index,check)
    if reply.get('ok') is not True or reply.get('status')!='completed':
        reject(reply.get('failed_index'),reply.get('failed_check') or reply.get('reason') or 'batch_failed')
    count=len(request['plan']['captures']);batch=reply.get('batch',{});captures=reply.get('captures',[])
    if not isinstance(batch,dict) or not isinstance(captures,list) or len(reply.get('planned_windows',[]))!=count:
        reject(None,'batch_shape')
    if (batch.get('contract')!=CAPTURE_PLAN_CONTRACT or len(captures)!=count
            or batch.get('completed_segments')!=count or batch.get('ring_overrun') is not False
            or any(batch.get(k)!=1 for k in ('overlay_downloads','source_loads','arm_count'))):
        reject(None,'batch_count_or_retention')
    if len({c.get('capture_id') for c in captures})!=count:reject(None,'capture_id_duplicate')
    for index,(cap,window) in enumerate(zip(captures,reply['planned_windows'])):
        try:
            path=Path(cap['path']).resolve();path.relative_to(Path(request['run_dir']).resolve())
            if cap['capture_id']!=window['capture_id']:raise ValueError('capture_id')
            if cap.get('source_sha256')!=reply['planned_source_sha256']:raise ValueError('capture_source_sha256')
            status_path=Path(cap['status_path']).resolve();status_path.relative_to(Path(request['run_dir']).resolve())
            status=json.loads(status_path.read_text(encoding='utf-8'))
            with np.load(path,allow_pickle=False) as z:
                md=json.loads(str(z['metadata_json']));source=z['source_pcm16']
                raw=np.column_stack((np.rint(z['reference']*2**23),np.rint(z['microphone']*2**23),z['prediction_pcm'],z['residual_pcm'])).astype(np.int64)
                q=z['coefficients_q20']
                if len(raw)!=16384 or np.any(q) or len(q)!=512:raise ValueError('frames_or_zero_coefficients')
                if source.dtype!=np.int16 or source.ndim!=1:raise ValueError('source_pcm16_format')
                if hashlib.sha256(source.tobytes()).hexdigest()!=reply['planned_source_sha256']:raise ValueError('source_sha256')
                if (md.get('fixture_id')!=request['scene_id'] or md.get('capture_id')!=cap['capture_id']
                        or md.get('gain_q12')!=0 or md.get('hp_volume')!=request['identity']['hp_volume']
                        or md.get('sample_rate_hz')!=request['identity']['sample_rate_hz']
                        or md.get('model_sha256')!=reply['calibration_model_sha256']):raise ValueError('capture_identity')
                if (md.get('zero_coeff') is not True or md.get('forward_path_open') is not True
                        or md.get('bypass') is not False or md.get('frames')!=16384
                        or md.get('completed_frames')!=count*16388
                        or int(md.get('capture_status',0)) & ((1<<22)|(1<<21)|(1<<19)|(1<<18)|(1<<17))):
                    raise ValueError('capture_mode_or_protection')
                if any(md.get(k)!=request['identity'][k] for k in ('driver_sha256','bit_sha256','hwh_sha256','helper_sha256')):
                    raise ValueError('capture_payload_identity')
                if (md.get('first_frame')!=window['first_frame'] or cap.get('first_frame')!=window['first_frame']
                        or cap.get('end_frame')!=window['end_frame'] or cap.get('valid_frames')!=16382
                        or md.get('stop_reason')!='completed' or md.get('source_schedule_verified') is not True):raise ValueError('window_or_completion')
                checks=verify_replay(raw,q,False,0,source,md['first_frame'])
            if md.get('verification',{}).get('bit_exact') is not True or checks['bit_exact'] is not True:
                raise ValueError('bit_exact')
            if (status.get('recovery_ok') is not True or status.get('save_error')
                    or status.get('fixture_id')!=request['scene_id'] or status.get('first_frame')!=window['first_frame']
                    or status.get('frames')!=16384 or status.get('stop_reason')!='completed'):
                raise ValueError('status_json')
            cursor=window['first_frame']
            for chunk in cap.get('read_proof',[]):
                a,b=chunk['first_frame'],chunk['end_frame'];before,after=chunk['completed_before'],chunk['completed_after']
                if not (all(type(v) is int for v in (a,b,before,after))
                        and a==cursor<b<=window['end_frame'] and b<=before<=after<=a+16384):raise ValueError('ring_retention')
                cursor=b
            if cursor!=window['end_frame']:raise ValueError('ring_read_incomplete')
        except (ValueError,KeyError,OSError,TypeError) as exc:reject(index,str(exc))
    return reply


def frozen_policy(algorithm):
    identity=algorithm.identity()
    return dict(runtime_profile='b-frozen-v1',algorithm_module='recal_algorithm',
        algorithm_identity=identity,attempts=copy.deepcopy(algorithm.ATTEMPTS),
        validation_kind='heldout_prediction',input_mode='prepared',cue=True,
        compute_timeout_seconds=150,io_timeout_seconds=150,quiet_seconds=4,run_seconds=30,
        indicator_encoding='led4',phase_gain_q12={k:[0,1631] for k in (
            'prepare','cue','input','training','validation','install','run')})


def capture_plans(attempts):
    """Transport of B's canonical plan; numeric requests retain the original plan."""
    result=[]
    for attempt in attempts:
        stages={}
        for phase in ('training','validation'):
            item=attempt[phase];seed=int(item.get('seed',4242))+(phase=='validation')
            stages[phase]=dict(seed=seed,validation_seed=seed,level_dbfs=item['rms_dbfs'],levels=[item['rms_dbfs']],
                captures=[dict(level_dbfs=item['rms_dbfs'],seed=seed,direct_only=True,
                               zero_coeff=True,content_kind='onboard_excitation')
                          for _ in range(item['segments'])])
        result.append(stages)
    return result


def ingest(request, reply, import_root):
    """Copy verified originals into this scene; preserve source bytes and metadata."""
    if not reply.get('captures'): return reply
    root=Path(import_root).resolve() if import_root else None;run=Path(request['run_dir']).resolve()
    output=copy.deepcopy(reply)
    for index,item in enumerate(output['captures']):
        source=Path(item['path']).resolve()
        try: source.relative_to(run);inside=True
        except ValueError: inside=False
        if not inside:
            if root is None: raise ValueError('capture escaped run directory')
            try: source.relative_to(root)
            except ValueError: raise ValueError('capture escaped approved import root')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('capture original hash changed')
        if not inside:
            target=run/('original-'+request['request_id']+'-'+str(index)+source.suffix)
            if target.exists(): raise ValueError('capture intake would replace existing evidence')
            shutil.copyfile(source,target)
            item.update(original_path=str(source),path=str(target))
        if source.suffix.lower()=='.npz' and ('end_frame' not in item or request.get('cue')):
            import numpy as np
            with np.load(source,allow_pickle=False) as z:
                md=json.loads(str(z['metadata_json']));first=int(md['first_frame'])
                end=first+len(z['microphone']);src_sha=hashlib.sha256(z['source_pcm16'].tobytes()).hexdigest()
            item['reported_window']={k:item.get(k) for k in ('first_frame','end_frame')}
            item.update(first_frame=first,end_frame=end,source_sha256=src_sha,
                        content_kind='human_private' if request.get('op')=='input' else item.get('content_kind','onboard_excitation'))
            if request.get('cue'):
                ready=reply.get('input_ready',{})
                if any(ready.get(k)!=request[k] for k in ('request_id','scene_id')):
                    raise ValueError('embedded input marker identity mismatch')
                cue_end=ready.get('cue_end_frame')
                if type(cue_end) is not int or not 0<cue_end<=first:
                    raise ValueError('measurement window overlaps cue/tail')
                output.update(valid_first_frame=first,cue_end_frame=cue_end)
    return output


def installed_model(request, reply, bundle, scene_root):
    """Accept A's serialized scene copy only with identical validated model content."""
    if reply.get('coefficients_sha256')!=bundle['coefficients_sha256']:
        raise ValueError('installed coefficients differ from validated model')
    if reply.get('model_sha256')==bundle['model_sha256']:
        return Path(bundle['model_path'])
    if reply.get('source_model_sha256')!=bundle['model_sha256']:
        raise ValueError('installed model has no validated source identity')
    original=json.loads(Path(bundle['model_path']).read_text(encoding='utf-8'))
    expected=dict(original,fixture_id=request['scene_id'])
    matches=[]
    for path in Path(scene_root).rglob('*.json'):
        if hashlib.sha256(path.read_bytes()).hexdigest()==reply.get('model_sha256'):
            if json.loads(path.read_text(encoding='utf-8'))!=expected:
                raise ValueError('installed scene copy changed model content')
            matches.append(path)
    if not matches: raise ValueError('installed scene copy not found in this run')
    return matches[0]


def run_evidence(request, reply, scene_root):
    """Separate the saved ring window from the driver's actual completed frame counter."""
    if 'audio_frames' not in reply:return reply  # Older adapters report run duration directly.
    import numpy as np
    path=Path(reply['path']).resolve()
    try:path.relative_to(Path(scene_root).resolve())
    except ValueError:raise ValueError('run capture escaped this scene')
    with np.load(path,allow_pickle=False) as z:
        md=json.loads(str(z['metadata_json']));count=len(z['microphone'])
    frames=md.get('completed_frames');first=md.get('first_frame');rate=md.get('sample_rate_hz')
    if (type(frames) is not int or type(first) is not int or not isinstance(rate,(int,float))
            or rate!=reply['identity']['sample_rate_hz'] or count!=md.get('frames')
            or count!=reply['audio_frames'] or first+count!=frames
            or md.get('stop_reason')!='completed' or md.get('early_stop') is True
            or not (int(md.get('capture_status') or 0)&1)):
        raise ValueError('run completion counter/window not verified')
    for field in ('model_sha256','coefficients_sha256'):
        if md.get(field)!=reply.get(field) or reply.get(field)!=request.get(field):
            raise ValueError('run capture model identity differs: '+field)
    output=dict(reply,capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        capture_elapsed_seconds=count/rate,audio_elapsed_seconds=frames/rate,
        completed_frames=frames,timing_source='driver.completed_frames',metadata=md)
    return output


def adapter_check(hardware, config, state, model, save, cancel=None):
    """A explicitly runs this one short chain; C runs it with simulated leaf I/O."""
    state=Path(state);state.mkdir(parents=True,exist_ok=True)
    cancel=cancel or threading.Event();scene=json.loads(Path(model).read_text(encoding='utf-8')).get('fixture_id') or 'adapter-check-'+uuid.uuid4().hex
    receipt=dict(contract='recal-product-v1',scene_id=scene,scope='maintenance API chain; not recalibration acceptance',
        algorithm_identity=config.get('algorithm_identity'),steps=[],compatibility_issues=[],success=False,
        selected_model=dict(path=str(model),sha256=hashlib.sha256(Path(model).read_bytes()).hexdigest(),
            provenance=config.get('maintenance_model_provenance','frozen_package_model')))
    path=state/'adapter-check.json'
    def record(name,request,reply):
        receipt['steps'].append(dict(name=name,request=request,reply=reply));save(path,receipt)
        return reply
    def perform(op,**fields):
        if cancel.is_set(): raise RuntimeError('maintenance cancelled')
        req=dict(contract='recal-product-v1',request_id=uuid.uuid4().hex,scene_id=scene,
            run_dir=str(state),op=op,**fields)
        result=record(op,req,hardware.perform(req,cancel))
        if any(result.get(k)!=req[k] for k in ('contract','request_id','scene_id')):
            raise ValueError('adapter reply envelope mismatch')
        if result.get('ok') is not True or result.get('status')!='completed':
            raise ValueError('adapter operation failed: '+op+': '+str(result.get('reason')))
        return result
    try:
        muted=record('mute',{},hardware.mute())
        if not muted.get('ok') or not muted.get('muted'): raise ValueError('initial mute not confirmed')
        gain=config.get('maintenance_gain_q12',config['expected_identity']['gain_q12'])
        if type(gain) is not int or gain not in config.get('allowed_gain_q12',[config['expected_identity']['gain_q12']]):
            raise ValueError('maintenance gain is not approved')
        receipt['maintenance_gain_q12']=gain
        caps=record('capabilities',{},hardware.capabilities())
        if caps.get('prepared_capture') is not True:
            receipt['compatibility_issues'].append('prepared_capture=false: ordinary speech workflow remains blocked')
        perform('prepare')
        plan=dict(seed=4242,validation_seed=4243,level_dbfs=-22.,captures=[dict(
            capture_id=scene+'-training-0',level_dbfs=-22.,direct_only=True,zero_coeff=True)])
        trained=perform('training',plan=plan)
        receipt['capture_valid_frames']=[x.get('valid_frames') for x in trained.get('captures',[])]
        installed=perform('install',model_path=str(model),run_gain_q12=gain)
        original_sha=hashlib.sha256(Path(model).read_bytes()).hexdigest()
        if installed.get('model_sha256')!=original_sha and installed.get('source_model_sha256')!=original_sha:
            raise ValueError('install returned a different model file hash')
        if installed.get('applies_at')=='next_capture':
            receipt['compatibility_issues'].append('install registered for next_capture; no eligible model pointer committed')
        run=perform('run',seconds=3.,gain_q12=gain,bypass=False,
                    model_path=str(model),model_sha256=installed['model_sha256'],
                    coefficients_sha256=installed['coefficients_sha256'])
        for key in ('model_sha256','coefficients_sha256'):
            if run.get(key)!=installed[key]: raise ValueError('run model identity differs: '+key)
        if 'audio_frames' in run:
            run=run_evidence(dict(seconds=3.,model_sha256=installed['model_sha256'],
                coefficients_sha256=installed['coefficients_sha256']),run,state)
            receipt['verified_run_timing']=run
        elif 'audio_elapsed_seconds' not in run:
            receipt['compatibility_issues'].append('elapsed_seconds not independently separated from initialization wall time')
        receipt['success']=True
    except Exception as exc:
        receipt['error']=str(exc)
    finally:
        aborted=record('abort',{},hardware.abort())
        if not all(aborted.get(k) is True for k in ('ok','muted','quiescent')):
            receipt['success']=False;receipt['error']='final abort not confirmed'
        save(path,receipt)
    return receipt
