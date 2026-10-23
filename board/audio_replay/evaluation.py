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

VERSION = 'c-measurement-2.1.0'
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
    """ABI: {residual[15:0], prediction[15:0]}, gain32, mix32.

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
        flags['protection'] = m.get('guard_tripped') is True or m.get('protection_triggered') is True
        flags['early_stop'] = m.get('early_stop')
        flags['execution_error'] = bool(m.get('error'))
        flags['recovery_failed'] = m.get('recovery_ok') is False
        flags['instability_growth'] = False
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
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        result['category'] = 'invalid'
        result['reasons'].append(str(exc))
    return result


def analyze_npz(path, expected=None, positive_control_valid=False, external_source_active=False,
                external_source_off_verified=False, metadata_evidence=None):
    """No pickle, no writes to the source; independently check stored arithmetic."""
    path = Path(path)
    original = {}; m = {}; rate = 48828.125
    recorded_qhash=None; recorded_taps=None
    try:
        with np.load(path, allow_pickle=False) as z:
            m = json.loads(str(z['metadata_json'].item()))
            if not isinstance(m, dict):
                raise ValueError('metadata_must_be_object')
            original = dict(m)
            if metadata_evidence is not None:
                allowed = {'source_end_frame_exclusive','source_schedule_verified','transition_frames',
                           'external_source_off_verified','external_source_active','positive_control_valid',
                           'scene_sha256','session_id','comparison_id','repeat_id','mute_applied',
                           'mute_during_observation','source_schedule_provenance','positive_control_provenance'}
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
                from replay_tools import verify_replay
                v = verify_replay(raw, z['coefficients_q20'], m['bypass'], m['gain_q12'], z['source_pcm16'], m['first_frame'])
                m['verification'] = v
            if positive_control_valid:
                m['positive_control_valid'] = True
            if external_source_off_verified:
                m['external_source_off_verified']=True
                m['external_source_off_basis']='operator_confirmation_in_frozen_plan'
            if external_source_active:
                m['source_schedule_verified'] = False
                m['source_frames'] = None
            out = classify(m, channels[1], rate, expected)
            out['event_flags']['microphone_clipping']=bool(np.any((raw[:,1]==-2**23)|(raw[:,1]==2**23-1)))
            from tail_metrics import tail_statistics, empty_tail
            out['tail_statistics']=(tail_statistics(raw[:,1],raw[:,3],m,rate)
                                    if out['category']!='invalid' else empty_tail('invalid_capture'))
            out.update(recorded_coefficients_sha256=recorded_qhash,recorded_taps=recorded_taps,
                       silence_in_window=not bool(np.any(raw[:,1])),
                       original_metadata=original,
                       evaluation_metadata={k:v for k,v in m.items() if k!='frame_indices'},
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
