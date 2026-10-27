"""B model identity, flat telemetry and strict same-gain model pairs. No devices."""
import csv
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from tail_metrics import BANDS, empty_tail

SUMMARY_VERSION = 3
SUMMARY_REVISION = '3.2.1'
V3_BIT = '48e38f781f2ff64ca4fe66300b5aa3794e01835a77c26906150d4713c358fb78'
V3_IDENTITY = dict(hwh_sha256='9411adb5565902ff7f8dbf03ae16cdb7f254b258dfe1568c3e315920ccd1ce4e',
                   driver_sha256='6b397359b52b6c6d830f238ac5741845b5053cd0144ae9e01bc860735786cf7d',
                   replay_tools_sha256='0d4e1933b827ca5224aa61f5ca125ce88a6e3d36422b7abb45ddbe688cee4792')
MODEL_SELECTION = {'room_v1_20261021':'room_v1/calibrated_20261024.json',
                   'box_v1_20261016':'box_v1/baseline_256.json'}
BIT_CAPACITIES = {'8b2426f4fbcf27425731899557b179d2aea8a4ec2fa26dcc11b60102ecb45339':512,
                  V3_BIT:512,
                  'dadbbbabd75ec5c641b337819d33a5845e54da6b89bf6507b5323807d9ddcb05':256}
# Source: A's 2026-10-21-asg-field.md, sections 4.1 and 5 (full replay hash).
# The retired overlay is deliberately excluded from deployable BIT_CAPACITIES.
RETIRED_BITS = {'4d49dfbe53180536f0c2302a19ed6ead23e3336e959dd50567dc647473635316':256}
BIT_PROVENANCE = 'report/verification/audio-replay/2026-10-21-asg-field.md'
CONFIG_FIELDS = ('gain_q12','hp_volume','bit_sha256','coefficients_sha256','model_sha256')
PAIR_FIELDS = ('gain_q12','hp_volume','bit_sha256','fixture_id','sample_rate_hz',
               'source_pcm16_sha256','scene_sha256','session_id','bypass',
               'tail_first_frame','tail_end_frame')
HASH = re.compile(r'^[0-9a-f]{64}$')


def protection_evidence(metadata):
    """Read A's explicit outcome; absence in unversioned captures stays unknown."""
    values=[metadata.get('guard_tripped'),metadata.get('protection_triggered')]
    if any(v is True for v in values):return True,'explicit_guard_field'
    if metadata.get('bit_sha256') == V3_BIT:
        reason = metadata.get('stop_reason')
        if reason == 'guard':
            return True, 'v3:explicit_guard_stop'
        words = metadata.get('clip_counts_raw')
        status = metadata.get('capture_status')
        if (isinstance(words, list) and len(words) == 3 and
                all(type(w) is int and 0 <= w < 2**32 for w in words)):
            # The upper packed half is pre-gain diagnostic overflow in v3.
            if words[0] & 0xffff or words[1] or words[2]:
                return True, 'v3:prediction_or_post_gain_or_mix_protection'
            if (reason == 'completed' and metadata.get('early_stop') is False and
                    type(status) is int and status & 1 and not status & (3 << 17)):
                return False, 'v3:completed_without_stopping_counter'
        return None, None
    if any(v is False for v in values):return False,'explicit_guard_field'
    if metadata.get('driver_evidence_version')=='a-replay-evidence-v2':
        reason=metadata.get('stop_reason')
        if reason=='guard':return True,'a-replay-evidence-v2:stop_reason=guard'
        words=metadata.get('clip_counts_raw')
        if (reason=='completed' and metadata.get('early_stop') is False
                and type(metadata.get('capture_status')) is int
                and metadata['capture_status']&1 and not metadata['capture_status']&(3<<17)
                and isinstance(words,list) and len(words)==3
                and all(type(w) is int and w==0 for w in words)):
            return False,'a-replay-evidence-v2:completed_done_final_zero_counts'
    return None,None


def qhash(q):
    return hashlib.sha256(np.asarray(q,dtype='<i4').tobytes()).hexdigest()


def load_registry(folder):
    from residual_tools import load_candidate
    folder=Path(folder); manifest=json.loads((folder/'manifest.json').read_text(encoding='utf8'))
    result={}
    for item in manifest['models']:
        path=(folder/item['file']).resolve()
        if folder.resolve() not in path.parents: raise ValueError('model path escapes registry')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=item['sha256']:raise ValueError('model file hash mismatch: '+item['file'])
        model,q=load_candidate(path,item['fixture_id'],40,48828.125)
        for key in ('taps','lag_first','sample_rate_hz','fixture_id','hp_volume'):
            if model.get(key)!=item.get(key): raise ValueError('model manifest mismatch: '+key)
        entry=dict(file=item['file'],fixture_id=model['fixture_id'],
                            logical_taps=len(q),role='candidate' if 'candidate_' in path.name else 'baseline',
                            coefficients_sha256=qhash(q),
                            padded_512_sha256=qhash(np.pad(q,(0,512-len(q)))) if len(q)<=512 else None)
        for key in ('coefficients_sha256','padded_512_sha256'):
            if key in item and item[key]!=entry[key]:raise ValueError('model coefficient manifest mismatch: '+key)
        result[digest]=entry
    return result


def validate_model(path, fixture_id, bit_capacity):
    from residual_tools import load_candidate
    model,q=load_candidate(path,fixture_id,40,48828.125)
    if type(bit_capacity) is not int or len(q)>bit_capacity:
        raise ValueError('model taps exceed verified bitstream capacity')
    return model,q


def select_model(registry,fixture_id):
    path=MODEL_SELECTION.get(fixture_id)
    if path is None:raise ValueError('unregistered fixture; no silent model fallback')
    matches=[digest for digest,item in registry.items() if item['file']==path]
    if len(matches)!=1:raise ValueError('selected calibration missing or ambiguous; no old-session fallback')
    return matches[0]


def flat_trial(row, registry=None):
    """Never reconstruct actual gain from a requested dB value."""
    a=row.get('analysis',{})
    m=a.get('evaluation_metadata',a.get('original_metadata',row.get('metadata',{}))) or {}
    flags=a.get('event_flags',{})
    tail=a.get('tail_statistics',empty_tail('raw_tail_statistics_missing'))
    out={k:row.get(k) for k in ('index','mode','status','error','file')}
    out.update({k:m.get(k) for k in CONFIG_FIELDS})
    out.update({k:m.get(k) for k in ('fixture_id','sample_rate_hz','source_pcm16_sha256',
                                   'scene_sha256','session_id','comparison_id','repeat_id','bypass')})
    out.update(trial_role=row.get('trial_role',m.get('trial_role')),
               measurement_policy_version=m.get('measurement_policy_version'))
    control=row.get('path_comparison_control',{})
    g=row.get('amplifier_gate') or {}
    out.update(path_comparison_control_valid=control.get('valid'),
               path_comparison_mic_over_ref_range_db=control.get('mic_over_ref_range_db'),
               gate_mic_over_ref_db=g.get('mic_over_ref_db'),gate_mic_rms_dbfs=g.get('rms_dbfs'),
               gate_reference_rms_dbfs=g.get('reference_rms_dbfs'))
    out.update(tail)
    # Geometry exists even when a tail is too quiet for meaningful statistics.
    window=a.get('tail_analysis_window')
    if window and all(type(window.get(k)) is int for k in ('first_frame','end_frame','frames')):
        if window['frames']>0 and window['end_frame']-window['first_frame']==window['frames']:
            out.update(tail_first_frame=window['first_frame'],tail_end_frame=window['end_frame'],
                       tail_frames=window['frames'])
    out.update(category=a.get('category','unknown'),
               calculation_version=a.get('calculation_version'),
               evidence_kind=m.get('evidence_kind','board_recording' if m.get('source')=='board' else 'unverified_capture'),
               capture_id=m.get('capture_id',a.get('input_sha256')), model_role=None,
               logical_taps=None,loaded_taps=a.get('recorded_taps',m.get('loaded_taps')),
               summary_revision=SUMMARY_REVISION,
               derived_loaded_taps=None,derived_loaded_taps_basis=None,
               coefficients_sha256_basis='metadata',
               source_input_sha256=a.get('input_sha256'),effect_eligible=False,comparison_reasons=[])
    actual=a.get('recorded_coefficients_sha256')
    if actual:
        out['coefficients_sha256']=actual;out['coefficients_sha256_basis']='saved_q20_le_int32'
    if out['loaded_taps'] is None:out['loaded_taps']=m.get('loaded_taps')
    out['loaded_taps_basis']=('saved_q20_le_int32_length' if a.get('recorded_taps') is not None
                              else 'driver_metadata' if m.get('loaded_taps') is not None else None)
    bit=out['bit_sha256'];retired=bit in RETIRED_BITS
    known=bit in BIT_CAPACITIES or retired
    out.update(bitstream_overlay='audio_closed' if retired else 'audio_replay' if known else None,
               bitstream_capacity=BIT_CAPACITIES.get(bit,RETIRED_BITS.get(bit)),
               bitstream_provenance=('A:e132991:docs/contracts/audio-replay-v3.md' if bit == V3_BIT else BIT_PROVENANCE) if known else None,
               retired_overlay=retired if known else None,
               acoustic_evidence_eligible=False if retired else True if known else None,
               evidence_scope='pl_arithmetic_only' if retired else 'capture_window')
    protection,protection_basis=protection_evidence(m)
    out.update(protection_triggered=protection,
               protection_triggered_basis=protection_basis,
               positive_control_valid=m.get('positive_control_valid') if type(m.get('positive_control_valid')) is bool else None,
               prediction_saturation=flags.get('prediction_saturations'),
               residual_saturation=flags.get('residual_saturations'),
               gain_saturation=flags.get('gain_saturations'),mix_saturation=flags.get('mix_saturations'),
               microphone_clipping=flags.get('microphone_clipping'),
               mute_applied=m.get('mute_applied'),mute_during_observation=m.get('mute_during_observation'),
               silence_in_window=a.get('silence_in_window'))
    if bit == V3_BIT:
        out['residual_metric_semantics'] = tail.get('residual_semantics', 'wide25_pre_gain_not_available')
    errors=[]
    if bit == V3_BIT:
        errors.extend('v3_version_binding_missing_or_mismatch:'+k for k,v in V3_IDENTITY.items() if m.get(k) != v)
    if retired:errors.append('retired_overlay_no_dac_output')
    if type(out['gain_q12']) is not int or not 0<=out['gain_q12']<=32768:errors.append('actual_gain_q12_missing_or_invalid')
    if type(out['hp_volume']) is not int or not 10<=out['hp_volume']<=40:errors.append('actual_hp_volume_missing_or_invalid')
    for k in ('bit_sha256','coefficients_sha256'):
        if not isinstance(out[k],str) or not HASH.fullmatch(out[k]):errors.append(k+'_missing_or_invalid')
    if registry is not None:
        model=registry.get(out['model_sha256'])
        if model is None and actual:
            matches=[(digest,item) for digest,item in registry.items()
                     if item['fixture_id']==out['fixture_id'] and actual in
                     (item['coefficients_sha256'],item['padded_512_sha256'])]
            if len(matches)==1:
                out['model_registry_sha256'],model=matches[0]
                out['model_identity_basis']='saved_coefficients; original model file hash retained separately'
        if model is None:errors.append('model_not_in_approved_registry')
        else:
            if 'model_registry_sha256' not in out:out['model_registry_sha256']=out['model_sha256']
            out.update(model_role=model['role'],logical_taps=model['logical_taps'],model_file=model['file'])
            if m.get('model_role',model['role'])!=model['role']:errors.append('claimed_model_role_disagrees_with_coefficients')
            if out['fixture_id']!=model['fixture_id']:errors.append('model_fixture_mismatch')
            capacity=out['bitstream_capacity']
            if capacity is None:errors.append('bitstream_capacity_unverified')
            elif model['logical_taps']>capacity:errors.append('model_exceeds_bitstream_capacity')
            coefficient_hash=out['coefficients_sha256']
            if coefficient_hash==model['coefficients_sha256']:
                out['derived_loaded_taps']=model['logical_taps']
            elif coefficient_hash==model['padded_512_sha256']:
                out['derived_loaded_taps']=512
            if out['derived_loaded_taps'] is not None:
                out['derived_loaded_taps_basis']=out['coefficients_sha256_basis']+':approved_registry_hash_match'
            if out['loaded_taps'] is None:errors.append('actual_loaded_taps_missing')
            elif type(out['loaded_taps']) is not int or out['loaded_taps']<=0:errors.append('actual_loaded_taps_invalid')
            effective_taps=out['loaded_taps'] if out['loaded_taps'] is not None else out['derived_loaded_taps']
            if effective_taps is not None and capacity is not None and effective_taps!=capacity:
                errors.append('physical_taps_do_not_match_bitstream')
            expected=(model['coefficients_sha256'] if effective_taps==model['logical_taps']
                      else model['padded_512_sha256'] if effective_taps==512 else None)
            if coefficient_hash!=expected:errors.append('actual_coefficients_do_not_match_model')
    if errors:
        out['category']='invalid';out['comparison_reasons'].extend(errors)
    reasons=[]
    if not out['tail_valid']:reasons.append('tail_not_validated')
    if out['positive_control_valid'] is not True:
        reasons.append('positive_control_failed' if out['positive_control_valid'] is False else 'positive_control_not_validated')
    safety_keys = ['protection_triggered','microphone_clipping','mute_during_observation',
                   'prediction_saturation','gain_saturation','mix_saturation']
    if bit != V3_BIT:
        safety_keys.append('residual_saturation')
    else:
        sticky = m.get('input_full_scale_seen') is True or bool(int(m.get('capture_status') or 0) & (1 << 22))
        out['input_full_scale_seen'] = sticky
        if sticky:
            out['microphone_clipping'] = True
            out['category'] = 'invalid'
            out['comparison_reasons'].append('input_full_scale_seen')
    safety=[out[k] is False for k in safety_keys]
    if not all(safety):reasons.append('safety_not_validated')
    if m.get('verification',{}).get('bit_exact') is not True:reasons.append('arithmetic_not_validated')
    if out['evidence_kind']!='board_recording':reasons.append('evidence_not_board_recording')
    if out['category']=='invalid':reasons.append('configuration_or_capture_invalid')
    if row.get('path_comparison_control',{}).get('valid') is False:reasons.append('path_comparison_control_failed')
    if retired:reasons.append('retired_overlay_no_dac_output')
    out['eligibility_reasons']=reasons
    out['effect_eligible']=not reasons
    out['comparison_reasons']=list(dict.fromkeys(out['comparison_reasons']+reasons))
    for low,high in BANDS:
        out[f'tail_residual_over_mic_db_{low}_{high}']=out['tail_residual_over_mic_db'][f'{low}-{high}']
    return out


def pair_models(rows):
    """Pair within explicit comparison identity; never choose a flattering repeat."""
    groups={};pairs=[]
    for row in rows:
        if row.get('retired_overlay') is True:continue
        if row.get('trial_role') in ('amplifier_gate','speech'):continue
        if row.get('model_role') not in ('baseline','candidate'):continue
        group=row.get('comparison_id')
        if not group:
            parts=[row.get(k) for k in ('session_id','fixture_id','repeat_id','gain_q12')]
            if any(v is None for v in parts):
                row['comparison_reasons'].append('comparison_identity_missing');continue
            group=json.dumps(parts,separators=(',',':'))
        groups.setdefault(group,[]).append(row)
    for group,items in groups.items():
        base=[r for r in items if r['model_role']=='baseline'];candidate=[r for r in items if r['model_role']=='candidate']
        pair=dict(comparison_id=group,configuration_matches=False,effect_eligible=False,
                  baseline_capture_id=None,candidate_capture_id=None,reasons=[],asg_db=None)
        if len(base)!=1 or len(candidate)!=1:
            pair['baseline_capture_id']=base[0]['capture_id'] if len(base)==1 else None
            pair['candidate_capture_id']=candidate[0]['capture_id'] if len(candidate)==1 else None
            pair['reasons'].append('missing_or_ambiguous_baseline_candidate');pairs.append(pair);continue
        a,b=base[0],candidate[0]
        pair.update(baseline_capture_id=a['capture_id'],candidate_capture_id=b['capture_id'])
        pair['evidence_kind']=a.get('evidence_kind')
        mismatch=[k for k in PAIR_FIELDS if a.get(k) is None or b.get(k) is None or a[k]!=b[k]]
        if a.get('bypass') is not False or b.get('bypass') is not False:mismatch.append('cancel_mode_required')
        if a.get('evidence_kind')!=b.get('evidence_kind'):mismatch.append('evidence_kind')
        if mismatch:
            pair['reasons'].append('pair_configuration_mismatch:'+','.join(mismatch))
            for r in (a,b):
                r['category']='invalid';r['effect_eligible']=False;r['comparison_reasons'].extend(pair['reasons'])
        else:
            pair['configuration_matches']=True;pair['gain_q12']=a['gain_q12']
            pair['effect_eligible']=a['effect_eligible'] and b['effect_eligible']
            if not pair['effect_eligible']:pair['reasons'].append('safety_only_or_tail_not_valid')
        pairs.append(pair)
    return pairs


CSV_FIELDS = ['index','capture_id','file','mode','model_role','model_file','logical_taps','loaded_taps',
              'trial_role','measurement_policy_version','path_comparison_control_valid',
              'path_comparison_mic_over_ref_range_db','gate_mic_over_ref_db',
              'gate_mic_rms_dbfs','gate_reference_rms_dbfs',
              'loaded_taps_basis','derived_loaded_taps','derived_loaded_taps_basis',
              'bitstream_overlay','bitstream_capacity','bitstream_provenance','retired_overlay',
              'acoustic_evidence_eligible','evidence_scope','positive_control_valid','eligibility_reasons','summary_revision',
              *CONFIG_FIELDS,'fixture_id','sample_rate_hz','source_pcm16_sha256','scene_sha256',
              'session_id','comparison_id','repeat_id','category','effect_eligible','evidence_kind',
              'tail_valid','tail_rms_dbfs','tail_slope_db_per_s','tail_residual_over_mic_db',
              *[f'tail_residual_over_mic_db_{a}_{b}' for a,b in BANDS],
              'tail_first_frame','tail_end_frame','tail_frames','tail_reasons','comparison_reasons',
              'protection_triggered','protection_triggered_basis','prediction_saturation','residual_saturation','gain_saturation',
              'mix_saturation','microphone_clipping','mute_applied','mute_during_observation','silence_in_window',
              'source_input_sha256','calculation_version','error']


def export_csv(path,rows):
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=CSV_FIELDS);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(row.get(k),ensure_ascii=False) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in CSV_FIELDS})
