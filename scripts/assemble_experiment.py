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


def assemble_product(out, hardware=None, algorithm=None, review=False):
    """C product white-list; never copies a stale C driver or executes hardware."""
    import importlib.util
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    origin=ROOT/'board/audio_replay'
    names=['recal_entry.sh','recal_product.py','recal_policy_consumer.py','recal_runtime.py','recal_link.py','product-install.sh','shengdi-product.service']
    # Source names differ after integration; the installed C entry stays unchanged.
    for name in names:
        source_name = "recal_product_entry.sh" if name == "recal_entry.sh" else name
        shutil.copyfile(origin/source_name,out/name)
    # B's numeric library is copied byte-for-byte; the C bridge adds no thresholds.
    (out/'feedback').mkdir()
    for name in ('__init__.py','recal_policy.py','excitation.py'):
        shutil.copyfile(ROOT/'src/feedback'/name,out/'feedback'/name)
    adapters={};missing=[]
    for kind,folder in [('hardware',hardware),('algorithm',algorithm)]:
        if folder is None:
            missing.append(kind+': v1 adapter and approved policy not delivered');continue
        folder=Path(folder).resolve()
        meta=json.loads((folder/'product-adapter.json').read_text(encoding='utf-8'))
        if meta.get('contract')!='recal-product-v1' or meta.get('kind')!=kind or (not review and meta.get('field_approved') is not True):
            raise ValueError('adapter contract/approval missing: '+kind)
        for name,digest in meta['hashes'].items():
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts: raise ValueError('unsafe adapter path')
            source=(folder/relative).resolve()
            if folder not in source.parents or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
                raise ValueError('adapter identity mismatch: '+name)
            target=out/relative
            if target.exists() and target.read_bytes()!=source.read_bytes(): raise ValueError('adapter owner collision: '+name)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
        adapters[kind]=meta
    if not (out/'residual_tools.py').is_file(): shutil.copyfile(origin/'residual_tools.py',out/'residual_tools.py')
    if review and len(adapters)!=2: raise ValueError('review requires both exact adapters; no real/mock mixture')
    simulation=bool(missing)
    if simulation:
        # No partial real/mock mixture is runnable. The demo always uses two mocks.
        shutil.copyfile(origin/'recal_mock.py',out/'recal_mock.py')
        spec=importlib.util.spec_from_file_location('product_fixture_config',origin/'recal_mock.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);config=module.sample_config()
    else:
        if adapters['algorithm'].get('algorithm_contract')=='recalibration-algorithm-v1':
            sys.path.insert(0,str(ROOT/'src'))
            from recal_runtime import product_policy
            spec=importlib.util.spec_from_file_location('frozen_package_algorithm',out/'recal_algorithm.py')
            algorithm=importlib.util.module_from_spec(spec);spec.loader.exec_module(algorithm)
            if callable(getattr(algorithm,'identity',None)):
                from recal_link import frozen_policy,capture_plans
                policy=frozen_policy(algorithm);policy['capture_plans']=capture_plans(policy['attempts'])
            else: policy=product_policy()
            (out/'product-policy.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
        required=['hw_api.py','recal_algorithm.py','product-policy.json','physical-controls.json']
        if any(not (out/name).is_file() for name in required): raise ValueError('incomplete real adapter package')
        config=json.loads((out/'product-policy.json').read_text(encoding='utf-8'))
        config.update(simulation=False,hardware_module='hw_api',
                      expected_identity=adapters['hardware']['expected_identity'])
        config.setdefault('algorithm_module','recal_algorithm')
        config.update(adapters['hardware'].get('config',{}))
        if config.get('bootstrap_model'):
            if config['bootstrap_model']!='bootstrap-model.json':raise ValueError('unsupported bootstrap path')
            bootstrap=dict(fixture_id='bootstrap-muted',taps=512,lag_first=1,
                coefficient_format='signed24_fraction20',training_source='board',
                hp_volume=config['expected_identity']['hp_volume'],
                sample_rate_hz=config['expected_identity']['sample_rate_hz'],
                coefficients_q20=[0]*512,coefficients=[0.0]*512,bias=0.0,
                bootstrap_only=True,eligible=False,
                provenance='generated zero coefficients for muted open-loop initialization; no measured model')
            (out/config['bootstrap_model']).write_text(json.dumps(bootstrap,indent=2)+'\n',encoding='utf-8')
        allowed=adapters['hardware'].get('allowed_gain_q12',[])
        gains=[g for values in config.get('phase_gain_q12',{}).values() for g in values]
        calibration=adapters['hardware'].get('allowed_calibration_gain_q12',[])
        if config.get('bootstrap_model'):
            # mute preserves the previous approved gain; prepare changes it to open-loop zero.
            config['phase_gain_q12']['prepare']=sorted(set(allowed+calibration))
        if (config['expected_identity']['gain_q12'] not in allowed
                or any(type(g) is not int or g not in allowed+calibration for g in gains)):
            if not review: raise ValueError('B phase gain policy exceeds A approved gains')
            missing.append('hardware: calibration gain approval missing')
        caps=adapters['hardware'].get('capabilities',{})
        ready=(caps.get('cue_input_ready_event') is True if config.get('input_mode')=='cue_input'
               else caps.get('prepared_capture') is True)
        if not ready: missing.append('hardware: input capture is not prepared before speech prompt')
        for kind,meta in adapters.items():
            missing.extend(kind+': '+v for v in meta.get('blockers',[]))
            if meta.get('field_approved') is not True: missing.append(kind+': integration not approved')
        if missing and not review:
            raise ValueError('product adapter blockers: '+','.join(missing))
        if config.get('runtime_profile') in ('b-heldout-v1','b-frozen-v1') and config.get('compute_timeout_seconds',0)<15:
            raise ValueError('fit timeout must be at least 15 seconds')
    (out/'product-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    operations=(ROOT/'docs/ref/recal-product.md').read_text(encoding='utf-8').replace(
        '../contracts/recal-product-v1.md','INTERFACE.md').replace(
        '../contracts/recal-policy-consumer-v1.md','POLICY-CONSUMER.md').replace(
        '../contracts/recal-runtime-v2.md','RUNTIME.md').replace(
        '../contracts/recal-runtime-v3.md','FROZEN-RUNTIME.md').replace(
        '../contracts/recal-runtime-v4.md','INSTALL-RUNTIME.md').replace(
        '../contracts/recal-runtime-v5.md','MAINTENANCE-RUNTIME.md').replace(
        '../contracts/recal-runtime-v6.md','FINAL-RUNTIME.md').replace(
        '../contracts/recal-runtime-v7.md','BOOT-RECOVERY.md').replace(
        '../contracts/recal-runtime-v8.md','IO-INDICATOR.md').replace(
        '../contracts/recal-runtime-v9.md','GUARD-RUNTIME.md').replace(
        '../contracts/recal-runtime-v10.md','DEMO-RUNTIME.md').replace(
        '../contracts/recalibration-algorithm-v1.md','ALGORITHM.md')
    # Historical evidence belongs to the source repository, outside this install whitelist.
    import re
    operations=re.sub(r'\[([^\]]+)\]\(\.\./\.\./report/[^)]+\)',r'\1（见源码仓库report目录）',operations)
    (out/'OPERATIONS.md').write_text(operations,encoding='utf-8')
    (out/'INTERFACE.md').write_text((ROOT/'docs/contracts/recal-product-v1.md').read_text(encoding='utf-8').replace(
        '../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'POLICY.md').write_bytes((ROOT/'docs/contracts/recalibration-policy-v1.md').read_bytes())
    (out/'POLICY-CONSUMER.md').write_text((ROOT/'docs/contracts/recal-policy-consumer-v1.md').read_text(encoding='utf-8').replace(
        'recal-product-v1.md','INTERFACE.md').replace('recalibration-policy-v1.md','POLICY.md').replace(
        '../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v2.md').read_text(encoding='utf-8').replace(
        '../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'ALGORITHM.md').write_bytes((ROOT/'docs/contracts/recalibration-algorithm-v1.md').read_bytes())
    (out/'FROZEN-RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v3.md').read_text(encoding='utf-8').replace(
        '../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'INSTALL-RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v4.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v3.md','FROZEN-RUNTIME.md').replace('../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'MAINTENANCE-RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v5.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v4.md','INSTALL-RUNTIME.md').replace('../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'FINAL-RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v6.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v5.md','MAINTENANCE-RUNTIME.md').replace('../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'BOOT-RECOVERY.md').write_text((ROOT/'docs/contracts/recal-runtime-v7.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v6.md','FINAL-RUNTIME.md').replace('../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'IO-INDICATOR.md').write_text((ROOT/'docs/contracts/recal-runtime-v8.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v7.md','BOOT-RECOVERY.md').replace('../ref/recal-product.md','OPERATIONS.md'),encoding='utf-8')
    (out/'GUARD-RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v9.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v8.md','IO-INDICATOR.md').replace('../ref/recal-product.md','OPERATIONS.md').replace(
        '../../report/verification/audio-replay/guard-2026-11-02/README.md',
        'https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/dd0825065462a8433bde2ffaff120798ae73ca2f/report/verification/audio-replay/guard-2026-11-02/README.md'),encoding='utf-8')
    guard=out/'GUARD-RUNTIME.md'
    guard.write_text(guard.read_text(encoding='utf-8').replace(
        '../../report/verification/recal-product-v1/guard150-baseline-probe.json',
        'https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/main/report/verification/recal-product-v1/guard150-baseline-probe.json'),encoding='utf-8')
    (out/'DEMO-RUNTIME.md').write_text((ROOT/'docs/contracts/recal-runtime-v10.md').read_text(encoding='utf-8').replace(
        'recal-runtime-v9.md','GUARD-RUNTIME.md').replace('../ref/recal-product.md','OPERATIONS.md').replace(
        '../../report/verification/audio-replay/demo-protocol-2026-11-02/README.md',
        'https://github.com/cu616/ShengDi_PYNQ_Feedback_Suppression/blob/eb881fe405fcafbf8b0e35cc8356de3213520366/report/verification/audio-replay/demo-protocol-2026-11-02/README.md'),encoding='utf-8')
    payloads=[p for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts
              and p.suffix not in ('.pyc','.pyo')]
    manifest=dict(contract='recal-product-v1',simulation=simulation,deployment_ready=not simulation and not review and not missing,
        missing=missing,adapters=adapters,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        algorithm_identity=config.get('algorithm_identity'),
        adapter_check_allowed=bool(adapters.get('hardware',{}).get('adapter_check_allowed')),
        field_trial_allowed=bool(adapters.get('hardware',{}).get('field_trial_allowed')),
        diagnostic_model=adapters.get('hardware',{}).get('diagnostic_model'),
        source_tree_clean=not bool(subprocess.check_output(['git','status','--porcelain','--',
            'board/audio_replay/recal_product.py','board/audio_replay/recal_mock.py','board/audio_replay/recal_product_entry.sh',
            'board/audio_replay/recal_policy_consumer.py',
            'board/audio_replay/recal_runtime.py','board/audio_replay/recal_algorithm.py',
            'board/audio_replay/recal_link.py',
            'board/audio_replay/product-install.sh','board/audio_replay/shengdi-product.service',
            'src/feedback/recal_policy.py','src/feedback/excitation.py',
            'scripts/assemble_experiment.py','docs/ref/recal-product.md','docs/contracts/recal-product-v1.md',
            'docs/contracts/recalibration-policy-v1.md','docs/contracts/recal-policy-consumer-v1.md',
            'docs/contracts/recal-runtime-v2.md','docs/contracts/recal-runtime-v3.md',
            'docs/contracts/recal-runtime-v4.md','docs/contracts/recal-runtime-v5.md','docs/contracts/recal-runtime-v6.md',
            'docs/contracts/recal-runtime-v7.md',
            'docs/contracts/recal-runtime-v8.md',
            'docs/contracts/recal-runtime-v9.md','scripts/freeze_recal_guard.py',
            'docs/contracts/recal-runtime-v10.md',
            'docs/contracts/recalibration-algorithm-v1.md'],cwd=ROOT).strip()),
        hashes={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in payloads})
    (out/'product-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(payloads+[out/'product-manifest.json']):
            z.write(path,path.relative_to(out))
    return dict(status='software_simulation_only' if simulation else
                'integration_review_blocked' if review else 'adapters_bound_pending_field_acceptance',missing=missing)

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


def assemble_layout(out, candidate_commit=None, repair_binding=None, baseline_first=False):
    """New-layout preparation: exact A assets, no legacy candidate or hardware."""
    from layout_experiment import POLICY, FIXTURE, PLAN as LAYOUT_PLAN, A_COMMIT, SCENE_COMMIT, REPAIRED_CAPTURE_MANIFEST, REPAIRED_CAPTURE_SET, template, scene_template, notebook_code_hash, check as check_layout
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    for name in ('layout_experiment.py','listener_metrics.py','sprint_continuous.py','evaluation.py',
                 'growth_monitor.py','tail_metrics.py','model_comparison.py','room_experiment.py'):
        shutil.copy2(ROOT/'board/audio_replay'/name,out/name)
    origins={name:'board/audio_replay/'+name for name in
             ('replay_trial.py','live_run.py','replay_tools.py','closed_tools.py','residual_tools.py')}
    origins.update({name:'board/audio_replay/v2/'+name for name in ('audio_replay.bit','audio_replay.hwh')})
    origins['a-field-config-original.json']='report/verification/audio-replay/field-config-2026-10-26.json'
    origins.update({'a-'+name+'-original.json':'report/verification/audio-replay/'+name+'-2026-10-26.json'
        for name in ('scene-input','live-round','mic-fault-impact','usable-point')})
    origins['a-repaired-capture-manifest.json']='report/verification/audio-replay/bind-capture-2026-10-26/manifest.json'
    origins['a-repaired-capture-details.json']='report/verification/audio-replay/bind-capture-2026-10-26/bind_manifest.json'
    for name,origin in origins.items():
        commit=SCENE_COMMIT if origin.startswith('report/') else A_COMMIT
        (out/name).write_bytes(subprocess.check_output(['git','show',commit+':'+origin],cwd=ROOT))
    if sha(out/'a-repaired-capture-manifest.json')!=REPAIRED_CAPTURE_MANIFEST:raise ValueError('repair capture manifest mismatch')
    for name in ('a-field-config-original.json','a-live-round-original.json','a-mic-fault-impact-original.json','a-usable-point-original.json'):
        json.loads((out/name).read_text(encoding='utf8'))
    (out/'candidate-input.json').write_text(json.dumps(template(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    scene=json.loads((out/'a-scene-input-original.json').read_text(encoding='utf8'))
    scene['fixture_id']=FIXTURE
    scene['fixture_provenance']=dict(original_scene_fixture='room_v1_20261026',
        original_capture_metadata_fixture='room_v1_20261021',actual_fixture=FIXTURE,
        basis='A=52ee4e4 repaired capture geometry + B=b6bcfb2 matching model; confirm unchanged at FIELD_READY',
        original_files_modified=False)
    if baseline_first:
        scene.update(talker_to_microphone_cm=5.,verified_by_A=False,source_kind='human_live',talker_id=None,phrase=None,
            fixed_speech_source=dict(kind='human_live',talker_id=None,phrase=None),
            talker_distance_basis='0f17c74: silence-output qualification at recorded 5cm; one distance-only variant if rejected; historical microphone state unknown',
            a_limits_basis='0f17c74 success-first protocol: recorded -8dB zero FIR, input-qualified 5cm; one distance-only variant 15-30cm if rejected; no gain scan')
        history_origin='report/verification/audio-replay/usable-point-2026-10-26.json'
        (out/'a-historical-usable-point.json').write_bytes(subprocess.check_output(['git','show','0f17c74:'+history_origin],cwd=ROOT))
        (out/'baseline-model.json').write_bytes(subprocess.check_output(['git','show','b6bcfb2:models/room_v1/rewired_512_20261026.json'],cwd=ROOT))
        if sha(out/'baseline-model.json')!='01c9102af5e010e5d40fe01edb54f38b1c34f09b4690a936f17a88cb8e235c23':
            raise ValueError('baseline zero-transport file changed')
        import numpy as np
        from sprint_continuous import driver_request
        from layout_experiment import sources
        cue=sources(None)[2]
        baseline_checks=[driver_request(out,'replay_trial',out/'software-only-9p5.npz',FIXTURE,out/'baseline-model.json',cue,
            gain_db=-8.,seconds=9.5,hp_volume=40,bypass=False,zero_coeff=True,speaker_confirmed=True,local_capture_confirmed=True),
            driver_request(out,'live_run',out/'software-only-60s.npz',FIXTURE,out/'baseline-model.json',
            gain_db=-8.,seconds=60.,hp_volume=40,bypass=False,zero_coeff=True,speaker_confirmed=True,local_capture_confirmed=True)]
        (out/'baseline-driver-compatibility.json').write_text(json.dumps(dict(checks=baseline_checks,
            scope='pure driver argument/frame-budget validation, not actual speaker or human confirmation',hardware_access=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (out/'scene-input.json').write_text(json.dumps(scene,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if candidate_commit:
        import numpy as np
        from layout_experiment import RATE, FIXTURE
        from sprint_continuous import driver_request
        from model_comparison import qhash
        candidate_commit=subprocess.check_output(['git','rev-parse',candidate_commit],cwd=ROOT).decode().strip()
        files={'candidate-unbound.json':'models/room_v1/rewired_512_20261026.json',
               'b-metrics.json':'report/verification/rewired-candidate-2026-10-26/metrics.json',
               'b-readme-original.txt':'report/verification/rewired-candidate-2026-10-26/README.md',
               'b-repro-original.txt':'report/verification/rewired-candidate-2026-10-26/repro.txt',
               'b-model-registry.json':'models/manifest.json'}
        for name,origin in files.items():
            (out/name).write_bytes(subprocess.check_output(['git','show',candidate_commit+':'+origin],cwd=ROOT))
        metrics=json.loads((out/'b-metrics.json').read_text(encoding='utf8'))
        model,q=load_candidate(out/'candidate-unbound.json',FIXTURE,40,RATE)
        identity=metrics['model_file']
        if len(q)!=512 or sha(out/'candidate-unbound.json')!=identity['file_sha256'] or qhash(q)!=identity['q20_sha256']:
            raise ValueError('B candidate/metrics identity mismatch')
        if hashlib.sha256(np.asarray(model['coefficients'],dtype='<f8').tobytes()).hexdigest()!=identity['float_sha256']:
            raise ValueError('B float array identity mismatch')
        registry=json.loads((out/'b-model-registry.json').read_text(encoding='utf8'))
        entry=next(item for item in registry['models'] if item['file']=='room_v1/rewired_512_20261026.json')
        if entry.get('sha256')!=identity['file_sha256'] or entry.get('coefficients_sha256')!=identity['q20_sha256']:
            raise ValueError('B registry identity mismatch')
        capture_manifest=json.loads((out/'a-repaired-capture-manifest.json').read_text(encoding='utf8'))
        captured={name:info['sha256'] for name,info in capture_manifest['files'].items() if name.endswith('.npz')}
        declared={item['file']:item['sha256'] for item in metrics['data_identity']}
        if len(declared)!=6 or declared!=captured or hashlib.sha256(json.dumps(declared,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=REPAIRED_CAPTURE_SET:
            raise ValueError('B model does not bind the six repaired A captures')
        if model['fixture_id']!=FIXTURE or metrics['fixture_id']!=FIXTURE or model.get('bias')!=0:
            raise ValueError('repaired model fixture/bias mismatch')
        if identity['file_sha256']!='01c9102af5e010e5d40fe01edb54f38b1c34f09b4690a936f17a88cb8e235c23' or identity['q20_sha256']!='6118e85df7d9765bd5ae93fc204a32301135666b188bcc0fcf61e1447f6e8927':
            raise ValueError('candidate changed; review before releasing another field package')
        candidate=template();candidate.update(b_commit=candidate_commit,model_sha256=identity['file_sha256'],
            coefficients_sha256=identity['q20_sha256'],deployment_evidence='b-metrics.json:model_file/deployment_axis',
            original_timeline_holdout='b-metrics.json:split/time_domain/unaligned_deployment; held-out val, raw deployment kept separate',
            diagnostic_alignment='b-metrics.json:alignment; raw deployment kept separate',
            input_manifest_sha256=hashlib.sha256(json.dumps(metrics['data_identity'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            gain_and_injection_basis='A=52ee4e4 five allowed points, B=b6bcfb2 and forwarded 254b8e9 errata; no added injection, level dependence unknown',
            b_allowed_gains_db=LAYOUT_PLAN['runtime_scan_gains_db'],gain_db=-8.,profile='runtime_scan',scan_gains_db=LAYOUT_PLAN['runtime_scan_gains_db'],
            bands=[dict(low_hz=low,high_hz=high,minimum_signal_snr_db=None,
                basis='B coherence>=0.8 applies to frequency estimates; not estimated in the no-injection runtime branch')
                for low,high in ((300,460),(460,1000),(1000,3000),(3000,8200),(8200,8600),(8600,10250))],
            prediction_and_failure_actions='c-integration-notes.json; five points only; protection ends sound, cause unknown; completed arms do not imply gain boundary or lower bound; both at ceiling unresolved',
            wire_repair_binding=dict(capture_manifest_sha256=REPAIRED_CAPTURE_MANIFEST,capture_set_sha256=REPAIRED_CAPTURE_SET,
                wire_state='repaired',model_sha256=identity['file_sha256'],coefficients_sha256=identity['q20_sha256'],
                b_commit=candidate_commit,basis_ref='b-metrics.json:data_identity + A original manifest; C direct six-NPZ/hash/global-source audit'))
        if baseline_first:
            candidate.update(profile='human_pair',workflow='success_first',scan_gains_db=[],
                gain_and_injection_basis='0f17c74 recorded zero baseline -8dB; live human, no added noise, no gain scan')
        if repair_binding:
            candidate['wire_repair_binding']=json.loads(Path(repair_binding).read_text(encoding='utf8'))
        (out/'candidate-input.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        # These are pure argument-budget checks, not permission for these probe values.
        probe=driver_request(out,'replay_trial',out/'compatibility-probe.npz',FIXTURE,out/'candidate-unbound.json',
            np.zeros(1,dtype='<i2'),gain_db=-8.,seconds=2.52,hp_volume=40,
            speaker_confirmed=True,local_capture_confirmed=True)
        receipt=dict(B_commit=candidate_commit,A_later_facts_commit=SCENE_COMMIT,model=identity,logical_taps=len(q),loaded_taps=512,
            serial_cycles=3*len(q)+3,frame_budget=2048,bias_loaded=False,lag_first=1,forward_schedule_frames=2,
            identity_and_driver_compatibility=True,probe=probe,probe_scope='software argument validation only; not actual board loading or effect',
            historical_fixture_alias=scene['fixture_provenance'],
            decision_basis=dict(worth_bounded_board_test=True,basis='repaired-source identity and positive held-out/raw deployment prediction justify a bounded test only',
                automatic_gain_accept_reject=False,effect_established=False),
            repaired_capture_binding=candidate['wire_repair_binding'],sources=files,
            unresolved=['Actual A loading and paired operation not yet measured',
                'Frequency/path estimates not scheduled: no extra injection; no broadband SNR cutoff invented',
                'Quantitative listener disabled; qualitative phone-source facts entered once at field binding'])
        notes=dict(source='C integration interpretation of B=b6bcfb2 plus user-forwarded B=254b8e9 errata',
            git_report_source_commit=candidate_commit,forwarded_errata_commit='254b8e9',
            evidence_scope='Bundled original B report is exact Git bytes from git_report_source_commit; errata handoff is separate authority',
            coefficient_identity_unchanged=True,
            saturation='Q20 coefficient range is not PCM output range; L1 bound is not an observed saturation event. Noise RMS formula needs input assumptions and is not a peak guarantee. All A guards retained.',
            offline_bounds='5.08/8.48dB are sampled/gated offline differences under different FFT grids, not a field benefit interval or lower guarantee; failure of a sufficient bound does not prove instability.',
            scan_interpretation='Only -14/-12/-10/-8/-6. Same-gain zero stopped/candidate completed is an execution contrast, not a one-grid-step acoustic gain lower bound. Protection has unknown acoustic cause. Ceiling censoring leaves boundary/gain difference unknown.',
            stop='Any guard, bad microphone precheck, invalid observation or configuration mismatch ends subsequent sound; preserve completed data and mark unattempted arms/listening unknown. No automatic gain extension or replay after protection.',
            applicable_bands='Gated samples now include 190 bins in 1-3k, not whole-band coverage; <300Hz, >10.25kHz and level dependence remain unknown.',
            training_capture='Actual gain_q12=0; source/reference equality verified on global frames with stopped-source tail; original labels/files preserved.',
            summary_copies='A Git summary 13aeb0a2.../1731 matches A manifest. B local 03ff23a3.../1788 is a distinct newline representation per forwarded errata; not a six-NPZ mismatch.',
            positive_control='Runtime uses relative-tone-projection-v1 at unchanged 1kHz/peak -20dBFS/1.02s; >=10dB projection contrast over max(quiet target, quiet/concurrent neighbours), equal windows; no broadband dominance or absolute microphone-level threshold.',
            positive_failure='A failed reference, timeline or relative path detection ends acoustic branches and retains records. Do not bypass the path test or run the old gate a third time. Raw contaminated data is diagnostic only.',
            listener='Quantitative not_tested, AGC unknown; heard sound and amplification relative to system mute are separate qualitative reports.',
            layout_benefit='not_tested; this experiment only compares FIR to zero in the same current layout',hardware_executed=False)
        if baseline_first:
            notes.update(positive_control='Confirm real speech input response, actual registered DAC source and manual output from the named loudspeaker. Legacy and relative 1kHz statistics are diagnostic; no arbitrary threshold lowering.',
                positive_failure='Unknown input, actual output route, reference, or protection stops dependent sound. An unknown isolated 1kHz estimate does not erase independent human baseline observations.',
                scan_interpretation='No gain scan in this workflow. Reproduce the zero-FIR -8dB baseline first; optional same-gain human candidate pairs follow; missing candidate cannot block zero baseline.',
                listener='Live human only. Two output-muted/on comparisons, separate heard/clarity/original words; conditional zero-FIR 60s human use. No phone substitute or quantitative SPL claim.')
        (out/'c-integration-notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        if baseline_first:
            receipt['unresolved']=['Historical microphone state and exact source loudness not reconstructed',
                'Current human baseline requires real input/output confirmations and two reports',
                'Candidate is optional after baseline; missing/mismatched candidate does not block zero FIR use']
        (out/'candidate-compatibility.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    code=('# 成功工作点集中复现：输入与路径确认后执行\n' if baseline_first else '# 新布局集中实验：核对绑定后执行\n')+'from layout_experiment import run\nresult = run()\n'
    nb=dict(nbformat=4,nbformat_minor=5,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},
        cells=[dict(cell_type='markdown',metadata={},source=[('先读 OPERATIONS.md；先复现零系数基线，候选缺项只停止候选分支；真人动作必须真实确认。' if baseline_first else '先读 OPERATIONS.md；缺候选/场景身份时只生成停止回包，不操板。')]),
               dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=code.splitlines(True))])
    (out/'layout.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
    guide=(ROOT/'board/audio_closed/BATCH_GUIDE.md').read_text(encoding='utf8')
    start=guide.index('## 2026-10-27 成功工作点集中复现' if baseline_first else '## 2026-10-26 新布局一次集中实验')
    stop=guide.index('\n## ',start+4)
    (out/'OPERATIONS.md').write_text(guide[start:stop],encoding='utf8')
    manifest=dict(policy=POLICY,plan=LAYOUT_PLAN,package_status='pending_repaired_scene_model',
        A_commit=A_COMMIT,A_scene_commit=SCENE_COMMIT,A_origins=origins,C_source_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        source_tree_clean=not bool(subprocess.check_output(['git','status','--porcelain','--',
            'board/audio_replay','scripts/assemble_experiment.py','board/audio_closed/BATCH_GUIDE.md',
            'sim/feedback/test_layout_experiment.py'],cwd=ROOT).strip()),
        hardware_executed=False,notebook_code_sha256=notebook_code_hash(out/'layout.ipynb'),
        hashes={str(p.relative_to(out)).replace('\\','/'):sha(p)
            for p in sorted(out.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='layout.ipynb'})
    if baseline_first:
        manifest.update(workflow='success_first',workflow_basis='A 0f17c74 development-plan 2026-10-27 execution order',
            baseline_transport_sha256=sha(out/'baseline-model.json'),
            active_plan=dict(baseline_gain_db=-8.,baseline_actual_Q20='all_zero_512',short_seconds=9.5,
                baseline_repeats=2,listener_order=['off','on','off','on'],historical_distance_cm=5.,
                permitted_distance_variant_cm=[15,30],distance_variant_attempts=1,conditional_live_human_seconds=60.,
                candidate_gain_db=-8.,candidate_pair_repeats=2,gain_scan=False,source_kind='human_live'),
            candidate_optional_files=[name for name in manifest['hashes'] if name.startswith('b-') or name in ('candidate-input.json','candidate-unbound.json')])
    (out/'layout-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    pending=check_layout(out)
    manifest['missing']=pending['missing']
    if baseline_first:manifest['package_status']='ready_for_human_baseline_then_optional_candidate'
    elif not any(e.startswith('B:') for e in pending['missing']):manifest['package_status']='ready_for_A_field_binding'
    (out/'layout-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:z.write(path,path.relative_to(out))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--assets',type=Path)
    p.add_argument('--review-only',action='store_true')
    p.add_argument('--room-ready',action='store_true')
    p.add_argument('--sprint-ready',action='store_true')
    p.add_argument('--sprint-human',action='store_true')
    p.add_argument('--layout-prepared',action='store_true')
    p.add_argument('--baseline-first',action='store_true')
    p.add_argument('--candidate-commit')
    p.add_argument('--repair-binding',type=Path)
    p.add_argument('--product',action='store_true')
    p.add_argument('--product-hardware',type=Path)
    p.add_argument('--product-algorithm',type=Path)
    p.add_argument('--product-review',action='store_true')
    p.add_argument('--r4-b-handoff',action='store_true')
    p.add_argument('--model',type=Path)
    a=p.parse_args()
    if a.product:
        m=assemble_product(a.output,a.product_hardware,a.product_algorithm,review=a.product_review)
    elif a.layout_prepared:
        m=assemble_layout(a.output,a.candidate_commit,a.repair_binding,a.baseline_first)
    elif a.r4_b_handoff:
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
