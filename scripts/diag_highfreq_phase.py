"""Read-only open-loop audit. No PYNQ imports, playback or sample realignment.

Default board command:
 python3 diag_highfreq_phase.py --board-scene --out /tmp/hf-phase.json
JSON contains derived spectra and coefficients, never microphone/reference PCM.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

SCENE = '6b2e43d4b77c4b73b84923ea17d4a5e6'
MODEL_SHA = 'ba432ad195711069c5160480b21eb6ec2073c423144d4e21f15e93b8b2799580'
COEFF_SHA = '6507565c444929737d8b44486c7064d4226792070e4f6eac8a3f84827287f1cf'
POINTS = (400, 4000, 8000, 8350, 8500, 9000)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def find_model(roots, expected):
    matches = []
    for root in roots:
        for p in sorted(root.rglob('*.json')):
            if p.is_file() and p.stat().st_size < 1000000 and sha(p) == expected:
                matches.append(p)
    if not matches:
        raise ValueError('MATCHING_MODEL_NOT_FOUND sha256=' + expected)
    return matches[0]


def read_model(path, expected=None, expected_q=None):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected and digest != expected:
        raise ValueError('MODEL_HASH_MISMATCH')
    m = json.loads(raw.decode('utf-8-sig'))
    q0 = np.asarray(m['coefficients_q20'])
    if q0.ndim != 1 or not np.isfinite(q0).all() or np.any(q0 != np.floor(q0)):
        raise ValueError('INVALID_Q20')
    if np.any(q0 < -(1 << 23)) or np.any(q0 >= 1 << 23):
        raise ValueError('Q20_OUT_OF_RANGE')
    q = q0.astype('<i4')
    qdigest = hashlib.sha256(q.tobytes()).hexdigest()
    if expected_q and qdigest != expected_q:
        raise ValueError('COEFFICIENT_HASH_MISMATCH')
    if len(q) != m['taps'] or int(m['lag_first']) != m['lag_first'] or m['lag_first'] < 0:
        raise ValueError('INVALID_MODEL_SHAPE_OR_LAG')
    fs = float(m['sample_rate_hz'])
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError('INVALID_SAMPLE_RATE')
    return q.astype(float) / 2**20, int(m['lag_first']), fs, {
        'path': str(path), 'sha256': digest, 'coefficients_sha256': qdigest,
        'coefficients_q20': q.tolist(), 'taps': len(q), 'lag_first': int(m['lag_first']),
        'sample_rate_hz': fs, 'fixture_id': m.get('fixture_id'), 'hp_volume': m.get('hp_volume')}


def stage_for(path):
    # Stage comes from the recorded file name, never from array contents.
    name = path.stem.lower()
    if re.search(r'training(?:_|\d|$)', name):
        return 'training'
    if re.search(r'validation(?:_|\d|$)', name):
        return 'validation'
    return None


def read_capture(path, fs, model_info):
    with np.load(path, allow_pickle=False) as z:
        u, m = np.asarray(z['reference']), np.asarray(z['microphone'])
        md = json.loads(str(z['metadata_json'].item()))
        rate = float(z['sample_rate_hz'])
        if u.dtype.kind != 'f' or m.dtype.kind != 'f':
            raise ValueError('PCM_UNITS_REQUIRE_NORMALIZED_FLOAT')
        if u.ndim != 1 or m.shape != u.shape or not np.isfinite(u).all() or not np.isfinite(m).all():
            raise ValueError('INVALID_PAIR_SHAPE_OR_VALUES')
        if rate != fs or float(md.get('sample_rate_hz', rate)) != fs:
            raise ValueError('SAMPLE_RATE_MISMATCH')
        if md.get('forward_path_open') is not True or md.get('gain_q12') != 0:
            raise ValueError('NOT_OPEN_LOOP_GAIN_ZERO')
        if md.get('zero_coeff') is not True or md.get('source') != 'board':
            raise ValueError('NOT_BOARD_ZERO_MODEL_CALIBRATION')
        if md.get('stop_reason') != 'completed' or md.get('dropped_frames', 0) != 0:
            raise ValueError('CAPTURE_NOT_COMPLETED_OR_DROPPED')
        if md.get('input_full_scale_seen') or md.get('mic_full_scale_samples', 0):
            raise ValueError('INPUT_CLIPPED')
        for key in ('prediction_saturations', 'gain_saturations', 'mix_saturations'):
            if md.get(key, 0):
                raise ValueError('CAPTURE_SATURATED_' + key)
        if np.any(np.abs(u) >= 1) or np.any(m <= -1) or np.any(m >= 1 - 2**-23):
            raise ValueError('NORMALIZED_PCM_CLIPPED')
        for key in ('fixture_id', 'hp_volume'):
            if model_info.get(key) is not None and md.get(key) != model_info[key]:
                raise ValueError('CONFIG_MISMATCH_' + key)
        first = int(md['first_frame'])
        end = int(md.get('source_end_frame_exclusive', md.get('source_frames', -1)))
        if 'source_pcm16' in z.files:
            source_len = len(z['source_pcm16'])
            if end != -1 and end != source_len:
                raise ValueError('SOURCE_WINDOW_METADATA_MISMATCH')
            end = source_len
        if first < 0 or end <= first:
            raise ValueError('SOURCE_WINDOW_UNKNOWN_OR_EMPTY')
        n = min(len(u), end - first)
        if not np.any(u[:n]):
            raise ValueError('ZERO_REFERENCE')
        keys = ('capture_id', 'fixture_id', 'hp_volume', 'gain_q12', 'first_frame',
                'aux_input_gain_db', 'aux_raw_left', 'aux_raw_right', 'driver_sha256', 'bit_sha256',
                'source_pcm16_sha256', 'verification')
        info = {k: md[k] for k in keys if k in md}
        info.update(path=str(path), sha256=sha(path), source_window_frames=n,
                    capture_frames=len(u), alignment='unchanged_same_frame')
        return u[:n].astype(float), m[:n].astype(float), info


def model_H(h, f, fs, lag):
    return np.exp(-2j * np.pi * np.outer(f / fs, np.arange(len(h)) + lag)).dot(h)


def spectra(u, m, h, lag, nfft):
    # Build prediction from the actual reference, excluding unknown pre-capture history.
    impulse = np.r_[np.zeros(lag), h]
    pred = np.convolve(u, impulse)[:len(u)]
    warmup = len(impulse) - 1
    if len(u) - warmup < nfft + nfft // 2:
        raise ValueError('INSUFFICIENT_STEADY_WINDOWS')
    win = np.hanning(nfft + 1)[:-1]
    sums = np.zeros((4, nfft // 2 + 1), dtype=complex)
    windows = 0
    for start in range(warmup, len(u) - nfft + 1, nfft // 2):
        chunk = np.stack([u[start:start+nfft], m[start:start+nfft], pred[start:start+nfft]])
        chunk -= chunk.mean(axis=1, keepdims=True)
        U, M, P = np.fft.rfft(chunk * win, axis=1)
        sums += np.array([np.abs(U)**2, M * U.conj(), np.abs(M)**2, P * U.conj()])
        windows += 1
    return sums, windows, warmup


def phase_slopes(f, H, Hh, coh, fs):
    # Never unwrap across rejected gaps. Slopes describe response differences, not a cause.
    good = (coh >= .8) & (np.abs(H) > 1e-8) & (np.abs(Hh) > 1e-8)
    out = []
    for lo, hi in ((300, 2000), (8000, 8800)):
        ids = np.flatnonzero(good & (f >= lo) & (f <= hi))
        for run in np.split(ids, np.flatnonzero(np.diff(ids) > 1) + 1):
            if len(run) < 8:
                continue
            phase = np.unwrap(np.angle(H[run] * Hh[run].conj()))
            slope, intercept = np.polyfit(f[run], phase, 1)
            rms = np.sqrt(np.mean((phase - (slope*f[run] + intercept))**2))
            out.append({'first_hz': float(f[run[0]]), 'last_hz': float(f[run[-1]]),
                        'bins': len(run), 'equivalent_delay_samples': float(-slope*fs/(2*np.pi)),
                        'fit_rms_deg': float(np.degrees(rms)),
                        'interpretation': 'descriptive slope; not proof of a digital alignment fault'})
    return out


def response_report(sums, windows, h, lag, fs, nfft, gain, forward_delay):
    f = np.fft.rfftfreq(nfft, 1/fs)
    power = sums[0].real
    valid = power > max(float(power.max()) * 1e-12, 1e-30)
    H = np.divide(sums[1], power, out=np.zeros_like(sums[1]), where=valid)
    # Window-matched prediction diagnoses finite-window bias in analytic-Hhat subtraction.
    Hmatched = np.divide(sums[3], power, out=np.zeros_like(sums[3]), where=valid)
    Hh = model_H(h, f, fs, lag)
    denom = power * sums[2].real
    coh = np.divide(np.abs(sums[1])**2, denom, out=np.zeros_like(power), where=denom > 0)
    coh = np.clip(coh, 0, 1)
    E = H-Hh
    loop = gain * E * np.exp(-2j*np.pi*f/fs*forward_delay)
    rows = []
    for i in np.flatnonzero((f >= 150) & (f <= 10000)):
        angle = float(np.degrees(np.angle(H[i]*Hh[i].conj()))) if abs(H[i]*Hh[i]) > 1e-20 else None
        a, b, r = abs(H[i]), abs(Hh[i]), abs(E[i])
        cosine = np.sqrt(max(0., a*a+b*b-2*a*b*np.cos(np.radians(angle)))) if angle is not None else r
        rows.append({'grid_hz': float(f[i]), 'reference_excited': bool(valid[i]),
                     'reference_power': float(power[i]/windows), 'coherence': float(coh[i]),
                     'H_re': float(H[i].real), 'H_im': float(H[i].imag),
                     'Hh_re': float(Hh[i].real), 'Hh_im': float(Hh[i].imag),
                     'H_abs': float(a), 'Hh_abs': float(b), 'phase_diff_deg': angle,
                     'residual_abs': float(r), 'cosine_identity_error': float(abs(cosine-r)),
                     'window_matched_residual_abs': float(abs(H[i]-Hmatched[i])),
                     'estimated_loop_abs': float(abs(loop[i])),
                     'estimated_loop_phase_deg': float(np.degrees(np.angle(loop[i]))),
                     'distance_to_positive_feedback_point': float(abs(1-loop[i]))})
    return {'windows': windows, 'rows': rows, 'phase_slopes': phase_slopes(f,H,Hh,coh,fs),
            'interpretation': 'sampled open-loop estimates; no stability, MSG or ASG certification'}


def analyze(run_dir, model_path, expected=None, expected_q=None, nfft=4096, gain_q12=5786, forward_delay=2):
    h, lag, fs, mi = read_model(model_path, expected, expected_q)
    outputs, groups, ignored = [], {}, []
    seen = set()
    for path in sorted(Path(run_dir).rglob('*.npz')):
        stage = stage_for(path)
        if stage is None:
            ignored.append(str(path)); continue
        u, m, info = read_capture(path, fs, mi)
        cid = info.get('capture_id')
        if not cid or cid in seen:
            raise ValueError('MISSING_OR_DUPLICATE_CAPTURE_ID ' + str(path))
        seen.add(cid)
        sums, windows, warmup = spectra(u,m,h,lag,nfft)
        report = response_report(sums,windows,h,lag,fs,nfft,gain_q12/4096,forward_delay)
        ncor = 1 << (2*len(u)-1).bit_length()
        cross = np.fft.irfft(np.fft.rfft(m,ncor)*np.fft.rfft(u,ncor).conj(),ncor)
        peak = int(np.argmax(np.abs(cross)))
        peak = peak-ncor if peak > ncor//2 else peak
        info.update(stage=stage, warmup_excluded_frames=warmup,
                    correlation_peak_lag_samples=peak,
                    model_peak_lag_samples=int(np.argmax(np.abs(h)))+lag,
                    lag_note='descriptive correlation peak; no samples shifted',analysis=report)
        outputs.append(info)
        if stage not in groups:
            groups[stage] = [sums.copy(), windows]
        else:
            groups[stage][0] += sums; groups[stage][1] += windows
    if not outputs:
        raise ValueError('NO_TRAINING_OR_VALIDATION_CAPTURES')
    return {'schema_version': 2, 'script_sha256': sha(__file__), 'model': mi,
            'nfft': nfft, 'window': 'periodic Hann; per-window mean removed; 50% overlap',
            'gain_q12': gain_q12, 'assumed_forward_delay_samples': forward_delay,
            'alignment': 'no sample shift; model lag_first applied once',
            'files': outputs, 'ignored_noncalibration_files': ignored,
            'groups': {key: response_report(s,w,h,lag,fs,nfft,gain_q12/4096,forward_delay)
                       for key,(s,w) in groups.items()},
            'limitations': ['No hardware access or new experiment.',
                           'Missing metadata cannot establish unchanged hardware state.',
                           'Per-file results take precedence over pooled spectra for path variation.',
                           'Frequency samples and high coherence alone do not certify stability.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board-scene', action='store_true')
    p.add_argument('--run-dir', type=Path)
    p.add_argument('--model', type=Path)
    p.add_argument('--model-sha256', default=MODEL_SHA)
    p.add_argument('--coefficients-sha256', default=COEFF_SHA)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--nfft', type=int, default=4096)
    args = p.parse_args()
    if args.nfft < 256 or args.nfft % 2:
        p.error('nfft must be even and >=256')
    if args.board_scene:
        base = Path.home()/'.local/state/shengdi'
        args.run_dir = base/'runs'/SCENE/'io'
        roots = [base/'runs'/SCENE, base/'models', base/'compute']
        args.model = find_model(roots,args.model_sha256)
    if args.run_dir is None or args.model is None:
        p.error('use --board-scene or supply --run-dir and --model')
    if args.out.exists():
        p.error('output already exists; choose a new filename')
    result = analyze(args.run_dir,args.model,args.model_sha256,args.coefficients_sha256,nfft=args.nfft)
    with args.out.open('x',encoding='utf-8') as out:
        json.dump(result,out,ensure_ascii=False,indent=1,allow_nan=False)
    print('MODEL_SHA256',result['model']['sha256'])
    print('COEFFICIENTS_SHA256',result['model']['coefficients_sha256'])
    for rec in result['files']:
        print('CAPTURE',rec['stage'],rec['capture_id'],'windows',rec['analysis']['windows'])
        for hz in POINTS:
            r = min(rec['analysis']['rows'],key=lambda x:abs(x['grid_hz']-hz))
            print('%8.2f Hz H=%.5f Hhat=%.5f dphi=%+.2f residual=%.5f matched=%.5f coh=%.4f' %
                  (r['grid_hz'],r['H_abs'],r['Hh_abs'],r['phase_diff_deg'] or 0,
                   r['residual_abs'],r['window_matched_residual_abs'],r['coherence']))
    print('DERIVED_JSON',str(args.out),'NO_PCM_EXPORTED; NO_HARDWARE_ACCESSED')


if __name__ == '__main__':
    main()
