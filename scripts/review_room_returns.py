"""Silent review of C room return ZIPs. Never imports a hardware driver."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
from evaluation import VERSION,sha
from model_comparison import (SUMMARY_REVISION,export_csv,flat_trial,load_registry,
                              protection_evidence)
from room_experiment import comparison_controls,gate_repeatability,room_model_pairs,write_json


def reported_band_bounds(report,target_db=6.):
    """Re-express A's reported scalar maxima, without pretending to refit H."""
    bands=[]
    for name,item in report['improved_calibration']['bands'].items():
        value=item.get('max_H_minus_Hhat_db')
        bound=-float(value) if type(value) in (int,float) and np.isfinite(value) else None
        bands.append(dict(band_hz=name,residual_path_max_db=value,
                          predicted_gain_bound_db=bound,worst_hz=item.get('worst_hz'),
                          coherence_reported=item.get('coherence'),
                          meets_proposed_band_target=None if bound is None else bound>target_db))
    return dict(kind='A_reported_prediction; not independently refitted',
                formula='gain_db < -20*log10(max_f abs(H(f)-Hhat(f)))',
                proposed_design_target_db=target_db,bands=bands,
                fullband_predicted_gain_bound_db=None,fullband_target_pass=None,
                measured_msg_db=None,measured_asg_db=None,
                missing=['raw_complex_transfer_estimates_and_frequency_grid',
                         'fullband_including_DC_and_9131_Hz',
                         'model_file_and_Q20_hashes',
                         'independent_validation_and_repeated_path_uncertainty'],
                interpretation='Strict small-gain sufficient condition for the assumed stable linear path. '
                'Selected frequency bands and a finite spectral grid do not certify the full loop. '
                'A +3 dB failure below a proposed +5.42 dB bound is an unresolved consistency check, '
                'not confirmation of that bound. Speech and linear headroom require separate evidence.')


def review_return(packet,out,field_report):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(packet) as z:
        summary_bytes=z.read('summary.json');state=json.loads(summary_bytes)
        # Only the registry/model JSON is extracted; reject path traversal.
        for name in z.namelist():
            if not name.startswith('models/') or not name.endswith('.json'):continue
            target=(out/name).resolve()
            if out.resolve() not in target.parents:raise ValueError('unsafe model path')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    registry=load_registry(out/'models');state=copy.deepcopy(state)
    report=json.loads(Path(field_report).read_text(encoding='utf8'))
    proxy_runs={v.get('run') for k,v in report.items() if k.startswith('attempt_') and isinstance(v,dict)}
    proxy=(state['run_id'] in proxy_runs and report.get('hearing_codes',{}).get('closed_trials','').startswith('PROXY:'))
    original_version=state['calculation_version']
    for row in state['trials']:
        for key in ('amplifier_gate','post_gate'):
            g=row.get(key)
            if g and g.get('rms_dbfs') is not None and g.get('reference_rms_dbfs') is not None:
                g['mic_over_ref_db']=g['rms_dbfs']-g['reference_rms_dbfs']
        a=row.get('analysis',{});m=a.get('evaluation_metadata',{})
        if a:
            a['event_flags']['protection']=protection_evidence(m)[0]
            # The source summary's waveform analysis remains authoritative here.
            a['waveform_calculation_version']=a.get('calculation_version')
            a['calculation_version']=VERSION
        if proxy and row.get('hearing_code') is not None:
            row['hearing_evidence_kind']='software_proxy'
            row['hearing_provenance']=dict(file='inputs/field-report.json',sha256=sha(field_report),
                                          basis='A identifies closed trial hearing codes as PROXY')
    comparison_controls(state['trials'])
    for row in state['trials']:row.update(flat_trial(row,registry))
    room_model_pairs(state)
    gates=[r.get('amplifier_gate') or {} for r in state['trials'] if r['trial_role']=='amplifier_gate']
    state['gate_repeatability']=gate_repeatability(gates)
    state.update(calculation_version=VERSION,summary_revision=SUMMARY_REVISION,
                 review_provenance=dict(source_zip_sha256=sha(packet),
                     original_calculation_version=original_version,waveform_recomputed=False,
                     scope='saved summary and metadata only; original NPZ not available to C',
                     original_policy_preserved=True))
    write_json(out/'summary.json',state);export_csv(out/'summary.csv',state['trials'])
    pairs=state['model_pairs']
    return dict(run_id=state['run_id'],source_zip_sha256=sha(packet),trials=len(state['trials']),
                closed_trials=sum(r['trial_role']=='closed_model' for r in state['trials']),
                pair_groups=state['comparison_group_count'],complete_pairs=len(pairs),
                configuration_matched_pairs=sum(p['configuration_matches'] for p in pairs),
                effect_eligible_pairs=sum(p['effect_eligible'] for p in pairs),
                valid_closed_tails=sum(r['trial_role']=='closed_model' and r['tail_valid'] for r in state['trials']),
                stop_reason=state['stop_reason'],gate_repeatability=state['gate_repeatability'])


def review(packets,repeatability,lowband,field_report,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    inputs=out/'inputs';inputs.mkdir()
    result=dict(review_version='c-room-return-review-1.0.0',waveform_recomputed=False,
                evidence_kind='board_recording_metadata_review',runs=[])
    for i,packet in enumerate(packets,1):
        saved=inputs/('room-return-%d.zip'%i);shutil.copyfile(packet,saved)
        result['runs'].append(review_return(saved,out/('run-%d'%i),field_report))
    for name,path in [('repeatability.json',repeatability),('lowband.json',lowband),('field-report.json',field_report)]:
        shutil.copyfile(path,inputs/name)
    repeat=json.loads(Path(repeatability).read_text(encoding='utf8'))
    result['independent_fixture_repeatability']=gate_repeatability([dict(rms_dbfs=x) for x in repeat['mic_rms_dbfs']])
    result['prediction_review']=reported_band_bounds(json.loads(Path(lowband).read_text(encoding='utf8')))
    result['input_hashes']={p.name:sha(p) for p in sorted(inputs.iterdir())}
    write_json(out/'audit.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--returns',type=Path,nargs='+',required=True)
    p.add_argument('--repeatability',type=Path,required=True)
    p.add_argument('--lowband',type=Path,required=True)
    p.add_argument('--field-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=review(a.returns,a.repeatability,a.lowband,a.field_report,a.output)
    print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False))
