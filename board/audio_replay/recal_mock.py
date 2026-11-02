"""Software fixtures only. Never imports PYNQ or opens an audio device."""
import hashlib
import json
from pathlib import Path
import time

CONTRACT='recal-product-v1'

def sample_config():
    return dict(simulation=True,hardware_module='recal_mock',algorithm_module='recal_mock',
        expected_identity=dict(aux_db=0.,aux_raw_left=5,aux_raw_right=5,hp_volume=40,gain_q12=1631,
            sample_rate_hz=48828.125,driver_sha256='1'*64,bit_sha256='2'*64,hwh_sha256='3'*64,helper_sha256='4'*64),
        attempts=[dict(training={'signal':'synthetic training'},validation={'signal':'independent synthetic validation'})],
        quiet_seconds=.01,run_seconds=.05,compute_timeout_seconds=30,cue=True)


def envelope(req): return {k:req[k] for k in ('contract','request_id','scene_id')}


def evaluate(req):
    """Fixed B-return fixtures, not a numerical fit or an effect measurement."""
    plan=req['plan'];phase=req['phase']
    if phase=='fit' and plan.get('slow_seconds'): time.sleep(plan['slow_seconds'])
    decision=plan.get(phase+'_decision','valid_pass')
    reply=dict(envelope(req),decision=decision,reason='SYNTHETIC fixed algorithm result; not measured benefit')
    if phase=='fit' and decision=='valid_pass':
        q=[0]*512;q[0]=2**18
        model=dict(taps=512,lag_first=1,coefficient_format='signed24_fraction20',training_source='board',
            fixture_id=req['scene_id'],hp_volume=req['identity']['hp_volume'],sample_rate_hz=48828.125,bias=0,
            coefficients_q20=q,coefficients=[v/2**20 for v in q],simulation=True,
            evidence_kind='software_fixture; training_source field is schema compatibility only')
        path=Path(req['run_dir'])/'synthetic-model.json';path.write_text(json.dumps(model),encoding='utf-8')
        reply.update(model_path=str(path),model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if phase=='validate':
        reply.update(model_sha256=req['model_sha256'],validation_ids=[v['capture_id'] for v in req['validation']],
            qualifies_cancellation=not plan.get('no_effect_evidence',False),evidence={'kind':'synthetic fixed decision, not hardware'})
    return reply


class Board:
    def __init__(self, config):
        self.config=config;self.identity=dict(config['expected_identity']);self.mode='muted'
        self.prompts=[];self.calls=[];self.events=[];self.installed={};self.fault=None
        self.block_op=None;self.caps_missing=None;self.input_window_bad=False;self.shared_validation=False
        self.install_bad=False;self.abort_bad=False;self.protected=False

    def capabilities(self):
        result=dict(contract=CONTRACT,buttons=True,indicator=True,nonintrusive_events=True,
            abort_mutes=True,prepared_capture=True,bounded_run=True,mode_readback=True)
        if self.caps_missing: result[self.caps_missing]=False
        return result

    def mute(self): self.mode='muted';return dict(ok=True,muted=True)
    def abort(self):
        self.mode='muted';self.calls.append('abort')
        return dict(ok=not self.abort_bad,muted=not self.abort_bad,quiescent=not self.abort_bad)

    def poll(self):
        events=self.events;self.events=[]
        return dict(ok=True,identity=dict(self.identity),events=events,protected=self.protected,
                    effective_mode=self.mode,**self.installed)

    def indicate(self,prompt): self.prompts.append(dict(prompt));return dict(ok=True)

    def perform(self,req,cancel):
        op=req['op'];self.calls.append(op)
        if self.block_op==op:
            cancel.wait(4)
            return dict(envelope(req),ok=False,status='error',identity=self.identity)
        time.sleep(.005)
        reply=dict(envelope(req),ok=True,status='completed',identity=dict(self.identity))
        if cancel.is_set():
            self.mode='muted';return dict(reply,ok=False,status='error')
        if self.fault==op:
            return dict(reply,ok=False,status='protected',input_clip=True)
        if op=='cue': reply.update(end_frame=1000,tail_frames=200)
        if op in ('input','training','validation'):
            token='training' if self.shared_validation and op=='validation' else op
            capture_id=req['scene_id']+'-'+token+'-'+str(req['attempt'])
            path=Path(req['run_dir'])/(op+str(req['attempt'])+'.json')
            path.write_text(json.dumps({'software_fixture':True,'capture_id':capture_id}),encoding='utf-8')
            first=0 if self.input_window_bad else 1200
            reply.update(valid_first_frame=first,captures=[dict(capture_id=capture_id,path=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),first_frame=first,end_frame=2400,
                content_kind='human_private' if op=='input' else 'software_fixture',
                source_sha256=hashlib.sha256(capture_id.encode()).hexdigest())])
        if op=='install':
            self.installed={k:req[k] for k in ('model_sha256','coefficients_sha256')}
            reply.update(self.installed)
            if self.install_bad: reply['model_sha256']='0'*64
        if op=='run':
            self.mode='cancel'
            if cancel.wait(req['seconds']):
                self.mode='muted';return dict(reply,ok=False,status='error')
            reply.update(self.installed,effective_mode=self.mode,elapsed_seconds=req['seconds'])
            self.mode='muted'
        return reply


def create_product(config): return Board(config)
