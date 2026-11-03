"""Batch scheduling/retention with synthetic driver files, not board timing."""
import hashlib
import json
from pathlib import Path
import sys
import threading
import types
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'board/audio_replay'),str(ROOT/'scripts')]
from recal_link import CAPTURE_PLAN_CONTRACT,perform_capture_plan,check_capture_plan,capture_plans
from recal_mock import Board,sample_config
from replay_tools import verify_replay
import test_recal_product as base


class Driver:
    CAPTURE_PLAN_API=CAPTURE_PLAN_CONTRACT
    def __init__(self,identity):self.identity=identity;self.calls=0;self.bad_index=None;self.tamper_index=None
    def replay_capture_plan(self,outputs,fixture,model,source,**kw):
        self.calls+=1;assert kw['before_start']() and kw['gain_q12']==0
        assert kw['direct_only'] and kw['zero_coeff'] and not kw['restore_stock']
        caps=[];digest=hashlib.sha256(source.tobytes()).hexdigest()
        for index,window in enumerate(outputs):
            if self.bad_index==index:
                return dict(contract=CAPTURE_PLAN_CONTRACT,request_id=kw['request_id'],scene_id=kw['scene_id'],
                    op=kw['op'],ok=False,status='error',failed_index=index,failed_check='bit_exact',captures=caps,batch={})
            first,end=window['first_frame'],window['end_frame'];ref=np.zeros(16384,dtype=np.int64)
            valid=max(0,min(end,len(source))-first);ref[:valid]=source[first:first+valid].astype(np.int64)*256
            raw=np.column_stack((ref,ref//4,np.zeros(16384,np.int64),ref//4));q=np.zeros(512,np.int32)
            checks=verify_replay(raw,q,False,0,source,first)
            md=dict(self.identity,fixture_id=fixture,capture_id=window['capture_id'],gain_q12=0,
                forward_path_open=True,zero_coeff=True,bypass=False,first_frame=first,frames=16384,
                completed_frames=len(outputs)*16388,stop_reason='completed',source_schedule_verified=True,
                model_sha256=hashlib.sha256(Path(model).read_bytes()).hexdigest(),verification=checks,capture_status=1)
            if self.tamper_index==index:md['fixture_id']='wrong-scene'
            path=Path(window['output_path']);status=path.with_suffix('.status.json')
            np.savez(path,reference=raw[:,0]/2**23,microphone=raw[:,1]/2**23,prediction_pcm=raw[:,2],
                residual_pcm=raw[:,3],coefficients_q20=q,source_pcm16=source,sample_rate_hz=48828.125,metadata_json=json.dumps(md))
            status.write_text(json.dumps(dict(recovery_ok=True,save_error=None,fixture_id=fixture,
                first_frame=first,frames=16384,stop_reason='completed')))
            proof=[]
            for a in range(first,end,2048):
                b=min(a+2048,end);proof.append(dict(first_frame=a,end_frame=b,completed_before=b,completed_after=b))
            caps.append(dict(capture_id=window['capture_id'],path=str(path),status_path=str(status),first_frame=first,
                end_frame=end,valid_frames=16382,source_sha256=digest,content_kind='onboard_excitation',read_proof=proof))
        return dict(contract=CAPTURE_PLAN_CONTRACT,request_id=kw['request_id'],scene_id=kw['scene_id'],op=kw['op'],
            ok=True,status='completed',captures=caps,failed_index=None,failed_check=None,
            batch=dict(completed_segments=len(outputs),ring_overrun=False,overlay_downloads=1,source_loads=1,arm_count=1))


class Facade:
    def __init__(self,folder,identity):
        self.identity_value=identity;self.driver=Driver(identity);self._current_op=None;self._op_hold=0;self._scene_frames=0
        self.hp_volume=40;self.model_path=folder/'bootstrap.json';self.run_dir=str(folder)
        self.model_path.write_text(json.dumps(dict(fixture_id='old-scene',coefficients_q20=[0]*512)))
    def identity(self):return dict(self.identity_value)
    def _driver(self):return self.driver
    def _arm_baseline(self,cancel):return not cancel.is_set()
    def _capture_path(self,scene,op,index):return Path(self.run_dir)/('%s-%02d.npz'%(op,index)),str(index)
    def _make_stimulus(self,seed,level_dbfs):
        x=np.random.default_rng(seed).standard_normal(16386);x-=x.mean()
        x*=10**(level_dbfs/20)/float(np.sqrt(np.mean(x*x)))
        return np.rint(x*32767).astype(np.int16)


class CapturePlanTests(unittest.TestCase):
    setUp=base.ProductTests.setUp
    app=base.ProductTests.app
    until=base.ProductTests.until
    def request(self,op='training',n=4):
        folder=self.folder/(op+str(n));folder.mkdir()
        identity=sample_config()['expected_identity'];identity['gain_q12']=0
        hw=Facade(self.folder,identity)
        request=dict(contract='recal-product-v1',request_id='r-'+op,scene_id='scene',op=op,run_dir=str(folder),
            identity=identity,plan=dict(seed=4242 if op=='training' else 4243,levels=[-22.],
                captures=[dict(capture_id=op+str(i)) for i in range(n)]))
        return hw,request

    def test_four_training_and_two_validation_each_call_driver_once(self):
        for op,n in [('training',4),('validation',2)]:
            hw,req=self.request(op,n);before=hw.model_path.read_bytes()
            reply=perform_capture_plan(hw,req,threading.Event());check_capture_plan(req,reply)
            self.assertEqual(hw.driver.calls,1);self.assertEqual(len(reply['captures']),n)
            self.assertEqual(hw.model_path.read_bytes(),before)
            self.assertEqual([c['first_frame'] for c in reply['captures']],[4+i*16388 for i in range(n)])

    def test_middle_segment_failure_rejects_whole_plan_without_retry(self):
        hw,req=self.request();hw.driver.bad_index=1
        reply=perform_capture_plan(hw,req,threading.Event())
        with self.assertRaisesRegex(ValueError,'segment 1: bit_exact'):check_capture_plan(req,reply)
        self.assertEqual(hw.driver.calls,1);self.assertFalse(reply['ok']);self.assertEqual(len(reply['captures']),1)

    def test_mixed_fixture_and_overwritten_ring_are_rejected(self):
        hw,req=self.request();hw.driver.tamper_index=2
        reply=perform_capture_plan(hw,req,threading.Event())
        with self.assertRaisesRegex(ValueError,'segment 2: capture_identity'):check_capture_plan(req,reply)
        # Retention is checked separately from arithmetic, which can pass for overwritten repeated noise.
        hw,req=self.request('validation',2);reply=perform_capture_plan(hw,req,threading.Event())
        reply['captures'][0]['read_proof'][0]['completed_after']=999999
        with self.assertRaisesRegex(ValueError,'segment 0: ring_retention'):check_capture_plan(req,reply)

    def test_pre_cancel_does_not_invoke_driver(self):
        hw,req=self.request();cancel=threading.Event();cancel.set()
        reply=perform_capture_plan(hw,req,cancel)
        self.assertFalse(reply['ok']);self.assertEqual(hw.driver.calls,0);self.assertEqual(hw._op_hold,0)

    def test_panel_flow_with_batch_CAL_and_BTN2_resume(self):
        cfg=sample_config();cfg.update(quiet_seconds=0,request_capture_directories=True)
        cfg['attempts']=[dict(training=dict(rms_dbfs=-22.,segments=4,seed=4242),validation=dict(rms_dbfs=-22.,segments=2,seed=4242))]
        cfg['capture_plans']=capture_plans(cfg['attempts'])
        cfg['phase_gain_q12']={op:[0,1631] for op in ('prepare','cue','input','training','validation','install','run','runtime')}
        hw=Board(cfg);facade=Facade(self.folder,hw.identity);original=hw.perform
        caps=hw.capabilities;hw.capabilities=lambda:dict(caps(),capture_plan_batch=CAPTURE_PLAN_CONTRACT)
        def batch(req,cancel):hw.identity['gain_q12']=0;return perform_capture_plan(facade,req,cancel)
        hw.perform_capture_plan=batch
        def perform(req,cancel):
            if req['op']=='install':hw.identity['gain_q12']=1631
            return original(req,cancel)
        hw.perform=perform;app,_,calc=self.app(cfg,hw);app.event('recalibrate');self.until(app,lambda:app.state=='ready')
        self.assertEqual(facade.driver.calls,2);self.assertEqual(len(app.training),4);self.assertEqual(len(app.validation),2)
        hw.block_op='run';app.event('start');hw.protected=True;app.tick();self.until(app,app.hw_idle.is_set)
        hw.protected=False;hw.events=[dict(kind='confirm_quiet',value='btn2')];app.tick()
        self.assertEqual(app.state,'ready');self.assertEqual(app.resume_count,1)
        hw.block_op=None;app.event('start');self.until(app,lambda:app.state=='ended')
        self.assertEqual(facade.driver.calls,2)


if __name__=='__main__':unittest.main()
