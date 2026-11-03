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
STALE_FIXTURE = '9dc20d41edc047b6a86db0b242c95ea8'
POINTS = (400, 4000, 4134, 4148, 4200, 8000, 8350, 8500, 9000)


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


def receipt_inputs(receipt_path, run_dir, model_info):
    """Use the completed scene's final training/validation lists, not all attempts.

    This verifies file membership, not an unchanged physical fixture. The original
    driver fixture label is retained separately even when the receipt repairs its
    scene association for the one documented historical bug.
    """
    receipt_path = Path(receipt_path)
    record = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
    scene = model_info['fixture_id']
    bundle = record.get('bundle') or {}
    if record.get('scene_id') != scene or bundle.get('scene_id') != scene:
        raise ValueError('RECEIPT_SCENE_MISMATCH')
    if (bundle.get('model_sha256') != model_info['sha256'] or
            bundle.get('coefficients_sha256') != model_info['coefficients_sha256']):
        raise ValueError('RECEIPT_MODEL_IDENTITY_MISMATCH')
    selected, seen, source_sets = [], set(), {}
    root = Path(run_dir).resolve()
    for stage in ('training', 'validation'):
        items = record.get(stage)
        if not isinstance(items, list) or not items:
            raise ValueError('RECEIPT_MISSING_' + stage)
        source_sets[stage] = set()
        for entry in items:
            candidates = [Path(entry[k]).resolve() for k in ('path','original_path') if entry.get(k)]
            matches = []
            for path in candidates:
                try:
                    path.relative_to(root)
                except ValueError:
                    continue
                if path.is_file() and sha(path) == entry.get('sha256'):
                    matches.append(path)
            if not matches:
                raise ValueError('RECEIPT_CAPTURE_HASH_OR_PATH_MISMATCH ' + str(entry.get('path')))
            path = matches[0]
            if path in seen:
                raise ValueError('RECEIPT_DUPLICATE_CAPTURE')
            seen.add(path)
            label = stage_for(path)
            if label is not None and label != stage:
                raise ValueError('RECEIPT_STAGE_MISMATCH')
            source_sha = entry.get('source_sha256')
            if source_sha:
                source_sets[stage].add(source_sha)
            selected.append((path, stage, {
                'receipt_path': str(receipt_path), 'receipt_sha256': sha(receipt_path),
                'scene_id': scene, 'model_sha256': bundle['model_sha256'],
                'coefficients_sha256': bundle['coefficients_sha256'],
                'capture_sha256': entry['sha256'], 'stage': stage,
                'receipt_capture_id': entry.get('capture_id'), 'source_sha256': source_sha}))
    if source_sets['training'] & source_sets['validation']:
        raise ValueError('RECEIPT_TRAIN_VALIDATION_SOURCE_OVERLAP')
    return selected


def read_capture(path, fs, model_info, provenance=None):
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
        if model_info.get('hp_volume') is not None and md.get('hp_volume') != model_info['hp_volume']:
            raise ValueError('CONFIG_MISMATCH_hp_volume')
        fixture_note = None
        if model_info.get('fixture_id') is not None and md.get('fixture_id') != model_info['fixture_id']:
            known_case = (model_info['fixture_id'] == SCENE and
                          model_info['sha256'] == MODEL_SHA and
                          model_info['coefficients_sha256'] == COEFF_SHA and
                          md.get('fixture_id') == STALE_FIXTURE)
            verified = (provenance and provenance['scene_id'] == model_info['fixture_id'] and
                        provenance['model_sha256'] == model_info['sha256'] and
                        provenance['coefficients_sha256'] == model_info['coefficients_sha256'] and
                        provenance['capture_sha256'] == sha(path))
            if not (known_case and verified):
                raise ValueError('CONFIG_MISMATCH_fixture_id; requires matching scene receipt and documented case')
            fixture_note = {'kind': 'documented_stale_fixture_label',
                            'raw_fixture_id': md.get('fixture_id'),
                            'receipt_scene_id': provenance['scene_id'],
                            'basis': 'A e553471; install-time fixture binding; unchanged NPZ hash',
                            'scope': 'historical diagnostic only; not proof of unchanged acoustics'}
        if provenance and provenance.get('source_sha256'):
            if md.get('source_pcm16_sha256') != provenance['source_sha256']:
                raise ValueError('RECEIPT_SOURCE_HASH_MISMATCH')
            if 'source_pcm16' in z.files:
                source_digest = hashlib.sha256(np.asarray(z['source_pcm16'],dtype='<i2').tobytes()).hexdigest()
                if source_digest != provenance['source_sha256']:
                    raise ValueError('SOURCE_BYTES_HASH_MISMATCH')
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
                    capture_frames=len(u), alignment='unchanged_same_frame',
                    scene_provenance=provenance, fixture_annotation=fixture_note)
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
    for lo, hi in ((300, 2000), (3800, 4500), (8000, 8800)):
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


def analyze(run_dir, model_path, expected=None, expected_q=None, nfft=4096, gain_q12=5786, forward_delay=2,
            scene_receipt=None):
    h, lag, fs, mi = read_model(model_path, expected, expected_q)
    outputs, groups, ignored = [], {}, []
    seen = set()
    if scene_receipt:
        selected = receipt_inputs(scene_receipt, run_dir, mi)
        chosen = {path.resolve() for path,_,_ in selected}
        ignored = [str(p) for p in sorted(Path(run_dir).rglob('*.npz')) if p.resolve() not in chosen]
    else:
        selected = []
        for path in sorted(Path(run_dir).rglob('*.npz')):
            stage = stage_for(path)
            if stage is None:
                ignored.append(str(path)); continue
            selected.append((path,stage,None))
    for path,stage,provenance in selected:
        u, m, info = read_capture(path, fs, mi, provenance)
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
    return {'schema_version': 3, 'script_sha256': sha(__file__), 'model': mi,
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
    p.add_argument('--state-root', type=Path, default=Path('/home/xilinx/.local/state/shengdi'))
    p.add_argument('--scene-receipt', type=Path)
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
        base = args.state_root
        args.run_dir = base/'runs'/SCENE/'io'
        args.scene_receipt = base/'runs'/SCENE/'result.json'
        roots = [base/'runs'/SCENE, base/'models', base/'compute']
    if args.run_dir is None or (not args.board_scene and args.model is None):
        p.error('use --board-scene or supply --run-dir and --model')
    if args.out.exists():
        p.error('output already exists; choose a new filename')
    try:
        if args.board_scene:
            args.model = find_model(roots,args.model_sha256)
        result = analyze(args.run_dir,args.model,args.model_sha256,args.coefficients_sha256,
                         nfft=args.nfft,scene_receipt=args.scene_receipt)
        result['status'] = 'computed'
    except (ValueError,KeyError,OSError,TypeError) as exc:
        # Return useful diagnostics even when a further evidence problem exists.
        result = {'schema_version': 3, 'status': 'blocked', 'error': str(exc),
                  'error_type': type(exc).__name__, 'script_sha256': sha(__file__),
                  'run_dir': str(args.run_dir), 'model_path': str(args.model),
                  'scene_receipt': str(args.scene_receipt),
                  'npz_paths': [str(p) for p in sorted(args.run_dir.rglob('*.npz'))],
                  'interpretation': 'no numerical result; no PCM exported; no hardware accessed'}
    with args.out.open('x',encoding='utf-8') as out:
        json.dump(result,out,ensure_ascii=False,indent=1,allow_nan=False)
    if result['status'] != 'computed':
        print('ANALYSIS_BLOCKED',result['error'])
        print('DIAGNOSTIC_JSON',str(args.out))
        raise SystemExit(2)
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
