"""Only the three requested protection-resume cases; software hardware fixture."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'scripts')]
import test_recal_product as base


class ResumeTests(unittest.TestCase):
    setUp=base.ProductTests.setUp
    app=base.ProductTests.app
    ready=base.ProductTests.ready
    until=base.ProductTests.until
    pointer=base.ProductTests.pointer

    def protect(self,app,hw):
        hw.block_op='run';app.event('start')
        self.until(app,lambda:not app.hw_idle.is_set())
        hw.protected=True;app.tick()
        self.until(app,app.hw_idle.is_set)
        self.assertEqual(app.state,'protected');hw.protected=False

    def press(self,app,hw):
        hw.events=[dict(kind='confirm_quiet',value='btn2')];app.tick()

    def test_normal_resume_uses_same_model_and_start_runs_without_CAL(self):
        cfg=base.sample_config();gain=cfg['expected_identity']['gain_q12']
        cfg['phase_gain_q12']={op:[0,gain] for op in (
            'prepare','cue','input','training','validation','install','run','runtime')}
        app,hw,calc=self.app(cfg);self.ready(app)
        scene=app.scene;model=app.bundle['model_sha256'];fits=len(calc.calls)
        self.protect(app,hw);self.assertFalse(self.pointer(app)['eligible'])
        hw.identity['gain_q12']=0  # A's observed readback after protection mute.
        self.press(app,hw)
        self.assertEqual(app.state,'ready');self.assertEqual(app.scene,scene)
        self.assertEqual(app.bundle['model_sha256'],model);self.assertEqual(len(calc.calls),fits)
        self.assertTrue(self.pointer(app)['eligible'])
        status=json.loads((app.root/'status.json').read_text())
        self.assertEqual((status['resume_count'],status['resumed_from']),(1,'protected'))
        hw.block_op=None;app.event('start');self.until(app,lambda:app.state=='ended')

    def test_changed_model_hash_is_rejected_and_stays_protected(self):
        app,hw,_=self.app();self.ready(app);self.protect(app,hw)
        path=Path(app.bundle['model_path']);path.write_bytes(path.read_bytes()+b'\n')
        self.press(app,hw)
        self.assertEqual(app.state,'protected');self.assertEqual(app.resume_count,0)
        self.assertIn('CAL',app.reason);self.assertFalse(self.pointer(app)['eligible'])

    def test_fourth_resume_is_rejected_after_three_in_same_scene(self):
        app,hw,_=self.app();self.ready(app);scene=app.scene
        for count in range(1,4):
            self.protect(app,hw);self.press(app,hw)
            self.assertEqual(app.state,'ready');self.assertEqual(app.resume_count,count)
        self.protect(app,hw);self.press(app,hw)
        self.assertEqual(app.scene,scene);self.assertEqual(app.state,'protected')
        self.assertEqual(app.resume_count,3);self.assertIn('CAL',app.reason)
        self.assertFalse(self.pointer(app)['eligible'])


if __name__=='__main__':unittest.main()
