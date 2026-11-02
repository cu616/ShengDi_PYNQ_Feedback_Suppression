"""Stage A's exact published guard patch and B's frozen algorithm, without board I/O.

This is payload assembly, not a second entry or a hardware implementation. The
six replacements are read from A's committed script; the resulting bytes must
match A's reported test-copy digest before they can be packaged.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
A='dd0825065462a8433bde2ffaff120798ae73ca2f'
B='0b09ef6'
OLD='8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0'
GUARDED='7ae449af37f270503a8448892ee0dba03d790b54fb718c8b852e8de68843ee08'
PATCH='report/verification/audio-replay/guard-2026-11-02/full_cal_guard3.sh'


def blob(ref,path):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def stage(destination):
    out=Path(destination).resolve();out.mkdir(parents=True,exist_ok=False)
    hardware=out/'a';hardware.mkdir();algorithm=out/'b';algorithm.mkdir()
    script=blob(A,PATCH)
    python=script.decode().split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
    assignment=next(n for n in ast.parse(python).body if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='edits' for t in n.targets))
    edits=ast.literal_eval(assignment.value)
    raw=blob(A,'board/audio_replay/v3-io/hw_api.py')
    if sha(raw)!=OLD:raise ValueError('A patch base differs from its published input')
    text=raw.decode().replace('\r\n','\n')
    for before,after in edits:
        if text.count(before)!=1:raise ValueError('A patch anchor is not unique')
        text=text.replace(before,after)
    guarded=text.encode()
    if len(edits)!=6 or sha(guarded)!=GUARDED:raise ValueError('not A reported guarded bytes')
    runtime=json.loads(blob(A,'board/audio_replay/v3-io/manifest.json'))
    hashes={}
    for name,digest in runtime['hashes'].items():
        original=blob(A,'board/audio_replay/v3-io/'+name)
        if sha(original)!=digest:raise ValueError('A runtime mismatch: '+name)
        content=guarded if name=='hw_api.py' else original
        (hardware/name).write_bytes(content);hashes[name]=sha(content)
    runtime['hashes']=dict(hashes)
    (hardware/'manifest.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes['manifest.json']=sha((hardware/'manifest.json').read_bytes())
    original_contract=blob(A,'docs/contracts/product-adapter.json')
    contract=json.loads(original_contract)
    for name,content in [('physical-controls.json',blob(A,'docs/contracts/physical-controls.json')),
                         ('upstream-product-adapter.json',original_contract)]:
        (hardware/name).write_bytes(content);hashes[name]=sha(content)
    provenance=dict(base_commit=A,base_helper_sha256=OLD,patch_path=PATCH,
        patch_sha256=sha(script),patch_edits=len(edits),result_helper_sha256=GUARDED,
        exact_A_reported_bytes=True,B_commit=subprocess.check_output(['git','rev-parse',B],cwd=ROOT).decode().strip(),
        adopted=['MMIO read gate during Overlay construction','AUX cache during driver call','driver owns arm; remove pre-arm'],
        raw_poll_status_exposed=False,protection_baseline_verified=False,
        limitations=['button observation may be delayed about 0.9 seconds during download; not measured end-to-end',
                     'AUX cache not independently isolated on hardware; fresh identity checked after driver return',
                     'new C package still needs START/30-second run and repeat CAL on hardware',
                     'reproduced software fault: idle baseline hides the same fault in a later capture; installation blocked'],
        no_board_access=True)
    (hardware/'hardware-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    hashes['hardware-provenance.json']=sha((hardware/'hardware-provenance.json').read_bytes())
    identity=dict(contract['expected_identity'],helper_sha256=GUARDED,gain_q12=1631)
    meta=dict(contract='recal-product-v1',kind='hardware',source_commit=A,source_derivation=provenance,
        field_approved=True,adapter_check_allowed=False,field_trial_allowed=False,
        hashes=hashes,expected_identity=identity,allowed_gain_q12=contract['gain_sets']['run_gain_q12'],
        capabilities={k:True for k in ('buttons','indicator','nonintrusive_events','abort_mutes',
                                      'prepared_capture','bounded_run','mode_readback')},
        allowed_calibration_gain_q12=[0],diagnostic_model='bootstrap-model.json',
        blockers=['A protection baseline retains an idle fault across a new capture; a repeated runtime fault is hidden'],
        upstream_blockers=contract.get('blockers',[]),
        approval_scope='A-supervised integration validation; not formal demonstration or 200ms button latency acceptance',
        config=dict(hp_volume=40,aux_db=0.,input_mode='embedded',speech_seconds=2.5,
            request_capture_directories=True,indicator_armed_safe=True,bootstrap_model='bootstrap-model.json',
            install_readback_required=True,embedded_cue_frames=21969,cue_indicator_guard_seconds=.1))
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
    args=parser.parse_args();print(json.dumps(stage(args.stage),ensure_ascii=False))
