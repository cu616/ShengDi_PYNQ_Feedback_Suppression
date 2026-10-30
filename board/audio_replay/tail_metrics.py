"""Descriptive tail statistics with explicit frame/source/quality gates. No I/O."""
import math
import numpy as np

BANDS = ((300, 1000), (1000, 3000), (8200, 8600))
TAIL_CONFIG = dict(block_seconds=.02, minimum_blocks=8,
                   minimum_mic_dbfs=-55., minimum_band_mic_dbfs=-80.)


def empty_tail(reason):
    return dict(tail_valid=False, tail_rms_dbfs=None, tail_slope_db_per_s=None,
                tail_slope_fit_r2=None,
                tail_residual_over_mic_db={f'{a}-{b}': None for a,b in BANDS},
                tail_band_reasons={}, tail_reasons=[reason], tail_config=TAIL_CONFIG)


def tail_statistics(microphone, residual, metadata, rate, residual_wide=False):
    from evaluation import window_gate
    out = empty_tail('unvalidated_tail')
    effective_config=dict(TAIL_CONFIG)
    try:
        mic, err = np.asarray(microphone), np.asarray(residual)
        if (mic.ndim != 1 or mic.shape != err.shape or mic.dtype.kind not in 'iu'
            or err.dtype.kind not in 'iu' or not len(mic)
            or np.any(mic < -2**23) or np.any(mic >= 2**23)
            or np.any(err < -(2**24 if residual_wide else 2**23))
            or np.any(err >= (2**24 if residual_wide else 2**23))):
            raise ValueError('invalid_tail_pcm')
        gate = window_gate(metadata, rate, len(mic))
        if not gate['pure_tail']: raise ValueError(gate['reason'])
        if metadata.get('external_source_off_verified') is not True:
            raise ValueError('external_source_off_unverified')
        if metadata.get('external_source_active') is True:
            raise ValueError('external_source_active')
        if metadata.get('dropped_frames',0): raise ValueError('missing_frames')
        indices = metadata.get('frame_indices')
        if indices is not None:
            ix=np.asarray(indices)
            if (ix.shape!=mic.shape or ix.dtype.kind not in 'iu'
                or ix[0]!=gate['first_frame'] or ix[-1]+1!=gate['end_frame']
                or np.any(np.diff(ix)!=1)):
                raise ValueError('invalid_frame_indices')
        clipped_channels = (mic,) if residual_wide else (mic, err)
        if any(np.any((x==-2**23)|(x==2**23-1)) for x in clipped_channels):
            raise ValueError('tail_clipped')
        nblock=max(2,round(rate*TAIL_CONFIG['block_seconds']))
        blocks=len(mic)//nblock
        if blocks<TAIL_CONFIG['minimum_blocks']: raise ValueError('tail_too_short')
        x=mic.astype(float)/2**23; y=err.astype(float)/2**23
        x-=x.mean(); y-=y.mean()
        rms=float(np.sqrt(np.mean(x*x)))
        if not rms: raise ValueError('zero_microphone_energy')
        level=20*math.log10(rms)
        floor=TAIL_CONFIG['minimum_mic_dbfs']
        if 'noise_floor_dbfs' in metadata:
            noise=float(metadata['noise_floor_dbfs'])
            if not math.isfinite(noise):raise ValueError('invalid_noise_floor')
            floor=max(floor,noise+6.)
        effective_config['minimum_mic_dbfs']=floor
        out['tail_config']=effective_config
        if level<floor: raise ValueError('tail_below_signal_floor')
        # DC is removed independently within each block for the slope.
        frames=mic[:blocks*nblock].astype(float).reshape(blocks,nblock)/2**23
        frames-=frames.mean(axis=1,keepdims=True)
        levels=np.sqrt(np.mean(frames*frames,axis=1))
        if np.any(levels<10**(floor/20)):
            raise ValueError('slope_blocks_below_signal_floor')
        db=20*np.log10(levels)
        times=(np.arange(blocks)*nblock+(nblock-1)/2)/rate
        centered=times-times.mean()
        slope=float(np.dot(centered,db-db.mean())/np.dot(centered,centered))
        variance=float(np.sum((db-db.mean())**2))
        fit=None if variance<1e-15 else max(0.,1-float(np.sum((db-(db.mean()+slope*centered))**2))/variance)
        out.update(tail_rms_dbfs=level,tail_slope_db_per_s=slope,tail_slope_fit_r2=fit,
                   tail_reasons=[],tail_first_frame=gate['first_frame'],tail_end_frame=gate['end_frame'],
                   tail_frames=len(mic),tail_slope_frames=blocks*nblock)
        window=np.hanning(len(x)); freq=np.fft.rfftfreq(len(x),1/rate)
        xp=np.abs(np.fft.rfft(x*window))**2; yp=np.abs(np.fft.rfft(y*window))**2
        scale=2/(len(x)*np.sum(window**2))
        for low,high in BANDS:
            key=f'{low}-{high}';mask=(freq>=low)&(freq<high)
            if high>rate/2 or not mask.any():
                out['tail_band_reasons'][key]='band_unavailable';continue
            denom=float(xp[mask].sum()); numer=float(yp[mask].sum())
            if denom*scale<10**(TAIL_CONFIG['minimum_band_mic_dbfs']/10):
                out['tail_band_reasons'][key]='band_below_signal_floor';continue
            if not numer:
                out['tail_band_reasons'][key]='zero_residual_energy_finite_db_undefined';continue
            out['tail_residual_over_mic_db'][key]=10*math.log10(numer/denom)
        out['tail_valid']=all(v is not None for v in out['tail_residual_over_mic_db'].values())
        if not out['tail_valid']:out['tail_reasons'].append('one_or_more_bands_unavailable')
    except (ValueError,TypeError,OverflowError) as exc:
        out=empty_tail(str(exc))
    out['tail_config']=effective_config
    out['residual_semantics']='wide25_pre_gain' if residual_wide else 'captured_clamped24'
    return out
