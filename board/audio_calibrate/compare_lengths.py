"""Run next to calibration.py and existing NPZ files; NO audio hardware access.

Usage in Jupyter: %run compare_lengths.py
Reuses inspected validation data for development, not final acceptance.
"""
import json
from pathlib import Path
import numpy as np
from calibration import load_capture, fit_path, evaluate_path, fixed_fir, quantize_coefficients, predict


def compare_lengths():
    train=load_capture('training_box_v1.npz')
    valid=load_capture('validation_box_v1.npz')
    output=Path('length_comparison_v1.json')
    if output.exists():
        raise FileExistsError('Keep the previous result; choose a new output name before rerunning')
    rows=[]
    for taps in (128,256,512):
        print('FITTING_TAPS',taps,flush=True)
        model=fit_path(train,taps)
        metrics=evaluate_path(model,valid,train)
        # Capture values are exact PCM/2^23; rint recovers integers without new quantization.
        u=np.rint(valid.reference*2**23).astype(np.int64)
        mic=np.rint(valid.microphone*2**23).astype(np.int64)
        pred,psat=fixed_fir(u,quantize_coefficients(model['coefficients']))
        delta=mic-pred.astype(np.int64)
        rsat=int(np.count_nonzero((delta < -2**23)|(delta > 2**23-1)))
        # 统一跳过512帧，确保不同长度在同一批样本上比较。
        error=np.clip(delta,-2**23,2**23-1)[512:]/2**23-model['bias']
        target=valid.microphone[512:]-model['bias']
        float_error=target-predict(valid.reference,model['coefficients'])[512:]
        row=dict(taps=taps,common_warmup_frames=512,
            float_prediction_db=float(20*np.log10(np.linalg.norm(target)/max(np.linalg.norm(float_error),1e-15))),
            integer_prediction_db=float(20*np.log10(np.linalg.norm(target)/max(np.linalg.norm(error),1e-15))),
            prediction_saturations=psat,residual_saturations=rsat,core_cycles=3*taps+3)
        rows.append(row); print(json.dumps(row),flush=True)
    with output.open('x') as f:
        json.dump(dict(rows=rows,interpretation='Development data reused; not final independent acceptance or ASG'),f,indent=2)
    print('LOCAL_RESULTS_SAVED',str(output),'NO_AUDIO_PLAYED_NO_RECORDING_UPLOADED')


if __name__=='__main__': compare_lengths()
