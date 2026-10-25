"""Freeze an experiment from C tools and A/B's exact, accepted assets.

Without --assets, produces an explicit OFFLINE_ONLY distribution. Missing assets
are never replaced with synthetic coefficients or silently enabled hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
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
    from model_comparison import load_registry, SUMMARY_REVISION
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
    manifest=dict(package_version='c-tail-review-'+SUMMARY_REVISION,summary_revision=SUMMARY_REVISION,calculation_version=VERSION,
                  board_actions=False,model_registry=registry,
                  b_commit='59ab1ee55bf54d1e075647afffd14a9e0f4eff32',
                  hashes={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*')
                          if p.is_file() and p.name!='tail-review.ipynb'},
                  notebook_code_sha256=hashlib.sha256(json.dumps([code],ensure_ascii=False,separators=(',',':')).encode()).hexdigest())
    (out/'review-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(out))
    return manifest


def assemble_room(out,assets):
    """Freeze A's current-session models and exact driver; no hardware actions."""
    from room_experiment import PLAN as ROOM_PLAN, POLICY, sources
    from model_comparison import load_registry, qhash, SUMMARY_REVISION
    import numpy as np
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);assets=Path(assets)
    for name in ('room_experiment.py','evaluation.py','growth_monitor.py','model_comparison.py',
                 'tail_metrics.py'):
        shutil.copy2(ROOT/'board/audio_replay'/name,out/name)
    for name in ('replay_trial.py','replay_tools.py','closed_tools.py','residual_tools.py',
                 'audio_replay.bit','audio_replay.hwh','live_pa.py'):
        shutil.copy2(assets/name,out/name)
    expected={'replay_trial.py':'212766325d6f0f65f75503638f8d350caf6f3397813893bf360f40f94847aa62',
              'audio_replay.bit':'8b2426f4fbcf27425731899557b179d2aea8a4ec2fa26dcc11b60102ecb45339',
              'audio_replay.hwh':'3873b16b0e273945be8acff0cdebcfbc6e41a6b694d179d3b62955fd452505bb'}
    for name,digest in expected.items():
        if sha(out/name)!=digest:raise ValueError('A audited asset mismatch: '+name)
    acceptance=check(out,out/'a-acceptance.json')
    if not acceptance['accepted']:raise ValueError('A acceptance failed')
    original=json.loads((assets/'scene.json').read_text(encoding='utf8'))
    if (original.get('fixture_id')!=ROOM_PLAN['fixture_id'] or original.get('hp_volume')!=40
        or original.get('matches_calibration') is not True or original.get('speakers',{}).get('count')!=1):
        raise ValueError('A current room scene mismatch')
    shutil.copy2(assets/'scene.json',out/'a-scene.json')
    scene=dict(original);scene['prior_approved_model']=scene.pop('approved_model',None)
    scene['integration_recorded_by']='C; current model evidence from A db29698 recalibration and gated records'
    scene['approved_models']=[];registry=dict(schema_version=1,models=[],derived_artifacts=[])
    model_files={}
    for role,taps,digest in (
        ('baseline',256,'5537483e4cc1abd6e8566a8f8bbd6ad8bf436bae14c37a920f1a6458e56db36a'),
        ('candidate',512,'98d0956813720f4a791db0fa510e2216897f3aba2dac35083668e47678430d17')):
        path=out/'models/room-current'/('%s_%d.json'%(role,taps));path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(assets/('model_%d.json'%taps),path)
        if sha(path)!=digest:raise ValueError('A current-session model mismatch')
        model,q=load_candidate(path,ROOM_PLAN['fixture_id'],40,48828.125)
        item={k:model[k] for k in ('fixture_id','hp_volume','sample_rate_hz','lag_first','taps')}
        item.update(file=str(path.relative_to(out/'models')).replace('\\','/'),sha256=digest,role=role,
                    coefficients_sha256=qhash(q),padded_512_sha256=qhash(np.pad(q,(0,512-len(q)))),
                    source_commit='db296988a444cf2f72852dec66f777edb7c103f6',status=model['status'])
        registry['models'].append(item);scene['approved_models'].append(dict(role=role,sha256=digest,logical_taps=taps))
        model_files[role]=str(path.relative_to(out)).replace('\\','/')
    model_files['bypass']=model_files['candidate']
    (out/'models/manifest.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf8')
    load_registry(out/'models')
    (out/'scene.json').write_text(json.dumps(scene,ensure_ascii=False,indent=2),encoding='utf8')
    burst,tone=sources();np.save(out/'burst.npy',burst,allow_pickle=False);np.save(out/'gate.npy',tone,allow_pickle=False)
    source='# C current-room gated experiment entry\nfrom room_experiment import run_room\nresult = run_room()\n'
    nb=dict(nbformat=4,nbformat_minor=5,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},
            cells=[dict(cell_type='markdown',metadata={},source=['C 房间门禁实验。重启内核，仅运行下方唯一代码格；见 OPERATIONS.md。']),
                   dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=source.splitlines(True))])
    (out/'experiment.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(ROOT/'board/audio_closed/BATCH_GUIDE.md',out/'OPERATIONS.md')
    manifest=dict(package_version='c-room-experiment-1.1.0',status='ready',measurement_policy_version=POLICY,
                  calculation_version=VERSION,summary_revision=SUMMARY_REVISION,plan=ROOM_PLAN,model_files=model_files,
                  a_commit='db296988a444cf2f72852dec66f777edb7c103f6',
                  driver_acceptance=acceptance,hardware_executed=False,online_microphone_clip_protection=False,
                  model_provenance='A current-session recalibration; B prior models retained separately for history',
                  sources={name:dict(frames=len(pcm),pcm16_sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
                               rms_dbfs=float(20*np.log10(np.std(pcm.astype(float)/32768))),
                               peak_dbfs=float(20*np.log10(np.max(np.abs(pcm.astype(float)))/32768)))
                           for name,pcm in [('burst',burst),('gate',tone)]},
                  notebook_code_sha256=hashlib.sha256(json.dumps([source],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
                  hashes={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in sorted(out.rglob('*'))
                          if p.is_file() and p.name!='experiment.ipynb' and '__pycache__' not in p.parts})
    (out/'experiment-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(out))
    return manifest


def assemble_r4_b_handoff(out):
    """One data-only handoff: original r4 summaries plus C's bounded review."""
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    a_commit='d013930f0624c35101c92cc8b62d985f10e21e0c'
    packet=subprocess.check_output(['git','show',a_commit+':report/verification/audio-replay/c-sprint-rc01-r4-return.zip'],cwd=ROOT)
    evidence=ROOT/'report/verification/audio_closed/sprint-rc0-20261025'
    c_source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    review=json.loads(subprocess.check_output(['git','show',c_source+':report/verification/audio_closed/sprint-rc0-20261025/a-d013930-review.json'],cwd=ROOT))
    assert review['metadata_review_passed'] and hashlib.sha256(packet).hexdigest()==review['return_zip_sha256']
    (out/'a-original-return.zip').write_bytes(packet)
    import io
    with zipfile.ZipFile(io.BytesIO(packet)) as original:
        original_manifest=json.loads(original.read('return-manifest.json'))
        assert all(hashlib.sha256(original.read(n)).hexdigest()==h for n,h in original_manifest['hashes'].items())
        for name in ('summary-v3.json','summary-v3.csv','summary.json','summary.csv',
                     '07-fir-off.status.json','09-fir-on.status.json','11-fir-on.status.json',
                     '13-fir-off.status.json','15-continuous-60s.status.json'):
            (out/name).write_bytes(original.read(name))
    assert len(json.loads((out/'summary-v3.json').read_text(encoding='utf8'))['fir_switch_pairs'])==2
    for source,target in (('a-d013930-review.json','c-validity-review.json'),
        ('b-71d6a34-review.json','c-b-revision-review.json'),('b-71d6a34-tests.txt','b-control-tests.txt')):
        frozen=subprocess.check_output(['git','show',c_source+':report/verification/audio_closed/sprint-rc0-20261025/'+source],cwd=ROOT)
        (out/target).write_bytes(frozen)
    (out/'README.md').write_text('''# r4 → B：汇总判读输入

唯一数据入口：summary-v3.json → fir_switch_pairs（2组）。每项源内响应见summary.json → trials → source_response。
原返回ZIP、汇总和状态保持字节原样；逐文件哈希在handoff-manifest.json，来源A=d013930。
C配置/配对区间/差分算术/寄存器时间线审核通过，详见c-validity-review.json。

现在即可完成Part二的元数据限定判读；原PCM独立复算仍等5个既有NPZ，不因此搁置汇总分析。
列两次repeat的原值和方向，repeat散布只作描述；不以1.5dB门禁或两次散布设通用分辨率。
区分实际全频带测量与只覆盖门控bin的白谱稳态参考，低频方向不一致和高频增大照实列出。
不生成MSG/ASG，不写全程音质或抗啸叫通过；PROXY真人/听众仍未测。

B=71d6a34闭环/余量/控制数值已由C独立通过；N1–N3发布措辞与机器标签仍待修，详见c-b-revision-review.json。
修订在现场结果到达后发生，不追认为事前预测。默认模型和无新候选决定保持。
本包为离线数据交接，无板端执行步骤；真人现场继续使用已发布的c-sprint-rc01-human-r1完整包。
''',encoding='utf8')
    manifest=dict(kind='r4_to_b_metadata_handoff',entry='summary-v3.json',array='fir_switch_pairs',
        a_result_commit=a_commit,a_asset_commit='85f4967f242eed61eaa6b74041be931c2f5bc7a0',
        b_revision_commit='71d6a349af3af2675e5be95b583180902ab9a090',
        c_source_commit=c_source,
        original_return_sha256=hashlib.sha256(packet).hexdigest(),metadata_validity='passed',
        raw_waveform_independent_review='not_tested_missing_five_existing_npz',raw_audio_included=False,
        missing_raw_files=review['missing_raw_once'],
        hashes={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'handoff-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(out.iterdir()):archive.write(p,p.name)
    with zipfile.ZipFile(out.with_suffix('.zip')) as archive:
        assert not any(n.endswith(('.npz','.wav','.bit','.hwh')) for n in archive.namelist())
        assert all(hashlib.sha256(archive.read(n)).hexdigest()==h for n,h in manifest['hashes'].items())
        assert archive.read('a-original-return.zip')==packet
    print(json.dumps(dict(artifact=str(out.with_suffix('.zip')),size_bytes=out.with_suffix('.zip').stat().st_size,
        sha256=sha(out.with_suffix('.zip')),pairs=2,metadata_validity='passed'),ensure_ascii=False))
    return dict(package_status='r4_b_metadata_ready')


def assemble_sprint(out, assets, model_path, human_only=False):
    """RC0 with the strong historical baseline and byte-identical A drivers.

    A future candidate is integrated by rebuilding the complete package with a
    reviewed model_path, never by patching files on a running board.
    """
    from sprint_experiment import POLICY, PLAN as SPRINT_PLAN, DEFAULT_MODEL, A_ASSETS
    from model_comparison import qhash
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);assets=Path(assets)
    for name in ('sprint_experiment.py','sprint_selftest.py','listener_metrics.py','sprint_continuous.py','evaluation.py','growth_monitor.py','tail_metrics.py',
                 'model_comparison.py','room_experiment.py'):
        shutil.copy2(ROOT/'board/audio_replay'/name,out/name)
    origins={name:'board/audio_replay/'+name for name in
             ('replay_trial.py','replay_tools.py','closed_tools.py','residual_tools.py','live_run.py')}
    origins.update({name:'board/audio_replay/v2/'+name for name in ('audio_replay.bit','audio_replay.hwh')})
    for name,origin in origins.items():
        shutil.copy2(assets/Path(origin).relative_to('board/audio_replay'),out/name)
    expected={'audio_replay.bit':A_ASSETS['bit_sha256'],'audio_replay.hwh':A_ASSETS['hwh_sha256']}
    for name,digest in expected.items():
        if sha(out/name)!=digest:raise ValueError('RC0 bit/hwh mismatch: '+name)
    for name,origin in origins.items():
        frozen=subprocess.check_output(['git','show',A_ASSETS['commit']+':'+origin],cwd=ROOT)
        if (out/name).read_bytes()!=frozen:raise ValueError('ASSET_MISMATCH: '+name+' differs from bound A commit')
    acceptance=check(out,out/'a-driver-acceptance.json')
    if not acceptance['accepted']:raise ValueError('A driver software acceptance failed')
    from check_a_driver import check_continuous
    live_acceptance=check_continuous(assets,out/'a-continuous-acceptance.json')
    if not live_acceptance['accepted']:raise ValueError('A continuous driver software acceptance failed')
    model,q=load_candidate(model_path,SPRINT_PLAN['fixture_id'],40,48828.125)
    if len(q)!=512:raise ValueError('RC0 requires a 512-tap model')
    if sha(model_path)!=DEFAULT_MODEL['file_sha256'] or qhash(q)!=DEFAULT_MODEL['coefficients_sha256']:
        raise ValueError('RC0 default must be calibrated_20261024; review and re-freeze before selecting another model')
    shutil.copy2(model_path,out/'model.json')
    (out/'models/room_v1').mkdir(parents=True)
    shutil.copy2(model_path,out/'models/room_v1/calibrated_20261024.json')
    registry_entry={k:model[k] for k in ('fixture_id','hp_volume','sample_rate_hz','lag_first','taps')}
    registry_entry.update(file='room_v1/calibrated_20261024.json',sha256=sha(out/'model.json'))
    (out/'models/manifest.json').write_text(json.dumps({'models':[registry_entry]},indent=2),encoding='utf8')
    shutil.copy2(assets/'scene.json',out/'a-historical-scene.json')
    (out/'eq.json').write_text(json.dumps({'type':'identity','contribution':'not_tested'}),encoding='utf8')
    guide=(ROOT/'board/audio_closed/BATCH_GUIDE.md').read_text(encoding='utf8')
    marker='## 2026-10-25 集中实验 RC0'
    (out/'OPERATIONS.md').write_text(guide[guide.index(marker):],encoding='utf8')
    title=('# C sprint RC0.1-human-r1: live speech and listener only, -14 dB, v2' if human_only else
           '# C sprint RC0.1-full: source 2.50s/run 2.52s, -14 dB, v2 continuous 60s')
    source=title+'\nfrom sprint_experiment import run_sprint\nresult = run_sprint()\n'
    notebook=dict(nbformat=4,nbformat_minor=5,
        metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},
        cells=[dict(cell_type='markdown',metadata={},source=['只运行从上往下第1个代码格；先读 OPERATIONS.md。']),
               dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=source.splitlines(True))])
    (out/'sprint.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf8')
    evidence=ROOT/'report/verification/audio_closed/sprint-rc0-20261025'
    for name in ('audit.json','tests.txt','tests-r1.txt','tests-rc01.txt','tests-rc01-r1.txt','tests-rc01-r2.txt',
                 'tests-rc01-r3.txt','tests-rc01-r4.txt','tests-rc01-human-r1.txt','a-r4-receipt.json','b-dbf2858-review.json',
                 'a-cf949f2-review.json','a-1219851-review.json','a-d013930-review.json',
                 'a-85f4967-review.json','a-85f4967-driver-review.json',
                 'a-1cddd52-continuous-review.json','a-1cddd52-driver-review.json',
                 'b-handoff-review.json','rc01-input-review.json',
                 'b-6128282-review.json','b-6128282-tests.txt','b-6128282-repro.txt'):
        if (evidence/name).exists():
            (out/'offline-evidence').mkdir(exist_ok=True);shutil.copy2(evidence/name,out/'offline-evidence'/name)
    manifest=dict(policy=POLICY,calculation_version=VERSION,detector_config=CONFIG,plan=SPRINT_PLAN,
        workflow='human_only' if human_only else 'full',
        default_model=DEFAULT_MODEL,
        a_assets=A_ASSETS,
        a_file_origins=origins,
        package_status='human_session_ready' if human_only else 'baseline_and_v2_continuous_ready_for_board_execution',
        source_commits={'A':A_ASSETS['commit'],
                        'B':'d033d0047542d5e50654a0333777c48ec08dce21',
                        'C':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()},
        b_independently_reviewed_commit='6128282f2853b829768c7310e57b08f0d84c4b89',
        coefficients_sha256=qhash(q),driver_software_acceptance=acceptance,continuous_driver_software_acceptance=live_acceptance,
        hardware_executed=False,online_growth_detection=False,continuous_60s=not human_only,
        source_tree_clean=not bool(subprocess.check_output(['git','status','--porcelain','--',
            'board/audio_replay','scripts/assemble_experiment.py'],cwd=ROOT).strip()),
        hashes={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in sorted(out.rglob('*'))
                if p.is_file() and '__pycache__' not in p.parts})
    (out/'sprint-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    from sprint_experiment import check_package
    from sprint_selftest import run_selftest, selftest_line
    preflight=run_selftest(out,require_preflight=False)
    print(selftest_line(preflight))
    if preflight['all_ok'] is not True:raise ValueError('PREFLIGHT_FAIL: '+str(preflight.get('stop_reason')))
    (out/'preflight.json').write_text(json.dumps(preflight,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    manifest['hashes']['preflight.json']=sha(out/'preflight.json')
    (out/'sprint-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    check_package(out)
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(out.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:archive.write(p,p.relative_to(out))
    with zipfile.ZipFile(out.with_suffix('.zip')) as archive:
        for name,digest in manifest['hashes'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                raise ValueError('archive payload hash mismatch: '+name)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--assets',type=Path)
    p.add_argument('--review-only',action='store_true')
    p.add_argument('--room-ready',action='store_true')
    p.add_argument('--sprint-ready',action='store_true')
    p.add_argument('--sprint-human',action='store_true')
    p.add_argument('--r4-b-handoff',action='store_true')
    p.add_argument('--model',type=Path)
    a=p.parse_args()
    if a.r4_b_handoff:
        m=assemble_r4_b_handoff(a.output)
    elif a.sprint_ready or a.sprint_human:
        if not a.assets or not a.model:p.error('sprint package requires --assets and --model')
        m=assemble_sprint(a.output,a.assets,a.model,human_only=a.sprint_human)
    elif a.room_ready:
        if not a.assets:p.error('--room-ready requires --assets')
        m=assemble_room(a.output,a.assets)
    else:m=assemble_review(a.output) if a.review_only else assemble(a.output,a.assets)
    print(json.dumps({'package':str(a.output),'status':m.get('status',m.get('package_status','silent_review')),
                      'missing':m.get('missing',[])},ensure_ascii=False))
