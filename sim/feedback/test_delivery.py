"""Project delivery checks: real WAV controls and tamper-resistant acceptance."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import wave
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('c_delivery_test',ROOT/'tools/deliver_check.py')
delivery=importlib.util.module_from_spec(spec);spec.loader.exec_module(delivery)


class DeliveryChecks(unittest.TestCase):
    def work(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='delivery-test-')

    def setUp(self):
        # These checks cover the be3200e r1 delivery, not today's field tools.
        # Keep its five source pins and validate an exact, independently frozen
        # archive instead of silently repinning them to the integration tree.
        archive=ROOT/'build/packages/c-cold-start-r1.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                         'aba7466c675dd1829cbfae8a0db03621bac21a210692eac50923da0cedee790a')
        temp=self.work();self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        with zipfile.ZipFile(archive) as z:
            cfg=json.loads(z.read('tools/delivery-freeze.json'))
            names=set(cfg['source_sha256'])|{'tools/delivery-freeze.json',cfg['package']['path']}
            for name in names:
                relative=Path(name)
                self.assertFalse(relative.is_absolute() or '..' in relative.parts)
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(z.read(name))
        patcher=mock.patch.object(delivery,'ROOT',root)
        patcher.start();self.addCleanup(patcher.stop)
        self.assertEqual(delivery.config(),cfg)  # Still checks all five hashes.

    def test_known_snr_and_three_bad_wav_inputs(self):
        with self.work() as temp:
            r=delivery.listener_fixture(Path(temp))
            self.assertLess(abs(r['relative_change_error_db']),.01)
            self.assertLess(abs(r['total_to_background_error_db']),.5)
            self.assertTrue(all(v['status']=='failed' and v['reason'] for v in r['negative_cases'].values()))
            self.assertIsNone(r['absolute_spl'])
            self.assertEqual(r['real_listener_test'],'not_tested')

    def test_stdlib_pipeline_matches_frozen_production(self):
        with zipfile.ZipFile(ROOT/'build/packages/c-sprint-rc01-human-r1.zip') as z:
            node=next(n for n in ast.parse(z.read('sprint_experiment.py')).body
                      if isinstance(n,ast.FunctionDef) and n.name=='listener_metrics')
        ns=dict(np=np,wave=wave,Path=Path,sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest())
        exec(compile(ast.Module(body=[node],type_ignores=[]),'exact frozen listener','exec'),ns)
        with self.work() as temp:
            folder=Path(temp);delivery.listener_fixture(folder)
            current=delivery.metrics()
            for case in ('positive','length-mismatch','clipped','rate-mismatch'):
                old=ns['listener_metrics'](folder/case,delivery.CONFIRM)
                new=current(folder/case,delivery.CONFIRM)
                self.assertEqual(old['status'],new['status'])
                if new['status']=='passed':
                    self.assertAlmostEqual(old['relative_speech_change_db'],new['relative_speech_change_db'],places=11)
                    for mode in ('off','on'):self.assertAlmostEqual(old['snr_db'][mode],new['snr_db'][mode],places=11)
                else:self.assertEqual(old['reason'],new['reason'])

    def test_truncated_pcm_is_explicit_failure(self):
        with self.work() as temp:
            folder=Path(temp);delivery.listener_fixture(folder)
            p=folder/'positive/on-speech.wav';p.write_bytes(p.read_bytes()[:-10])
            result=delivery.metrics()(folder/'positive',delivery.CONFIRM)
            self.assertEqual(result['status'],'failed');self.assertIn('truncated',result['reason'])

    def test_deployed_model_and_three_mapping_points(self):
        cfg=delivery.config()
        a=delivery.asset_checks((delivery.ROOT/cfg['package']['path']).read_bytes(),cfg)
        controls=delivery.mapping_controls(a['q'])
        self.assertEqual([r['gain_db'] for r in controls],[-12,-6,0])
        self.assertTrue(all(r['ok'] and r['prediction_mismatches']==0 for r in controls))
        self.assertEqual(a['assets'],cfg['assets'])

    def test_corrupt_asset_never_accepted(self):
        cfg=delivery.config();data=bytearray((delivery.ROOT/cfg['package']['path']).read_bytes());data[-1]^=1
        with self.assertRaises(delivery.DeliveryError) as cm:delivery.asset_checks(bytes(data),cfg)
        self.assertEqual(cm.exception.defect,'D2')
        # Redirecting the historical scope must not become a source-hash bypass.
        source=delivery.ROOT/'board/audio_replay/sprint_selftest.py'
        source.write_bytes(source.read_bytes()+b'\n# deliberate bad source\n')
        with self.assertRaises(delivery.DeliveryError) as cm:delivery.config()
        self.assertEqual(cm.exception.defect,'D2')

    def test_report_boolean_and_rehashed_manifest_cannot_fake_delivery(self):
        cfg=delivery.config()
        with self.work() as temp:
            root=Path(temp)
            for name in cfg['source_sha256']:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(delivery.source_bytes(delivery.ROOT/name))
            (root/'tools/delivery-freeze.json').write_bytes(delivery.encoded(cfg))
            with mock.patch.object(delivery,'ROOT',root),mock.patch.object(delivery,'identity',return_value={
                    'repository_commit':'1'*40,'clean_checkout':True,'test_fixture':True}):
                path,_=delivery.build('listener-pipeline',cfg)
                with zipfile.ZipFile(path) as z:payload={n:z.read(n) for n in z.namelist()}
                r=json.loads(payload['listener-pipeline.json']);r['positive']['relative_speech_change_db']=999
                payload['listener-pipeline.json']=delivery.encoded(r)
                manifest=json.loads(payload['artifact-manifest.json'])
                manifest['sha256']['listener-pipeline.json']=delivery.digest(payload['listener-pipeline.json'])
                payload['artifact-manifest.json']=delivery.encoded(manifest)
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                    for n,b in payload.items():z.writestr(n,b)
                with self.assertRaises(delivery.DeliveryError):delivery.verify_artifact(path,cfg)

    def test_missing_artifact_exits_nonzero_without_completion_line(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):result=delivery.main(['does-not-exist.zip'])
        self.assertEqual(result,2)
        self.assertIn('DELIVERY_FAILED D3',output.getvalue());self.assertNotIn('PACKAGE_COMPLETE',output.getvalue())


if __name__=='__main__':unittest.main()
