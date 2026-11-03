"""White-list export from immutable Git objects; never merges or controls hardware."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
import posixpath
import subprocess

ROOT = Path(__file__).resolve().parents[3]
REFS = {'A': 'facd3de', 'B': '86061a7', 'C': '330e135'}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--local-ref', help='C commit containing this delivery; omit only for an uncommitted draft')
    args = p.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise SystemExit('Refusing to overwrite an existing candidate; choose a fresh directory.')
    refs = {k: git('rev-parse', v).decode().strip() for k, v in REFS.items()}
    chosen = {}
    def add(owner, path, purpose):
        if path in chosen and chosen[path][0] != owner:
            raise ValueError('Unresolved owner collision: ' + path)
        chosen[path] = (owner, purpose)
    trees = {k: git('ls-tree', '-r', '--name-only', v).decode().splitlines() for k,v in refs.items()}
    # A owns all runtime drivers, the RTL, build scripts and hardware evidence.
    exact_a = ['src/rtl/audio_pl_replay.v', 'src/rtl/feedback_fir.v',
        'build/scripts/create_audio_replay.tcl', 'build/scripts/audio_bringup.xdc',
        'build/scripts/test_audio_replay.tcl', 'build/scripts/test_audio_replay_wide.tcl',
        'build/scripts/test_feedback_fir.tcl', 'sim/audio/tb_audio_replay.v',
        'sim/audio/tb_replay_wide.v', 'sim/audio/tb_feedback_fir.v', 'sim/audio/iis_sim_models.v',
        'docs/contracts/audio-replay-v3.md', 'docs/contracts/audio-replay-v2.md',
        'docs/contracts/audio-replay-v1.md', 'docs/contracts/feedback-fir-v1.md',
        'board/audio_replay/README.md']
    for f in exact_a:
        add('A', f, 'v3 source/build/contract; preserve A semantics')
    for f in trees['A']:
        if f.startswith(('board/audio_replay/v3/', 'src/vendor/pynq_v2_4/',
                         'report/verification/audio-replay/wide-residual-v3/')):
            add('A', f, 'frozen v3 payload, vendor notice or hardware evidence')
        if f.startswith('report/verification/audio-replay/b-request-2026-10-25/'):
            add('A', f, 'existing non-speech calibration input and provenance; no new recording')
    for name in ['closed_tools.py','residual_tools.py','replay_tools.py','replay_trial.py',
                 'tone_round_guard.py','test_runtime_stop.py','test_verify_replay_v3.py',
                 'test_tone_round_guard.py','live_run.py','poll_state.py']:
        add('A', 'board/audio_replay/'+name, 'A runtime dependency; root bit/hwh deliberately excluded')
    for name in ['live-human-first-confirmed-2026-10-27.json','reproduction-result-2026-10-27.json',
                 'residual-overflow-result-2026-10-27.json']:
        add('A','report/verification/audio-replay/'+name,'historical success/failure provenance')
    for f in trees['B']:
        if f.startswith('src/feedback/') and f.endswith('.py'):
            add('B',f,'algorithm source, offline only; no B hardware copied')
    for f in trees['C']:
        if f.startswith('report/ai-records/') and f.endswith('.md'):
            add('C',f,'original AI collaboration and correction records; no fabricated interaction')
    for f in trees['A']:
        if f.startswith('materials/planning/') or f=='materials/prompts/c.txt':
            add('A',f,'captain assignment and original task provenance')
    add('B','models/room_v1/rewired_512_20261026.json','only selected deployable candidate; fixed fixture')
    # Follow project-local script imports rather than copying all historical tools.
    pending = ['answer_new_layout_325.py','fit_newlayout_candidate.py',
               'audit_units_and_saturation.py','make_fir_vectors.py','verify_r4_waveforms.py']
    visited = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        path = 'scripts/'+name
        source = git('show',f'{refs["B"]}:{path}').decode('utf-8-sig')
        add('B',path,'offline fit, reference or transitive local dependency')
        for node in ast.walk(ast.parse(source)):
            names = [node.module] if isinstance(node,ast.ImportFrom) else [n.name for n in node.names] if isinstance(node,ast.Import) else []
            for module in names:
                candidate = (module or '').split('.')[0]+'.py'
                if 'scripts/'+candidate in trees['B']:
                    pending.append(candidate)
    add('B','sim/feedback/test_unit_scale_guard.py','Q20/PCM unit counterexample in selected combination')
    for name in ['evaluation.py','growth_monitor.py','model_comparison.py','tail_metrics.py']:
        add('C','board/audio_replay/'+name,'C current offline consumer; no driver replacement')
    for f in ['scripts/review_itemized_20261027.py',
              'sim/feedback/test_itemized_20261027.py']:
        add('C',f,'C current source/window/golden-reference checks')
    entries = []
    for path,(owner,purpose) in sorted(chosen.items()):
        data = git('show',f'{refs[owner]}:{path}')
        source_digest=hashlib.sha256(data).hexdigest()
        # Omitted history stays reachable by pinned source links; never alter payload bytes.
        if path.endswith('.md'):
            def source_link(match):
                label,target=match.group(1),match.group(2)
                if target.startswith(('http:','https:','mailto:','#')): return match.group(0)
                core,sep,anchor=target.partition('#')
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(path),core))
                if resolved in chosen or any(f.startswith(resolved.rstrip('/')+'/') for f in chosen): return match.group(0)
                return '['+label+'](https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/'+refs[owner]+'/'+resolved+(sep+anchor if sep else '')+')'
            data=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',source_link,data.decode('utf-8')).encode('utf-8')
        target = out/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        entries.append(dict(path=path,owner=owner,source_commit=refs[owner],source_path=path,
            sha256=hashlib.sha256(data).hexdigest(),source_sha256=source_digest,bytes=len(data),purpose=purpose,
            dependencies={'A':['Vivado 2018.3/PYNQ-Z2 for build or hardware; Python+NumPy for pure checks'],
                          'B':['Python+NumPy; A signed24/Q20 contract'],
                          'C':['Python+NumPy; A v3 identity and B selected model']}[owner],
            public_review='preserve BSD notice' if path.startswith('src/vendor/') else
                          'team source/evidence; final license and anonymity review by captain'))
    # Local C authoring outputs are explicitly enumerated, never a recursive materials copy.
    local = ['skill/README.md','skill/audio-evidence/SKILL.md','skill/ai-collaboration/SKILL.md',
        'sim/feedback/test_replay_v3_consumer.py','sim/feedback/fixtures/legacy-replay-tools-v2.py',
        'materials/work/c/verify_candidate.py','materials/work/c/review_return.py',
        'materials/work/c/assemble_candidate.py','materials/work/c/technical-report.md',
        'materials/work/c/validate_delivery.py',
        'materials/work/c/render_report.py','materials/work/c/claims.md',
        'materials/work/c/conflicts.md','materials/work/c/conflict-context.diff','materials/work/c/release-checklist.md',
        'materials/work/c/tone-return.json','materials/work/c/tone-review.json']
    local_ref=git('rev-parse',args.local_ref).decode().strip() if args.local_ref else None
    for path in local:
        data=git('show',f'{local_ref}:{path}') if local_ref else (ROOT/path).read_bytes()
        source_digest=hashlib.sha256(data).hexdigest()
        if path=='materials/work/c/release-checklist.md':
            data=data.replace(b'](integration.json)',b'](../../../integration.json)').replace(b'](validation.json)',b'](../../../validation.json)')
        target=out/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
        entries.append(dict(path=path,owner='C',source_commit=local_ref or 'uncommitted C draft; not a final freeze',source_path=path,
            sha256=hashlib.sha256(data).hexdigest(),source_sha256=source_digest,bytes=len(data),purpose='C submission material/skill or isolated historical test oracle',
            dependencies=['selected candidate sources'],public_review='team authored; report is a draft'))
    summary = dict(schema_version=1,kind='directory-candidate-not-git-merge',source_commits=refs,c_delivery_commit=local_ref,
        destination=str(out.relative_to(ROOT)).replace('\\','/'),
        inputs_missing=['materials/work/a/integration.json','materials/work/a/hardware.md',
                        'materials/work/b/integration.json','materials/work/b/algorithm.md'],
        release_ready=False,hardware_operations=0,files=entries,
        exclusions=[{'pattern':x,'reason':r} for x,r in [
            ('*.zip, old packages','duplicate deliveries; original history preserved'),
            ('board/audio_replay root *.bit/*.hwh and v2/rollback payloads','avoid old payload ambiguity; v3 pair only'),
            ('other models and diagnostics with + names','not the selected fixture/model; original history preserved'),
            ('raw/private, speech PCM, authorization, credentials, .git, worktrees, caches','not public source deliverables'),
            ('references/**/*.pdf','third-party redistribution not established; retain official references'),
            ('old REQUESTS, STATE and historical run notebooks','do not restore superseded state or operational entry points')]],
        required_checks=['ten v3 manifest hashes','model file/Q20/fixture',
                         'imports and selected A/B/C numerical tests','skill positive/negative examples'],
        unexecuted=['new hardware execution','full FPGA rebuild','full external I/O timing sign-off'])
    readme = '''# ShengDi submission directory candidate r1

This is a source export, not a merge of main. Run `python materials/work/c/verify_candidate.py --candidate .` first.
The ten payload hashes in board/audio_replay/v3/manifest.json are binding. Only v3 contains a bit/hwh pair.
Python 3.12 + NumPy is the C validation environment. Board use needs the existing PYNQ environment and A approval of its final entry point.
Vivado 2018.3 is required by build/scripts/create_audio_replay.tcl; install TUL PYNQ-Z2 board files separately.
Build: vivado -mode batch -source build/scripts/create_audio_replay.tcl -tclargs build
FIR vectors: python scripts/make_fir_vectors.py (generate fixtures before the FIR Tcl simulation).
Pure software checks and evidence scope are in skill/audio-evidence/SKILL.md.
Directory mapping: src hardware/algorithm; sim tests; build Tcl/XDC; board runtime; models frozen Q20;
report evidence; scripts references; skill reusable checks; materials report and submission audit.
No automatic hardware/audio operation is part of this export. A/B manifests/fragments and captain conflict decisions are outstanding.
Third party: src/vendor/pynq_v2_4/LICENSE is BSD-3-Clause and must remain. Team license is pending the user's repository decision.
See materials/work/c/release-checklist.md for the remaining release gates. No upload has occurred.
'''
    data=readme.encode(); (out/'README.md').write_bytes(data)
    entries.append(dict(path='README.md',owner='C',source_commit=local_ref or 'uncommitted C draft',
        source_path='materials/work/c/assemble_candidate.py',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
        purpose='candidate entry and directory mapping',dependencies=[],public_review='team authored'))
    encoded=json.dumps(summary,ensure_ascii=False,indent=2)+'\n'
    (out/'integration.json').write_text(encoded,encoding='utf-8')
    (ROOT/'materials/work/c/integration.json').write_text(encoded,encoding='utf-8')
    print(json.dumps({'candidate':str(out),'files':len(entries),'bytes':sum(e['bytes'] for e in entries),'release_ready':False}))

if __name__=='__main__':
    main()
