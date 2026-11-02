"""Frozen B dispatch and A factory API under simulated hardware leaf operations."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest import mock
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'src')]
import recal_algorithm as b
import recal_product as product
from recal_link import frozen_policy,capture_plans,ingest
from recal_mock import Board,sample_config
import test_recal_product as base_tests


class FrozenBoard(Board):
    def perform(self,req,cancel):
        op=req['op']
        if op not in ('input','training','validation'): return super().perform(req,cancel)
        self.calls.append(op);entries=[]
        items=[{}] if op=='input' else req['plan']['captures']
        for i,item in enumerate(items):
            if op=='input':
                src=np.zeros(16384,dtype=np.int16);ref=src.astype(float);mic=.1*np.sin(np.arange(len(src))*.03)
            else:
                rng=np.random.default_rng(item['seed']);x=rng.standard_normal(16384);x-=x.mean()
                src=np.rint(x/np.sqrt(np.mean(x*x))*10**(item['level_dbfs']/20)*32767).astype(np.int16)
                ref=src.astype(float)/32768;mic=np.concatenate([np.zeros(180),ref[:-180]])*.25
            name='%s-%s-%s-%s'%(req['scene_id'],req['attempt'],op,i);path=Path(req['run_dir'])/(name+'.npz')
            np.savez(path,reference=ref,microphone=mic,source_pcm16=src,sample_rate_hz=48828.125,
                metadata_json=json.dumps(dict(first_frame=0,bit22=0)))
            entries.append(dict(capture_id=name,path=str(path),sha256=product.sha(path),
                source_sha256=hashlib.sha256(src.tobytes()).hexdigest(),first_frame=1200,end_frame=17584,
                content_kind='human_private' if op=='input' else 'software_fixture'))
        return dict(**{k:req[k] for k in ('contract','scene_id','request_id')},ok=True,status='completed',
            identity=dict(self.identity),captures=entries,valid_first_frame=1200)


class FrozenTests(unittest.TestCase):
    setUp=base_tests.ProductTests.setUp
    app=base_tests.ProductTests.app
    until=base_tests.ProductTests.until
    pointer=base_tests.ProductTests.pointer

    def config(self):
        cfg=sample_config();cfg.update(frozen_policy(b));cfg['capture_plans']=capture_plans(cfg['attempts'])
        cfg['quiet_seconds']=.01;return cfg

    def test_B_attempts_are_unmodified_and_real_dispatch_binds_identity(self):
        cfg=self.config();self.assertEqual(cfg['attempts'],b.ATTEMPTS)
        self.assertEqual(cfg['algorithm_module'],'recal_algorithm')
        hw=FrozenBoard(cfg);calc=product.Calculator('recal_algorithm',self.folder/'frozen-calc')
        app,_,_=self.app(cfg,hardware=hw,calculator=calc);app.event('recalibrate')
        self.until(app,lambda:app.state in ('ready','failed','inconclusive'),timeout=20)
        self.assertEqual(app.state,'ready',app.reason)
        self.assertEqual([r['request']['phase'] for r in app.algorithm_receipts],['input','fit','validate'])
        self.assertTrue(app.bundle['validation']['evidence']['not_asg'])
        receipt=json.loads((app.run_dir/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['algorithm_identity']['file_sha256'],b.identity()['file_sha256'])
        self.assertEqual(receipt['numeric_exit_reason'],'PASS')
        for item in app.algorithm_receipts:
            self.assertEqual(item['reply']['algorithm_identity']['version'],b.VERSION)

    def test_algorithm_worker_refuses_mixed_hash_before_evaluation(self):
        req=dict(contract='recal-product-v1',request_id='mixed',scene_id='s',phase='input',input=[],
                 algorithm_identity=dict(b.identity(),file_sha256='f'*64))
        result=product.Calculator('recal_algorithm',self.folder/'mixed-calc').evaluate(req,__import__('threading').Event())
        self.assertEqual(result['cause'],'HARDWARE_ERROR')
        self.assertEqual(result['algorithm_identity']['file_sha256'],b.identity()['file_sha256'])

    def test_speech_retry_does_not_raise_excitation_level_and_is_bounded(self):
        cfg=self.config();app,hw,_=self.app(cfg,hardware=FrozenBoard(cfg))
        req=dict(contract='recal-product-v1',request_id='r',scene_id=app.scene,phase='input')
        reply=dict(req,decision='retry',reason='讲话没声',algorithm_identity=b.identity())
        app._hw=mock.Mock()
        for _ in range(2): app._algorithm_done(req,reply)
        self.assertEqual(app.attempt,0);self.assertEqual(app.speech_retries,2)
        with self.assertRaises(product.Failure): app._algorithm_done(req,reply)

    def test_external_original_is_ingested_without_changing_bytes(self):
        outside=self.folder/'capture-root';outside.mkdir();raw=outside/'original.bin';raw.write_bytes(b'original')
        run=self.folder/'scene';run.mkdir();req=dict(run_dir=str(run),request_id='r')
        reply=dict(captures=[dict(path=str(raw),sha256=product.sha(raw),capture_id='c')])
        result=ingest(req,reply,outside);item=result['captures'][0]
        self.assertEqual(Path(item['path']).read_bytes(),raw.read_bytes());self.assertEqual(item['original_path'],str(raw))
        self.assertEqual(reply['captures'][0]['path'],str(raw))
        with self.assertRaises(ValueError): ingest(dict(req,request_id='r2'),reply,self.folder/'unapproved')

    def test_pending_install_never_commits_current_model(self):
        app,hw,_=self.app();original=hw.perform
        def pending(req,cancel):
            out=original(req,cancel)
            if req['op']=='install':out['applies_at']='next_capture'
            return out
        hw.perform=pending;app.event('recalibrate');self.until(app,lambda:app.state=='inconclusive')
        self.assertFalse(self.pointer(app)['eligible']);self.assertNotIn('run',hw.calls)

    def test_current_model_hash_mismatch_is_rejected_before_hardware_import(self):
        package=self.folder/'blocked';package.mkdir()
        product.write_json(package/'product-manifest.json',dict(contract='recal-product-v1',hashes={},
            simulation=False,deployment_ready=False,adapter_check_allowed=True))
        model=self.folder/'current.json';model.write_text('{}',encoding='utf-8')
        with mock.patch.object(sys,'argv',['recal_product.py','--base',str(package),'--adapter-check',
            '--model',str(model),'--model-sha256','f'*64]),mock.patch.object(product.importlib,'import_module') as loader:
            with self.assertRaisesRegex(ValueError,'hash mismatch'):product.main()
        self.assertFalse(loader.called)

    def test_A_factory_chain_through_C_main_with_fake_leaf_IO(self):
        package=self.folder/'a-package';package.mkdir()
        raw=subprocess.check_output(['git','show','a3f516f:board/audio_replay/v3-io/manifest.json'])
        manifest=json.loads(raw)
        for name in manifest['hashes']:
            (package/name).write_bytes(subprocess.check_output(['git','show','a3f516f:board/audio_replay/v3-io/'+name]))
        model=self.folder/'current-model.json';model.write_bytes(subprocess.check_output(['git','show',
            'a3f516f:models/room_v1/rewired_512_20261026.json']))
        selected=json.loads(model.read_text());selected['fixture_id']='maintenance-current-scene'
        model.write_text(json.dumps(selected),encoding='utf-8')
        (package/'recal_algorithm.py').write_bytes((ROOT/'board/audio_replay/recal_algorithm.py').read_bytes())
        cfg=self.config();cfg.update(hardware_module='hw_api',fixture='room_v1_20261026b',hp_volume=40,aux_db=0,
            allowed_gain_q12=[1631,2303,3254,4096])
        product.write_json(package/'product-config.json',cfg)
        hashes={p.name:product.sha(p) for p in package.iterdir()}
        product.write_json(package/'product-manifest.json',dict(contract='recal-product-v1',hashes=hashes,
            algorithm_identity=b.identity(),simulation=False,deployment_ready=False,missing=['prepared_capture'],
            adapter_check_allowed=True,diagnostic_model=model.name))
        spec=importlib.util.spec_from_file_location('hw_api',package/'hw_api.py');a=importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules,{'fcntl':types.ModuleType('fcntl')}):spec.loader.exec_module(a)
        class Register:
            value=0
            def read(self,*args):return self.value
            def write(self,offset,value):self.value=value
        control=Register();status=Register();calls=[]
        q=json.loads(model.read_text())['coefficients_q20'];qsha=hashlib.sha256(np.asarray(q,dtype='<i4').tobytes()).hexdigest()
        def trial(path,fixture,model_path,source,**kw):
            calls.append(dict(seconds=kw['seconds'],direct_only=kw['direct_only'],source_frames=len(source),fixture=fixture))
            control.value=0 if kw['direct_only'] else 1631<<16
            md=dict(first_frame=4,stop_reason='completed',capture_status=0,
                source_pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest(),
                model_sha256=product.sha(model_path),coefficients_sha256=qsha)
            np.savez(path,microphone=np.zeros(16384),reference=np.zeros(16384),source_pcm16=source,
                     sample_rate_hz=48828.125,metadata_json=json.dumps(md))
        driver=types.SimpleNamespace(__file__=str(package/'replay_trial_repair.py'),replay_trial=trial)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(sys.modules,{'hw_api':a}))
            stack.enter_context(mock.patch.object(a.ProductHardware,'_ensure_mmio',lambda self,**kw:dict(control=control,status=status)))
            stack.enter_context(mock.patch.object(a.ProductHardware,'_driver',lambda self:driver))
            stack.enter_context(mock.patch.object(a.Board,'_fd',lambda self:os.open(os.devnull,os.O_RDWR)))
            stack.enter_context(mock.patch.object(a.Board,'_write8',lambda *args:None))
            stack.enter_context(mock.patch.object(a.Board,'get_aux_gain_db',lambda self:dict(aux_gain_db=0,raw_left=5,raw_right=5)))
            stack.enter_context(mock.patch.object(a.Board,'set_aux_gain_db',lambda *args:dict(ok=True)))
            stack.enter_context(mock.patch.object(product.signal,'signal'))
            state=self.folder/'entry-state'
            stack.enter_context(mock.patch.object(sys,'argv',['recal_product.py','--base',str(package),
                '--adapter-check','--state-dir',str(state),'--model',str(model),'--model-sha256',product.sha(model)]))
            with contextlib.redirect_stdout(io.StringIO()):code=product.main()
        self.assertEqual(code,0)
        receipt=json.loads((state/'adapter-check.json').read_text(encoding='utf-8'))
        self.assertEqual([s['name'] for s in receipt['steps']],['mute','capabilities','prepare','training','install','run','abort'])
        self.assertEqual(receipt['capture_valid_frames'],[16382]);self.assertFalse(receipt['steps'][1]['reply']['prepared_capture'])
        self.assertEqual(calls[1]['source_frames'],16386);self.assertEqual(calls[-1]['seconds'],3.)
        self.assertTrue(all(c['fixture']=='maintenance-current-scene' for c in calls))
        self.assertFalse((state/'models/current.json').exists())
        self.assertTrue(receipt['compatibility_issues'])
        self.assertEqual(receipt['selected_model']['provenance'],'operator_supplied_current_model')


if __name__=='__main__':unittest.main()
