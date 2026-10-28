"""Offline review of A's 2026-10-27 itemized captures; never imports board APIs.

This is a derived review, not a native r6 return. Run beside existing captures,
return the JSON only, and retain speech PCM on the board. Unknown source state,
operator actions and missing history are never reconstructed from filenames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SCALE = 1 << 23
MINIMUM, MAXIMUM = -SCALE, SCALE - 1
COUNT_KEYS = ('prediction_saturations', 'residual_saturations',
              'gain_saturations', 'mix_saturations')
FIXTURE = 'room_v1_20261026b'
BIT = '61bb71aabb824c57191edcea93d1333143cd959c16d43028585913c54a8f61fa'
V3_BIT = '48e38f781f2ff64ca4fe66300b5aa3794e01835a77c26906150d4713c358fb78'
V3_IDENTITY = dict(hwh_sha256='9411adb5565902ff7f8dbf03ae16cdb7f254b258dfe1568c3e315920ccd1ce4e',
                   driver_sha256='c2b2a86ad9eeae7be861e55fc1a048cdaf5f7ccdaece9ae111715a62e1fe6493',
                   replay_tools_sha256='bba221020c154968939aba0f23b21a0bbe38fb0ba8051448553388210d7aa246')
V3_IDENTITY_PROFILES = (V3_IDENTITY,
    dict(V3_IDENTITY, replay_tools_sha256='5b11b656255d2406a3b08bfc14ac6fbd76380ab264b380ee32a6679c43e8941d'), dict(V3_IDENTITY,
    driver_sha256='6b397359b52b6c6d830f238ac5741845b5053cd0144ae9e01bc860735786cf7d',
    replay_tools_sha256='0d4e1933b827ca5224aa61f5ca125ce88a6e3d36422b7abb45ddbe688cee4792'))
CANDIDATE = '6118e85df7d9765bd5ae93fc204a32301135666b188bcc0fcf61e1447f6e8927'
ZERO = hashlib.sha256(np.zeros(512, dtype='<i4').tobytes()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def outside_pcm(x):
    return (x < MINIMUM) | (x > MAXIMUM)


def rounded_shift(x, bits):
    x = np.asarray(x, dtype=np.int64)
    magnitude = (np.abs(x) + (1 << (bits - 1))) >> bits
    return np.where(x < 0, -magnitude, magnitude)


def unpack_counts(words):
    if len(words) != 3 or any(type(v) is not int or not 0 <= v < 2**32 for v in words):
        raise ValueError('three unsigned 32-bit counter words required')
    return dict(zip(COUNT_KEYS, (words[0] & 0xffff, words[0] >> 16, words[1], words[2])))


def db_power(power):
    return float(10 * np.log10(power)) if power > 0 else None


def power_metrics(x, rate):
    """Parseval-consistent one-sided Hann power, with DC removal explicit.

    All spectral total/band/share figures use exactly the same window and
    denominator N*sum(window**2). Raw RMS and centered RMS are separate metrics.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or len(x) < 4 or not np.isfinite(x).all():
        raise ValueError('finite window of at least four samples required')
    centered = x - np.mean(x)
    window = np.hanning(len(x))
    powers = np.abs(np.fft.rfft(centered * window))**2 / (len(x) * np.sum(window**2))
    powers[1:(-1 if len(x) % 2 == 0 else None)] *= 2
    frequencies = np.fft.rfftfreq(len(x), 1 / rate)
    band = (frequencies >= 300) & (frequencies < 360)
    total, band_power = float(np.sum(powers)), float(np.sum(powers[band]))
    return dict(frames=len(x), dc=float(np.mean(x)),
                rms_including_dc_dbfs=db_power(float(np.mean(x*x))),
                centered_rms_dbfs=db_power(float(np.mean(centered*centered))),
                spectral_total_power=total, spectral_total_dbfs=db_power(total),
                band_300_360_power=band_power, band_300_360_dbfs=db_power(band_power),
                band_share=band_power / total if total else None,
                definition='mean removed; Hann; one-sided bin power; 300<=f<360; normalized by N*sum(w*w)')


def pcm_codes(x):
    values = np.asarray(x, dtype=np.float64) * SCALE
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError('finite one-dimensional normalized PCM required')
    codes = np.rint(values).astype(np.int64)
    if np.any(outside_pcm(codes)) or np.max(np.abs(values - codes), initial=0) > 1e-5:
        raise ValueError('PCM is outside signed24 or not on its integer grid')
    return codes


def review_capture(path):
    """Keep measured residual arithmetic separate from predictor history replay."""
    path = Path(path)
    issues, unknown = [], []
    with np.load(path, allow_pickle=False) as cap:
        meta = json.loads(str(cap['metadata_json']))
        reference, mic = pcm_codes(cap['reference']), pcm_codes(cap['microphone'])
        prediction = np.asarray(cap['prediction_pcm'])
        residual = np.asarray(cap['residual_pcm'])
        for x in (prediction, residual):
            if x.dtype.kind not in 'iu' or x.ndim != 1 or np.any(outside_pcm(x)):
                raise ValueError('invalid recorded integer prediction/residual')
        prediction, residual = prediction.astype(np.int64), residual.astype(np.int64)
        n = len(mic)
        if not n or any(len(x) != n for x in (reference, prediction, residual)):
            raise ValueError('missing or unequal channel lengths')
        rate = float(meta.get('sample_rate_hz', cap['sample_rate_hz'] if 'sample_rate_hz' in cap else float('nan')))
        if not np.isfinite(rate) or rate <= 0:
            raise ValueError('invalid sample rate')
        first, end = meta.get('first_frame'), meta.get('completed_frames')
        if first is None and meta.get('mode') == 'continuous' and type(end) is int:
            first = end - n  # derived from actual continuous counter, not request duration
        extent_valid = type(first) is int and type(end) is int and first >= 0 and end-first == n
        if not extent_valid:
            issues.append('actual_capture_extent_missing_or_inconsistent')
        count = meta.get('frames')
        if count is not None and count != n:
            issues.append('metadata_frame_count_mismatch')
        side = path.with_suffix('.status.json')
        status = json.loads(side.read_text(encoding='utf-8')) if side.exists() else {}
        is_v3 = meta.get('bit_sha256') == V3_BIT
        sticky = None
        if not status:
            unknown.append('status_sidecar_missing')
        for key in ('fixture_id', 'bit_sha256', 'first_frame', 'completed_frames',
                    'source_end_frame_exclusive', 'clip_counts_raw', 'coefficients_sha256',
                    'gain_q12', 'hp_volume', 'stop_reason', 'capture_status',
                    'input_full_scale_seen', *COUNT_KEYS):
            if key in meta and key in status and meta[key] != status[key]:
                issues.append('status_metadata_mismatch:' + key)
        if meta.get('fixture_id') != FIXTURE or meta.get('bit_sha256') not in (BIT, V3_BIT):
            issues.append('fixture_or_bit_identity_mismatch')
        if meta.get('replay_abi_version') == 3 and not is_v3:
            issues.append('v3_driver_with_other_bitstream')
        if meta.get('bit_sha256') == BIT and any(meta.get(k, status.get(k)) == v for profile in V3_IDENTITY_PROFILES for k,v in profile.items()):
            issues.append('v3_package_component_with_v2_bitstream')
        if meta.get('bit_sha256') == BIT and 'input_full_scale_seen' in meta:
            issues.append('v3_input_field_with_v2_bitstream')
        if is_v3:
            if meta.get('replay_abi_version') not in (None, 3):
                issues.append('v3_abi_marker_mismatch')
            word = meta.get('capture_status')
            explicit = meta.get('input_full_scale_seen')
            if type(word) is not int or not 0 <= word < 2**32:
                unknown.append('v3_capture_status_missing')
            else:
                sticky = bool(word & (1 << 22))
            if type(explicit) is not bool:
                unknown.append('v3_input_full_scale_field_missing')
            elif sticky is not None and explicit != sticky:
                issues.append('input_full_scale_field_status_mismatch')
            if sticky is True or explicit is True:
                issues.append('input_full_scale_seen')
            identity = {key:meta.get(key, status.get(key)) for key in V3_IDENTITY}
            absent = [key for key,value in identity.items() if value is None]
            unknown.extend('v3_' + key + '_missing' for key in absent)
            if not absent and not any(identity == profile for profile in V3_IDENTITY_PROFILES):
                issues.append('v3_version_binding_mismatch:release_tuple')
        if meta.get('hp_volume') != 40 or rate != 48828.125:
            issues.append('codec_or_rate_mismatch')
        for key in ('logical_taps', 'loaded_taps'):
            if meta.get(key) is None:
                unknown.append(key + '_missing')
            elif meta[key] != 512:
                issues.append(key + '_mismatch')
        coefficient_status = meta.get('coefficient_status', status.get('coefficient_status'))
        if coefficient_status is None:
            unknown.append('coefficient_load_status_missing')
        elif (int(coefficient_status) >> 4) & 0xffff != 512 or int(coefficient_status) & 0xe != 0xa:
            issues.append('coefficient_load_status_invalid')
        recovered = status.get('recovery_ok', meta.get('recovered'))
        if recovered is False:
            issues.append('recovery_failed')
        elif recovered is not True:
            unknown.append('recovery_not_verified')
        if status.get('save_error') or meta.get('save_error'):
            issues.append('capture_save_error_recorded')
        if meta.get('early_stop') is True or meta.get('stop_reason') not in (None, 'completed'):
            issues.append('execution_not_completed')
        if is_v3 and type(meta.get('capture_status')) is int and meta['capture_status'] & (3 << 17):
            issues.append('v3_config_or_protocol_fault')
        raw_counts = meta.get('clip_counts_raw', status.get('clip_counts_raw'))
        try:
            decoded = unpack_counts(raw_counts) if raw_counts is not None else None
        except ValueError:
            decoded = None
            issues.append('raw_counter_words_invalid')
        if decoded:
            for key, value in decoded.items():
                for source in (meta, status):
                    if key in source and source[key] != value:
                        issues.append('decoded_counter_mismatch:' + key)
        else:
            unknown.append('raw_counter_words_missing')

        q = np.asarray(cap['coefficients_q20']) if 'coefficients_q20' in cap else None
        identity = dict(bit_sha256=meta.get('bit_sha256'), fixture_id=meta.get('fixture_id'),
                        coefficients_sha256=meta.get('coefficients_sha256'),
                        model_sha256=meta.get('model_sha256'), gain_q12=meta.get('gain_q12'),
                        hp_volume=meta.get('hp_volume'), capture_id=meta.get('capture_id'))
        arithmetic = dict(replay_generation=3 if is_v3 else 2)
        replayed = None
        skip = 0
        if q is not None:
            if q.shape != (512,) or q.dtype.kind not in 'iu' or np.any(outside_pcm(q)):
                raise ValueError('invalid 512 signed24 Q20 coefficients')
            actual_hash = hashlib.sha256(q.astype('<i4').tobytes()).hexdigest()
            identity['actual_q20_sha256'] = actual_hash
            if actual_hash != meta.get('coefficients_sha256') or actual_hash not in (ZERO, CANDIDATE):
                issues.append('actual_q20_identity_mismatch')
            if meta.get('zero_coeff') is True and np.any(q):
                issues.append('zero_flag_with_nonzero_coefficients')
            acc = np.convolve(reference, np.r_[np.int64(0), q.astype(np.int64)])[:n]
            replayed = np.clip(rounded_shift(acc, 20), MINIMUM, MAXIMUM)
            # Missing predecessor history affects only local FIR replay. Never use its
            # zero-filled prefix to invent a full-run first event or saturation count.
            skip = min(len(q), n) if first != 0 and (is_v3 or np.any(q)) else 0
            arithmetic.update(history_excluded_frames=skip,
                              prediction_evaluated_frames=n-skip,
                              prediction_mismatches=int(np.count_nonzero(replayed[skip:] != prediction[skip:])))
            if not n-skip:
                unknown.append('no_prediction_frames_after_history_exclusion')
            elif arithmetic['prediction_mismatches']:
                issues.append('prediction_replay_mismatch')
        else:
            unknown.append('coefficients_array_missing')

        wide = mic - prediction  # uses actual recorded prediction, not invented history
        bypass = meta.get('bypass')
        if type(bypass) is bool:
            expected = mic if bypass else np.clip(wide, MINIMUM, MAXIMUM)
            arithmetic['recorded_residual_mismatches'] = int(np.count_nonzero(expected != residual))
            if arithmetic['recorded_residual_mismatches']:
                issues.append('recorded_residual_mismatch')
        else:
            unknown.append('bypass_state_missing')
        overflow = outside_pcm(wide) if bypass is False else np.zeros(n, dtype=bool)
        arithmetic['wide_residual_frames'] = int(np.count_nonzero(overflow))
        arithmetic['wide_residual_frames_scope'] = 'whole captured window, actual recorded prediction, strict signed24 bounds'
        indices = np.flatnonzero(overflow)
        first_local = int(indices[0]) if len(indices) else None
        recorded_count = decoded['residual_saturations'] if decoded else None
        event = dict(observed_residual_overflows=int(len(indices)),
                     first_in_capture_index=first_local,
                     first_in_capture_global_frame=first+first_local if extent_valid and first_local is not None else None,
                     capture_pre_event_frames=first_local,
                     full_run_first_event='unknown: requires reset/counter coverage and event census consistency',
                     final_residual_counter=recorded_count,
                     observed_count_equals_unsaturated_final_counter=(recorded_count == len(indices)) if recorded_count is not None and recorded_count < 65535 else None,
                     counter_semantics='pred/res16 saturate at65535; gain/mix32; counter coverage is not waveform coverage',
                     frequency_of_first_event_hz=None)
        if recorded_count is not None and recorded_count < len(indices):
            issues.append('observed_overflow_exceeds_final_counter')
        if first_local is not None:
            event['first_sample_codes'] = dict(microphone=int(mic[first_local]), prediction=int(prediction[first_local]),
                                               residual_wide=int(wide[first_local]), residual_recorded=int(residual[first_local]))
        gain = meta.get('gain_q12')
        source = np.asarray(cap['source_pcm16']) if 'source_pcm16' in cap else None
        source_identity = None
        if source is not None:
            if source.dtype.kind not in 'iu' or source.ndim != 1 or np.any(source < -32768) or np.any(source > 32767):
                raise ValueError('invalid source PCM16')
            source_identity = hashlib.sha256(source.astype('<i2').tobytes()).hexdigest()
            if source_identity != meta.get('source_pcm16_sha256'):
                issues.append('source_hash_mismatch')
            if len(source) != meta.get('source_end_frame_exclusive') or meta.get('source_schedule_verified') is not True:
                issues.append('source_schedule_mismatch')
        if source is not None and extent_valid and type(gain) is int:
            frames = np.arange(first, end)
            injection = np.zeros(n, dtype=np.int64)
            active = frames < len(source)
            injection[active] = source[frames[active]].astype(np.int64) * 256
            start = skip + 2 if is_v3 and first else 2
            if is_v3 and replayed is None:
                unknown.append('v3_prediction_replay_unavailable_for_output')
            else:
                operand = (mic if bypass else mic-replayed) if is_v3 else residual
                gained = np.clip(rounded_shift(operand[max(start-2, 0):n-2]*gain, 12), MINIMUM, MAXIMUM)
                output = np.clip(injection[start:] + gained, MINIMUM, MAXIMUM)
                mismatch = int(np.count_nonzero(output != reference[start:]))
                startup = 2 if first == 0 else 0
                if startup:
                    mismatch += int(np.count_nonzero(reference[:2] != injection[:2]))
                arithmetic.update(output_evaluated_frames=max(n-start, 0), output_checked_frames=max(n-start, 0),
                                  output_prediction_source='local model replay after history exclusion' if is_v3 else 'captured clamped residual',
                                  startup_output_checked_frames=startup, output_first_capture_index=start,
                                  output_mismatches=mismatch,
                                  output_operand='wide residual' if is_v3 else 'captured clamped residual')
                if not n-start > 0:
                    unknown.append('no_output_frames_after_history_exclusion')
                if mismatch:
                    issues.append('played_reference_replay_mismatch')
        else:
            unknown.append('source_or_gain_unavailable_for_output_replay')
        rails = (mic == MINIMUM) | (mic == MAXIMUM)
        rail_positive, rail_negative = int(np.count_nonzero(mic == MAXIMUM)), int(np.count_nonzero(mic == MINIMUM))
        # Only statistics leave the board. Do not export raw speech or window FFTs.
        blocks = [power_metrics(mic[i:i+2048] / SCALE, rate) for i in range(0, n-3, 2048) if len(mic[i:i+2048]) >= 4]
        measurement = power_metrics(mic / SCALE, rate)
        measurement.update(microphone_positive_rail_samples=rail_positive,
                           microphone_negative_rail_samples=rail_negative,
                           microphone_rail_samples=int(np.count_nonzero(rails)),
                           absolute_peak_including_dc_dbfs=db_power(float(np.max(np.abs(mic)/SCALE)**2)))
        if rails.any():
            issues.append('captured_microphone_clipping')
        protection_counts = None if decoded is None else any(v for k,v in decoded.items()
                            if not is_v3 or k != 'residual_saturations')
        flags = dict(input_clipped=bool(rails.any()) or sticky is True or meta.get('input_full_scale_seen') is True,
                     input_full_scale_seen=sticky,
                     captured_input_clipped=bool(rails.any()),
                     protection=(True if meta.get('stop_reason') == 'guard' else
                                 bool(protection_counts) if decoded is not None else None),
                     residual_overflow=bool(len(indices)),
                     acoustic_regeneration='not inferred from rail counts, prediction_saturations=0, or envelope alone')
        intervals = {}
        if extent_valid and source is not None:
            boundaries = (('source_on', first, min(end, len(source))),
                          ('source_off_after_50ms', max(first, len(source)+int(np.ceil(.05*rate))), end))
            for label, lo, hi in boundaries:
                if hi-lo >= 4:
                    intervals[label] = dict(first_frame=lo, end_frame=hi,
                                           source_scope='onboard PCM only; external speech/source state requires separate evidence',
                                           microphone=power_metrics(mic[lo-first:hi-first]/SCALE, rate))
        return dict(original_capture=str(path), original_sha256=sha(path),
                    original_status_sha256=sha(side) if side.exists() else None,
                    original_metadata=meta, identity=identity, source_pcm16_sha256=source_identity,
                    source_has_nonzero_samples=bool(source is not None and np.any(source)),
                    actual_interval=dict(first_frame=first, end_frame=end, captured_frames=n,
                                         rate_hz=rate, extent_verified=extent_valid,
                                         missing_waveform_intervals=[[0, first]] if extent_valid and first else [],
                                         coverage_fraction=n/end if extent_valid and end else None),
                    decoded_counts=decoded, arithmetic=arithmetic, residual_event=event,
                    measurement=measurement, interval_measurements=intervals, block_measurements=blocks,
                    event_flags=flags, issues=sorted(set(issues)), unknown=sorted(set(unknown)),
                    execution_completed=(meta.get('stop_reason') == 'completed' and
                        meta.get('early_stop') is not True and extent_valid and
                        bool(int(meta.get('capture_status') or 0) & 1) and
                        not bool(int(meta.get('capture_status') or 0) & (3 << 17))) if type(meta.get('capture_status')) is int else None,
                    captured_numeric_checks_clear=not issues and not unknown,
                    whole_run_adc_headroom_verified=False,
                    whole_run_input_full_scale_seen=sticky,
                    human_confirmations='not inferred; attach original operator log separately')


def source_pairs(results):
    pairs = []
    for zero in results:
        if zero.get('identity', {}).get('actual_q20_sha256') != ZERO or not zero.get('source_has_nonzero_samples'):
            continue
        for candidate in results:
            if candidate.get('identity', {}).get('actual_q20_sha256') != CANDIDATE:
                continue
            keys = ('fixture_id', 'bit_sha256', 'gain_q12', 'hp_volume', 'sample_rate_hz')
            if (zero.get('source_pcm16_sha256') != candidate.get('source_pcm16_sha256') or
                    zero['actual_interval'] != candidate['actual_interval'] or
                    any(zero['original_metadata'].get(k) != candidate['original_metadata'].get(k) for k in keys)):
                continue
            windows = {'whole_capture': (zero['measurement'], candidate['measurement'])}
            for label in zero['interval_measurements'].keys() & candidate['interval_measurements'].keys():
                a, b = zero['interval_measurements'][label], candidate['interval_measurements'][label]
                if (a['first_frame'], a['end_frame']) == (b['first_frame'], b['end_frame']):
                    windows[label] = (a['microphone'], b['microphone'])
            differences = {}
            for label, (a, b) in windows.items():
                if all(x is not None for x in (a['band_300_360_dbfs'], b['band_300_360_dbfs'], a['band_share'], b['band_share'])) and a['band_share'] > 0 and b['band_share'] > 0:
                    differences[label] = dict(
                        absolute_band_drop_db=a['band_300_360_dbfs']-b['band_300_360_dbfs'],
                        spectral_total_drop_db=a['spectral_total_dbfs']-b['spectral_total_dbfs'],
                        share_drop_db=float(10*np.log10(a['band_share']/b['band_share'])))
            pairs.append(dict(zero=zero['original_capture'], candidate=candidate['original_capture'],
                              source_pcm16_sha256=zero['source_pcm16_sha256'], windows=differences,
                              numerical_checks_clear=zero['captured_numeric_checks_clear'] and candidate['captured_numeric_checks_clear'],
                              operator_and_background_confirmation='not inferred; check original logs',
                              interpretation='same digital excitation and captured intervals; no ASG/listener/whole-run stability claim'))
    return pairs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture-dir', type=Path, required=True)
    p.add_argument('--pattern', action='append', required=True,
                   help='repeat for existing capture names; no recursive/private audio export')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error('output already exists; choose a new derived result path')
    root = a.capture_dir.resolve()
    if not root.is_dir():
        p.error('existing capture directory not found; no operation performed')
    paths = sorted({x.resolve() for pattern in a.pattern for x in root.glob(pattern) if x.suffix == '.npz'})
    if any(not path.is_relative_to(root) for path in paths):
        p.error('capture path outside selected directory')
    results = []
    for path in paths:
        try:
            results.append(review_capture(path))
        except Exception as exc:
            results.append(dict(original_capture=str(path), original_sha256=sha(path),
                                issues=['review_failed:' + type(exc).__name__ + ':' + str(exc)]))
    record = dict(schema_version=1, artifact_kind='C-derived-review-of-A-itemized-20261027',
                  r6_native_execution=False, producer_sha256=sha(__file__),
                  hardware_operations=0, selected_patterns=a.pattern,
                  results=results, missing_selection=not paths,
                  directory_inventory=[dict(name=x.name, bytes=x.stat().st_size) for x in sorted(root.glob('*.npz'))],
                  directory_identity={name:sha(root/name) for name in ('audio_replay.bit','audio_replay.hwh',
                                      'replay_trial.py','replay_tools.py') if (root/name).is_file()},
                  directory_identity_scope='files at offline review time; original execution requires frozen run/version provenance',
                  missing_patterns=[pattern for pattern in a.pattern if not list(root.glob(pattern))],
                  controlled_source_pairs=source_pairs(results),
                  original_sources_retained=True,
                  no_effect_pass_implied=True,
                  limits=['Final-ring statistics do not establish full-run ADC headroom.',
                          'No automatic human confirmation or feedback cause.',
                          'Counter agreement alone does not establish full-run first-event coverage.',
                          'Keep source/waveform alignment, background and operator actions explicit.'])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('DERIVED_REVIEW_SAVED', a.out, 'captures', len(paths), 'board/audio actions 0')
    return 0 if paths else 2


if __name__ == '__main__':
    raise SystemExit(main())
