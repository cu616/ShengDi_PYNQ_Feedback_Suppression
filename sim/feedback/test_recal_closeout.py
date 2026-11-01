"""C closeout checks: late driver return, bounded level and metadata intake."""
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'src')]
from recal_link import capture_plans,ingest,installed_model,run_evidence
from recal_mock import Board,sample_config
import recal_algorithm as b
import recal_product as p
import test_recal_product as base_tests


class CloseoutTests(unittest.TestCase):
    setUp=base_tests.ProductTests.setUp
    app=base_tests.ProductTests.app
    until=base_tests.ProductTests.until
    pointer=base_tests.ProductTests.pointer

    def delayed(self):
        cfg=sample_config();hw=Board(cfg);release=threading.Event();original=hw.perform
        def late(req,cancel):
            if req['op']=='training' and not release.is_set():
                hw.calls.append('old_training');release.wait(4)
            return original(req,cancel)
        hw.perform=late;self.addCleanup(release.set)
        app,_,_=self.app(cfg,hardware=hw);app.event('recalibrate')
        self.until(app,lambda:'old_training' in hw.calls)
        return app,hw,release

    def test_stop_mutes_immediately_and_waits_before_reusing_hardware(self):
        app,hw,release=self.delayed();app.event('stop')
        self.assertEqual(hw.mode,'muted');self.assertEqual(app.state,'stopping')
        count=hw.calls.count('prepare');hw.events=[dict(kind='recalibrate')];app.tick()
        self.assertEqual(hw.calls.count('prepare'),count);self.assertFalse(self.pointer(app)['eligible'])
        release.set();self.until(app,lambda:hw.calls.count('prepare')>count)
        self.assertNotEqual(app.outcome,'valid_pass')

    def test_second_stop_cancels_queued_recalibration(self):
        app,hw,release=self.delayed();app.event('stop');app.event('recalibrate')
        count=hw.calls.count('prepare');app.event('stop');release.set()
        self.until(app,lambda:app.state=='cancelled')
        self.assertEqual(hw.calls.count('prepare'),count);self.assertFalse(app.queued_recalibrate)

    def test_each_attempt_seals_one_level_so_adapter_cannot_rescan(self):
        for canonical,io in zip(b.ATTEMPTS,capture_plans(b.ATTEMPTS)):
            for phase in ('training','validation'):
                self.assertEqual(io[phase]['levels'],[canonical[phase]['rms_dbfs']])
                self.assertEqual(len(io[phase]['captures']),canonical[phase]['segments'])

    def test_explicit_safe_indicator_receives_actual_running_mode_changes(self):
        cfg=sample_config();cfg.update(indicator_encoding='led4',indicator_armed_safe=True,run_seconds=.5)
        app,hw,_=self.app(cfg);app.event('recalibrate');self.until(app,lambda:app.state=='ready')
        app.event('start');self.until(app,lambda:hw.mode=='cancel');app.tick()
        hw.mode='bypass';app.tick();self.assertEqual(hw.prompts[-1]['mode'],'bypass')
        self.assertFalse(app.indicator_deferred)

    def test_run_initialization_zero_gain_is_allowed_only_while_muted(self):
        cfg=sample_config();cfg['phase_gain_q12']={'run':[0,1631]};cfg['run_seconds']=.5
        app,hw,_=self.app(cfg);app.event('recalibrate');self.until(app,lambda:app.state=='ready')
        original=hw.perform;release=threading.Event();self.addCleanup(release.set)
        def preparing(req,cancel):
            if req['op']=='run':
                hw.identity['gain_q12']=0;release.wait(2);hw.identity['gain_q12']=1631
            return original(req,cancel)
        hw.perform=preparing;app.event('start');self.until(app,lambda:hw.identity['gain_q12']==0)
        self.assertEqual(app.state,'running');self.assertEqual(app.gain_scope,'run')
        release.set();self.until(app,lambda:hw.mode=='cancel');app.tick()
        hw.identity['gain_q12']=0;app.tick()
        self.assertEqual(app.outcome,'hardware_error');self.assertFalse(self.pointer(app)['eligible'])

    def test_embedded_marker_uses_original_source_coordinates_without_editing_pcm(self):
        run=self.folder/'window';run.mkdir();path=run/'capture.npz'
        np.savez(path,reference=np.zeros(16384),microphone=np.zeros(16384),source_pcm16=np.zeros(122068,dtype=np.int16),
            metadata_json=json.dumps(dict(first_frame=105686)))
        digest=p.sha(path);req=dict(run_dir=str(run),request_id='r',scene_id='s',op='input',cue=True)
        raw=dict(captures=[dict(capture_id='c',path=str(path),sha256=digest,end_frame=32768)],
            input_ready=dict(request_id='r',scene_id='s',cue_end_frame=95700))
        normalized=ingest(req,raw,None);record=normalized['captures'][0]
        self.assertEqual(record['first_frame'],105686);self.assertEqual(record['end_frame'],122070)
        self.assertEqual(record['content_kind'],'human_private');self.assertEqual(p.sha(path),digest)
        self.assertEqual(raw['captures'][0]['end_frame'],32768)

    def test_unapproved_field_trial_cannot_import_hardware(self):
        folder=self.folder/'blocked';folder.mkdir()
        p.write_json(folder/'product-manifest.json',dict(contract='recal-product-v1',hashes={},
            simulation=False,deployment_ready=False,missing=['A runtime defects'],field_trial_allowed=False))
        with mock.patch.object(sys,'argv',['recal_product.py','--base',str(folder),'--field-trial']),\
             mock.patch.object(p.importlib,'import_module') as loader:
            with self.assertRaisesRegex(ValueError,'not enabled'):p.main()
        self.assertFalse(loader.called)

    def test_embedded_input_calls_one_cue_capture_before_B_input(self):
        from recal_link import frozen_policy
        from test_recal_frozen import FrozenBoard
        cfg=sample_config();cfg.update(frozen_policy(b));cfg['capture_plans']=capture_plans(cfg['attempts'])
        cfg.update(input_mode='embedded',quiet_seconds=.01,speech_seconds=2.5)
        hw=FrozenBoard(cfg);original=hw.perform
        def embedded(req,cancel):
            if req['op']!='input':return original(req,cancel)
            hw.calls.append('embedded_input');self.assertTrue(req['cue']);self.assertEqual(req['seconds'],2.5)
            path=Path(req['run_dir'])/'input.npz';np.savez(path,reference=np.zeros(16384),
                microphone=.1*np.sin(np.arange(16384)*.03),source_pcm16=np.zeros(122068,dtype=np.int16),
                sample_rate_hz=48828.125,metadata_json=json.dumps(dict(first_frame=105686)))
            return dict(**{k:req[k] for k in ('contract','request_id','scene_id')},ok=True,status='completed',
                identity=dict(hw.identity),captures=[dict(capture_id='input',path=str(path),sha256=p.sha(path))],
                input_ready=dict(request_id=req['request_id'],scene_id=req['scene_id'],cue_end_frame=95700))
        hw.perform=embedded;calc=p.Calculator('recal_algorithm',self.folder/'embedded-calc')
        app,_,_=self.app(cfg,hardware=hw,calculator=calc);app.event('recalibrate')
        self.until(app,lambda:app.state in ('ready','failed','inconclusive'),timeout=20)
        self.assertEqual(app.state,'ready',app.reason);self.assertEqual(hw.calls.count('embedded_input'),1)
        self.assertNotIn('cue',hw.calls);self.assertEqual(app.cue_end,95700)

    def test_scene_serialization_may_change_bytes_but_not_validated_model(self):
        src=self.folder/'model.json';src.write_text(json.dumps(dict(fixture_id='s',coefficients_q20=[1,2])))
        actual=self.folder/'bound.json';actual.write_text(json.dumps(json.loads(src.read_text()),indent=2))
        bundle=dict(model_path=str(src),model_sha256=p.sha(src),coefficients_sha256='q'*64)
        reply=dict(source_model_sha256=p.sha(src),model_sha256=p.sha(actual),coefficients_sha256='q'*64)
        self.assertEqual(installed_model(dict(scene_id='s'),reply,bundle,self.folder),actual)
        actual.write_text(json.dumps(dict(fixture_id='s',coefficients_q20=[2,2])))
        reply['model_sha256']=p.sha(actual)
        with self.assertRaisesRegex(ValueError,'changed model content'):
            installed_model(dict(scene_id='s'),reply,bundle,self.folder)
        reply['source_model_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'source identity'):
            installed_model(dict(scene_id='s'),reply,bundle,self.folder)

    def test_ring_window_is_not_used_as_completed_run_duration(self):
        path=self.folder/'run.npz';rate=48828.125;frames=int(3*rate)
        md=dict(first_frame=frames-16384,frames=16384,completed_frames=frames,sample_rate_hz=rate,
            stop_reason='completed',capture_status=1,model_sha256='m',coefficients_sha256='q')
        def save():np.savez(path,microphone=np.zeros(16384),metadata_json=json.dumps(md))
        save();reply=dict(path=str(path),audio_frames=16384,elapsed_seconds=.336,wall_seconds=8.,
            identity=dict(sample_rate_hz=rate),model_sha256='m',coefficients_sha256='q')
        request=dict(seconds=3.,model_sha256='m',coefficients_sha256='q')
        result=run_evidence(request,reply,self.folder)
        self.assertAlmostEqual(result['audio_elapsed_seconds'],3.,places=4)
        self.assertEqual(result['elapsed_seconds'],.336);self.assertEqual(result['wall_seconds'],8.)
        md['capture_status']=0;save()
        with self.assertRaisesRegex(ValueError,'completion counter'):run_evidence(request,reply,self.folder)

    def test_bootstrap_zero_cannot_become_eligible_model(self):
        app,hw,_=self.app();app.event('recalibrate');self.until(app,lambda:app.state=='ready')
        model=Path(app.bundle['model_path']);data=json.loads(model.read_text());data['bootstrap_only']=True
        data.pop('simulation',None)
        path=self.folder/'bootstrap.json';p.write_json(path,data)
        with self.assertRaisesRegex(p.Failure,'初始化零模型'):
            app.store.stage(path,p.sha(path),app.scene,app.cfg['expected_identity'],{})


if __name__=='__main__':unittest.main()
