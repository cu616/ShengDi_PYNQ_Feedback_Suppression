"""C runtime integration: true B arithmetic, simulated board, no sound or PYNQ."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'src')]
import recal_algorithm as b
from recal_runtime import product_policy,evaluate
from recal_mock import Board,sample_config
from recal_product import Calculator
from test_recal_algorithm import room_ir
import test_recal_product as product_tests


class NumericBoard(Board):
    def capabilities(self):
        return dict(super().capabilities(),prepared_capture=False,cue_input_ready_event=True)

    def perform(self,req,cancel):
        op=req['op']
        if op=='cue_input':
            self.calls.append(op)
            if not self.config.get('omit_input_ready'):
                self.events.append(dict(kind='input_ready',request_id=req['request_id'],scene_id=req['scene_id'],
                    frame_domain=req['request_id'],cue_end_frame=1000,tail_frames=200,valid_first_frame=1200))
            reply=self._capture(req,'speech',0)
            reply.update(frame_domain=req['request_id'],valid_first_frame=1200)
            return reply
        if op in ('training','validation'):
            self.calls.append(op)
            entries=[self._capture(req,op,i)['captures'][0] for i in range(req['plan'][op]['segments'])]
            return dict(contract=req['contract'],request_id=req['request_id'],scene_id=req['scene_id'],
                ok=True,status='completed',identity=dict(self.identity),captures=entries)
        return super().perform(req,cancel)

    def _capture(self,req,phase,segment):
        from feedback.excitation import white_noise_pcm16
        if phase=='speech':
            ref=np.zeros(16384);src=np.zeros(16384,dtype=np.int16)
            mic=.1*np.sin(np.arange(16384)*.03)
        else:
            plan=req['plan'][phase];seed=plan['sources'][segment]['seed']
            src,record=white_noise_pcm16(plan['rms_dbfs'],16384,seed=seed,peak_cap=.8)
            ref=src.astype(float)/32768
            mic=np.concatenate([np.zeros(180),ref[:-180]])*.25
        name='%s-%s-%s-%s'%(req['scene_id'],phase,req['attempt'],segment)
        path=Path(req['run_dir'])/(name+'.npz')
        np.savez(path,reference=ref,microphone=mic,source_pcm16=src,sample_rate_hz=48828.125,
                 metadata_json=json.dumps(dict(first_frame=0,bit22=0,dropped_frames=0)))
        entry=dict(capture_id=name,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_sha256=hashlib.sha256(src.astype('<i2').tobytes()).hexdigest(),first_frame=1200,end_frame=17584,
            content_kind='human_private' if phase=='speech' else 'software_fixture')
        return dict(contract=req['contract'],request_id=req['request_id'],scene_id=req['scene_id'],
            ok=True,status='completed',identity=dict(self.identity),captures=[entry])


class RuntimeTests(unittest.TestCase):
    setUp=product_tests.ProductTests.setUp
    app=product_tests.ProductTests.app
    until=product_tests.ProductTests.until
    ready=product_tests.ProductTests.ready
    pointer=product_tests.ProductTests.pointer

    def config(self):
        cfg=sample_config();cfg.update(product_policy());cfg['quiet_seconds']=.01
        return cfg

    def test_policy_three_levels_and_independent_actual_pcm(self):
        cfg=product_policy()
        self.assertGreaterEqual(cfg['compute_timeout_seconds'],15)
        self.assertEqual([a['training']['rms_dbfs'] for a in cfg['attempts']],[-22.,-19.3,-16.5])
        shas=set()
        for plan in cfg['attempts']:
            for phase,count in [('training',6),('validation',2)]:
                self.assertEqual(plan[phase]['segments'],count)
                for source in plan[phase]['sources']:
                    self.assertNotIn(source['sha256'],shas);shas.add(source['sha256'])
                    self.assertLessEqual(source['peak_linear'],.8)

    def test_real_B_subprocess_workflow_on_simulated_captures(self):
        cfg=self.config();hw=NumericBoard(cfg)
        calc=Calculator('recal_runtime',self.folder/'real-calc')
        app,_,_=self.app(cfg,hardware=hw,calculator=calc)
        app.event('recalibrate');self.until(app,lambda:app.state in ('ready','failed','inconclusive'),timeout=20)
        self.assertEqual(app.state,'ready',app.reason)
        phases=[r['request']['phase'] for r in app.algorithm_receipts]
        self.assertEqual(phases,['speech','input','fit','validate'])
        self.assertEqual(len(app.training),6);self.assertEqual(len(app.validation),2)
        self.assertEqual(app.algorithm_receipts[1]['request']['input'],app.training)
        self.assertEqual(app.algorithm_receipts[1]['request']['attempts_total'],3)
        self.assertTrue(app.bundle['validation']['evidence']['not_asg'])
        self.assertEqual(app.bundle['validation']['validation_kind'],'heldout_prediction')
        self.assertNotIn('run',hw.calls)

    def test_cue_input_missing_ready_marker_never_promotes(self):
        cfg=self.config();cfg['omit_input_ready']=True;hw=NumericBoard(cfg)
        app,_,_=self.app(cfg,hardware=hw);app.event('recalibrate')
        self.until(app,lambda:app.state=='inconclusive')
        self.assertNotIn('install',hw.calls);self.assertNotIn('speaking',[p['state'] for p in hw.prompts])

    def test_input_ready_cancel_priority_and_old_identity_are_ignored(self):
        cfg=self.config();hw=NumericBoard(cfg);app,_,_=self.app(cfg,hardware=hw)
        req=dict(op='cue_input',request_id='new',scene_id=app.scene)
        app.pending=('hw',req)
        app._input_ready_event(dict(kind='input_ready',request_id='old',scene_id=app.scene))
        self.assertIsNone(app.input_ready)
        hw.events=[dict(kind='cancel'),dict(kind='input_ready',request_id='new',scene_id=app.scene)]
        app.tick();self.assertEqual(app.state,'cancelled');self.assertIsNone(app.input_ready)

    def test_unprepared_A_cannot_be_enabled_and_fit_timeout_has_floor(self):
        cfg=self.config();hw=Board(cfg);hw.caps_missing='prepared_capture'
        app,_,_=self.app(cfg,hardware=hw);self.assertTrue(app.fatal)
        cfg['compute_timeout_seconds']=3;hw=NumericBoard(cfg)
        app,_,_=self.app(cfg,hardware=hw);self.assertTrue(app.fatal)
        self.assertEqual(app.outcome,'data_insufficient')

    def test_button_short_press_ignored_and_btn1_uses_C_running_state(self):
        app,hw,_=self.app();hw.events=[dict(kind='recalibrate',value='short_ignored')]
        scene=app.scene;app.tick();self.assertEqual(app.scene,scene)
        self.ready(app);app.cfg['run_seconds']=.5;app.event('start')
        hw.events=[dict(kind='start',value='btn1')];app.tick()
        self.assertEqual(hw.mode,'muted');self.assertIn(app.state,('stopping','ended'))
        self.until(app,lambda:app.state=='ended')

    def test_led4_is_translated_and_never_written_when_running(self):
        cfg=sample_config();cfg['indicator_encoding']='led4'
        app,hw,_=self.app(cfg);self.ready(app)
        self.assertIn('0010',[p['pattern'] for p in hw.prompts]);self.assertEqual(hw.prompts[-1]['pattern'],'1000')
        app.event('start');self.until(app,lambda:hw.mode=='cancel')
        app.tick();count=len(hw.prompts);hw.mode='bypass';app.tick()
        self.assertEqual(len(hw.prompts),count);self.assertTrue(app.indicator_deferred)
        self.assertEqual(app.mode,'bypass')

    def test_run_deadline_includes_requested_audio_time(self):
        app,hw,_=self.app();self.ready(app);app.cfg['run_seconds']=60
        now=app.clock();app.event('start');self.assertGreaterEqual(app.job_deadline,now+60)

    def test_B_scope_missing_and_validate_retry_are_rejected(self):
        base=dict(contract='recal-product-v1',scene_id='s',request_id='r',phase='validate')
        for output in (dict(decision='valid_pass',reason='x',evidence={}),dict(decision='retry',reason='x')):
            with mock.patch.object(b,'evaluate',return_value=output):
                self.assertEqual(evaluate(base)['decision'],'data_insufficient')

    def test_original_driver_clip_flags_and_file_tamper_are_preserved(self):
        cfg=self.config();hw=NumericBoard(cfg)
        req=dict(contract='recal-product-v1',request_id='r',scene_id='s',run_dir=str(self.folder),
            plan=cfg['attempts'][0],phase='input')
        reply=hw._capture(dict(req,attempt=0),'training',0);entry=reply['captures'][0]
        path=Path(entry['path'])
        with np.load(path) as z: arrays={k:z[k] for k in z.files}
        arrays['metadata_json']=json.dumps(dict(first_frame=0,capture_status=1<<22,input_full_scale_seen=True))
        np.savez(path,**arrays);entry['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        out=evaluate(dict(req,input=[entry]));self.assertEqual(out['decision'],'input_overload')
        entry['sha256']='f'*64
        out=evaluate(dict(req,input=[entry]));self.assertEqual(out['cause'],'HARDWARE_ERROR')

    def test_single_validation_capture_cannot_bypass_B_contract_minimum(self):
        with mock.patch.object(b,'evaluate',return_value=dict(decision='valid_pass',reason='x')) as call:
            out=evaluate(dict(contract='recal-product-v1',request_id='r',scene_id='s',phase='validate',validation=[{}]))
        self.assertEqual(out['cause'],'DATA_INSUFFICIENT');self.assertFalse(call.called)

    def test_review_bundle_keeps_exact_adapters_and_is_never_deployable(self):
        import assemble_experiment as assembler
        for kind,name,content in [('hardware','hw_api.py',b'raise RuntimeError("must not import during packaging")\n'),
                                  ('algorithm','recal_algorithm.py',(ROOT/'board/audio_replay/recal_algorithm.py').read_bytes())]:
            folder=self.folder/kind;folder.mkdir();(folder/name).write_bytes(content)
            hashes={name:hashlib.sha256(content).hexdigest()}
            meta=dict(contract='recal-product-v1',kind=kind,field_approved=False,hashes=hashes,blockers=['pending actual adaptation'])
            if kind=='hardware':
                controls=folder/'physical-controls.json';controls.write_text('{}',encoding='utf-8')
                hashes['physical-controls.json']=hashlib.sha256(controls.read_bytes()).hexdigest()
                # A helper must take precedence over C's historical helper copy.
                helper=folder/'residual_tools.py';helper.write_text('# A exact accepted helper\n',encoding='utf-8')
                hashes['residual_tools.py']=hashlib.sha256(helper.read_bytes()).hexdigest()
                meta.update(expected_identity=sample_config()['expected_identity'],allowed_gain_q12=[1631],
                            allowed_calibration_gain_q12=[],capabilities=dict(prepared_capture=False))
            else: meta['algorithm_contract']='recalibration-algorithm-v1'
            (folder/'product-adapter.json').write_text(json.dumps(meta),encoding='utf-8')
        out=self.folder/'review'
        result=assembler.assemble_product(out,self.folder/'hardware',self.folder/'algorithm',review=True)
        manifest=json.loads((out/'product-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'],'integration_review_blocked')
        self.assertFalse(manifest['deployment_ready']);self.assertFalse(manifest['simulation'])
        self.assertEqual((out/'residual_tools.py').read_bytes(),(self.folder/'hardware/residual_tools.py').read_bytes())
        self.assertEqual((out/'recal_algorithm.py').read_bytes(),(ROOT/'board/audio_replay/recal_algorithm.py').read_bytes())

    def test_B_mixed_current_lags_fit_after_signed_alignment_fix(self):
        from test_recal_algorithm import white,write_capture
        entries=[]
        for i,delay in enumerate((180,181)):
            ref=white(seed=5+i);mic=np.concatenate([np.zeros(delay),ref[:-delay]])*.25
            entries.append(write_capture(self.folder,'mixed'+str(i),ref,mic))
        out=b.evaluate(dict(contract='recal-product-v1',request_id='r',scene_id='s',phase='fit',
            run_dir=str(self.folder),training=entries,attempt=0,attempts_total=3,identity={}))
        self.assertEqual(out['decision'],'valid_pass',out['reason'])
        self.assertEqual(out['evidence']['metrics']['alignment_shifts'],[0,-1])


if __name__=='__main__': unittest.main()
