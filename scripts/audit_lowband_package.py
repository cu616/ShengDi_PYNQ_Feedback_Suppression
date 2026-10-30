"""Read-only audit of A's lowband2 ZIP; emits numbers, never captured PCM.

No supplied script is executed. Spectral estimates compare the recorded Q20 model
on an explicit split/grid; they are not a measured stability threshold.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
from closed_tools import rounded_shift
from replay_tools import verify_replay
from room_experiment import gate_metrics,gate_repeatability,write_json

RATE=48828.125
BANDS=((0,300),(300,1000),(1000,2000),(2000,3400),(3400,6000),
       (6000,8200),(8200,8600),(8600,10250),(10250,RATE/2+1))


def digest(data):return hashlib.sha256(data).hexdigest()
def db(value):return float(20*np.log10(max(float(abs(value)),1e-30)))


def load_npz(data):
    with np.load(io.BytesIO(data),allow_pickle=False) as z:
        arrays={k:np.array(z[k]) for k in z.files if k!='metadata_json'}
        m=json.loads(str(z['metadata_json'].item()))
    return arrays,m


def inspect_packet(packet):
    with zipfile.ZipFile(packet) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC mismatch')
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('duplicate ZIP member')
        for n in names:
            p=PurePosixPath(n)
            if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n:
                raise ValueError('unsafe ZIP path')
        blobs={n:z.read(n) for n in names}
    manifest=json.loads(blobs['manifest.json']);bound={}
    for row in manifest['files']:
        name=row['path']
        if name in bound:raise ValueError('duplicate manifest entry')
        data=blobs[name]
        if digest(data)!=row['sha256'] or len(data)!=row['size_bytes']:
            raise ValueError('manifest hash/size mismatch: '+name)
        bound[name]=row
    model=manifest['model'];model_data=blobs[model['file']]
    if digest(model_data)!=model['sha256']:raise ValueError('model file mismatch')
    model_json=json.loads(model_data);q=np.asarray(model_json['coefficients_q20'],dtype='<i4')
    if digest(q.tobytes())!=model['coefficients_q20_sha256']:raise ValueError('model Q20 mismatch')
    inventory=[dict(path=n,sha256=digest(data),size_bytes=len(data),
                    original_file_hash_bound=n in bound or n==model['file'],
                    provenance=bound.get(n,{}).get('provenance','C computed from exact received ZIP'))
               for n,data in sorted(blobs.items())]
    unbound=[n for n in names if n!='manifest.json' and n not in bound and n!=model['file']]
    return blobs,manifest,model_json,inventory,unbound


def phase_crossing_estimate(freqs,response,gate):
    """Adjacent eligible bins only; negative-real crossings are not positive feedback."""
    candidates=[]
    for k in range(len(freqs)-1):
        if not (gate[k] and gate[k+1]):continue
        a,b=response[k:k+2];ia,ib=a.imag,b.imag
        if ia==0:t=0.
        elif ia*ib<0:t=-ia/(ib-ia)
        else:continue
        value=a+t*(b-a)
        if value.real>0:
            candidates.append((float(value.real),float(freqs[k]+t*(freqs[k+1]-freqs[k]))))
    if not candidates:return dict(estimated_db=None,frequency_hz=None,crossings=0)
    amplitude,freq=max(candidates)
    return dict(estimated_db=-db(amplitude),frequency_hz=freq,crossings=len(candidates))


def spectral_estimate(captures,q,nfft,source_on_only=False,include_last_window=True):
    """Average each record separately; no artificial boundary between captures."""
    suu=np.zeros(nfft//2+1);smm=suu.copy();sum_=np.zeros_like(suu,dtype=complex)
    count=0;extents=[];win=np.hanning(nfft)
    for arrays,m in captures:
        ref,mic=arrays['reference'],arrays['microphone'];end=len(ref)
        if source_on_only:
            if m.get('source_schedule_verified') is not True:raise ValueError('source timing unverified')
            end=min(end,m['source_end_frame_exclusive']-m['first_frame']-int(.01*RATE))
        starts=list(range(0,end-nfft+int(include_last_window),nfft//2))
        for start in starts:
            u=np.fft.rfft(ref[start:start+nfft]*win);v=np.fft.rfft(mic[start:start+nfft]*win)
            suu+=abs(u)**2;smm+=abs(v)**2;sum_+=u.conj()*v;count+=1
        extents.append(dict(capture_id=m['capture_id'],available_first_frame=m['first_frame'],
                            available_end_frame=m['first_frame']+end,windows=len(starts)))
    if not count:raise ValueError('no spectral windows')
    H=np.divide(sum_,suu,out=np.zeros_like(sum_),where=suu>0)
    coh=np.divide(abs(sum_)**2,suu*smm,out=np.zeros_like(suu),where=suu*smm>0)
    F=np.fft.rfftfreq(nfft,1/RATE);omega=2*np.pi*F/RATE
    Hhat=np.fft.rfft(q,nfft)*np.exp(-1j*omega)
    E=H-Hhat;eligible=(coh>=.8)&(suu>0)
    def peak(mask):
        ids=np.flatnonzero(mask&eligible)
        if not len(ids):return dict(estimated_db=None,worst_hz=None,selected_bins=0)
        k=int(ids[np.argmax(abs(E[ids]))])
        return dict(estimated_db=-db(E[k]),worst_hz=float(F[k]),selected_bins=len(ids),
                    coherence_at_worst=float(coh[k]))
    comparison=(F>=300)&(F<=10250)
    bands={f'{lo:g}-{hi:g}':dict(**peak((F>=lo)&(F<hi)),
                total_bins=int(np.sum((F>=lo)&(F<hi)))) for lo,hi in BANDS}
    probes=[]
    for target in (0,435,441,3898,8416,9131,12000,20000):
        k=int(np.argmin(abs(F-target)))
        probes.append(dict(requested_hz=target,bin_hz=float(F[k]),H_db=db(H[k]),
                           Hhat_db=db(Hhat[k]),residual_path_db=db(E[k]),coherence=float(coh[k])))
    return dict(nfft=nfft,bin_width_hz=RATE/nfft,window='symmetric Hann; 50% overlap; no demeaning',
                coherence_filter=.8,source_on_only=source_on_only,include_last_window=include_last_window,
                spectral_windows=count,per_record_windows=extents,
                comparison_band_hz=[300,10250],sampled_small_gain_estimate=peak(comparison),bands=bands,
                phase_crossing_estimate=phase_crossing_estimate(F,E*np.exp(-2j*omega),eligible&comparison),
                probes=probes,fullband_certified=False,
                interpretation='Finite-grid prediction with omitted low-coherence bins; not measured MSG/ASG or a physical ceiling')


def record_metrics(name,arrays,m):
    mic=np.rint(arrays['microphone']*2**23).astype(np.int64)
    q=np.asarray(arrays['coefficients_q20'],dtype='<i4') if 'coefficients_q20' in arrays else None
    result=dict(path=name,capture_id=m.get('capture_id'),frames=len(mic),
        first_frame=m.get('first_frame'),completed_frames=m.get('completed_frames'),
        extent_consistent=m.get('frames')==len(mic) and m.get('completed_frames',0)-m.get('first_frame',0)==len(mic),
        gain_q12=m.get('gain_q12'),hp_volume=m.get('hp_volume'),model_sha256=m.get('model_sha256'),
        bit_sha256=m.get('bit_sha256'),source_end_frame_exclusive=m.get('source_end_frame_exclusive'),
        source_schedule_verified=m.get('source_schedule_verified'),
        saved_coefficients_sha256=digest(q.tobytes()) if q is not None else None,
        saved_loaded_taps=len(q) if q is not None else None,mic_rms_dbfs=db(np.std(mic/2**23)),
        mic_peak_dbfs=db(np.max(abs(mic))/2**23),
        mic_full_scale_samples=int(np.sum((mic==-2**23)|(mic==2**23-1))),
        guard_tripped=m.get('guard_tripped'),
        saved_counters={k:m.get(k) for k in ('prediction_saturations','residual_saturations','gain_saturations','mix_saturations')})
    if name.startswith('closed_loop/'):
        raw=np.column_stack([np.rint(arrays[k]*2**23).astype(np.int64) if k in ('reference','microphone')
                             else arrays[k] for k in ('reference','microphone','prediction_pcm','residual_pcm')])
        result['zero_digital_injection_arithmetic']=verify_replay(raw,q,m['bypass'],m['gain_q12'],np.zeros(1,dtype='<i2'),m['first_frame'])
        unclipped=rounded_shift(raw[:-2,3]*m['gain_q12'],12)
        result['saved_gain_stage_clipping_samples']=int(np.sum((unclipped < -2**23)|(unclipped>2**23-1)))
        result['recording_seconds']=len(mic)/RATE
        result['unobserved_first_interval']=[0,m['first_frame']] if m['first_frame'] else None
        result['measured_stability_threshold_db']=None
        result['interpretation']='Saved-window arithmetic/events only. Zero digital injection does not verify external sound off or initial acoustic conditions.'
    return result


def audit(packet,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    blobs,manifest,model,inventory,unbound=inspect_packet(packet)
    q=np.asarray(model['coefficients_q20'],dtype=float)/2**20
    records={n:load_npz(data) for n,data in blobs.items() if n.endswith('.npz')}
    binding_issues=[]
    fields=('actual_gain_q12','hp_volume','bypass','zero_coeff','bit_sha256','model_sha256',
            'coefficients_sha256','frames','completed_frames','source_end_frame_exclusive',
            'source_schedule_verified','guard_tripped','stop_reason','driver_evidence_version')
    for entry in manifest['files']:
        m=records[entry['path']][1]
        for key in fields:
            actual_key='gain_q12' if key=='actual_gain_q12' else key
            if entry.get(key) is not None and entry[key]!=m.get(actual_key):
                binding_issues.append(dict(path=entry['path'],field=key,manifest=entry[key],actual=m.get(actual_key)))
    metrics=[record_metrics(n,*record) for n,record in sorted(records.items())]
    gates=[]
    for n in sorted(name for name in records if name.startswith('gate_tones/')):
        # Gate helper reads a file. Only this raw temporary copy is used, outside the report.
        path=Path(packet).parent/'gate-audit-inputs'/Path(n).name
        path.parent.mkdir(exist_ok=True);path.write_bytes(blobs[n])
        g=gate_metrics(path,manifest['noise_floor_dbfs']);g['path']=n;gates.append(g)
    baseline=gates[0]['rms_dbfs']
    for g in gates:
        g['drift_from_first_db']=g['rms_dbfs']-baseline
        g['would_pass_original_1p5_db_gate']=g['passed'] and abs(g['drift_from_first_db'])<=1.5
    estimates=[]
    for label,ids,nfft,on,last in [
        ('all16_B4096',range(16),4096,False,True),
        ('holdout6_B4096',range(10,16),4096,False,True),
        ('holdout6_source_on4096',range(10,16),4096,True,True),
        ('all16_A8192_legacy_endpoint',range(16),8192,False,False),
        ('holdout6_A8192_legacy_endpoint',range(10,16),8192,False,False),
        ('holdout6_8192_inclusive_endpoint',range(10,16),8192,False,True),
        ('holdout6_source_on8192',range(10,16),8192,True,True)]:
        names=['lowband2/seg_%d.npz'%i for i in ids]
        result=spectral_estimate([records[n] for n in names],q,nfft,on,last)
        result.update(label=label,input_paths=names,uses_training_records=any(i<10 for i in ids))
        estimates.append(result)
    write_json(out/'member-inventory.json',inventory)
    write_json(out/'record-metrics.json',metrics)
    write_json(out/'gate-review.json',dict(gates=gates,repeatability=gate_repeatability(gates),
               maximum_drift_from_first_db=max(abs(g['drift_from_first_db']) for g in gates)))
    write_json(out/'spectral-review.json',dict(model_file_sha256=manifest['model']['sha256'],
        deployed_Q20_sha256=manifest['model']['coefficients_q20_sha256'],
        split_provenance='A manifest declares seg_0..9 train, seg_10..15 valid; audit does not refit',estimates=estimates))
    result=dict(audit_version='c-lowband-audit-1.0.0',source_a_commit='1003728',
        packet_sha256=digest(Path(packet).read_bytes()),members=len(blobs),npz_files=len(records),
        original_manifest_npz_hashes_verified=len(manifest['files']),model_hash_and_Q20_verified=True,
        metadata_binding_issues=binding_issues,
        original_manifest_unbound_members=unbound,manifest_missing_claim=manifest['missing'],
        metadata_missing_fields_retained=True,raw_PCM_written_to_report=False,board_access=False,
        new_field_acquisitions=0,measured_msg_db=None,measured_asg_db=None,
        memory_sweep_independently_reproduced=False,
        memory_sweep_reason='A memory_sweep uses a different 20-segment sideways dataset absent from this 16-segment upright package')
    write_json(out/'audit.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(audit(a.packet,a.output),ensure_ascii=False,indent=2,allow_nan=False))
