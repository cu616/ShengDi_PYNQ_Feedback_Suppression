"""Read fixed Git objects and existing ZIP; never run a supplied entry point.

B's functions are loaded from its exact Git blob with AST, not copied/forked.
Expected crossing results come from the signs of the real/imaginary parts.
"""
import argparse
import ast
import io
import json
import platform
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
from evaluation import classify, VERSION
from audit_lowband_package import inspect_packet, load_npz, record_metrics, spectral_estimate, digest


def blob(commit,path):
    return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)


def b_functions(commit):
    source = blob(commit,'scripts/diagnose_peak_margin.py')
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n,ast.FunctionDef) and
             n.name in ('phase_consistent_threshold','positive_real_crossing','model_response','welch_cross')]
    scope = {'np':np,'FMIN_HZ':300.}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'B exact AST functions','exec'),scope)
    return scope,digest(source)


def matched_boundary_control(record, coefficients):
    """A 512-tap FIR has identical history after each piece's first 512 frames.

    Compare exactly the same indices once on both sides. The second calculation
    reproduces the unbounded suffix selection in B=9937113's section 5a only to
    identify its weighting error; it is not an alternate fitting implementation.
    """
    arrays,_=record
    u=np.asarray(arrays['reference'],float);m=np.asarray(arrays['microphone'],float)
    taps=len(coefficients);pieces=np.array_split(np.arange(len(u)),8)
    def prediction(signal,indices):
        values=[]
        for start in range(0,len(indices),2048):
            selected=indices[start:start+2048]
            values.append(signal[selected[:,None]-1-np.arange(taps)[None,:]]@coefficients)
        return np.concatenate(values)
    whole=m[taps:]-prediction(u,np.arange(taps,len(u)))
    reset=[];matched=[]
    for piece in pieces:
        indices=np.arange(taps,len(piece))
        reset.append(m[piece][indices]-prediction(u[piece],indices))
        matched.append(whole[piece[indices]-taps])
    reset=np.concatenate(reset);matched=np.concatenate(matched)
    weighted=np.concatenate([whole[max(0,piece[0]-taps):] for piece in pieces])
    delta=lambda a,b:float(20*np.log10(np.sqrt(np.mean(a*a))/np.sqrt(np.mean(b*b))))
    return dict(probe='lowband2/seg_10.npz',taps=taps,pieces=len(pieces),
        matched_frames=len(matched),reset_frames=len(reset),
        matched_residual_max_difference=float(np.max(abs(reset-matched))),
        matched_delta_db=delta(reset,matched),b_unbounded_suffix_frames=len(weighted),
        unbounded_suffix_reproduced_delta_db=delta(reset,weighted),
        conclusion='The 0.53 dB comes from unmatched/repeated suffix weighting, not a resolution bound.')


def audit(a_commit,b_commit,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    packet=out/'source.zip'
    packet.write_bytes(blob(a_commit,'report/verification/audio-replay/lowband2-return.zip'))
    blobs,manifest,model,inventory,unbound=inspect_packet(packet)
    # Authorized raw data stay in tmp; report contains no copied PCM.
    packet.unlink()
    funcs,bhash=b_functions(b_commit)
    cases=[]
    for name,phases,gate in [('negative-real-wrap',[179.,-179.],[True,True]),
                              ('low-coherence-hole',[10.,0.,-10.],[True,False,True]),
                              ('positive-real-control',[10.,-10.],[True,True]),
                              ('last-bin-on-positive-real-axis',[10.,0.],[True,True]),
                              ('disconnected-positive-real-endpoints',[0.,10.,0.],[True,False,True])]:
        f=400.+10*np.arange(len(phases));mag=np.ones(len(f))*.5
        if 'positive_real_crossing' in funcs:
            threshold,frequency=funcs['positive_real_crossing'](mag*np.exp(1j*np.deg2rad(phases)),f,np.array(gate))
        else:
            threshold,frequency=funcs['phase_consistent_threshold'](mag,np.deg2rad(phases),f,np.array(gate))
        expected=name in ('positive-real-control','last-bin-on-positive-real-axis',
                         'disconnected-positive-real-endpoints'); finite=bool(np.isfinite(threshold))
        cases.append(dict(case=name,frequencies_hz=f.tolist(),phase_deg=phases,gate=gate,
            expected_crossing=expected,returned_crossing=finite,check_passed=finite==expected,
            returned_db=float(threshold) if finite else None,
            returned_hz=float(frequency) if np.isfinite(frequency) else None))
    q=np.asarray(model['coefficients_q20'],float)/2**20
    w=2*np.pi*np.arange(2049)/4096
    independent=sum(c*np.exp(-1j*w*(i+1)) for i,c in enumerate(q))
    actual=funcs['model_response'](q,4096)
    qerr=float(np.max(abs(actual-independent)))
    float_delta=float(np.max(abs(funcs['model_response'](model['coefficients'],4096)-actual)))
    # Each record alone is shorter than the FFT: there are zero legal windows.
    # Concatenation creates one fabricated cross-record spectral window.
    u=np.r_[np.ones(8),-np.ones(8)];m=u*.5
    separate=sum(float(np.sum(funcs['welch_cross'](x,x*.5,16)[0])) for x in (u[:8],u[8:]))
    concatenated=float(np.sum(funcs['welch_cross'](u,m,16)[0]))
    records={n:load_npz(data) for n,data in blobs.items() if n.endswith('.npz')}
    closed=[]
    for name in sorted(n for n in records if n.startswith('closed_loop/')):
        arrays,meta=records[name];r=record_metrics(name,arrays,meta)
        mic=np.rint(arrays['microphone']*2**23).astype(np.int64)
        result=classify(meta,mic)
        r.update(category=result['category'],classification_reasons=result['reasons'],
                 growth_evidence=result['instability_evidence'],whole_trial_stability='unknown',
                 source_off_verified=meta.get('external_source_off_verified'))
        closed.append(r)
    estimates=[]
    for split,ids in [('all16',range(16)),('holdout6',range(10,16))]:
        names=['lowband2/seg_%d.npz'%i for i in ids]
        for nfft in (4096,8192):
            estimate=spectral_estimate([records[n] for n in names],q,nfft)
            estimate.update(split=split,input_paths=names)
            if 'positive_real_crossing' in funcs:
                suu=np.zeros(nfft//2+1);smm=suu.copy();cross=np.zeros_like(suu,dtype=complex)
                for name in names:
                    arrays,_=records[name]
                    a,b,c=funcs['welch_cross'](arrays['reference'],arrays['microphone'],nfft)
                    suu+=a;smm+=b;cross+=c
                h=np.divide(cross,suu,out=np.zeros_like(cross),where=suu>0)
                coh=np.divide(abs(cross)**2,suu*smm,out=np.zeros_like(suu),where=suu*smm>0)
                freq=np.fft.rfftfreq(nfft,1/48828.125);omega=2*np.pi*freq/48828.125
                gate=(freq>=300)&(coh>=.8)&(suu>0)
                loop=(h-funcs['model_response'](q,nfft))*np.exp(-2j*omega)
                threshold,frequency=funcs['positive_real_crossing'](loop,freq,gate)
                estimate['b_fixed_function']=dict(estimated_db=float(threshold),frequency_hz=float(frequency),
                    difference_from_c_estimate_db=float(threshold-estimate['phase_crossing_estimate']['estimated_db']))
                estimate['gate_coverage']=dict(selected_bins=int(gate.sum()),total_bins=len(gate),fraction=float(gate.mean()))
            estimates.append(estimate)
    old_model=json.loads(blob(b_commit,'models/room_v1/candidate_512.json'))
    old_q=np.asarray(old_model['coefficients_q20'],float)/2**20
    for split,ids in [('all16',range(16)),('holdout6',range(10,16))]:
        for label,coefficients in [('old_candidate_cross_session',old_q),
                                    ('no_cancellation',np.zeros_like(old_q))]:
            for nfft in (4096,8192):
                names=['lowband2/seg_%d.npz'%i for i in ids]
                estimate=spectral_estimate([records[n] for n in names],coefficients,nfft)
                estimate.update(split=split+'_'+label,input_paths=names)
                estimates.append(estimate)
    bmain=next(n for n in ast.parse(blob(b_commit,'scripts/diagnose_peak_margin.py')).body
               if isinstance(n,ast.FunctionDef) and n.name=='main')
    float_reads=any(isinstance(n,ast.Subscript) and isinstance(n.ctx,ast.Load) and
                    isinstance(n.value,ast.Name) and n.value.id=='model' and
                    isinstance(n.slice,ast.Constant) and n.slice.value=='coefficients'
                    for n in ast.walk(bmain))
    memory_source=blobs['scripts/memory_sweep.py']
    result=dict(a_commit=a_commit,b_commit=b_commit,calculation_version=VERSION,
        runtime=dict(python=platform.python_version(),numpy=np.__version__),
        verification_level='offline_numeric_and_controlled_counterexamples',board_access=False,
        packet_sha256=digest(blob(a_commit,'report/verification/audio-replay/lowband2-return.zip')),
        original_npz_hashes_verified=len(manifest['files']),npz_count=len(records),unbound_members=unbound,
        b_script_sha256=bhash,b_counterexamples=cases,
        deployment=dict(model_sha256=manifest['model']['sha256'],
            q20_sha256=manifest['model']['coefficients_q20_sha256'],
            q20_response_vs_direct_lag_polynomial_max_error=qerr,
            b_response_q20_check_passed=qerr<1e-10,float_vs_deployed_response_max_difference=float_delta,
            b_main_uses_float_coefficients=float_reads),
        boundaries=dict(independent_record_spectral_energy=separate,
            fabricated_concatenated_spectral_energy=concatenated,
            expected_legal_windows=0,concatenation_produces_illegal_window=concatenated>0,
            original_memory_script_sha256=digest(memory_source),
            inspected_concatenation_lines=[dict(line=i,text=line.strip())
                for i,line in enumerate(memory_source.decode('utf8').splitlines(),1) if 'concatenate' in line],
            memory_sweep_reproduced=False,
            missing='sideways 20 records, model, exact ordered scan list, train/valid IDs and filter edge provenance'),
        historical_closed=closed,spectral_estimates=estimates,
        matched_boundary_control=matched_boundary_control(records['lowband2/seg_10.npz'],q),
        interpretation='Phase estimates and sampled small-gain predictions omit unqualified bins; no fullband certification or measured MSG/ASG.',
        measured_msg_db=None,measured_asg_db=None)
    (out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    return result


def audit_return(a_commit, out):
    """Inspect this sprint's metadata return and declared assets, without PCM or board access."""
    a_commit=subprocess.check_output(
        ['git','rev-parse',a_commit],cwd=ROOT).decode().strip()
    packet=blob(a_commit,'report/verification/audio-replay/c-sprint-rc01-return.zip')
    with zipfile.ZipFile(io.BytesIO(packet)) as archive:
        manifest=json.loads(archive.read('return-manifest.json'))
        checks={n:digest(archive.read(n))==h for n,h in manifest['hashes'].items()}
        if not all(checks.values()):raise ValueError('return member hash mismatch')
        state=json.loads(archive.read('summary.json'))
        with zipfile.ZipFile(ROOT/'build/packages/c-sprint-rc01-r1.zip') as original:
            frozen=json.loads(original.read('sprint-manifest.json'))
        package_identity=dict(policy=state['policy']==frozen['policy'],plan=state['plan']==frozen['plan'],
            source_commits=state['package_source']==frozen['source_commits'],payload_hashes=state['package_hashes']==frozen['hashes'])
        if not all(package_identity.values()):raise ValueError('returned package identity mismatch')
        trials=[]
        for row in state['trials']:
            side=json.loads(archive.read('%02d-%s.status.json'%(row['id'],row['role'])))
            trials.append(dict(id=row['id'],role=row['role'],category=row['category'],
                acoustic_reasons=row['analysis']['reasons'],path_gate=row.get('path_gate'),
                completed_frames=row['completed_frames'],duration_seconds=row['completed_frames']/48828.125,
                frames=row['frames'],first_frame=row['first_frame'],stop_reasons=row['stop_reasons'],
                sidecar=side,counts_from_raw=dict(prediction=side['clip_counts_raw'][0]&65535,
                    residual=side['clip_counts_raw'][0]>>16,gain=side['clip_counts_raw'][1],mix=side['clip_counts_raw'][2])))
    assets=[]
    for path in subprocess.check_output(['git','ls-tree','-r','--name-only',a_commit],cwd=ROOT).decode().splitlines():
        if path.endswith(('.bit','.hwh')):
            value=blob(a_commit,path)
            assets.append(dict(path=path,bytes=len(value),sha256=digest(value)))
    continuous=json.loads(blob(a_commit,'report/verification/audio-replay/v2-continuous-run-2026-10-25.json'))
    declared={k:continuous['build'][k] for k in ('bit_sha256','hwh_sha256')}
    driver=ast.parse(blob(a_commit,'board/audio_replay/live_run.py'))
    entry=next(n for n in driver.body if isinstance(n,ast.FunctionDef) and n.name=='live_run')
    parents={child:node for node in ast.walk(entry) for child in ast.iter_child_nodes(node)}
    save=next(n for n in ast.walk(entry) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
              and isinstance(n.func.value,ast.Name) and n.func.value.id=='np' and n.func.attr=='savez_compressed')
    ancestors=[];cursor=save
    while cursor in parents:
        cursor=parents[cursor];ancestors.append(cursor)
    result=dict(a_commit=a_commit,return_zip_sha256=digest(packet),member_hash_checks=checks,package_identity=package_identity,
        verification_level='independent_metadata_integrity_and_fixed_git_asset_inventory; no PCM or board reproduction',
        trials=trials,reported_checks=state['checks'],reported_stop_reason=state.get('stop_reason'),
        raw_capture_inventory=state['raw_files'],raw_npz_in_return=False,
        hearing_provenance=dict(user_report='PROXY; SSH noninteractive',
            explicit_top_level_proxy_field_present=any('proxy' in k.lower() for k in state),
            assessment='human speech and hearing not independently verified; must not mark passed'),
        asset_inventory=assets,declared_v2_assets=declared,
        declared_v2_found={k:any(x['sha256']==v for x in assets) for k,v in declared.items()},
        continuous_report=continuous,continuous_raw_timeline_present=False,continuous_tail_pcm_present=False,
        continuous_acceptance='A reports engineering completion and stop; C accepts scope, not yet independently reproduced',
        live_run_static_review=dict(before_start_parameter_present=any(n.arg=='before_start' for n in entry.args.args),
            npz_save_in_protected_try=any(isinstance(n,ast.Try) for n in ancestors),
            integration_requests=['A-owned muted after-configuration start/cancel callback',
                'NPZ write error must not skip independent status save; preserve save_error and cleanup facts']),
        missing_for_v2=['actual matching v2 bit and hwh blobs',
            'raw 5s/60s/stop status with complete timeline and existing tail PCM; config/model/Q20 binding',
            'v2 build timing/utilization reports bound to source and assets',
            'A condition-4 silent/simulated saturation protection evidence'],
        decisions=dict(path_gate='passed; source-on tone gate is independent from acoustic category unknown',
            real_voice_trial='protection after 9835 frames; not a measured howl onset threshold',
            r2='fixed -14 dB / Q12=817; unchanged direct gate and thresholds; exact v1 assets',
            v2='defer integration until exact assets and acceptance evidence available'),board_access=False)
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--a-commit',default='bb56ef13300dbfecb6bbd525528a0dcf47ebd7e6')
    p.add_argument('--b-commit',default='d033d0047542d5e50654a0333777c48ec08dce21')
    p.add_argument('--return-only',action='store_true')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit_return(a.a_commit,a.output) if a.return_only else audit(a.a_commit,a.b_commit,a.output)
    keys=('a_commit','declared_v2_found','decisions') if a.return_only else ('a_commit','b_commit','npz_count','b_counterexamples','deployment')
    print(json.dumps({k:result[k] for k in keys},ensure_ascii=False))
