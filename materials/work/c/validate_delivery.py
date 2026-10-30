"""One scoped submission check, recording real commands and negative controls."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
CANDIDATE=ROOT/'materials/staging/tmp/submission-candidate-r3'
SCRATCH=ROOT/'materials/staging/tmp'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',type=Path,default=CANDIDATE)
    parser.add_argument('--reuse',type=Path,help='previous real check results; reuse only unchanged A/B/import sources')
    args=parser.parse_args()
    candidate=args.candidate.resolve()
    previous=json.loads(args.reuse.read_bytes()) if args.reuse else None
    old_manifest=json.loads((ROOT/'materials/staging/tmp/submission-candidate-r2/integration.json').read_bytes()) if previous else None
    new_manifest=json.loads((candidate/'integration.json').read_bytes())
    old_hashes={e['path']:e['sha256'] for e in old_manifest['files']} if old_manifest else {}
    new_hashes={e['path']:e['sha256'] for e in new_manifest['files']}
    reusable_prefixes=('src/','scripts/','board/','models/')
    same_runtime=bool(previous) and all(old_hashes.get(k)==v for k,v in new_hashes.items() if k.startswith(reusable_prefixes))
    results=[]
    def run(name,args,cwd=None,expected=0):
        cwd=cwd or candidate
        reusable={'A golden reference in exported v3','B PCM/Q20 unit counterexamples with A RTL','selected pure imports'}
        prior=next((r for r in previous['checks'] if r['name']==name and r['passed']),None) if previous else None
        if same_runtime and name in reusable and prior:
            record=dict(prior,reused_from=str(parser_args_reuse),reuse_basis='all src/scripts/board/models exported hashes unchanged; B test file also unchanged')
            if name.startswith('B ') and old_hashes.get('sim/feedback/test_unit_scale_guard.py')!=new_hashes.get('sim/feedback/test_unit_scale_guard.py'):
                raise ValueError('cannot reuse changed B test')
            results.append(record); print(name,'REUSED PASS (same bytes)',flush=True); return None
        p=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1'})
        results.append(dict(name=name,args=args,cwd=str(cwd.relative_to(ROOT)),exit_code=p.returncode,expected_exit_code=expected,passed=p.returncode==expected,output=p.stdout+p.stderr))
        print(name,p.returncode,'PASS' if results[-1]['passed'] else 'FAIL',flush=True)
        return p
    parser_args_reuse=args.reuse
    run('candidate file/model identity',['materials/work/c/verify_candidate.py','--candidate','.'])
    run('A golden reference in exported v3',['board/audio_replay/v3/test_verify_replay_v3.py'])
    run('B PCM/Q20 unit counterexamples with A RTL',['-m','unittest','discover','-s','sim/feedback','-p','test_unit_scale_guard.py','-v'])
    run('C exact round/source/window/amplitude regressions',['-m','unittest','discover','-s','sim/feedback','-p','test_replay_v3_consumer.py','-k','round','-v'])
    run('C wide arithmetic/identity with A helper',['-m','unittest','discover','-s','sim/feedback','-p','test_replay_v3_consumer.py','-k','wide','-v'])
    run('selected pure imports',['-c',"import sys; sys.path[:0]=['src','scripts','board/audio_replay']; import feedback.calibration, feedback.cancellation, feedback.path_analysis, feedback.closed_loop_sim, fit_newlayout_candidate, verify_r4_waveforms, evaluation, model_comparison, tail_metrics; print('PURE_IMPORTS_OK')"])
    run('report and candidate scripts compile',['-m','compileall','-q','src','scripts','board/audio_replay','materials/work/c'])
    # Archive used only to test independent extraction; it is not the required RAR deliverable.
    archive=SCRATCH/(candidate.name+'-extraction-check.zip')
    extracted=SCRATCH/(candidate.name+'-clean-extraction')
    if archive.exists() or extracted.exists():
        raise SystemExit('Refusing to overwrite earlier extraction evidence')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in candidate.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts and 'tmp' not in f.relative_to(candidate).parts:
                z.write(f,f.relative_to(candidate).as_posix())
    with zipfile.ZipFile(archive) as z: z.extractall(extracted)
    run('independent extraction identity',['materials/work/c/verify_candidate.py','--candidate','.'],cwd=extracted)
    bad=SCRATCH/(candidate.name+'-bad-identity')
    shutil.copytree(extracted,bad)
    target=bad/'board/audio_replay/v3/replay_tools.py'
    target.write_bytes(target.read_bytes()+b'\n# deliberately invalid test copy\n')
    p=run('skill negative: mismatched helper rejected',['materials/work/c/verify_candidate.py','--candidate','.'],cwd=bad,expected=2)
    results[-1]['passed'] &= 'v3 identity mismatch: replay_tools.py' in p.stdout
    # Shape/coverage failures are existing C round test cases, not new sound trials.
    import pypdf
    pdf=ROOT/'materials/final/shengdi-report.pdf'; reader=pypdf.PdfReader(pdf)
    report=dict(path='materials/final/shengdi-report.pdf',sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
                bytes=pdf.stat().st_size,pages=len(reader.pages),draft=True,
                visual_review='all nine rendered pages inspected; no clipping/overlap; template pending')
    result=dict(schema_version=1,ok=all(r['passed'] for r in results),python=sys.version,checks=results,report=report,
        initial_failures=[
            'default Python3.14 lacked NumPy and PyYAML; switched to bundled document runtime / existing Anaconda for skill validator',
            'first docs scan included white-list export copies with omitted historical links; moved generated copies beneath materials/staging/tmp and changed omitted reference links to pinned source URLs',
            'r2 C test imported the running helper as old_verify; correct A helper made the historical-negative assertion fail. Fixed C-owned test to load a SHA-pinned legacy helper only from sim fixtures; A runtime untouched. Original failure kept in validation-initial.json'],
        hardware_operations=0,rar=dict(found=False,created=False,search='PATH and common C:/Program Files, C:/Program Files (x86), D:/Program Files, D:/Ksoftware; no executable found',
            blocker='RAR executable unavailable; ZIP is extraction-only test evidence, never renamed or delivered as RAR'),
        pending=['A/B integration manifests and report fragments','captain main conflict decisions','official report template','final media and anonymity review','actual RAR generation and independent RAR extraction'])
    (HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('VALIDATION',result['ok'],len(results),'checks',report['pages'],'PDF pages')
    raise SystemExit(0 if result['ok'] else 2)

if __name__=='__main__': main()
