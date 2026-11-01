"""C protocol transport and maintenance check; never imports a board driver."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import threading
import uuid


def frozen_policy(algorithm):
    identity=algorithm.identity()
    return dict(runtime_profile='b-frozen-v1',algorithm_module='recal_algorithm',
        algorithm_identity=identity,attempts=copy.deepcopy(algorithm.ATTEMPTS),
        validation_kind='heldout_prediction',input_mode='prepared',cue=True,
        compute_timeout_seconds=30,io_timeout_seconds=30,quiet_seconds=2,run_seconds=30,
        indicator_encoding='led4',phase_gain_q12={k:[0,1631] for k in (
            'prepare','cue','input','training','validation')})


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
        caps=record('capabilities',{},hardware.capabilities())
        if caps.get('prepared_capture') is not True:
            receipt['compatibility_issues'].append('prepared_capture=false: ordinary speech workflow remains blocked')
        perform('prepare')
        plan=dict(seed=4242,validation_seed=4243,level_dbfs=-22.,captures=[dict(
            capture_id=scene+'-training-0',level_dbfs=-22.,direct_only=True,zero_coeff=True)])
        trained=perform('training',plan=plan)
        receipt['capture_valid_frames']=[x.get('valid_frames') for x in trained.get('captures',[])]
        installed=perform('install',model_path=str(model),run_gain_q12=config['expected_identity']['gain_q12'])
        if installed.get('model_sha256')!=hashlib.sha256(Path(model).read_bytes()).hexdigest():
            raise ValueError('install returned a different model file hash')
        if installed.get('applies_at')=='next_capture':
            receipt['compatibility_issues'].append('install registered for next_capture; no eligible model pointer committed')
        run=perform('run',seconds=3.,gain_q12=config['expected_identity']['gain_q12'],bypass=False,
                    model_path=str(model),model_sha256=installed['model_sha256'],
                    coefficients_sha256=installed['coefficients_sha256'])
        for key in ('model_sha256','coefficients_sha256'):
            if run.get(key)!=installed[key]: raise ValueError('run model identity differs: '+key)
        if 'audio_elapsed_seconds' not in run:
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
