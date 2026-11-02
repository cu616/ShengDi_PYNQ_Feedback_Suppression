"""Cold-codec AUX initialization and explicit physical CAL recovery."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'src')]
from recal_mock import Board,sample_config
import recal_product as p
from recal_link import frozen_policy
import recal_algorithm as b
import test_recal_product as base


class ColdCodec(Board):
    def __init__(self,cfg,wrong_after_prepare=False):
        super().__init__(cfg);self.identity.update(aux_db=None,aux_raw_left=0,aux_raw_right=0)
        self.wrong_after_prepare=wrong_after_prepare
    def perform(self,req,cancel):
        if req['op']=='prepare':
            self.identity.update(aux_db=6. if self.wrong_after_prepare else 0.,
                aux_raw_left=7 if self.wrong_after_prepare else 5,aux_raw_right=7 if self.wrong_after_prepare else 5)
        return super().perform(req,cancel)


class BootRetryTests(unittest.TestCase):
    setUp=base.ProductTests.setUp
    app=base.ProductTests.app
    until=base.ProductTests.until
    pointer=base.ProductTests.pointer

    def test_power_on_unknown_aux_stays_muted_then_prepare_establishes_identity(self):
        cfg=sample_config();hw=ColdCodec(cfg);app,_,_=self.app(cfg,hw)
        self.assertEqual(app.state,'uncalibrated');self.assertFalse(app.fatal)
        self.assertFalse(app.configuration_ready);self.assertEqual(app.identity['aux_raw_left'],0)
        self.assertEqual(hw.mode,'muted');self.assertNotIn('prepare',hw.calls)
        self.assertFalse(self.pointer(app)['eligible'])
        hw.events=[dict(kind='recalibrate',value='start')];app.tick()
        self.until(app,lambda:app.state=='ready')
        self.assertTrue(app.configuration_ready);self.assertEqual(app.identity['aux_db'],0.)
        self.assertEqual(app.identity['aux_raw_left'],5)

    def test_wrong_post_prepare_aux_is_rejected_before_speech_or_training(self):
        cfg=sample_config();hw=ColdCodec(cfg,wrong_after_prepare=True);app,_,_=self.app(cfg,hw)
        app.event('recalibrate');self.until(app,lambda:app.state=='failed')
        self.assertIn('aux_db',app.reason);self.assertFalse(app.configuration_ready)
        self.assertFalse(self.pointer(app)['eligible']);self.assertEqual(hw.mode,'muted')
        self.assertNotIn('input',hw.calls);self.assertNotIn('training',hw.calls)
        hw.wrong_after_prepare=False;hw.events=[dict(kind='recalibrate',value='start')];app.tick()
        self.until(app,lambda:app.state=='ready')

    def test_missed_speech_and_rejection_accept_another_long_CAL_without_restart(self):
        for outcome in ('data_insufficient','model_rejected','hardware_error'):
            with self.subTest(outcome=outcome):
                cfg=sample_config();cfg['attempts'][0]['input_decision']=outcome
                app,hw,_=self.app(cfg);app.event('recalibrate')
                self.until(app,lambda:app.state in ('failed','inconclusive'))
                old=app.scene;self.assertFalse(app.fatal);self.assertFalse(self.pointer(app)['eligible'])
                hw.events=[dict(kind='recalibrate',value='short_ignored')];app.tick();self.assertEqual(app.scene,old)
                app.cfg['attempts'][0].pop('input_decision');hw.events=[dict(kind='recalibrate',value='start')];app.tick()
                self.until(app,lambda:app.state=='ready')
                self.assertNotEqual(app.scene,old);self.assertTrue(self.pointer(app)['eligible'])
                self.assertEqual(app.speech_retries,0)

    def test_explicit_retry_still_cannot_bypass_code_identity_or_failed_abort(self):
        app,hw,_=self.app();hw.identity['bit_sha256']='f'*64;app.tick()
        self.assertTrue(app.fatal);count=hw.calls.count('prepare')
        hw.events=[dict(kind='recalibrate',value='start')];app.tick();self.assertEqual(hw.calls.count('prepare'),count)
        app2,hw2,_=self.app();hw2.abort_bad=True;app2.event('stop');self.assertTrue(app2.fatal)
        hw2.abort_bad=False;hw2.events=[dict(kind='recalibrate',value='start')];app2.tick()
        self.assertNotIn('prepare',hw2.calls)

    def test_quiet_wait_is_four_seconds_without_changing_B_attempts(self):
        policy=frozen_policy(b);self.assertEqual(policy['quiet_seconds'],4)
        self.assertEqual(policy['attempts'],b.ATTEMPTS)


if __name__=='__main__':unittest.main()
