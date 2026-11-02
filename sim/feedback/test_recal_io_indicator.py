"""Slow capture deadlines and truthful cue/physical LED timing."""
from pathlib import Path
import sys
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'src')]
import recal_product as p
import recal_algorithm as b
from recal_link import frozen_policy
from recal_mock import Board,sample_config
import test_recal_product as base


class IOIndicatorTests(unittest.TestCase):
    setUp=base.ProductTests.setUp
    app=base.ProductTests.app
    until=base.ProductTests.until
    pointer=base.ProductTests.pointer

    def training_wait(self,timeout):
        cfg=sample_config();cfg.update(io_timeout_seconds=timeout,quiet_seconds=0,
            indicator_encoding='led4',indicator_armed_safe=True)
        hw=Board(cfg);original=hw.perform;release=threading.Event();entered=threading.Event()
        self.addCleanup(release.set)
        def slow(req,cancel):
            if req['op']=='training':
                entered.set()
                while not release.wait(.005):
                    if cancel.is_set():break
            return original(req,cancel)
        hw.perform=slow;app,_,_=self.app(cfg,hw);clock={'now':0.};app.clock=lambda:clock['now']
        app.event('recalibrate');self.until(app,entered.is_set)
        return app,hw,clock,release

    def test_old_30_second_budget_reproduces_failure_at_52_seconds(self):
        app,hw,clock,release=self.training_wait(30)
        clock['now']=52.;app.tick()
        self.assertEqual(app.outcome,'hardware_error');self.assertIn('阶段超时',app.reason)
        self.assertEqual(hw.mode,'muted');self.assertFalse(self.pointer(app)['eligible'])

    def test_150_second_budget_allows_six_capture_elapsed_time(self):
        policy=frozen_policy(b);self.assertEqual(policy['io_timeout_seconds'],150)
        self.assertEqual(policy['compute_timeout_seconds'],30)
        app,hw,clock,release=self.training_wait(policy['io_timeout_seconds'])
        clock['now']=6*8.6;app.tick()
        self.assertEqual(app.state,'capturing');self.assertIsNone(app.outcome)
        quiet=next(x['pattern'] for x in hw.prompts if x['state']=='quiet')
        capture=next(x['pattern'] for x in hw.prompts if x['state']=='capturing')
        self.assertEqual((quiet,capture),('0100','0101'))
        release.set();self.until(app,lambda:app.state=='ready')

    def test_long_deadline_does_not_delay_physical_stop(self):
        app,hw,clock,release=self.training_wait(150);clock['now']=52.
        original_abort=hw.abort;stopped=[]
        def abort():stopped.append(time.monotonic());return original_abort()
        hw.abort=abort
        hw.events=[dict(kind='cancel',value='btn3')];started=time.monotonic();app.tick()
        self.assertTrue(stopped);self.assertLess(stopped[0]-started,.2)
        self.assertEqual(hw.mode,'muted');self.assertEqual(app.outcome,'user_cancelled')
        self.assertFalse(self.pointer(app)['eligible'])

    def test_embedded_speech_LED_waits_for_arm_and_complete_cue(self):
        cfg=sample_config();cfg.update(input_mode='embedded',speech_seconds=2.5,embedded_cue_frames=21969,
            cue_indicator_guard_seconds=.1,indicator_encoding='led4',indicator_armed_safe=True,io_timeout_seconds=150)
        hw=Board(cfg);original=hw.perform;release=threading.Event();entered=threading.Event()
        self.addCleanup(release.set)
        def input_wait(req,cancel):
            if req['op']=='input':
                entered.set()
                while not release.wait(.005):
                    if cancel.is_set():break
            return original(req,cancel)
        hw.perform=input_wait;app,_,_=self.app(cfg,hw);clock={'now':0.};app.clock=lambda:clock['now']
        app.event('recalibrate');self.until(app,entered.is_set)
        clock['now']=20.;app.tick()
        self.assertEqual(app.state,'input_capture');self.assertIsNone(app.input_armed_at)
        self.assertNotIn('speaking',[x['state'] for x in hw.prompts])
        hw.mode='cancel';app.tick();self.assertEqual(app.input_armed_at,20.)
        clock['now']=20.44;app.tick();self.assertEqual(app.state,'input_capture')
        clock['now']=20.56;app.tick();self.assertEqual(app.state,'speaking')
        self.assertEqual(hw.prompts[-1]['pattern'],'0010');self.assertFalse(app.indicator_deferred)
        app.event('stop');self.assertEqual(hw.mode,'muted')


if __name__=='__main__':unittest.main()
