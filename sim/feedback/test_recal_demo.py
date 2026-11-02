"""Fixed-gain demo packaging and C runtime identity; no board or acoustic claim."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'board/audio_replay')]
import assemble_experiment as assembler
import freeze_recal_guard as freeze
from recal_mock import Board,sample_config,envelope
from recal_link import adapter_check
import test_recal_product as base


class DemoTests(unittest.TestCase):
    setUp=base.ProductTests.setUp
    app=base.ProductTests.app
    ready=base.ProductTests.ready
    until=base.ProductTests.until

    def demo(self):
        stage=self.folder/'adapters';freeze.stage(stage,demo=True)
        out=self.folder/'package';assembler.assemble_product(out,stage/'a',stage/'b')
        return out,json.loads((out/'product-config.json').read_text())

    def test_package_passes_gain_to_factory_and_keeps_open_loop_plan(self):
        out,cfg=self.demo();manifest=json.loads((out/'product-manifest.json').read_text())
        self.assertTrue(manifest['deployment_ready']);self.assertEqual(manifest['missing'],[])
        self.assertEqual(cfg['allowed_gain_q12'],[1631,2303,3254,4096,6900])
        self.assertEqual(cfg['expected_identity']['gain_q12'],6900)
        self.assertEqual(cfg['run_seconds'],8)
        self.assertEqual(cfg['maintenance_gain_q12'],1631)
        self.assertEqual(cfg['io_timeout_seconds'],150);self.assertEqual(cfg['compute_timeout_seconds'],150)
        self.assertEqual(cfg['phase_gain_q12']['prepare'],[0,1631,2303,3254,4096,6900])
        self.assertNotIn('runtime',cfg['phase_gain_q12'])
        for op in ('training','validation','install','run'):
            self.assertEqual(cfg['phase_gain_q12'][op],[0,6900])
        for attempt in cfg['capture_plans']:
            for phase in ('training','validation'):
                for cap in attempt[phase]['captures']:
                    self.assertTrue(cap['direct_only']);self.assertTrue(cap['zero_coeff'])
        self.assertEqual(manifest['hashes']['hw_api.py'],freeze.HELPER)
        self.assertEqual((out/'hw_api.py').read_bytes(),freeze.blob(freeze.A,'board/audio_replay/v3-io/hw_api.py'))

    def test_single_6900_eight_second_run_and_other_runtime_gain_rejected(self):
        cfg=sample_config();cfg['expected_identity']['gain_q12']=6900
        cfg.update(run_seconds=8,phase_gain_q12={op:[0,6900] for op in (
            'prepare','cue','input','training','validation','install','run')})
        hw=Board(cfg);original=hw.perform;runs=[]
        def perform(req,cancel):
            if req['op']!='run':return original(req,cancel)
            runs.append(req);hw.calls.append('run')
            return dict(envelope(req),ok=True,status='completed',identity=dict(hw.identity),
                        effective_mode='muted',elapsed_seconds=req['seconds'],**hw.installed)
        hw.perform=perform;app,_,_=self.app(cfg,hw);self.ready(app)
        app.event('start');self.until(app,lambda:app.state=='ended')
        self.assertEqual([(r['gain_q12'],r['seconds']) for r in runs],[(6900,8)])
        app.tick();self.assertEqual(len(runs),1)
        # A lower gain in the maintenance allowlist is still an identity error at START.
        hw.identity['gain_q12']=4096;app.event('start')
        self.assertEqual(app.outcome,'hardware_error');self.assertEqual(len(runs),1)

    def test_ordinary_profile_is_unchanged(self):
        stage=self.folder/'ordinary';freeze.stage(stage)
        meta=json.loads((stage/'a/product-adapter.json').read_text())
        self.assertEqual(meta['expected_identity']['gain_q12'],1631)
        self.assertNotIn(6900,meta['allowed_gain_q12'])
        self.assertNotIn('run_seconds',meta['config'])
        self.assertNotIn('demo_authorization',meta)

    def test_bootstrap_maintenance_does_not_use_high_demo_gain(self):
        import hashlib
        cfg=sample_config();cfg['expected_identity']['gain_q12']=6900
        cfg.update(allowed_gain_q12=[1631,2303,3254,4096,6900],maintenance_gain_q12=1631)
        model=self.folder/'bootstrap.json';model.write_text('{"fixture_id":"maintenance"}')
        digest=hashlib.sha256(model.read_bytes()).hexdigest();calls=[]
        class Hardware:
            def mute(self):return dict(ok=True,muted=True)
            def abort(self):return dict(ok=True,muted=True,quiescent=True)
            def capabilities(self):return dict(prepared_capture=True)
            def perform(self,req,cancel):
                calls.append(req)
                return dict(envelope(req),ok=True,status='completed',model_sha256=digest,
                            coefficients_sha256='1'*64,audio_elapsed_seconds=3.)
        result=adapter_check(Hardware(),cfg,self.folder/'check',model,
            lambda path,value:path.write_text(json.dumps(value)))
        self.assertTrue(result['success']);self.assertEqual(result['maintenance_gain_q12'],1631)
        self.assertEqual(next(r for r in calls if r['op']=='install')['run_gain_q12'],1631)
        self.assertEqual(next(r for r in calls if r['op']=='run')['gain_q12'],1631)


if __name__=='__main__':unittest.main()
