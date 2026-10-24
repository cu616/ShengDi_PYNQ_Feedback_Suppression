"""Controlled room orchestration; every runner and hearing response is software."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
import room_experiment as room
from evaluation import analyze_npz,sha
from closed_tools import gain_pcm

BIT='8b2426f4fbcf27425731899557b179d2aea8a4ec2fa26dcc11b60102ecb45339'


def setup(base):
    entries=[];files={}
    for role,taps in [('baseline',256),('candidate',512)]:
        model=dict(taps=taps,lag_first=1,coefficient_format='signed24_fraction20',
                   training_source='board',fixture_id=room.PLAN['fixture_id'],hp_volume=40,
                   sample_rate_hz=room.RATE,coefficients=[0.]*taps,coefficients_q20=[0]*taps,bias=0.)
        path=base/'models'/('%s_%d.json'%(role,taps));path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(model));files[role]=str(path.relative_to(base))
        entries.append(dict(file=path.name,sha256=sha(path),taps=taps,lag_first=1,
                            fixture_id=room.PLAN['fixture_id'],hp_volume=40,sample_rate_hz=room.RATE))
    files['bypass']=files['candidate']
    (base/'models/manifest.json').write_text(json.dumps({'models':entries}))
    scene=dict(fixture_id=room.PLAN['fixture_id'],hp_volume=40,noise_floor_dbfs=-60.)
    (base/'scene.json').write_text(json.dumps(scene))
    burst,tone=room.sources();np.save(base/'burst.npy',burst);np.save(base/'gate.npy',tone)
    return {'hashes':{'audio_replay.bit':BIT},'model_files':files},scene


class Runner:
    def __init__(self,clip_first_closed=False,drift_gate=None):
        self.calls=[];self.gates=0;self.clip=clip_first_closed;self.drift_gate=drift_gate
    def __call__(self,path,fixture,model,source,**kw):
        if not kw['before_start']():raise RuntimeError('operator_cancel')
        self.calls.append(dict(direct=kw['direct_only'],bypass=kw['bypass'],model=model,gain=kw['gain_db']))
        n=int(kw['seconds']*room.RATE);first=max(0,n-16384);t=np.arange(n)/room.RATE
        if kw['direct_only']:
            self.gates+=1
            mic=np.zeros(n,dtype=np.int64)
            amp=.5 if self.gates!=self.drift_gate else .1
            mic[125:125+min(len(source),n-125)]=np.rint(source[:min(len(source),n-125)].astype(float)*256*amp).astype(np.int64)
        else:
            mic=np.rint(2**23*.01*(np.sin(2*np.pi*500*t)+np.sin(2*np.pi*2000*t)+np.sin(2*np.pi*8400*t))).astype(np.int64)
            if self.clip:mic[first+100]=2**23-1;self.clip=False
        gain=0 if kw['direct_only'] else int(np.floor(4096*10**(kw['gain_db']/20)+.5))
        ref=np.zeros(n,dtype=np.int64);ref[:len(source)]=source.astype(np.int64)*256
        ref[2:]=np.clip(ref[2:]+gain_pcm(mic[:-2],gain),-2**23,2**23-1)
        q=np.zeros(512,dtype='<i4')
        m=dict(capture_id='software-'+path.stem,driver_evidence_version='a-replay-evidence-v2',first_frame=first,completed_frames=n,frames=n-first,
               fixture_id=fixture,gain_q12=gain,hp_volume=40,sample_rate_hz=room.RATE,bypass=kw['bypass'],
               bit_sha256=BIT,model_sha256=sha(model),coefficients_sha256=hashlib.sha256(q.tobytes()).hexdigest(),
               source_pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest(),source_frames=len(source),
               source_end_frame_exclusive=len(source),source_schedule_verified=True,
               clip_counts_raw=[0,0,0],guard_tripped=False,prediction_saturations=0,residual_saturations=0,
               gain_saturations=0,mix_saturations=0,verification={'bit_exact':True},evidence_kind='software_fixture')
        np.savez_compressed(path,reference=ref[first:]/2**23,microphone=mic[first:]/2**23,
            prediction_pcm=np.zeros(n-first,dtype=np.int64),residual_pcm=mic[first:],
            coefficients_q20=q,source_pcm16=source,sample_rate_hz=room.RATE,metadata_json=json.dumps(m))
        path.with_suffix('.status.json').write_text(json.dumps({'recovery_ok':True,'cleanup_errors':[],'save_error':None}))
        return m


class RoomTests(unittest.TestCase):
    def work(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=ROOT/'tmp')
    def execute(self,base,runner,action='RUN'):
        manifest,scene=setup(base)
        def answer(prompt):return action if 'RUN固定' in prompt else 'START' if 'START' in prompt else 'H1'
        with contextlib.redirect_stdout(io.StringIO()):
            return room.run_room(base,ask=answer,runner=runner,validator=lambda _: (manifest,scene))

    def test_full_schedule_has_gate_before_every_closed_trial_and_real_pairs_zero(self):
        with self.work() as d:
            runner=Runner();state=self.execute(Path(d),runner)
            self.assertEqual(state['status'],'completed',state.get('stop_reason'))
            self.assertEqual(len(runner.calls),38)
            for i,c in enumerate(runner.calls):
                if not c['direct']:self.assertTrue(runner.calls[i-1]['direct'])
            self.assertEqual(len(state['model_pairs']),8)
            self.assertFalse(any(p['effect_eligible'] for p in state['model_pairs']))
            self.assertFalse(state['normal_mic_amplification_demonstrated'])
            self.assertTrue(state['functional_hearing_accepted'])
            closed=[r for r in state['trials'] if r['trial_role']=='closed_model']
            self.assertTrue(all(r['analysis']['tail_statistics']['tail_frames']>=.16*room.RATE for r in closed))
            self.assertTrue(all(r['analysis']['capture_window']['first_frame']<r['analysis']['tail_analysis_window']['first_frame'] for r in closed))
            packet=next(Path(d).rglob('return-results.zip'))
            with zipfile.ZipFile(packet) as z:
                self.assertTrue(any(n.startswith('models/') for n in z.namelist()))
                self.assertFalse(any(n.endswith(('.npz','.npy','.wav')) for n in z.namelist()))

    def test_microphone_full_scale_without_guard_stops_before_any_next_trial(self):
        with self.work() as d:
            runner=Runner(clip_first_closed=True);state=self.execute(Path(d),runner)
            self.assertEqual(state['status'],'stopped');self.assertEqual(len(runner.calls),4)
            self.assertIn('microphone_full_scale',state['stop_reason'])
            self.assertTrue(state['amplifier_reset_required'])
            last=state['trials'][-1]
            self.assertFalse(last['metadata']['guard_tripped'])
            self.assertTrue(last['analysis']['event_flags']['microphone_clipping'])
            self.assertEqual(last['analysis']['category'],'invalid')

    def test_gate_drift_skips_target_without_rebaselining(self):
        with self.work() as d:
            runner=Runner(drift_gate=3);state=self.execute(Path(d),runner)
            self.assertEqual(state['status'],'stopped')
            self.assertIn('gate_drift_exceeds_5_db',state['stop_reason'])
            self.assertTrue(all(c['direct'] for c in runner.calls))
            self.assertEqual(len(runner.calls),3)

    def test_failed_next_gate_invalidates_preceding_closed_measurement(self):
        with self.work() as d:
            runner=Runner(drift_gate=4);state=self.execute(Path(d),runner)
            closed=[r for r in state['trials'] if r['trial_role']=='closed_model']
            self.assertEqual(len(closed),1)
            self.assertEqual(closed[0]['category'],'invalid')
            self.assertFalse(closed[0]['positive_control_valid'])
            self.assertIn('post_trial_gate_failed',closed[0]['analysis']['reasons'])

    def test_initial_noise_only_is_not_a_valid_amplifier_gate(self):
        with self.work() as d:
            base=Path(d);manifest,scene=setup(base)
            source=np.load(base/'gate.npy');path=base/'noise.npz'
            r=Runner();r(path,scene['fixture_id'],base/manifest['model_files']['candidate'],source,
                         direct_only=True,bypass=True,gain_db=0.,seconds=1.02,before_start=lambda:True)
            with np.load(path) as z:data={k:np.array(z[k]) for k in z.files}
            data['microphone']=np.random.default_rng(1).normal(size=len(data['microphone']))*1e-4
            np.savez(path,**data)
            gate=room.gate_metrics(path,-60.)
            self.assertFalse(gate['passed']);self.assertIn('gate_tone_not_observed',gate['reasons'])

    def test_gate_5_db_boundary_is_applied_to_fixed_baseline(self):
        with self.work() as d:
            base=Path(d);manifest,scene=setup(base);path=base/'gate.npz';source=np.load(base/'gate.npy')
            Runner()(path,scene['fixture_id'],base/manifest['model_files']['candidate'],source,
                     direct_only=True,bypass=True,gain_db=0.,seconds=1.02,before_start=lambda:True)
            baseline=room.gate_metrics(path,-60.)['rms_dbfs']
            with np.load(path) as z:original={k:np.array(z[k]) for k in z.files}
            for delta,passed in [(4.99,True),(5.01,False),(-5.01,False)]:
                data=dict(original);data['microphone']=original['microphone']*10**(delta/20)
                np.savez(path,**data)
                result=room.gate_metrics(path,-60.,baseline)
                self.assertIs(result['passed'],passed)

    def test_noise_floor_tail_is_not_reported_as_stable(self):
        from tail_metrics import tail_statistics
        n=9000;t=np.arange(n)/room.RATE
        mic=np.rint(2**23*10**(-40/20)*np.sin(2*np.pi*1000*t)).astype(np.int64)
        m=dict(first_frame=10000,completed_frames=10000+n,frames=n,source_frames=1000,
               source_end_frame_exclusive=1000,source_schedule_verified=True,
               external_source_off_verified=True,external_source_active=False,noise_floor_dbfs=-40.)
        result=tail_statistics(mic,mic,m,room.RATE)
        self.assertFalse(result['tail_valid'])
        self.assertIn('tail_below_signal_floor',result['tail_reasons'])
        self.assertEqual(result['tail_config']['minimum_mic_dbfs'],-34.)

    def test_preflight_failure_and_operator_cancel_return_packet_without_driver(self):
        with self.work() as d:
            base=Path(d)
            with contextlib.redirect_stdout(io.StringIO()):
                state=room.run_room(base,ask=lambda _:self.fail('unexpected question'),runner=lambda *a,**k:self.fail('driver'))
            self.assertEqual(state['status'],'stopped');self.assertTrue(list(base.rglob('return-results.zip')))
        with self.work() as d:
            runner=Runner();state=self.execute(Path(d),runner,action='q')
            self.assertEqual(state['status'],'cancelled');self.assertFalse(runner.calls)

    def test_speech_only_has_initial_and_per_trial_gates(self):
        with self.work() as d:
            runner=Runner();state=self.execute(Path(d),runner,action='SPEECH')
            self.assertEqual(state['status'],'completed',state.get('stop_reason'))
            self.assertEqual(len(runner.calls),6)
            self.assertFalse(state['model_pairs'])
            self.assertFalse(state['normal_mic_amplification_demonstrated'])
            self.assertTrue(state['functional_hearing_accepted'])

    def test_proxy_hearing_cannot_pass_speech_acceptance(self):
        with self.work() as d:
            base=Path(d);manifest,scene=setup(base);runner=Runner()
            def answer(prompt):return 'SPEECH' if 'RUN固定' in prompt else 'START' if 'START' in prompt else 'P1'
            with contextlib.redirect_stdout(io.StringIO()):
                state=room.run_room(base,ask=answer,runner=runner,validator=lambda _: (manifest,scene))
            self.assertEqual(state['status'],'stopped')
            self.assertFalse(state['normal_mic_amplification_demonstrated'])
            self.assertEqual(state['trials'][-1]['hearing_evidence_kind'],'software_proxy')


if __name__=='__main__':unittest.main()
