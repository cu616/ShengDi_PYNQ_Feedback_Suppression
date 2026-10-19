"""Offline ablations: path length / full integer residual / changed-path NLMS.

Real capture comparisons reuse an already inspected validation set, so report
development metrics only. Never claim a new independent final acceptance test.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from feedback.calibration import Capture, load_capture, fit_path, evaluate_path, predict, quantize_coefficients
from feedback.cancellation import cancel_fixed, nlms_open_loop


def reduction(target, error):
    return float(20*np.log10(np.linalg.norm(target)/max(np.linalg.norm(error), 1e-15)))


def synthetic_capture(seed, h, frames=16384):
    rng = np.random.default_rng(seed)
    u = rng.uniform(-0.06, 0.06, frames)
    d = np.convolve(u, np.r_[0,h])[:frames] + rng.normal(0, 0.0005, frames)
    return Capture(u, d, 48828.125, dict(schema_version=1,capture_id='synthetic-%s'%seed,
        source='synthetic',forward_path_open=True,alignment='same_i2s_frame',dropped_frames=0))


def compare(train, validation):
    rows=[]
    warmup=512  # 所有长度评价相同区间，避免起始样本不同干扰比较。
    for taps in (128,256,512):
        model=fit_path(train,taps)
        metrics=evaluate_path(model,validation,train)
        # Signed PCM conversion uses ties away from zero, with range already checked.
        pcm=lambda x: (np.sign(x)*np.floor(np.abs(x)*(2**23)+0.5)).astype(np.int64)
        u,mic=pcm(validation.reference),pcm(validation.microphone)
        pred,res,rsat=cancel_fixed(u,mic,quantize_coefficients(model['coefficients']))
        target=validation.microphone[warmup:]-model['bias']
        float_error=target-predict(validation.reference,model['coefficients'])[warmup:]
        integer_error=res[warmup:]/2**23-model['bias']
        rows.append(dict(taps=taps, floating_db=reduction(target,float_error),
            common_warmup_frames=warmup,
            full_integer_db=reduction(target,integer_error),
            residual_saturated_samples=int(rsat.sum()),
            coefficient_abs_max=float(np.max(np.abs(model['coefficients']))),
            estimated_core_cycles=3*taps+3,
            frame_budget_cycles=2048))
    return rows


def adaptation_experiment():
    # Controlled independent excitation, not speech-fed closed-loop audio.
    taps,n,change=128,16000,8000
    h=np.zeros(taps); h[20:24]=[0.5,-0.2,0.1,0.05]; h[70]=0.12
    changed=np.roll(h,7)*0.85
    cap=synthetic_capture(991,h,n)
    d=cap.microphone.copy()
    d[change:]=np.convolve(cap.reference,np.r_[0,changed])[:n][change:]
    d[change:]+=np.random.default_rng(72).normal(0,0.0005,n-change)
    fixed=predict(cap.reference,h)
    adaptive,final,stats=nlms_open_loop(cap.reference,d,h,np.ones(n,bool),mu=0.2)
    # Known extra voice-like independent source, with explicit update freeze.
    speech=0.02*np.sin(2*np.pi*np.arange(n)*211/48828.125)
    freeze=np.zeros(n,bool)
    frozen,unchanged,_=nlms_open_loop(cap.reference,d+speech,h,freeze)
    assert np.array_equal(unchanged,h)
    tail=slice(n-2048,n)
    return dict(source='synthetic_independent_open_loop_excitation',
        path_change_frame=change, fixed_tail_db=reduction(d[tail],(d-fixed)[tail]),
        adaptive_tail_db=reduction(d[tail],(d-adaptive)[tail]),
        final_coefficient_l2_error=float(np.linalg.norm(final-changed)),
        freeze_coefficients_exact=True, **stats,
        limitation='No closed-loop decorrelation or automatic double-talk detector; not a deployable AFC.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training',type=Path); parser.add_argument('--validation',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if bool(args.training)!=bool(args.validation): parser.error('provide both captures')
    if args.output.exists(): parser.error('output exists')
    if args.training:
        train,valid=load_capture(args.training),load_capture(args.validation)
    else:
        rng=np.random.default_rng(133)
        h=rng.normal(0,0.025,512)*np.exp(-np.arange(512)/200)
        h[:30]=0; h[67]+=0.5; h[330]+=0.12
        train,valid=synthetic_capture(8,h),synthetic_capture(9,h)
    result=dict(source=train.metadata['source'], length_ablation=compare(train,valid),
        adaptation=adaptation_experiment(),
        interpretation='Development comparisons, not final independent acceptance or ASG')
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
