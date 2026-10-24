"""Read fixed Git objects and existing ZIP; never run a supplied entry point.

B's functions are loaded from its exact Git blob with AST, not copied/forked.
Expected crossing results come from the signs of the real/imaginary parts.
"""
import argparse
import ast
import json
import platform
from pathlib import Path
import subprocess
import sys

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
                              ('last-bin-on-positive-real-axis',[10.,0.],[True,True])]:
        f=400.+10*np.arange(len(phases));mag=np.ones(len(f))*.5
        if 'positive_real_crossing' in funcs:
            threshold,frequency=funcs['positive_real_crossing'](mag*np.exp(1j*np.deg2rad(phases)),f,np.array(gate))
        else:
            threshold,frequency=funcs['phase_consistent_threshold'](mag,np.deg2rad(phases),f,np.array(gate))
        expected=name in ('positive-real-control','last-bin-on-positive-real-axis'); finite=bool(np.isfinite(threshold))
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
    for label,coefficients in [('all16_old_candidate_cross_session',old_q),
                                ('all16_no_cancellation',np.zeros_like(old_q))]:
        for nfft in (4096,8192):
            names=['lowband2/seg_%d.npz'%i for i in range(16)]
            estimate=spectral_estimate([records[n] for n in names],coefficients,nfft)
            estimate.update(split=label,input_paths=names)
            estimates.append(estimate)
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
            b_main_uses_float_coefficients=True),
        boundaries=dict(independent_record_spectral_energy=separate,
            fabricated_concatenated_spectral_energy=concatenated,
            expected_legal_windows=0,concatenation_produces_illegal_window=concatenated>0,
            original_memory_script_sha256=digest(memory_source),
            inspected_concatenation_lines=[dict(line=i,text=line.strip())
                for i,line in enumerate(memory_source.decode('utf8').splitlines(),1) if 'concatenate' in line],
            memory_sweep_reproduced=False,
            missing='sideways 20 records, model, exact ordered scan list, train/valid IDs and filter edge provenance'),
        historical_closed=closed,spectral_estimates=estimates,
        interpretation='Phase estimates and sampled small-gain predictions omit unqualified bins; no fullband certification or measured MSG/ASG.',
        measured_msg_db=None,measured_asg_db=None)
    (out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--a-commit',default='bb56ef13300dbfecb6bbd525528a0dcf47ebd7e6')
    p.add_argument('--b-commit',default='d033d0047542d5e50654a0333777c48ec08dce21')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.a_commit,a.b_commit,a.output)
    print(json.dumps({k:result[k] for k in ('a_commit','b_commit','npz_count','b_counterexamples','deployment')},ensure_ascii=False))
