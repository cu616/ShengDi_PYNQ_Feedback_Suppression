"""Product behavior under simulated hardware/fixed B decisions, not field efficacy."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
sys.path.insert(0,str(ROOT/'scripts'))
from recal_product import Product, Calculator, verify_package, export_return, review_return
from recal_mock import Board, sample_config, evaluate


class FixedCalculator:
    def __init__(self): self.calls=[];self.block_phase=None
    def evaluate(self,req,cancel):
        self.calls.append(req)
        if req['phase']==self.block_phase: cancel.wait(4)
        if cancel.is_set(): return {}
        return evaluate(req)
    def cancel(self): pass


class ProductTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.apps=[]
        self.addCleanup(lambda: [app.event('cancel') for app in self.apps])

    def app(self,config=None,hardware=None,calculator=None):
        config=copy.deepcopy(config or sample_config());hw=hardware or Board(config)
        calc=calculator or FixedCalculator()
        app=Product(hw,config,self.folder/str(len(self.apps)),calculator=calc)
        self.apps.append(app);return app,hw,calc

    def until(self,app,predicate,timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            app.tick()
            if predicate(): return
            time.sleep(.003)
        self.fail((app.state,app.outcome,app.reason))

    def ready(self,app):
        app.event('recalibrate');self.until(app,lambda:app.state=='ready')

    def pointer(self,app): return json.loads(app.store.pointer.read_text(encoding='utf-8'))

    def test_complete_state_sequence_atomic_model_and_no_automatic_run(self):
        app,hw,_=self.app();self.assertEqual(hw.mode,'muted');self.ready(app)
        states=[p['state'] for p in hw.prompts]
        for state in ('uncalibrated','preparing','speaking','quiet','capturing','fitting','validating','installing','ready'):
            self.assertIn(state,states)
        self.assertLess(states.index('preparing'),states.index('speaking'))
        self.assertTrue(self.pointer(app)['eligible']);self.assertNotIn('run',hw.calls)
        self.assertEqual(self.pointer(app)['identity']['aux_raw_left'],5)
        app.record_listening('听不出差异','operator original words')
        self.assertEqual(app.outcome,'valid_pass');self.assertEqual(app.listening[0]['words'],'听不出差异')
        self.assertEqual(app.cue_end,1200)

    def test_cancellation_in_every_hardware_phase_cannot_promote_late_result(self):
        for op in ('prepare','cue','input','training','validation','install','run'):
            with self.subTest(op=op):
                app,hw,_=self.app()
                if op=='run': self.ready(app)
                hw.block_op=op
                app.event('start' if op=='run' else 'recalibrate')
                self.until(app,lambda:op in hw.calls)
                app.event('cancel');self.until(app,lambda:not app.pending)
                time.sleep(.01);app.tick()
                self.assertEqual(app.outcome,'user_cancelled');self.assertEqual(hw.mode,'muted')
                if op!='run': self.assertFalse(self.pointer(app)['eligible'])
                self.assertNotEqual(app.state,'ready')

    def test_input_overload_is_not_a_model_pass(self):
        app,hw,_=self.app();hw.fault='input';app.event('recalibrate')
        self.until(app,lambda:app.state=='protected')
        self.assertEqual(app.outcome,'input_overload');self.assertNotIn('install',hw.calls)
        self.assertFalse(self.pointer(app)['eligible'])
        self.assertTrue(app.hardware_receipts[-1]['reply']['input_clip'])

    def test_insufficient_data_and_model_rejection_never_install(self):
        for phase,outcome in [('input','data_insufficient'),('fit','model_rejected'),('validate','data_insufficient')]:
            with self.subTest(phase=phase):
                cfg=sample_config();cfg['attempts'][0][phase+'_decision']=outcome
                app,hw,_=self.app(cfg);app.event('recalibrate')
                self.until(app,lambda:app.state in ('failed','inconclusive'))
                self.assertEqual(app.outcome,outcome);self.assertNotIn('install',hw.calls)
                self.assertFalse(self.pointer(app)['eligible'])

    def test_install_mismatch_or_atomic_pointer_failure_leaves_no_active_model(self):
        for disk_failure in (False,True):
            with self.subTest(disk_failure=disk_failure):
                app,hw,_=self.app();hw.install_bad=not disk_failure
                if disk_failure:
                    app.store.commit=mock.Mock(side_effect=OSError('injected pointer write failure'))
                app.event('recalibrate');self.until(app,lambda:app.state=='failed')
                self.assertFalse(self.pointer(app)['eligible']);self.assertEqual(hw.mode,'muted')
                self.assertNotIn('run',hw.calls)

    def test_recalibration_invalidates_old_scene_even_if_new_calibration_fails(self):
        app,hw,_=self.app();self.ready(app);old=self.pointer(app);old_scene=app.scene
        hw.fault='input';app.event('recalibrate')
        self.assertNotEqual(app.scene,old_scene);self.assertFalse(self.pointer(app)['eligible'])
        self.until(app,lambda:app.state=='protected')
        app.event('start');self.assertNotIn('run',hw.calls)
        self.assertTrue(Path(old['model_path']).is_file())

    def test_identity_mixture_missing_capability_and_configuration_drift(self):
        cfg=sample_config();hw=Board(cfg);hw.identity['driver_sha256']='f'*64
        app,_,_=self.app(cfg,hw);self.assertTrue(app.fatal);app.event('recalibrate')
        self.assertNotIn('prepare',hw.calls)
        hw2=Board(cfg);hw2.caps_missing='buttons';app2,_,_=self.app(cfg,hw2)
        self.assertEqual(app2.outcome,'hardware_error');app2.event('recalibrate');self.assertNotIn('prepare',hw2.calls)
        app3,hw3,_=self.app();self.ready(app3);hw3.identity['aux_raw_right']=7;app3.tick()
        self.assertEqual(app3.state,'failed');self.assertFalse(self.pointer(app3)['eligible'])

    def test_cue_tail_and_independent_validation_windows_enforced(self):
        for fault in ('input_window_bad','shared_validation'):
            with self.subTest(fault=fault):
                app,hw,_=self.app();setattr(hw,fault,True);app.event('recalibrate')
                self.until(app,lambda:app.state=='inconclusive')
                self.assertEqual(app.outcome,'data_insufficient');self.assertNotIn('install',hw.calls)

    def test_no_protection_is_insufficient_without_B_effect_evidence(self):
        cfg=sample_config();cfg['attempts'][0]['no_effect_evidence']=True
        app,hw,_=self.app(cfg);app.event('recalibrate');self.until(app,lambda:app.state=='inconclusive')
        self.assertEqual(app.outcome,'data_insufficient');self.assertNotIn('install',hw.calls)

    def test_retry_is_bounded_by_supplied_policy(self):
        cfg=sample_config();cfg['attempts']=[dict(training={},validation={},fit_decision='retry') for _ in range(2)]
        app,hw,_=self.app(cfg);app.event('recalibrate');self.until(app,lambda:app.state=='inconclusive')
        self.assertEqual(hw.calls.count('training'),2);self.assertEqual(app.attempt,1)
        self.assertNotIn('install',hw.calls);self.assertEqual(app.outcome,'data_insufficient')

    def test_natural_end_does_not_stitch_or_restart_and_mode_is_actual(self):
        app,hw,_=self.app();self.ready(app);app.event('start')
        self.until(app,lambda:hw.mode=='cancel')
        hw.mode='bypass';app.tick();self.assertEqual(app.mode,'bypass')
        self.assertEqual(hw.prompts[-1]['mode'],'bypass')
        self.until(app,lambda:app.state=='ended');count=hw.calls.count('run')
        for _ in range(5): app.tick()
        self.assertEqual(hw.calls.count('run'),count);self.assertEqual(app.outcome,'completed')
        self.assertLessEqual(app.run_result['elapsed_seconds'],app.cfg['run_seconds'])

    def test_real_B_subprocess_is_cancelled_without_blocking_stop(self):
        cfg=sample_config();cfg['attempts'][0]['slow_seconds']=20;cfg['compute_timeout_seconds']=30
        calc=Calculator('recal_mock',self.folder/'process')
        app,hw,_=self.app(cfg,calculator=calc);app.event('recalibrate')
        self.until(app,lambda:app.state=='fitting' and calc.process is not None,timeout=8)
        process=calc.process;start=time.monotonic();app.event('stop')
        self.assertLess(time.monotonic()-start,.2);self.assertEqual(hw.mode,'muted')
        process.wait(timeout=2);self.assertFalse(self.pointer(app)['eligible']);self.assertNotEqual(app.state,'ready')

    def test_stop_event_wins_over_start_in_same_poll(self):
        app,hw,_=self.app();self.ready(app);hw.events=[dict(kind='start'),dict(kind='stop')]
        app.tick();self.assertNotIn('run',hw.calls)

    def test_simulation_model_cannot_be_installed_in_physical_mode(self):
        cfg=sample_config();cfg['simulation']=False
        app,hw,_=self.app(cfg);app.event('recalibrate')
        self.until(app,lambda:app.state=='failed')
        self.assertEqual(app.outcome,'model_rejected');self.assertNotIn('install',hw.calls)
        self.assertFalse(self.pointer(app)['eligible'])

    def test_invalid_cue_timeline_stops_instead_of_replaying_cues(self):
        app,hw,_=self.app();original=hw.perform
        def invalid(req,cancel):
            result=original(req,cancel)
            if req['op']=='cue': result['end_frame']=0;result['tail_frames']=0
            return result
        hw.perform=invalid;app.event('recalibrate');self.until(app,lambda:app.state=='failed')
        self.assertEqual(hw.calls.count('cue'),1);self.assertNotIn('input',hw.calls)
        self.assertEqual(app.outcome,'hardware_error');self.assertFalse(self.pointer(app)['eligible'])

    def test_direct_capture_gain_is_bound_per_phase_and_runtime_gain_cannot_drift(self):
        cfg=sample_config()
        cfg['phase_gain_q12']={op:[0,1631] for op in ('prepare','cue','input','training','validation')}
        app,hw,_=self.app(cfg);original=hw.perform
        def direct(req,cancel):
            if req['op'] in ('input','training','validation'): hw.identity['gain_q12']=0
            if req['op']=='install': hw.identity['gain_q12']=1631
            return original(req,cancel)
        hw.perform=direct;self.ready(app)
        self.assertEqual(self.pointer(app)['identity']['gain_q12'],1631)
        hw.identity['gain_q12']=0;app.tick()
        self.assertEqual(app.outcome,'hardware_error');self.assertFalse(self.pointer(app)['eligible'])

    def test_short_run_cannot_be_reported_as_full_duration(self):
        app,hw,_=self.app();self.ready(app)
        original=hw.perform
        def short(req,cancel):
            result=original(req,cancel)
            if req['op']=='run': result['elapsed_seconds']=.001
            return result
        hw.perform=short;app.cfg['run_seconds']=.25;app.event('start')
        self.until(app,lambda:app.state=='inconclusive')
        self.assertEqual(app.outcome,'data_insufficient');self.assertEqual(hw.calls.count('run'),1)

    def test_B_causes_stop_before_install_and_keep_original_receipts(self):
        for cause,outcome,state in (
            ('HARDWARE_ERROR','hardware_error','failed'),
            ('MEASUREMENT_INAPPLICABLE','measurement_inapplicable','inconclusive'),
            ('MODEL_UNQUALIFIED','model_rejected','failed'),
            ('DATA_INSUFFICIENT','data_insufficient','inconclusive')):
            with self.subTest(cause=cause):
                calc=FixedCalculator();original=calc.evaluate
                def judged(req,cancel):
                    out=original(req,cancel)
                    if req['phase']=='validate': out.update(decision='valid_pass',cause=cause,reason='B原判据')
                    return out
                calc.evaluate=judged
                app,hw,_=self.app(calculator=calc);app.event('recalibrate')
                self.until(app,lambda:app.state==state)
                self.assertEqual((app.outcome,app.cause),(outcome,cause))
                self.assertNotIn('install',hw.calls);self.assertEqual(hw.mode,'muted')
                self.assertFalse(self.pointer(app)['eligible'])
                stored=json.loads((app.run_dir/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(stored['algorithm_receipts'][-1]['reply']['cause'],cause)
                self.assertEqual(stored['cause'],cause)
                if cause=='HARDWARE_ERROR':
                    self.assertFalse(app.fatal);old_scene=app.scene;calc.evaluate=original
                    hw.events=[dict(kind='recalibrate',value='start')];app.tick()
                    self.until(app,lambda:app.state=='ready')
                    self.assertNotEqual(app.scene,old_scene)

    def test_partial_B_ready_decision_cannot_enable_candidate(self):
        calc=FixedCalculator();original=calc.evaluate
        def partial(req,cancel):
            out=original(req,cancel)
            if req['phase']=='validate':
                out.update(policy_contract='recal-policy-consumer-v1',policy_result=dict(
                    decision=dict(status='READY_TO_INSTALL'),steps=dict(capture=dict(status='NOT_RUN'),
                    fit=dict(status='NOT_RUN'),three_point=dict(status='PASS'))))
            return out
        calc.evaluate=partial
        app,hw,_=self.app(calculator=calc);app.event('recalibrate')
        self.until(app,lambda:app.state=='inconclusive')
        self.assertEqual(app.outcome,'data_insufficient');self.assertNotIn('install',hw.calls)

    def test_calculation_phase_cancellation_rejects_late_results(self):
        for phase in ('input','fit','validate'):
            with self.subTest(phase=phase):
                calc=FixedCalculator();calc.block_phase=phase
                app,hw,_=self.app(calculator=calc);app.event('recalibrate')
                self.until(app,lambda:any(r['phase']==phase for r in calc.calls))
                app.event('stop');time.sleep(.01);app.tick()
                self.assertEqual(hw.mode,'muted');self.assertFalse(self.pointer(app)['eligible'])
                self.assertNotEqual(app.state,'ready')

    def test_hardware_exception_and_abort_failure_never_resume(self):
        app,hw,_=self.app();hw.perform=mock.Mock(side_effect=OSError('injected I/O failure'))
        app.event('recalibrate');self.until(app,lambda:app.state=='failed')
        self.assertEqual(app.outcome,'hardware_error');self.assertFalse(self.pointer(app)['eligible'])
        hw.abort_bad=True;app.event('stop');self.assertTrue(app.fatal)
        hw.abort_bad=False;app.event('recalibrate');self.assertNotIn('run',hw.calls)

    def test_one_return_preserves_multiple_layouts_and_omits_private_input(self):
        cfg=sample_config();cfg['package_manifest_sha256']='a'*64
        app,hw,_=self.app(cfg);self.ready(app);first=app.scene
        app.event('start');self.until(app,lambda:hw.mode=='cancel');hw.mode='bypass';app.tick();app.event('stop')
        self.ready(app)
        maintenance=dict(success=True,compatibility_issues=[],scope='maintenance only')
        (app.root/'adapter-check.json').write_text(json.dumps(maintenance),encoding='utf-8')
        older=app.root/'runs/older-package';older.mkdir()
        (older/'result.json').write_text(json.dumps(dict(scene_id='older',package_manifest_sha256='b'*64)),encoding='utf-8')
        compute=app.root/'compute';compute.mkdir(exist_ok=True)
        (compute/'older-reply.json').write_text(json.dumps(dict(scene_id='older',decision='valid_pass')),encoding='utf-8')
        out=self.folder/'return.zip';export_return(app.root,out,'a'*64)
        result=review_return(out,'a'*64)
        self.assertTrue(result['identity_ok']);self.assertEqual(result['layout_count'],2)
        self.assertIn(first,{r['scene_id'] for r in result['layouts']})
        first_result=next(r for r in result['layouts'] if r['scene_id']==first)
        second_result=next(r for r in result['layouts'] if r['scene_id']!=first)
        self.assertEqual(first_result['observed_modes'],['bypass','cancel'])
        self.assertEqual(second_result['observed_modes'],[])
        import zipfile
        with zipfile.ZipFile(out) as z:
            self.assertFalse(any('/input' in n for n in z.namelist()))
            self.assertTrue(any('/training' in n for n in z.namelist()))
            self.assertEqual(json.loads(z.read('maintenance/adapter-check.json')),maintenance)
            self.assertNotIn('algorithm/older-reply.json',z.namelist())
        with self.assertRaisesRegex(ValueError,'different product'): review_return(out,'b'*64)


class ProductPackagingTests(unittest.TestCase):
    def test_one_shot_simulation_ends_on_inconclusive(self):
        import assemble_experiment as assembler
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            out=Path(temp)/'product';assembler.assemble_product(out)
            config=json.loads((out/'product-config.json').read_text(encoding='utf-8'))
            config['attempts'][0]['input_decision']='data_insufficient'
            (out/'product-config.json').write_text(json.dumps(config),encoding='utf-8')
            manifest=json.loads((out/'product-manifest.json').read_text(encoding='utf-8'))
            manifest['hashes']['product-config.json']=hashlib.sha256((out/'product-config.json').read_bytes()).hexdigest()
            (out/'product-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            run=subprocess.run([sys.executable,'-X','utf8',str(out/'recal_product.py'),'--base',str(out),
                '--simulate','--once','--state-dir',str(Path(temp)/'state')],capture_output=True,text=True,timeout=8)
            self.assertEqual(run.returncode,2,run.stderr)
            self.assertEqual(json.loads(run.stdout)['state'],'inconclusive')

    def test_software_package_is_not_mislabelled_as_field_ready_and_tamper_fails(self):
        spec=importlib.util.spec_from_file_location('product_assembler',ROOT/'scripts/assemble_experiment.py')
        assembler=importlib.util.module_from_spec(spec);spec.loader.exec_module(assembler)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            out=Path(temp)/'product';result=assembler.assemble_product(out)
            self.assertEqual(result['status'],'software_simulation_only')
            manifest=verify_package(out);self.assertFalse(manifest['deployment_ready'])
            self.assertNotIn('replay_trial.py',manifest['hashes'])
            # The retained A legacy script must never replace C's service launcher.
            entry=(out/'recal_entry.sh').read_bytes()
            self.assertEqual(entry,(ROOT/'board/audio_replay/recal_product_entry.sh').read_bytes())
            self.assertIn(b'recal_product.py',entry)
            self.assertNotEqual(entry,(ROOT/'board/audio_replay/recal_entry.sh').read_bytes())
            self.assertEqual((out/'feedback/recal_policy.py').read_bytes(),(ROOT/'src/feedback/recal_policy.py').read_bytes())
            loaded=subprocess.run([sys.executable,'-X','utf8','-c',
                "from recal_policy_consumer import Consumer; c=Consumer(); print(c.final(None,None,None)['decision'])"],
                cwd=out,capture_output=True,text=True,check=True)
            self.assertEqual(loaded.stdout.strip(),'data_insufficient')
            for name in ('POLICY.md','POLICY-CONSUMER.md'): self.assertIn(name,manifest['hashes'])
            target=out/'recal_product.py';target.write_bytes(target.read_bytes()+b'\n# bad\n')
            with self.assertRaisesRegex(ValueError,'identity mismatch'): verify_package(out)


if __name__=='__main__': unittest.main()
