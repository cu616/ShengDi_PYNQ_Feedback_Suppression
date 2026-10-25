"""Read fixed Git objects and existing ZIP; never run a supplied entry point.

B's functions are loaded from its exact Git blob with AST, not copied/forked.
Expected crossing results come from the signs of the real/imaginary parts.
"""
import argparse
import ast
import hashlib
import io
import json
import platform
import re
from pathlib import Path
import subprocess
import sys
import tempfile
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


def audit_b_prediction(commit,out):
    """Independent algebraic controls against B's exact new prediction function.

    Diagnostic only: return counterexamples to B, never fork its production CLI.
    """
    commit=subprocess.check_output(['git','rev-parse',commit],cwd=ROOT).decode().strip()
    source=blob(commit,'scripts/reproduce_b_screening.py')
    scope,_=b_functions(commit)
    helpers=ast.parse(blob(commit,'scripts/diagnose_peak_margin.py'))
    nodes=[n for n in helpers.body if isinstance(n,ast.FunctionDef) and n.name=='estimate_H']
    nodes += [n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='band_switch_table']
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'B exact prediction functions','exec'),scope)
    fs=48828.125;g=817/4096;nfft=1024;f=np.fft.rfftfreq(nfft,1/fs)
    coh=np.zeros(len(f));coh[9]=1.;H=np.full(len(f),.5+0j)
    row=scope['band_switch_table'](nfft,f,H,coh,np.zeros(1),1,fs,2,g,[])[0]
    assert abs(row['on_minus_off_response_db'])>.1
    counter=dict(case='zero coefficients: ON and OFF loops are identical',frequency_hz=float(f[9]),
        gain_q12=817,expected_on_minus_off_db=0.,b_original_on_minus_off_db=row['on_minus_off_response_db'],passed=False)
    packet=blob('bb56ef13300dbfecb6bbd525528a0dcf47ebd7e6','report/verification/audio-replay/lowband2-return.zip')
    data,manifest,model,inventory,unbound=inspect_packet(io.BytesIO(packet))
    coef=np.asarray(model['coefficients_q20'],float)/2**20
    tables=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as directory:
        paths=[]
        for i in range(10,16):
            path=Path(directory)/('seg_%d.npz'%i);path.write_bytes(data['lowband2/'+path.name]);paths.append(path)
        for nfft in (8192,4096):
            f,H,coh,_S,_n,fs=scope['estimate_H'](paths,nperseg=nfft)
            M=scope['model_response'](coef,nfft,lag_first=1);D=np.exp(-2j*2*np.pi*f/fs)
            original=scope['band_switch_table'](nfft,f,H,coh,coef,1,fs,2,g,[(300,1000),(1000,3000),(8200,8600)])
            values=[]
            for lo,hi in ((300,1000),(1000,3000),(8200,8600),(300,fs/2+1)):
                mask=(f>=lo)&(f<hi)&(coh>=.8)
                off=H[mask]/(1-g*D[mask]*H[mask]);on=H[mask]/(1-g*D[mask]*(H[mask]-M[mask]))
                values.append(dict(band='all' if hi>fs/2 else '%d-%d'%(lo,hi),gated_bins=int(mask.sum()),
                    c_white_source_stationary_reference_db=float(10*np.log10(np.sum(abs(on)**2)/np.sum(abs(off)**2)))))
            allowed=original[-1]
            tables.append(dict(nfft=nfft,heldout_ids=list(range(10,16)),b_original=original,c_reference=values,
                sampled_small_gain_headroom_db=dict(off=allowed['off_allowed_db']-20*np.log10(g),
                    on=allowed['on_allowed_db']-20*np.log10(g))))
    saved=json.loads(blob(commit,'report/verification/rc01-r4-2026-10-25/run/prediction.json'))
    result=dict(b_commit=commit,source_sha256=digest(source),hardware_access=False,production_code_modified=False,
        zero_model_control=counter,heldout_references=tables,
        equation=dict(off='H/(1-g*D*H)',on='H/(1-g*D*(H-M))',
            pointwise_on_over_off='(1-g*D*H)/(1-g*D*(H-M))',
            band_power='sum(abs(T_on)^2*Sss)/sum(abs(T_off)^2*Sss)',
            reference_scope='white stationary forcing on qualified bins only; not a finite-window board prediction'),
        saved_allband_worse_bins={k:v[-1]['worse_bins'] for k,v in saved['tables'].items()},
        stable_magnitude_counterexample=dict(loop='1.28*z^-2 - 0.4096*z^-4',closed_denominator='(1-0.64*z^-2)^2',
            poles=[.8,.8,-.8,-.8],loop_abs_at_quarter_rate=1.6896,
            conclusion='magnitude above unity at a sampled frequency does not prove instability or a fixed growth time'),
        review_status='changes_required_new_prediction_only',
        unchanged_decisions=['default model','no new candidate','previous phase/Q20/input/boundary acceptance'],
        required_changes=['include OFF feedback and correct power weighting; zero model must predict zero',
            'headroom is allowed_dB minus actual_gain_dB; omitted bins remain unknown',
            'pair drift gate is not measurement resolution; remove universal 1.5dB effect threshold',
            'protection is not howl; magnitude above unity is not sufficient for instability or guaranteed growth time',
            'reconcile prose with nonzero worse_bins; response window is a subset of 16384-frame tail, not the full run'])
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


def audit_b_revision(source_dir,repro_dir,out):
    """Check B revision 1 against a separate spectral sum and closed-form ratios."""
    source_dir=Path(source_dir);repro_dir=Path(repro_dir)
    provenance=json.loads((source_dir/'c-api-provenance.json').read_text(encoding='utf8'))
    tree=json.loads((source_dir/'c-api-tree.json').read_text(encoding='utf8'))
    assert provenance['b_commit']==tree['commit']
    hashes={e['path']:e['sha'] for e in tree['entries'] if e['type']=='blob'}
    used=['scripts/reproduce_b_screening.py','scripts/diagnose_peak_margin.py',
          'models/room_v1/calibrated_20261024.json',
          'report/verification/rc01-r4-2026-10-25/run-rev1/prediction.json',
          'report/verification/rc01-r4-2026-10-25/revision-1.md']
    source_hashes={}
    for name in used:
        data=(source_dir/name).read_bytes()
        assert hashlib.sha1(('blob %d\0'%len(data)).encode()+data).hexdigest()==hashes[name],name
        source_hashes[name]=digest(data)
    scope={'np':np,'FMIN_HZ':300.}
    diag=(source_dir/used[1]).read_bytes();code=(source_dir/used[0]).read_bytes()
    nodes=[n for n in ast.parse(diag).body if isinstance(n,ast.FunctionDef) and n.name=='positive_real_crossing']
    nodes += [n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and n.name in
              ('model_response_at','band_switch_table','switch_controls')]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'B revision exact AST functions','exec'),scope)
    fs=48828.125;gain=817/4096;f=np.array([429.1534423828125]);coh=np.ones(1);H=np.array([.5+0j])
    zero=scope['band_switch_table'](f,H,coh,np.zeros(1),1,fs,2,gain,[])[0]['on_minus_off_band_db']
    assert abs(zero)<1e-12
    q=np.array([.5]);hp=.5*np.exp(-2j*np.pi*f/fs);D=np.exp(-4j*np.pi*f/fs)
    with np.errstate(divide='ignore',invalid='ignore'):
        perfect=scope['band_switch_table'](f,hp,coh,q,1,fs,2,gain,[])[0]['on_minus_off_band_db']
    perfect_expected=float(20*np.log10(abs(1-gain*D*hp)[0]))
    assert abs(perfect-perfect_expected)<1e-12
    packet=blob('bb56ef13300dbfecb6bbd525528a0dcf47ebd7e6','report/verification/audio-replay/lowband2-return.zip')
    data,manifest,model,_inventory,_unbound=inspect_packet(io.BytesIO(packet))
    coef=np.asarray(model['coefficients_q20'],float)/2**20
    saved=json.loads((source_dir/used[3]).read_text(encoding='utf8'))
    actual=json.loads((repro_dir/'prediction.json').read_text(encoding='utf8'))
    numeric_errors=[];numeric_count=[0]
    def compare(a,b,path='prediction'):
        if isinstance(a,dict):
            assert set(a)==set(b),path
            for k in a:compare(a[k],b[k],path+'.'+k)
        elif isinstance(a,list):
            assert len(a)==len(b),path
            for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'[%d]'%i)
        elif isinstance(a,(float,int)) and not isinstance(a,bool):
            numeric_count[0]+=1;numeric_errors.append(abs(a-b));assert abs(a-b)<1e-10,path
        else:assert a==b,path
    compare(saved,actual)
    inputs=json.loads((repro_dir/'repro.json').read_text(encoding='utf8'))['inputs']
    assert len(inputs)==16 and all(r['sha_match'] is True for r in inputs)
    assert [r['seg_id'] for r in inputs if r['role']=='heldout']==list(range(10,16))
    tables=[];max_model_error=0.;band_errors=[]
    for cohort,ids in (('train',range(10)),('heldout',range(10,16))):
        for nfft in (8192,4096):
            uu=np.zeros(nfft//2+1);mm=uu.copy();um=np.zeros_like(uu,dtype=complex)
            window=np.hanning(nfft);windows=0
            for i in ids:
                with np.load(io.BytesIO(data['lowband2/seg_%d.npz'%i]),allow_pickle=False) as cap:
                    u=np.asarray(cap['reference'],float);m=np.asarray(cap['microphone'],float)
                # Every segment starts a separate set of windows; no concatenation.
                for start in range(0,len(u)-nfft+1,nfft//2):
                    U=np.fft.rfft(u[start:start+nfft]*window);M=np.fft.rfft(m[start:start+nfft]*window)
                    uu+=abs(U)**2;mm+=abs(M)**2;um+=U.conj()*M;windows+=1
            H=um/uu;coherence=abs(um)**2/(uu*mm);freq=np.fft.rfftfreq(nfft,1/fs)
            w=2*np.pi*freq/fs;model_response=np.fft.rfft(coef,nfft)*np.exp(-1j*w);delay=np.exp(-2j*w)
            b_model=scope['model_response_at'](coef,freq,fs,1)
            max_model_error=max(max_model_error,float(np.max(abs(b_model-model_response))))
            off=H/(1-gain*delay*H);on=H/(1-gain*delay*(H-model_response))
            key='%s_nfft%d'%(cohort,nfft);references=[]
            for row,(lo,hi) in zip(saved['tables'][key],((300,1000),(1000,3000),(8200,8600),(300,fs/2+1))):
                eligible=(freq>=lo)&(freq<hi)&(coherence>=.8)
                delta=float(10*np.log10(np.sum(abs(on[eligible])**2)/np.sum(abs(off[eligible])**2)))
                error=abs(delta-row['on_minus_off_band_db']);band_errors.append(error)
                assert error<1e-10 and int(eligible.sum())==row['gated'],key+':'+row['band']
                off_headroom=float(-20*np.log10(np.max(abs(gain*H[eligible]))))
                on_headroom=float(-20*np.log10(np.max(abs(gain*(H-model_response)[eligible]))))
                assert abs(off_headroom-row['off_margin_db'])<1e-10 and abs(on_headroom-row['on_margin_db'])<1e-10
                references.append(dict(band=row['band'],gated_bins=int(eligible.sum()),on_minus_off_db=delta,
                    off_sampled_headroom_db=off_headroom,on_sampled_headroom_db=on_headroom))
            controls=saved['controls'][key]
            assert controls['zero_model_ok'] and controls['perfect_model_ok'] and abs(controls['zero_model_db'])<1e-12
            tables.append(dict(cohort=cohort,nfft=nfft,independent_windows=windows,values=references))
    assert max_model_error<1e-10
    test_text=(ROOT/'report/verification/audio_closed/sprint-rc0-20261025/b-71d6a34-tests.txt').read_text(encoding='utf8')
    test_count=int(re.search(r'Ran (\d+) tests',test_text).group(1))
    assert re.search(r'^OK\s*$',test_text,re.MULTILINE) and 'FAILED' not in test_text
    issues=[dict(id='N1',scope='revision-1.md §2/§5; band_switch_table docstring',
        action='Separate sampled small-gain sufficient-bound reference from positive-real-crossing approximation; remove necessary-condition label and the retained 385dB/s/0.1s assertion, which fails even for linear fixed stable counterexamples. Loop gain dB is actual minus allowed; the old actual-plus-allowed expression was wrong, not merely a loop-gain label.'),
        dict(id='N2',scope='revision-1.md §4/§5',
        action='All-band means qualified bins only. Treat +1dB/two nonnegative repeats as investigation triggers, not calibrated falsification; two-repeat spread is descriptive, not a new resolution cutoff. Protection alone cannot contradict a prediction that omits frequency regions.'),
        dict(id='N3',scope='reproduce_b_screening.py [7], repro.txt and prediction.json',
        action='Machine entry still prints preregistered prediction; label revision 1 and pre_registered=false in emitted text/JSON, retaining the original dbf artifact.')]
    result=dict(b_commit=provenance['b_commit'],source_hashes=source_hashes,source_transport=provenance['source'],
        numerical_checks_passed=True,zero_model_control_db=zero,perfect_model_control_db=perfect,
        perfect_model_expected_db=perfect_expected,original_cli_completed=True,verified_input_files=16,
        original_control_tests=test_count,saved_prediction_numbers_compared=numeric_count[0],
        max_saved_prediction_difference=max(numeric_errors,default=0.),
        max_model_matrix_vs_fft_error=max_model_error,max_independent_band_difference=max(band_errors),
        phase_and_q20_entry_unchanged=diag==blob('6128282f2853b829768c7310e57b08f0d84c4b89','scripts/diagnose_peak_margin.py'),
        tables=tables,publication_changes_required=issues,raw_board_waveform_review='pending five existing NPZ files',
        interpretation='Numerical revision accepted on qualified bins under white stationary linear approximation; publication wording/labels remain open. No preregistered validation or measured MSG/ASG.',
        hardware_access=False,production_B_code_modified=False)
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    return result


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


def audit_return(a_commit, out, revision='r1'):
    """Inspect this sprint's metadata return and declared assets, without PCM or board access."""
    if revision=='r4':return audit_r4_return(a_commit,out)
    a_commit=subprocess.check_output(
        ['git','rev-parse',a_commit],cwd=ROOT).decode().strip()
    packet=blob(a_commit,'report/verification/audio-replay/c-sprint-rc01'+('-'+revision if revision!='r1' else '')+'-return.zip')
    with zipfile.ZipFile(io.BytesIO(packet)) as archive:
        manifest=json.loads(archive.read('return-manifest.json'))
        checks={n:digest(archive.read(n))==h for n,h in manifest['hashes'].items()}
        if not all(checks.values()):raise ValueError('return member hash mismatch')
        state=json.loads(archive.read('summary.json'))
        with zipfile.ZipFile(ROOT/('build/packages/c-sprint-rc01-'+revision+'.zip')) as original:
            frozen=json.loads(original.read('sprint-manifest.json'))
        package_identity=dict(policy=state['policy']==frozen['policy'],plan=state['plan']==frozen['plan'],
            source_commits=state['package_source']==frozen['source_commits'],payload_hashes=state['package_hashes']==frozen['hashes'])
        if not all(package_identity.values()):raise ValueError('returned package identity mismatch')
        trials=[]
        for row in state['trials']:
            name='%02d-%s.status.json'%(row['id'],row['role'])
            side=json.loads(archive.read(name)) if name in archive.namelist() else None
            packed=None if side is None else side.get('clip_counts_raw')
            completed=row.get('completed_frames')
            trials.append(dict(id=row['id'],role=row['role'],category=row['category'],
                acoustic_reasons=row['analysis']['reasons'],path_gate=row.get('path_gate'),
                completed_frames=completed,duration_seconds=None if completed is None else completed/48828.125,
                frames=row.get('frames'),first_frame=row.get('first_frame'),stop_reasons=row['stop_reasons'],
                tail_statistics=row['analysis'].get('tail_statistics'),observation_kind=state.get('observation_kind'),
                capture_window=row['analysis'].get('capture_window'),mic_rms_dbfs=row.get('mic_rms_dbfs'),
                sidecar=side,counts_from_raw=None if packed is None else dict(prediction=packed[0]&65535,
                    residual=packed[0]>>16,gain=packed[1],mix=packed[2])))
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
            explicit_top_level_proxy_field_present=state.get('observation_kind')=='proxy' or any('proxy' in k.lower() for k in state),
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
    if revision=='r2':
        build_paths=['board/audio_replay/v2/'+name for name in ('audio_replay.bit','audio_replay.hwh','timing.txt','utilization.txt','drc.txt')]
        timing=blob(a_commit,build_paths[2]).decode().splitlines()
        header=next(i for i,line in enumerate(timing) if line.strip().startswith('WNS(ns)'))
        values=timing[header+2].split()
        result['v2_build_artifacts']=dict(files={p:digest(blob(a_commit,p)) for p in build_paths},
            timing_wns_ns=float(values[0]),timing_whs_ns=float(values[4]),
            input_ports_without_delay=1,output_ports_without_delay=3,full_external_io_signoff=False,
            hwh_max_run_frames=3000000)
        result['decisions']=dict(workpoint='reported -14 dB runs completed without counters; no human/acoustic acceptance',
            fir='16384 source-off frames present; -38.014 dBFS below -31.8 dBFS floor; longer waiting does not solve eligibility',
            r3='same -14 dB v1 assets; sustained fixed forcing and same-frame source-on response pairs; no lower floors',
            v2='actual bit/hwh hashes matched; inspect later raw evidence and patched driver separately')
        result['missing_for_v2']=['raw evidence and driver acceptance tracked by later fixed commit 1cddd52']
    if revision=='r3':
        result['decisions']=dict(r3='C package input defect: first FIR trial, row 7, failed before driver hardware access; no FIR capture or cleanup sidecar',
            recovery='missing receipt is unverified, not proof that recovery hardware failed; earlier six cleanup receipts passed',
            r4='source 2.50s/run 2.52s, real A validation prefix in selftest, same gates; 14408 source-on frames',
            v2='942fd5b fixed both remaining callback/cancel controls; independent 7/7 passed; integrate exact v2 assets and current-model -14dB 60s')
        result['missing_for_v2']=[]
        result['continuous_acceptance']='historical raw records independently reviewed separately at 1cddd52; current-model run still untested'
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


def audit_r4_return(commit,out):
    commit=subprocess.check_output(['git','rev-parse',commit],cwd=ROOT).decode().strip()
    packet=blob(commit,'report/verification/audio-replay/c-sprint-rc01-r4-return.zip')
    with zipfile.ZipFile(ROOT/'build/packages/c-sprint-rc01-r4.zip') as original:
        frozen=json.loads(original.read('sprint-manifest.json'))
    with zipfile.ZipFile(io.BytesIO(packet)) as archive:
        inventory=json.loads(archive.read('return-manifest.json'))
        member_checks={n:digest(archive.read(n))==h for n,h in inventory['hashes'].items()}
        assert all(member_checks.values())
        s=json.loads(archive.read('summary.json'));rows=s['trials']
        identity=dict(policy=s['policy']==frozen['policy'],plan=s['plan']==frozen['plan'],
            source=s['package_source']==frozen['source_commits'],payloads=s['package_hashes']==frozen['hashes'],
            assets=s['a_assets']==frozen['a_assets'])
        assert all(identity.values())
        sides={r['id']:json.loads(archive.read('%02d-%s.status.json'%(r['id'],r['role']))) for r in rows}
        row_checks=[]
        for r in rows:
            live=r['role']=='continuous-60s';side=sides[r['id']]
            counts=side['counts'] if live else side['clip_counts_raw']
            zero=all(v==0 for v in counts.values()) if live else counts==[0,0,0]
            expected_gain=0 if r['role'] in ('path-gate','listener-off') else 817
            checks=dict(recovered=side.get('recovered' if live else 'recovery_ok') is True,
                no_errors=not any(side.get(k) for k in ('error','cleanup_errors','salvage_errors','save_error')),
                zero_digital_counts=zero,recorded_stop_reasons_empty=not r['stop_reasons'],
                gain=r['gain_q12']==expected_gain,hp=r['hp_volume']==40,
                bit=r['bit_sha256']==frozen['hashes']['audio_replay.bit'],
                model=r['model_sha256']==frozen['hashes']['model.json'],
                q20=r['coefficients_sha256']==frozen['coefficients_sha256'])
            row_checks.append(dict(id=r['id'],role=r['role'],checks=checks,all_ok=all(checks.values())))
        fir=[]
        config=('gain_q12','hp_volume','fixture_id','sample_rate_hz','bit_sha256','model_sha256','coefficients_sha256',
                'source_pcm16_sha256','session_id','scene_sha256','eq_sha256','comparison_id','repeat_id')
        for pair in s['fir_pairs']:
            a=next(r for r in rows if r.get('capture_id')==pair['off_capture_id'])
            b=next(r for r in rows if r.get('capture_id')==pair['on_capture_id'])
            ar,br=a['source_response'],b['source_response']
            geometry=all(r['source_frames']==122070 and r['completed_frames']==123046 and
                r['first_frame']==106662 and r['frames']==16384 and
                r['source_response']['first_frame']==107174 and r['source_response']['end_frame']==121582 and
                r['source_response']['frames']==14408 and r['source_response']['valid'] is True for r in (a,b))
            delta=br['rms_dbfs']-ar['rms_dbfs']
            band={k:br['mic_band_dbfs'][k]-v for k,v in ar['mic_band_dbfs'].items()}
            matched=all(a.get(k) is not None and a[k]==b.get(k) for k in config) and a['bypass'] is True and b['bypass'] is False
            drift=abs(a['gate_mic_over_ref_db']-b['gate_mic_over_ref_db'])
            arithmetic=abs(delta-pair['on_minus_off_response_rms_db'])<1e-12 and all(
                abs(v-pair['on_minus_off_band_response_db'][k])<1e-12 for k,v in band.items())
            fir.append(dict(repeat=pair['repeat'],configuration_matches=matched,geometry_matches=geometry,
                recorded_eligibility_passed=pair['window_comparison_valid'] is True and ar['valid'] and br['valid'],
                pair_path_drift_db=drift,drift_gate_passed=drift<=1.5,difference_arithmetic_matches=arithmetic,
                on_minus_off_response_db=delta,on_minus_off_band_response_db=band))
        c=sides[15];tl=np.asarray(c['timeline'],float)
        live_checks=dict(frames=c['frames_completed']==c['frames_requested']==2929687,
            tail_extent=c['first_frame']==2913303 and c['frames_completed']-c['first_frame']==16384,
            done=c['stop_reason']=='completed' and c['status']==32769,
            timeline_monotone=bool(np.all(np.diff(tl[:,:2],axis=0)>=0)),
            timeline_zero_counts=bool(np.all(tl[:,3:]==0)),
            timeline_no_fault_or_clip_flags=bool(np.all((tl[:,2].astype(np.int64)&((3<<17)|(7<<19)))==0)),
            timeline_endpoint=int(tl[-1,1])==2929687 and tl[-1,0]>=60,
            bound_hwh=c['hwh_sha256']==frozen['hashes']['audio_replay.hwh'],
            correct_mode=c['bypass'] is False and c['zero_coeff'] is False and c['pl_contract']=='v2',
            muted=c['muted'] is True and c['mute_ok'] is True and c['disarm_ok'] is True and c['recovered'] is True)
        live_checks={k:bool(v) for k,v in live_checks.items()}
        gates=[r for r in rows if r['role']=='path-gate']
        gate_check=len(gates)==7 and all(r['path_gate']['passed'] and
            r['path_gate']['end_frame']-r['path_gate']['first_frame']==14920 for r in gates)
        raw={r['file']:r for r in s['raw_files']}
        names=['07-fir-off.npz','09-fir-on.npz','11-fir-on.npz','13-fir-off.npz','15-continuous-60s.npz']
        script=blob(commit,'board/audio_replay/run_rc4_human.sh').decode()
        python=script.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        ask=next(n for n in ast.parse(python).body if isinstance(n,ast.FunctionDef) and n.name=='ask')
        events=[]
        class Clock:
            def sleep(self,seconds):events.append(['sleep_before_start_return',seconds])
        env=dict(time=Clock(),seq={'hearing':0,'real':0},queue=[],wait_for_answer=lambda _: 'UNKNOWN',
            print=lambda *a,**k:events.append(['print',*a]))
        exec(compile(ast.Module(body=[ask],type_ignores=[]),'A exact ask callback','exec'),env)
        answer=env['ask']('02 real-voice 已配置且静音；START才发声')
        result=dict(a_commit=commit,return_zip_sha256=digest(packet),return_zip_bytes=len(packet),
            verification_level='independent return integrity, recorded configuration, register timeline and summary-difference arithmetic; no raw PCM',
            member_hash_checks=member_checks,package_identity=identity,trials=row_checks,
            reported_status=s['status'],reported_checks=s['checks'],fir_pairs=fir,
            continuous=dict(checks=live_checks,register_review_passed=all(live_checks.values()),frames_completed=c['frames_completed'],
                elapsed_s=c['elapsed_s'],timeline_points=len(tl),max_poll_gap_s=c['max_poll_gap_s'],
                tail_frames=16384,waveform_coverage_fraction=16384/c['frames_completed'],
                raw_tail_arithmetic='reported passed by board C wrapper; C raw independent recomputation not_tested'),
            metadata_review_passed=len(rows)==15 and all(r['all_ok'] for r in row_checks) and gate_check and
                len(fir)==2 and all(all(p[k] for k in ('configuration_matches','geometry_matches','recorded_eligibility_passed',
                    'drift_gate_passed','difference_arithmetic_matches')) for p in fir) and all(live_checks.values()),
            raw_npz_received=False,missing_raw_once=[dict(file=n,sha256=raw[n]['sha256'],
                board_absolute_path=sides[int(n[:2])]['capture']) for n in names],
            hearing='PROXY; real_voice/listener/independent_reproduction not_tested',
            a_human_wrapper_review=dict(source_commit=commit,source_sha256=digest(script.encode()),callback_return=answer,
                callback_events=events,speech_cue_before_START_return=True,
                consequence='5s speech cue occurs while A driver remains muted; use C human notebook, or A must move cue after actual arm',
                fixed_source_measurement='A plan proposes live speaking for listener pair; cannot satisfy fixed recorded-source/fixed-gain quantitative comparison'),
            declared_v2_found={'bit_sha256':True,'hwh_sha256':True},
            decisions=dict(engineering='register/cleanup acceptance passed within approved scope; PCM recomputation awaits 5 existing files',
                fir='two recorded valid pairs; differences checked, no MSG/ASG or general improvement claim',
                human='C five-trial package; human speech begins after START, fixed recorded source for listener comparison'),
            measured_msg_db=None,measured_asg_db=None,hardware_access=False)
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


def audit_continuous_records(a_commit, out):
    """Recompute frame/timeline/mapping checks from the three existing raw v2 runs."""
    a_commit=subprocess.check_output(['git','rev-parse',a_commit],cwd=ROOT).decode().strip()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',a_commit,
        'report/verification/audio-replay/v2-runs'],cwd=ROOT).decode().splitlines()
    records=[]
    for name in names:
        if not name.endswith('.status.json'):continue
        side=blob(a_commit,name);state=json.loads(side);capture_name=name.replace('.status.json','.npz')
        capture_blob=blob(a_commit,capture_name)
        with np.load(io.BytesIO(capture_blob),allow_pickle=False) as capture:
            embedded=json.loads(str(capture['metadata_json'].item()))
            arrays={k:np.array(capture[k]) for k in ('microphone','reference','prediction_pcm','residual_pcm')}
        checks={k:embedded.get(k)==state.get(k) for k in ('timeline','first_frame','frames_completed','counts',
            'bit_sha256','hwh_sha256','model_sha256','coefficients_sha256','gain_q12','bypass')}
        frames=state['frames_completed'];first=state['first_frame'];timeline=np.asarray(state['timeline'])
        checks.update(tail_extent=all(x.shape==(16384,) for x in arrays.values()) and frames-first==16384,
            timeline_monotone=bool(np.all(np.diff(timeline[:,0])>=0) and np.all(np.diff(timeline[:,1])>=0)),
            zero_counter_samples=bool(np.all(timeline[:,3:]==0)),
            no_fault_samples=bool(np.all((timeline[:,2].astype(np.int64)&(3<<17))==0)),
            recovered=state['recovered'] is True and state['mute_ok'] is True and state['disarm_ok'] is True)
        checks.update(bit_asset_matches=state['bit_sha256']==digest(blob(a_commit,'board/audio_replay/v2/audio_replay.bit')),
            hwh_asset_matches=state['hwh_sha256']==digest(blob(a_commit,'board/audio_replay/v2/audio_replay.hwh')),
            terminal_read_after_last_poll=int(timeline[-1,1])<=frames and all(v==0 for v in state['counts'].values()),
            completed_frame_count=(frames==state['frames_requested'] if state['stop_reason']=='completed' else frames<state['frames_requested']))
        mic=np.rint(arrays['microphone']*2**23).astype(np.int64)
        ref=np.rint(arrays['reference']*2**23).astype(np.int64)
        v=mic[:-2]*state['gain_q12'];expected=np.sign(v)*((abs(v)+2048)//4096)
        residual_errors=int(np.count_nonzero(arrays['residual_pcm']!=mic))
        reference_errors=int(np.count_nonzero(ref[2:]!=expected))
        checks['bypass_mapping']=state['bypass'] is True and residual_errors==reference_errors==0
        gap=float(np.max(np.diff(timeline[:,0])))
        checks['gap_consistent_with_ms_rounding']=abs(gap-state['max_poll_gap_s'])<.002
        records.append(dict(status_path=name,status_sha256=digest(side),capture_path=capture_name,capture_sha256=digest(capture_blob),
            checks=checks,all_checks=all(checks.values()),seconds_requested=state['seconds_requested'],frames_requested=state['frames_requested'],
            frames_completed=frames,tail_first_frame=first,tail_frames=len(mic),tail_seconds=len(mic)/48828.125,
            waveform_coverage_fraction=len(mic)/frames,timeline_points=len(timeline),max_rounded_sample_gap_s=gap,
            terminal_frames_after_last_poll=frames-int(timeline[-1,1]),
            max_poll_gap_s=state['max_poll_gap_s'],stop_reason=state['stop_reason'],gain_q12=state['gain_q12'],gain_db=state['gain_db'],
            bypass=state['bypass'],model_file=state['model_file'],model_sha256=state['model_sha256'],coefficients_sha256=state['coefficients_sha256'],
            bit_sha256=state['bit_sha256'],hwh_sha256=state['hwh_sha256'],elapsed_s=state['elapsed_s'],
            residual_microphone_mismatches=residual_errors,reference_gain_mismatches=reference_errors,
            reported_stop_latency_s=state.get('stop_latency_s'),
            stop_latency_scope='poll detection to cleanup only; stop-file creation time not independently recorded',
            deployment_model_matches_r3=state['model_sha256']=='c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a'))
    result=dict(a_commit=a_commit,records=records,all_record_checks=len(records)==3 and all(r['all_checks'] for r in records),
        scope='independent raw historical engineering records; -12 dB, bypass, other side model; not r3 acceptance or full-run acoustic evidence',
        driver_identity_in_original_records='not recorded; these runs predate the patched before_start/save-error driver',hardware_access=False)
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--a-commit',default='bb56ef13300dbfecb6bbd525528a0dcf47ebd7e6')
    p.add_argument('--b-commit',default='d033d0047542d5e50654a0333777c48ec08dce21')
    p.add_argument('--return-only',action='store_true')
    p.add_argument('--return-revision',choices=('r1','r2','r3','r4'),default='r1')
    p.add_argument('--continuous-records',action='store_true')
    p.add_argument('--b-prediction',action='store_true')
    p.add_argument('--b-revision-dir',type=Path)
    p.add_argument('--b-repro-dir',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=(audit_b_revision(a.b_revision_dir,a.b_repro_dir,a.output) if a.b_revision_dir else
        audit_b_prediction(a.b_commit,a.output) if a.b_prediction else
        audit_continuous_records(a.a_commit,a.output) if a.continuous_records else
        audit_return(a.a_commit,a.output,a.return_revision) if a.return_only else audit(a.a_commit,a.b_commit,a.output))
    keys=(('b_commit','numerical_checks_passed','saved_prediction_numbers_compared','max_independent_band_difference') if a.b_revision_dir else
        ('b_commit','zero_model_control','review_status') if a.b_prediction else
        ('a_commit','all_record_checks','scope') if a.continuous_records else
        ('a_commit','declared_v2_found','decisions') if a.return_only else ('a_commit','b_commit','npz_count','b_counterexamples','deployment'))
    print(json.dumps({k:result[k] for k in keys},ensure_ascii=False))
