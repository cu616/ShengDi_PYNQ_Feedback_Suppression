"""Freeze an experiment from C tools and A/B's exact, accepted assets.

Without --assets, produces an explicit OFFLINE_ONLY distribution. Missing assets
are never replaced with synthetic coefficients or silently enabled hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
from experiment import PLAN
from evaluation import CONFIG, VERSION, sha
from residual_tools import load_candidate
from check_a_driver import check

def assemble(out, assets=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    origin = ROOT/'board/audio_replay'
    required = ['experiment.py','evaluation.py','growth_monitor.py','replay_trial.py',
                'tail_metrics.py','model_comparison.py',
                'replay_tools.py','closed_tools.py','residual_tools.py',
                'audio_replay.bit','audio_replay.hwh']
    for name in required: shutil.copy2(origin/name, out/name)
    source = '# C fixed experiment entry\nimport experiment\nresult = experiment.run_package()\n'
    nb = dict(nbformat=4,nbformat_minor=5,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},
              cells=[dict(cell_type='markdown',metadata={},source=['C 固定批次。只执行下方唯一代码格；见包内 OPERATIONS.md。']),
                     dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=source.splitlines(True))])
    (out/'experiment.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copytree(ROOT/'models',out/'models')
    shutil.copytree(ROOT/'report/verification/model-package-2026-10-23',
                    out/'report/verification/model-package-2026-10-23')
    from model_comparison import load_registry
    load_registry(out/'models')
    missing=['A repaired driver accepted by c-a-driver-acceptance-v2',
             'A verified 256-logical/512-physical baseline loading evidence',
             'A verified box scene.json with calibration_match_original=true']
    acceptance = None
    if assets:
        assets = Path(assets)
        for name in ('replay_trial.py','replay_tools.py','closed_tools.py','residual_tools.py',
                     'audio_replay.bit','audio_replay.hwh','model.json','scene.json'):
            shutil.copy2(assets/name,out/name)
        acceptance = check(out,out/'a-acceptance.json')
        if not acceptance['accepted']:
            raise ValueError('A driver acceptance failed; directory kept OFFLINE until fixed')
        if sha(out/'audio_replay.bit') != '8b2426f4fbcf27425731899557b179d2aea8a4ec2fa26dcc11b60102ecb45339':
            raise ValueError('unexpected bitstream; frozen experiment uses audited A 512 baseline')
        if sha(out/'audio_replay.hwh') != '3873b16b0e273945be8acff0cdebcfbc6e41a6b694d179d3b62955fd452505bb':
            raise ValueError('unexpected HWH')
        scene=json.loads((out/'scene.json').read_text(encoding='utf8'))
        if (scene.get('fixture_id')!='box_v1_20261016' or scene.get('operator_verified') is not True
            or scene.get('calibration_match_original') is not True or scene.get('hp_volume')!=40):
            raise ValueError('scene not confirmed for current box baseline')
        model,q=load_candidate(out/'model.json',scene['fixture_id'],40,48828.125)
        if len(q)>512: raise ValueError('model exceeds bitstream capacity')
        if len(q)==256:
            shutil.copy2(assets/'load_compatibility.json',out/'load_compatibility.json')
            compat=json.loads((out/'load_compatibility.json').read_text(encoding='utf8'))
            if not (compat.get('passed') is True and compat.get('logical_taps')==256
                    and compat.get('loaded_taps')==512 and compat.get('loaded_count_readback')==512
                    and compat.get('driver_sha256')==sha(out/'replay_trial.py')
                    and compat.get('model_sha256')==sha(out/'model.json')
                    and compat.get('bit_sha256')==sha(out/'audio_replay.bit')):
                raise ValueError('A 256/512 loading evidence missing or mismatched')
        if scene.get('approved_model_sha256')!=sha(out/'model.json'):
            raise ValueError('existing model hash needs A/B approval in scene.json')
        missing=[]
    digest=hashlib.sha256(json.dumps([source],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    names=required+(['model.json','scene.json','a-acceptance.json'] if assets else [])
    manifest=dict(package_version='c-experiment-'+VERSION.rsplit('-',1)[1],calculation_version=VERSION,
                  status='ready' if not missing else 'offline_only',missing=missing,
                  main_commit='03f3063a5dd7fbf658a8fe3be9bdf4da515f64f4',
                  a_commit='59aa10e537c43ba2ba259e474c487eebaa88740d',
                  b_reviewed_commit='ffa035a7d6b5b1ed598ac109ab7717ec12436e9d',
                  c_growth_origin='4e266e3999b11707e6a28dabacab9566f5fec302',
                  driver_acceptance=acceptance,plan=PLAN,detector_config=CONFIG,
                  hashes={name:sha(out/name) for name in names},notebook_code_sha256=digest,
                  hardware_executed=False,detector_online=False)
    (out/'experiment-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(ROOT/'board/audio_closed/BATCH_GUIDE.md',out/'OPERATIONS.md')
    shutil.copy2(ROOT/'scripts/review_measurements.py',out/'review_measurements.py')
    shutil.copy2(ROOT/'report/verification/audio_closed/batch-control.md',out/'REVIEW.md')
    evidence=out/'offline-evidence'; evidence.mkdir()
    for name in ('measurement-review-v2-final.json','a-driver-baseline-acceptance.json','measurement-v2-tests.txt'):
        p=ROOT/'report/verification/audio_closed'/name
        if p.exists(): shutil.copy2(p,evidence/name)
    # Bind all immutable payload, including instructions and offline programs.
    # Notebook execution output is mutable, so only its code hash is enforced.
    manifest['hashes'] = {str(p.relative_to(out)).replace('\\','/'):sha(p)
                          for p in sorted(out.rglob('*')) if p.is_file()
                          and p.name not in ('experiment-manifest.json','experiment.ipynb')
                          and '__pycache__' not in p.parts}
    (out/'experiment-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts: z.write(p,p.relative_to(out))
    return manifest

def assemble_review(out):
    """A standalone, read-only NPZ review bundle; no driver, bit or audio action."""
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    for name in ('evaluation.py','growth_monitor.py','tail_metrics.py','model_comparison.py',
                 'closed_tools.py','replay_tools.py','residual_tools.py'):
        shutil.copy2(ROOT/'board/audio_replay'/name,out/name)
    shutil.copy2(ROOT/'scripts/summarize_tail_batch.py',out/'summarize_tail_batch.py')
    shutil.copytree(ROOT/'models',out/'models')
    shutil.copytree(ROOT/'report/verification/model-package-2026-10-23',
                    out/'report/verification/model-package-2026-10-23')
    from model_comparison import load_registry
    registry=load_registry(out/'models')
    code='''# C existing NPZ review: silent, read only
from pathlib import Path
import hashlib, json, uuid
from summarize_tail_batch import summarize
here = Path.cwd()
manifest = json.loads((here / 'review-manifest.json').read_text(encoding='utf8'))
for name, digest in manifest['hashes'].items():
    assert hashlib.sha256((here / name).read_bytes()).hexdigest() == digest, name
notebook = json.loads((here / 'tail-review.ipynb').read_text(encoding='utf8'))
codes = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
assert hashlib.sha256(json.dumps(codes, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == manifest['notebook_code_sha256']
print('SILENT_PACKAGE_OK; no board devices or playback')
source = Path(input('已有房间试验 NPZ 根目录的完整路径：').strip())
evidence = input('A核实的 evidence.json 完整路径；没有则直接回车：').strip()
output = here / 'results' / ('review-' + uuid.uuid4().hex[:12])
summary = summarize(source, output, here / 'models', Path(evidence) if evidence else None)
'''
    nb=dict(nbformat=4,nbformat_minor=5,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},
            cells=[dict(cell_type='markdown',metadata={},source=['C 已有记录静默复算。只运行下方唯一代码格。']),
                   dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=code.splitlines(True))])
    (out/'tail-review.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(ROOT/'board/audio_closed/BATCH_GUIDE.md',out/'OPERATIONS.md')
    manifest=dict(package_version='c-tail-review-3.0.0',calculation_version=VERSION,
                  board_actions=False,model_registry=registry,
                  b_commit='ffa035a7d6b5b1ed598ac109ab7717ec12436e9d',
                  hashes={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*')
                          if p.is_file() and p.name!='tail-review.ipynb'},
                  notebook_code_sha256=hashlib.sha256(json.dumps([code],ensure_ascii=False,separators=(',',':')).encode()).hexdigest())
    (out/'review-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(out))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--assets',type=Path)
    p.add_argument('--review-only',action='store_true')
    a=p.parse_args()
    m=assemble_review(a.output) if a.review_only else assemble(a.output,a.assets)
    print(json.dumps({'package':str(a.output),'status':m.get('status','silent_review'),
                      'missing':m.get('missing',[])},ensure_ascii=False))
