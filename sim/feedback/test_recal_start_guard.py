"""Muted sticky bits, active protection, and the observed 70-second ARM fit."""
import json
import threading
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'src')]
import recal_algorithm as b
from recal_link import frozen_policy
from recal_mock import Board,sample_config
import test_recal_product as base


class StartGuardTests(unittest.TestCase):
    setUp=base.ProductTests.setUp
    app=base.ProductTests.app
    ready=base.ProductTests.ready
    until=base.ProductTests.until
    pointer=base.ProductTests.pointer
    def test_muted_idle_latch_does_not_consume_start(self):
        app,hw,_=self.app();self.ready(app);hw.block_op='run'
        original=hw.poll;first=[True]
        def poll():
            reply=original()
            if first and first.pop():
                reply.update(protected=True,protection={'fault':1},capture_status=1<<18,
                             control_word=1631<<16,events=[{'kind':'start','value':'btn1'}])
            return reply
        hw.poll=poll;app.tick()
        self.assertEqual(app.state,'running');self.until(app,lambda:'run' in hw.calls)
        self.assertTrue(self.pointer(app)['eligible'])
        record=app.protection_history[-1]
        self.assertEqual(record['state'],'ready');self.assertEqual(record['action'],'idle_latch_recorded')
        self.assertEqual(record['capture_status'],1<<18)
        # A new protection during the run is never hidden by the idle exception.
        hw.protected=True;app.tick()
        self.assertEqual(app.state,'protected');self.assertEqual(hw.mode,'muted')
        self.assertEqual(app.protection_history[-1]['action'],'abort')
        self.assertFalse(self.pointer(app)['eligible'])

    def test_idle_protection_requires_actual_mute(self):
        app,hw,_=self.app();self.ready(app);hw.mode='cancel';hw.protected=True
        hw.events=[dict(kind='start',value='btn1')];app.tick()
        self.assertEqual(app.state,'protected');self.assertNotIn('run',hw.calls)

    def test_pending_hardware_protects_even_before_arm(self):
        app,hw,_=self.app();self.ready(app);hw.block_op='run';app.event('start')
        self.until(app,lambda:'run' in hw.calls);self.assertEqual(hw.mode,'muted')
        hw.protected=True;app.tick()
        self.assertEqual(app.state,'protected');self.assertEqual(app.protection_history[-1]['op'],'run')
        record=json.loads((app.run_dir/'result.json').read_text())['protection_history'][-1]
        self.assertFalse(record['raw_status_available']);self.assertIsNone(record['capture_status'])

    def test_real_clip_is_classified_and_raw_flags_survive_abort(self):
        app,hw,_=self.app();self.ready(app);hw.block_op='run';app.event('start')
        self.until(app,lambda:'run' in hw.calls);original=hw.poll
        def clipped():
            return dict(original(),protected=True,protection={'input_clip_seen':1},
                        capture_status=(1<<22)|1,control_word=(1631<<16)|1,
                        saturation={'residual_clip_pre_gain':1},protect_baseline=0,mmio_held=False)
        hw.poll=clipped;app.tick()
        self.assertEqual(app.outcome,'input_overload');self.assertEqual(hw.mode,'muted')
        record=app.protection_history[-1]
        self.assertEqual(record['capture_status'],(1<<22)|1)
        self.assertEqual(record['protection'],{'input_clip_seen':1})
        self.assertEqual(record['saturation'],{'residual_clip_pre_gain':1})
        self.assertEqual(record['protect_baseline'],0);self.assertFalse(record['capture_status_cached'])

    def fit_wait(self,timeout):
        cfg=sample_config();cfg.update(compute_timeout_seconds=timeout,quiet_seconds=0)
        calculator=base.FixedCalculator();original=calculator.evaluate
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def slow(req,cancel):
            if req['phase']=='fit':
                entered.set()
                while not release.wait(.005):
                    if cancel.is_set():return {}
            return original(req,cancel)
        calculator.evaluate=slow;app,hw,_=self.app(cfg,calculator=calculator)
        clock={'now':0.};app.clock=lambda:clock['now'];app.event('recalibrate')
        self.until(app,entered.is_set);return app,hw,clock,release

    def test_70_second_fit_fails_old_budget_and_completes_new_budget(self):
        for budget,passes in ((30,False),(frozen_policy(b)['compute_timeout_seconds'],True)):
            with self.subTest(budget=budget):
                app,hw,clock,release=self.fit_wait(budget);clock['now']=70.;app.tick()
                if passes:
                    self.assertEqual(app.state,'fitting');self.assertEqual(app.pending[1]['compute_timeout_seconds'],150)
                    release.set();self.until(app,lambda:app.state=='ready')
                else:
                    self.assertEqual(app.outcome,'hardware_error');self.assertIn('阶段超时',app.reason)
                    self.assertEqual(hw.mode,'muted');self.assertFalse(self.pointer(app)['eligible'])

    def test_cancel_during_70_second_fit_does_not_wait_for_compute_budget(self):
        app,hw,clock,release=self.fit_wait(150);clock['now']=70.
        hw.events=[dict(kind='cancel',value='btn3')];app.tick()
        self.assertEqual(app.outcome,'user_cancelled');self.assertEqual(hw.mode,'muted')
        self.assertFalse(self.pointer(app)['eligible']);release.set()
        app.tick();self.assertNotEqual(app.state,'ready')


if __name__=='__main__':unittest.main()
