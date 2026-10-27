"""C-owned derived measurement v2. Pure offline; never imports a board API.

No legacy metadata is overwritten. Intervals are half-open, trial-relative ADC
frame indices. Growth is evidence in an observed window, not feedback causality.
"""
import hashlib
import json
import math
import zipfile
from pathlib import Path

import numpy as np
from growth_monitor import MonitorConfig, replay

VERSION = 'c-measurement-2.4.0'
CONFIG = dict(window_seconds=.016, hop_seconds=.008, growth_seconds=.08,
              confirm_seconds=.016, minimum_rise_db=3.,
              minimum_slope_db_per_second=12., minimum_fit_r2=.9,
              minimum_tonal_fraction=.55, minimum_tonal_dbfs=-55.)
TRANSITION_SECONDS = .05
MINIMUM_SIGNAL_DBFS = -55.
COUNT_KEYS = ('prediction_saturations', 'residual_saturations',
              'gain_saturations', 'mix_saturations')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unpack_counts(words):
    """ABI: {residual[31:16], prediction[15:0]}, gain32, mix32.

    65535 is a saturated lower bound for the first two counters, not exact.
    Do not feed the old guard metadata aliases into this function.
    """
    if len(words) != 3 or any(type(w) is not int or not 0 <= w < 2**32 for w in words):
        raise ValueError('three unsigned 32-bit raw register words required')
    packed, gain, mix = words
    return dict(zip(COUNT_KEYS, (packed & 0xffff, (packed >> 16) & 0xffff, gain, mix)))


def window_gate(metadata, rate, frames=None):
    """Only actual frame extents and a verified source schedule admit a tail.

    Planned source_frames can DISPROVE tail membership, never establish it.
    transition_frames is frozen before the trial, in this same frame domain.
    """
    m = metadata
    first, end, count = (m.get(k) for k in ('first_frame', 'completed_frames', 'frames'))
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError('invalid rate')
    if any(type(v) is not int or v < 0 for v in (first, end, count)):
        raise ValueError('actual first/completed/frames required')
    if end - first != count or (frames is not None and frames != count):
        raise ValueError('inconsistent actual frame extent')
    transition = m.get('transition_frames', math.ceil(TRANSITION_SECONDS * rate))
    if type(transition) is not int or transition < 0:
        raise ValueError('invalid transition')
    actual_end = m.get('source_end_frame_exclusive')
    planned = m.get('source_frames')
    if actual_end is not None and (type(actual_end) is not int or actual_end < 0):
        raise ValueError('invalid actual source end')
    if planned is not None and (type(planned) is not int or planned < 0):
        raise ValueError('invalid planned source length')
    verified = m.get('source_schedule_verified') is True and actual_end is not None
    if verified and planned is not None and actual_end != planned:
        raise ValueError('source_end_and_loaded_length_mismatch')
    boundary = actual_end if verified else planned
    pure = bool(verified and count and first >= actual_end + transition)
    overlaps = boundary is not None and first < boundary + transition
    source_active_at_stop = None if boundary is None else end < boundary
    return dict(first_frame=first, end_frame=end, frames=count,
                source_end_frame_exclusive=actual_end,
                source_schedule_verified=verified, planned_source_frames=planned,
                transition_frames=transition, pure_tail=pure,
                reason=('verified_source_off_tail' if pure else
                        'source_or_transition_overlap' if overlaps else 'source_end_unverified'),
                source_active_at_stop=source_active_at_stop,
                waveform_coverage_fraction=count / end if end else None,
                waveform_missing_intervals=[[0, first]] if first else [],
                counter_coverage=m.get('counter_coverage', 'unknown'))


def classify(metadata, signal=None, rate=48828.125, expected=None):
    """Independent validity, evidence and protection axes retain simultaneous flags.

    Invalid wins the display label. Growth and protection remain in event_flags.
    No acoustic label is inferred from an exception containing 'saturation'.
    """
    m = metadata
    result = dict(calculation_version=VERSION, category='unknown', reasons=[],
                  event_flags={}, instability_evidence=[], msg_db=None, asg_db=None,
                  scope='captured window only; no whole-trial stability claim')
    flags = result['event_flags']
    from model_comparison import protection_evidence, V3_BIT, V3_IDENTITY
    protection,protection_basis=protection_evidence(m)
    flags.update(protection=m.get('guard_tripped') is True or m.get('protection_triggered') is True,
                 early_stop=m.get('early_stop'), execution_error=bool(m.get('error')),
                 recovery_failed=m.get('recovery_ok') is False, instability_growth=False)
    words = m.get('clip_counts_raw')
    try:
        counts = unpack_counts(words) if words is not None else {k: m.get(k) for k in COUNT_KEYS}
        # Known A guard aliases cannot be repaired if the packed word was clamped.
        if m.get('artifact_kind') == 'replay_trial_guard' and words is None and m.get('driver_evidence_version') != 'a-replay-evidence-v2':
            counts = {k: None for k in COUNT_KEYS}
            result['reasons'].append('legacy_guard_counters_unrecoverable_without_raw_words')
        if any(v is not None and (type(v) is not int or v < 0) for v in counts.values()):
            raise ValueError('invalid count')
        result['counts'] = counts
        flags.update({k: None if v is None else v > 0 for k, v in counts.items()})
        flags['protection'] = protection
        result['protection_triggered_basis']=protection_basis
        flags['early_stop'] = m.get('early_stop')
        flags['execution_error'] = bool(m.get('error'))
        flags['recovery_failed'] = m.get('recovery_ok') is False
        flags['instability_growth'] = False
        if m.get('bit_sha256') == V3_BIT:
            status = m.get('capture_status')
            explicit = m.get('input_full_scale_seen')
            status_valid = type(status) is int and 0 <= status < 2**23
            sticky = status_valid and bool(status & (1 << 22))
            flags['input_full_scale_seen'] = sticky or explicit is True
            flags['microphone_clipping'] = sticky or explicit is True
            if sticky or explicit is True:
                raise ValueError('input_full_scale_seen')
            if not status_valid or type(explicit) is not bool:
                raise ValueError('v3_input_evidence_missing')
            if status & (3 << 17):
                raise ValueError('v3_config_or_protocol_fault')
            if explicit != sticky:
                raise ValueError('v3_input_evidence_inconsistent')
            if m.get('replay_abi_version') not in (None, 3):
                raise ValueError('v3_abi_marker_mismatch')
            missing = [k for k,v in V3_IDENTITY.items() if m.get(k) != v]
            if missing:
                raise ValueError('v3_version_binding_missing_or_mismatch:' + ','.join(missing))
        elif ('input_full_scale_seen' in m or m.get('replay_abi_version') == 3 or
              any(m.get(k) == v for k,v in V3_IDENTITY.items())):
            raise ValueError('v3_package_component_with_other_bitstream')
        if expected:
            mismatches = [k for k, v in expected.items() if m.get(k) != v]
            if mismatches:
                raise ValueError('configuration_mismatch:' + ','.join(mismatches))
        if m.get('verification', {}).get('bit_exact') is False or m.get('reference_alignment_verified') is False:
            raise ValueError('arithmetic_or_reference_alignment_failed')
        if m.get('source_valid') is False or m.get('version_valid') is False:
            raise ValueError('source_or_version_invalid')
        if any(m.get(k) is None for k in ('first_frame', 'completed_frames', 'frames')):
            result['reasons'].append('actual_frame_extent_not_available')
            result['category'] = 'protection' if flags['protection'] else 'unknown'
            return result
        x = None if signal is None else np.asarray(signal)
        gate = window_gate(m, rate, None if x is None else len(x))
        result['window'] = gate
        if x is not None:
            if x.ndim != 1 or x.dtype.kind not in 'iu' or np.any(x < -2**23) or np.any(x >= 2**23):
                raise ValueError('invalid_signed24_pcm')
            indices = m.get('frame_indices')
            if indices is not None:
                indices = np.asarray(indices)
                if (indices.shape != x.shape or indices.dtype.kind not in 'iu' or
                    len(indices) == 0 or indices[0] != gate['first_frame'] or
                    indices[-1]+1 != gate['end_frame'] or np.any(np.diff(indices) != 1)):
                    raise ValueError('missing_or_inconsistent_frame_indices')
            if m.get('dropped_frames', 0) != 0:
                raise ValueError('missing_frames')
            flags['microphone_clipping'] = bool(np.any((x == -2**23) | (x == 2**23-1)))
        else:
            flags['microphone_clipping'] = (m['mic_full_scale_samples'] > 0
                                            if type(m.get('mic_full_scale_samples')) is int else None)
        if not gate['pure_tail']:
            result['reasons'].append(gate['reason'])
        elif x is None or len(x) == 0:
            result['reasons'].append('raw_pcm_not_available')
        else:
            # Local replay avoids calling a tail incomplete just because its earlier
            # trial frames were not captured. Global coverage is separately retained.
            monitor = replay(x, rate, config=MonitorConfig(**CONFIG))
            result['detector'] = {k: v for k, v in monitor.items() if k != 'trace'}
            clipped = flags['microphone_clipping']
            events = monitor['events']
            for e in events:
                if e['kind'] != 'suspected_howl':
                    continue
                # Clipping contaminates the regression. Require its ENTIRE evidence
                # interval to precede the first clipped sample.
                end = e['frame']
                begin = e['evidence_first_frame']
                if not np.any((x[begin:end] == -2**23) | (x[begin:end] == 2**23-1)):
                    evidence = dict(e)
                    for key in ('frame', 'candidate_since_frame', 'evidence_first_frame'):
                        evidence[key] += gate['first_frame']
                    evidence['time_seconds'] = evidence['frame'] / rate
                    result['instability_evidence'].append(evidence)
            flags['instability_growth'] = bool(result['instability_evidence'])
            level = 20 * np.log10(max(float(np.std(x.astype(float) / 2**23)), 1e-12))
            result['window_rms_dbfs'] = float(level)
            if flags['instability_growth']:
                result['category'] = 'observed_instability'
            elif clipped:
                result['reasons'].append('clipping_without_valid_growth_evidence')
            elif not monitor['coverage']['sufficient_contiguous_history']:
                result['reasons'].append('observation_too_short')
            elif level < MINIMUM_SIGNAL_DBFS:
                result['reasons'].append('below_frozen_signal_floor')
            elif m.get('positive_control_valid') is not True:
                result['reasons'].append('speaker_path_positive_control_missing')
            else:
                result['category'] = 'no_instability_observed_in_window'
        if flags['protection'] and not flags['instability_growth']:
            result['category'] = 'protection'
        # A completed-looking tail cannot erase an interrupted run or failed
        # recovery. Retain valid local growth/protection evidence on those axes.
        for flag, reason in (('execution_error', 'execution_interrupted'),
                             ('recovery_failed', 'recovery_failed'),
                             ('early_stop', 'early_stop_without_complete_run')):
            if flags[flag]:
                result['reasons'].append(reason)
                if result['category'] == 'no_instability_observed_in_window':
                    result['category'] = 'unknown'
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        result['category'] = 'invalid'
        result['reasons'].append(str(exc))
    return result


def verify_v3_words(raw, q, bypass, gain, source, first):
    """Independent v3 consumer oracle; the A driver/helper files remain untouched."""
    from closed_tools import gain_pcm, rounded_shift
    raw, q = np.asarray(raw, dtype=np.int64), np.asarray(q, dtype=np.int64)
    acc = np.convolve(raw[:, 0], np.r_[np.int64(0), q])[:len(raw)]
    pred = np.clip(rounded_shift(acc, 20), -2**23, 2**23-1)
    diagnostic = raw[:, 1] if bypass else np.clip(raw[:, 1]-pred, -2**23, 2**23-1)
    skip = len(q) if first else 0
    start = skip+2
    if start >= len(raw):
        raise ValueError('no_v3_output_frames_after_history')
    indices = np.arange(first, first+len(raw))
    injection = np.zeros(len(raw), dtype=np.int64)
    active = indices < len(source)
    injection[active] = np.asarray(source, dtype=np.int64)[indices[active]]*256
    operand = raw[:, 1] if bypass else raw[:, 1]-pred
    expected = np.clip(injection[start:] + gain_pcm(operand[skip:-2], gain), -2**23, 2**23-1)
    pm = int(np.count_nonzero(pred[skip:] != raw[skip:, 2]))
    rm = int(np.count_nonzero(diagnostic[skip:] != raw[skip:, 3]))
    tm = int(np.count_nonzero(expected != raw[start:, 0]))
    if first == 0:
        tm += int(np.count_nonzero(raw[:2, 0] != injection[:2]))
    observed = raw[:, 1] if bypass else raw[:, 1]-raw[:, 2]
    return dict(bit_exact=pm == rm == tm == 0, prediction_mismatches=pm,
                residual_mismatches=rm, output_mismatches=tm,
                history_excluded_frames=skip, evaluated_frames=len(raw)-skip,
                output_checked_frames=max(len(raw)-start, 0), output_first_capture_index=start,
                startup_output_checked_frames=2 if first == 0 else 0,
                wide_residual_frames=int(np.count_nonzero((observed < -2**23) | (observed > 2**23-1))),
                wide_residual_frames_scope='actual recorded prediction, whole captured window',
                interpretation='v3: gain(wide residual), post-gain clamp then mix clamp; arithmetic only')


def analyze_npz(path, expected=None, positive_control_valid=False, external_source_active=False,
                external_source_off_verified=False, metadata_evidence=None, analysis_interval=None):
    """No pickle, no writes to the source; independently check stored arithmetic."""
    path = Path(path)
    original = {}; m = {}; rate = 48828.125
    recorded_qhash=None; recorded_taps=None
    try:
        with path.open('rb') as stream, np.load(stream, allow_pickle=False) as z:
            m = json.loads(str(z['metadata_json'].item()))
            if not isinstance(m, dict):
                raise ValueError('metadata_must_be_object')
            original = dict(m)
            if metadata_evidence is not None:
                allowed = {'source_end_frame_exclusive','source_schedule_verified','transition_frames',
                           'external_source_off_verified','external_source_active','positive_control_valid',
                           'scene_sha256','session_id','comparison_id','repeat_id','mute_applied',
                           'mute_during_observation','source_schedule_provenance','positive_control_provenance',
                           'measurement_policy_version','trial_role','noise_floor_dbfs'}
                allowed.update(('driver_sha256', 'replay_tools_sha256', 'hwh_sha256', 'replay_abi_version'))
                facts = metadata_evidence.get('metadata',{})
                if metadata_evidence.get('input_sha256') != sha(path) or not metadata_evidence.get('provenance'):
                    raise ValueError('unbound_metadata_evidence')
                if not isinstance(facts,dict) or set(facts)-allowed:
                    raise ValueError('evidence_cannot_override_actual_configuration')
                if any(k in m and m[k] is not None and m[k]!=v for k,v in facts.items()):
                    raise ValueError('evidence_conflicts_with_original_metadata')
                m.update(facts)
            rate = float(z['sample_rate_hz'].item())
            if m.get('sample_rate_hz', rate) != rate:
                raise ValueError('sample_rate_metadata_mismatch')
            channels = [np.array(z[k]) for k in ('reference', 'microphone', 'prediction_pcm', 'residual_pcm')]
            if any(c.ndim != 1 or len(c) != len(channels[0]) for c in channels):
                raise ValueError('four_channel_shape_mismatch')
            for i in (0, 1):
                c = channels[i]
                if not np.isfinite(c).all() or np.any(c < -1) or np.any(c >= 1):
                    raise ValueError('invalid_normalized_pcm')
                channels[i] = np.rint(c * 2**23).astype(np.int64)
            raw = np.column_stack(channels)
            if raw.dtype.kind not in 'iu' and not np.array_equal(raw, np.rint(raw)):
                raise ValueError('noninteger_raw_pcm')
            if np.any(raw < -2**23) or np.any(raw >= 2**23):
                raise ValueError('raw_pcm_out_of_range')
            raw = raw.astype(np.int64)
            recorded_qhash=None; recorded_taps=None
            if 'coefficients_q20' in z:
                q=np.asarray(z['coefficients_q20'])
                if q.ndim!=1 or q.dtype.kind not in 'iu' or np.any(q < -2**23) or np.any(q >= 2**23):
                    raise ValueError('invalid_recorded_coefficients')
                recorded_qhash=hashlib.sha256(q.astype('<i4').tobytes()).hexdigest()
                recorded_taps=len(q)
                if m.get('coefficients_sha256',recorded_qhash)!=recorded_qhash:
                    raise ValueError('coefficient_hash_mismatch')
            if 'frame_indices' in z:
                m['frame_indices'] = np.array(z['frame_indices']).tolist()
            if 'source_pcm16' in z and 'coefficients_q20' in z and len(raw) > len(z['coefficients_q20']):
                source = np.asarray(z['source_pcm16'])
                coefficients = np.asarray(z['coefficients_q20'])
                if (source.ndim != 1 or source.dtype.kind not in 'iu' or
                    np.any(source < -32768) or np.any(source > 32767) or
                    coefficients.ndim != 1 or coefficients.dtype.kind not in 'iu' or
                    np.any(coefficients < -2**23) or np.any(coefficients >= 2**23)):
                    raise ValueError('source_or_coefficient_data_invalid')
                source_hash = hashlib.sha256(source.astype('<i2').tobytes()).hexdigest()
                coefficients_hash = hashlib.sha256(coefficients.astype('<i4').tobytes()).hexdigest()
                if m.get('source_pcm16_sha256', source_hash) != source_hash:
                    raise ValueError('source_hash_mismatch')
                if m.get('coefficients_sha256', coefficients_hash) != coefficients_hash:
                    raise ValueError('coefficient_hash_mismatch')
                if m.get('source_frames', len(source)) != len(source):
                    raise ValueError('source_length_mismatch')
                from model_comparison import V3_BIT
                if m.get('bit_sha256') == V3_BIT:
                    v = verify_v3_words(raw, coefficients, m['bypass'], m['gain_q12'], source, m['first_frame'])
                else:
                    from replay_tools import verify_replay
                    v = verify_replay(raw, coefficients, m['bypass'], m['gain_q12'], source, m['first_frame'])
                m['verification'] = v
            if positive_control_valid:
                m['positive_control_valid'] = True
            if external_source_off_verified:
                m['external_source_off_verified']=True
                m['external_source_off_basis']='operator_confirmation_in_frozen_plan'
            if external_source_active:
                m['source_schedule_verified'] = False
                m['source_frames'] = None
            capture_window=window_gate(m,rate,len(raw))
            analysis_m=dict(m);analysis_raw=raw
            if analysis_interval is not None:
                if analysis_interval!='source_off_tail':raise ValueError('unknown_analysis_interval')
                if m.get('source_schedule_verified') is True and type(m.get('source_end_frame_exclusive')) is int:
                    begin=max(m['first_frame'],m['source_end_frame_exclusive']+capture_window['transition_frames'])
                    begin=min(begin,m['completed_frames'])
                    offset=begin-m['first_frame'];analysis_raw=raw[offset:]
                    analysis_m.update(first_frame=begin,frames=len(analysis_raw))
                    if 'frame_indices' in m:analysis_m['frame_indices']=m['frame_indices'][offset:]
            out = classify(analysis_m, analysis_raw[:,1], rate, expected)
            clipped=bool(np.any((raw[:,1]==-2**23)|(raw[:,1]==2**23-1)))
            out['event_flags']['microphone_clipping']=clipped
            if clipped:
                out['category']='invalid'
                out['reasons'].append('microphone_full_scale_in_capture')
            from tail_metrics import tail_statistics, empty_tail
            from model_comparison import V3_BIT
            wide_tail = m.get('bit_sha256') == V3_BIT
            err = (analysis_raw[:,1] if m.get('bypass') else analysis_raw[:,1]-analysis_raw[:,2]) if wide_tail else analysis_raw[:,3]
            out['tail_statistics']=(tail_statistics(analysis_raw[:,1],err,analysis_m,rate,residual_wide=wide_tail)
                                    if out['category']!='invalid' else empty_tail('invalid_capture'))
            out.update(recorded_coefficients_sha256=recorded_qhash,recorded_taps=recorded_taps,
                       silence_in_window=not bool(np.any(raw[:,1])),
                       capture_window=capture_window,
                       tail_analysis_window=dict(first_frame=analysis_m['first_frame'],end_frame=m['completed_frames'],frames=len(analysis_raw)),
                       original_metadata=original,
                       evaluation_metadata={k:v for k,v in analysis_m.items() if k!='frame_indices'},
                       supplemental_evidence=metadata_evidence)
    except (ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile, EOFError) as exc:
        out=classify(m if isinstance(m,dict) else {},rate=rate)
        out.update(category='invalid',original_metadata=original)
        out.update(recorded_coefficients_sha256=recorded_qhash,recorded_taps=recorded_taps)
        out['reasons'].append(str(exc))
    try: digest=sha(path) if path.is_file() else None
    except OSError as exc:
        digest=None;out['category']='invalid';out['reasons'].append('input_hash_unreadable:'+str(exc))
    out.update(input_path=str(path),input_sha256=digest)
    return out
