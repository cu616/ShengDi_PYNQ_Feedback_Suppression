"""RC0.1 v2 integration; A owns all hardware operations and their semantics."""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
from evaluation import VERSION, sha

RATE = 48828.125


def driver_request(base, name, *args, **kwargs):
    """Execute the exact shipped A entry's pure validation prefix, without PYNQ.

    Stop at the original PCM validation (replay) or state construction (live).
    No driver import, device API, configuration, signal handler or I/O write runs.
    Fail closed if the reviewed boundary changes. This is not a second predicate.
    """
    from closed_tools import trial_parameters
    path = Path(base)/(name+'.py')
    tree = ast.parse(path.read_text(encoding='utf8'))
    fn = copy.deepcopy(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name))
    if name == 'replay_trial':
        ends = [i for i,n in enumerate(fn.body) if isinstance(n,ast.If) and
                'invalid source PCM16 or insufficient duration' in ast.unparse(n)]
        returned = ast.Dict(keys=[ast.Constant(k) for k in ('budget','source_frames','headroom_frames')],
            values=[ast.Name('budget',ast.Load()),ast.Call(ast.Name('len',ast.Load()),[ast.Name('source_pcm16',ast.Load())],[]),
                    ast.BinOp(ast.Name('budget',ast.Load()),ast.Sub(),ast.Call(ast.Name('len',ast.Load()),[ast.Name('source_pcm16',ast.Load())],[]))])
        helpers = []
    elif name == 'live_run':
        ends = [i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and
                any(isinstance(t,ast.Name) and t.id=='state' for t in n.targets)]
        returned = ast.Name('state',ast.Load())
        helpers = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_sha256','pl_max_run_frames')]
    else:
        raise ValueError('unreviewed A entry')
    if len(ends)!=1:raise ValueError('A validation boundary changed')
    fn.body = fn.body[:ends[0]+1]+[ast.Return(returned)]
    module = ast.fix_missing_locations(ast.Module(body=helpers+[fn],type_ignores=[]))
    namespace = dict(np=np,Path=Path,json=json,math=math,hashlib=hashlib,trial_parameters=trial_parameters,
                     RATE=RATE,HARDWARE_TAPS=512,PL_MAX_RUN_FRAMES_V1=488281)
    exec(compile(module,str(path)+' (validation only)','exec'),namespace)
    result = namespace[name](*args,**kwargs)
    result['validation_driver_sha256'] = sha(path)
    return result


def review_continuous(path, manifest, plan, error=None, model_path=None):
    """Register timeline + tail PCM: engineering coverage, never full-run acoustics."""
    path=Path(path);side=path.with_suffix('.status.json')
    state={};original={};checks={};verification={};reasons=[]
    try:
        state=json.loads(side.read_text(encoding='utf8'))
        with np.load(path,allow_pickle=False) as capture:
            original=json.loads(str(capture['metadata_json'].item()))
            arrays={k:np.asarray(capture[k]) for k in ('reference','microphone','prediction_pcm','residual_pcm')}
        expected=dict(fixture_id=plan['fixture_id'],gain_q12=plan['gain_q12'],hp_volume=plan['hp_volume'],
            bypass=False,zero_coeff=plan.get('zero_coeff',False),sample_rate_hz=RATE,logical_taps=512,loaded_taps=512,
            frames_requested=int(plan['continuous_target_seconds']*RATE),pl_max_run_frames=3000000,
            driver_evidence_version='a-continuous-v1',mode='continuous',pl_contract='v2',
            model_sha256=manifest['hashes']['model.json'],coefficients_sha256=manifest['coefficients_sha256'],
            bit_sha256=manifest['hashes']['audio_replay.bit'],hwh_sha256=manifest['hashes']['audio_replay.hwh'])
        checks['configuration_bound']=all(state.get(k)==v and original.get(k)==v for k,v in expected.items())
        completed=state['frames_completed'];first=state['first_frame']
        checks['metadata_consistent']=all(original.get(k)==state.get(k) for k in
            ('frames_completed','first_frame','counts','status','stop_reason','timeline','recovered','mute_ok','disarm_ok'))
        checks['tail_extent']=(type(completed) is int and type(first) is int and completed-first==16384 and
            all(x.shape==(16384,) and np.isfinite(x).all() for x in arrays.values()))
        checks['completed']=completed==expected['frames_requested'] and state['stop_reason']=='completed' and not state.get('error')
        timeline=np.asarray(state['timeline'],dtype=float)
        checks['timeline']=(timeline.ndim==2 and timeline.shape[1]==7 and len(timeline)>=2 and
            np.isfinite(timeline).all() and np.all(np.diff(timeline[:,:2],axis=0)>=0) and
            0<=timeline[0,1]<completed and timeline[-1,1]<=completed and
            timeline[-1,0]>=plan['continuous_target_seconds']-.1 and
            np.all(timeline[:,1:]==np.floor(timeline[:,1:])))
        words=timeline[:,2].astype(np.int64)
        checks['no_protection']=(state['status']&((3<<17)|(7<<19)))==0 and bool(state['status']&1) and (
            all(type(v) is int and v==0 for v in state['counts'].values()) and len(state['counts'])==4 and
            np.all(timeline[:,3:]==0) and np.all((words&((3<<17)|(7<<19)))==0))
        checks['cleanup']=all(state.get(k) is True for k in ('recovered','mute_ok','disarm_ok','muted')) and not state.get('cleanup_errors')
        checks['save']=not state.get('save_error') and not state.get('salvage_errors')
        q=np.asarray(json.loads(Path(model_path or path.parent.parent.parent/'model.json').read_text(encoding='utf8'))['coefficients_q20'],dtype=np.int64)
        if plan.get('zero_coeff',False):q=np.zeros_like(q)
        from replay_tools import verify_replay
        raw=np.column_stack((np.rint(arrays['reference']*2**23),np.rint(arrays['microphone']*2**23),
                             arrays['prediction_pcm'],arrays['residual_pcm'])).astype(np.int64)
        checks['pcm_range']=bool(np.all(raw>=-2**23) and np.all(raw<=2**23-1) and
            np.array_equal(arrays['reference']*2**23,raw[:,0]) and
            np.array_equal(arrays['microphone']*2**23,raw[:,1]) and
            np.array_equal(arrays['prediction_pcm'],raw[:,2]) and np.array_equal(arrays['residual_pcm'],raw[:,3]))
        verification=verify_replay(raw,q,False,plan['gain_q12'],np.zeros(1,dtype='<i2'),first)
        checks['tail_arithmetic']=verification.get('bit_exact') is True
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError) as exc:
        reasons.append('continuous_evidence:'+str(exc))
    checks={k:bool(v) for k,v in checks.items()}
    reasons += [k for k,v in checks.items() if not v]
    if error:reasons.append('execution_error:'+error)
    passed=not reasons and bool(checks)
    frames=state.get('frames_completed');first=state.get('first_frame')
    if type(frames) is not int or frames<=0:frames=None
    if type(first) is not int or first<0:first=None
    counts=state.get('counts');word=state.get('status')
    protection=(any(counts.values()) or bool(word&((3<<17)|(7<<19)))) if isinstance(counts,dict) and type(word) is int else None
    analysis=dict(category='protection' if protection else 'unknown',reasons=['engineering_observation_only'],
        calculation_version=VERSION,original_metadata=original,
        evaluation_metadata=dict(original,completed_frames=frames,frames=None if frames is None or first is None else frames-first),
        event_flags=dict(protection=protection,early_stop=state.get('stop_reason')!='completed'),
        capture_window=dict(transition_frames=2442,first_frame=first,end_frame=frames,frames=16384 if first is not None else 0,
            waveform_coverage_fraction=16384/frames if frames else 0),verification=verification)
    return dict(status='passed' if passed else 'failed' if state else 'not_tested',checks=checks,reasons=reasons,
        scope='one continuous arm; register timeline plus final 16384 PCM frames; run/protection/stop only',
        acoustic_status='not_tested',full_trial_stability='unknown',
        timeline_points=len(state['timeline']) if isinstance(state.get('timeline'),list) else 0,max_poll_gap_s=state.get('max_poll_gap_s'),
        waveform_coverage_fraction=16384/frames if frames else None,
        source_schedule_provenance='one silent source frame from bound A live_run; derived for tail arithmetic only',
        analysis=analysis,driver_status=state)


def continuous_trial(base, folder, manifest, plan, ask, runner=None):
    """Copy matching assets beside A's output and call A exactly once."""
    for name in ('audio_replay.bit','audio_replay.hwh'):
        if sha(Path(base)/name)!=manifest['hashes'][name]:raise ValueError('ASSET_MISMATCH: '+name)
        shutil.copy2(Path(base)/name,Path(folder)/name)
        if sha(Path(folder)/name)!=manifest['hashes'][name]:raise ValueError('ASSET_MISMATCH: copied '+name)
    path=Path(folder)/'15-continuous-60s.npz';stop=Path(folder)/'STOP'
    print('CONTINUOUS_STOP_FILE',str(stop.resolve()),flush=True)
    print('60秒保持外部声源关闭；可用当前内核中断或创建上述STOP文件停止。',flush=True)
    if runner is None:
        from live_run import live_run
        runner=live_run
    error=None
    try:
        runner(path,plan['fixture_id'],Path(base)/'model.json',gain_db=plan['gain_db'],seconds=plan['continuous_target_seconds'],
            hp_volume=plan['hp_volume'],bypass=False,zero_coeff=False,speaker_confirmed=True,local_capture_confirmed=True,
            stop_file=str(stop.resolve()),before_start=lambda:ask('15 continuous-60s 已配置且仍静音；START开始，其他输入取消：').strip()=='START')
    except (Exception,KeyboardInterrupt) as exc:error=type(exc).__name__+':'+str(exc)
    return path,review_continuous(path,manifest,plan,error)
