"""Stage A's committed baseline repair and B's frozen algorithm without board I/O.

All nine A runtime files are copied as Git blob bytes; no patch is applied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
A='e6379ef331762b3162542d6325a644f5b34934da'
B='0b09ef6'
HELPER='0cabfc17cca1fb0e2629e1b382c119b48f00e1fe9b2a437a0302ed04e06ed3c5'
DEMO_EVIDENCE='eb881fe405fcafbf8b0e35cc8356de3213520366'
DEMO_GAIN=6900
DEMO_SECONDS=8


def blob(ref,path):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def stage(destination, demo=False):
    out=Path(destination).resolve();out.mkdir(parents=True,exist_ok=False)
    hardware=out/'a';hardware.mkdir();algorithm=out/'b';algorithm.mkdir()
    raw=blob(A,'board/audio_replay/v3-io/hw_api.py')
    if sha(raw)!=HELPER or raw!=blob(A,'board/audio_replay/hw_api.py'):
        raise ValueError('A helper identity or root/v3 copy differs')
    manifest=blob(A,'board/audio_replay/v3-io/manifest.json');runtime=json.loads(manifest)
    hashes={}
    for name,digest in runtime['hashes'].items():
        original=blob(A,'board/audio_replay/v3-io/'+name)
        if sha(original)!=digest:raise ValueError('A runtime mismatch: '+name)
        (hardware/name).write_bytes(original);hashes[name]=sha(original)
    (hardware/'manifest.json').write_bytes(manifest);hashes['manifest.json']=sha(manifest)
    original_contract=blob(A,'docs/contracts/product-adapter.json')
    contract=json.loads(original_contract)
    if contract['expected_identity']['helper_sha256']!=HELPER or contract['package_files_sha256']!=runtime['hashes']:
        raise ValueError('A adapter contract differs from runtime manifest')
    for name,content in [('physical-controls.json',blob(A,'docs/contracts/physical-controls.json')),
                         ('upstream-product-adapter.json',original_contract)]:
        (hardware/name).write_bytes(content);hashes[name]=sha(content)
    provenance=dict(source_commit=A,helper_sha256=HELPER,runtime_manifest_sha256=sha(manifest),
        exact_A_source_bytes=True,B_commit=subprocess.check_output(['git','rev-parse',B],cwd=ROOT).decode().strip(),
        adopted=['MMIO read gate during Overlay construction','AUX cache during driver call','driver owns arm; remove pre-arm'],
        arm_baseline_callback=True,raw_poll_status_exposed=True,
        protection_baseline_verification='software register substitutes; no board; see A probe_baseline.py and C test_recal_guard_payload.py',
        limitations=['button observation may be delayed about 0.9 seconds during download; not measured end-to-end',
                     'AUX cache not independently isolated on hardware; fresh identity checked after driver return',
                     'new C package still needs physical validation for its frozen operating point and duration'],
        no_board_access=True)
    (hardware/'hardware-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes['hardware-provenance.json']=sha((hardware/'hardware-provenance.json').read_bytes())
    identity=dict(contract['expected_identity'],gain_q12=1631)
    meta=dict(contract='recal-product-v1',kind='hardware',source_commit=A,source_derivation=provenance,
        field_approved=True,adapter_check_allowed=True,field_trial_allowed=False,
        hashes=hashes,expected_identity=identity,allowed_gain_q12=contract['gain_sets']['run_gain_q12'],
        capabilities={k:True for k in ('buttons','indicator','nonintrusive_events','abort_mutes',
                                      'prepared_capture','bounded_run','mode_readback')},
        allowed_calibration_gain_q12=[0],diagnostic_model='bootstrap-model.json',
        blockers=[],
        upstream_blockers=contract.get('blockers',[]),
        approval_scope='A-supervised integration validation; not formal demonstration or 200ms button latency acceptance',
        config=dict(hp_volume=40,aux_db=0.,input_mode='embedded',speech_seconds=2.5,
            request_capture_directories=True,indicator_armed_safe=True,bootstrap_model='bootstrap-model.json',
            install_readback_required=True,embedded_cue_frames=21969,cue_indicator_guard_seconds=.1))
    if demo:
        # A's explicit demonstration authorization changes configuration only.
        # Runtime still checks ONE gain; open-loop requests remain at zero.
        allowed=list(dict.fromkeys(meta['allowed_gain_q12']+[DEMO_GAIN]))
        meta['allowed_gain_q12']=allowed
        meta['expected_identity']['gain_q12']=DEMO_GAIN
        meta['config'].update(allowed_gain_q12=allowed,run_seconds=DEMO_SECONDS,maintenance_gain_q12=1631,
            phase_gain_q12={op:[0,DEMO_GAIN] for op in (
                'prepare','cue','input','training','validation','install','run')})
        meta['approval_scope']='A-supervised fixed-gain eight-second same-layout demo; not long-term equipment or product field acceptance'
        evidence_path='report/verification/audio-replay/demo-protocol-2026-11-02/README.md'
        meta['demo_authorization']=dict(source_commit=DEMO_EVIDENCE,evidence_path=evidence_path,
            evidence_sha256=sha(blob(DEMO_EVIDENCE,evidence_path)),gain_q12=DEMO_GAIN,run_seconds=DEMO_SECONDS,
            runtime_gain_identity='single fixed value, not membership in the maintenance allowed set',
            limitations=['bypass at this gain can howl loudly and stop by driver saturation protection, not software limiting',
                         'long-term loudspeaker headroom and safety not evaluated',
                         'about 0.9 seconds button observation gap remains unmeasured',
                         'A direct-entry evidence does not validate this product package or a new layout/model'])
    (hardware/'product-adapter.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    b=blob(B,'board/audio_replay/recal_algorithm.py');digest=sha(b)
    if digest!='489064051a63973c39c0f113aad28e26c2fad77fc4a5f578c44f83b0b9a1d417':
        raise ValueError('B frozen identity differs')
    (algorithm/'recal_algorithm.py').write_bytes(b)
    (algorithm/'product-adapter.json').write_text(json.dumps(dict(contract='recal-product-v1',kind='algorithm',
        algorithm_contract='recalibration-algorithm-v1',source_commit=provenance['B_commit'],field_approved=True,
        hashes={'recal_algorithm.py':digest},blockers=[],approval_scope='numerical software, not physical ASG or listening'),indent=2)+'\n',encoding='utf-8')
    return provenance


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',required=True)
    parser.add_argument('--demo',action='store_true',help='A-authorized fixed 6900 gain, eight-second demo only')
    args=parser.parse_args();print(json.dumps(stage(args.stage,args.demo),ensure_ascii=False))
