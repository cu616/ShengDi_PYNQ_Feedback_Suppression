"""Read-only candidate verification. Does not import PYNQ or issue board operations."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root):
    root=root.resolve(); issues=[]; payload=[]
    v3=root/'board/audio_replay/v3'
    manifest=json.loads((v3/'manifest.json').read_bytes())
    for name,expected in manifest['hashes'].items():
        path=v3/name
        ok=path.is_file() and digest(path)==expected
        payload.append(dict(file=name,ok=ok))
        if not ok: issues.append('v3 identity mismatch: '+name)
    inventory=json.loads((root/'integration.json').read_bytes())
    for entry in inventory['files']:
        path=(root/entry['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path)!=entry['sha256']:
            issues.append('inventory mismatch: '+entry['path'])
    sys.path.insert(0,str(root/'board/audio_replay/v3'))
    spec=importlib.util.spec_from_file_location('candidate_model_loader',v3/'residual_tools.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    import numpy as np
    model=root/'models/room_v1/rewired_512_20261026.json'
    expected=manifest['model']
    try:
        _,q=module.load_candidate(model,expected['fixture_id'],40,manifest['sample_rate_hz'])
        qhash=hashlib.sha256(np.asarray(q,dtype='<i4').tobytes()).hexdigest()
        if digest(model)!=expected['sha256'] or qhash!=expected['coefficients_sha256_q20_candidate']:
            issues.append('model file/Q20 identity mismatch')
    except Exception as exc:
        issues.append('model loader: '+str(exc)); qhash=None
    return dict(ok=not issues,hardware_operations=0,payload_checks=payload,
                inventory_files=len(inventory['files']),candidate_q20_sha256=qhash,issues=issues,
                scope='file identity and loader only; no hardware/effect/release pass implied')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--candidate',type=Path,required=True); p.add_argument('--out',type=Path)
    a=p.parse_args()
    try: result=verify(a.candidate)
    except Exception as exc: result=dict(ok=False,issues=[str(exc)],hardware_operations=0)
    if a.out: a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False)); raise SystemExit(0 if result['ok'] else 2)
