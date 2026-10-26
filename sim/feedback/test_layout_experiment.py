"""Synthetic execution controls plus exact B-asset compatibility; no board."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
sys.path.insert(0,str(ROOT/'scripts'))
import layout_experiment as x
from closed_tools import gain_pcm, rounded_shift
from replay_tools import verify_replay


def inputs(base):
    q=np.zeros(512,dtype=np.int64);q[184]=32
    model=dict(taps=512,lag_first=1,coefficient_format='signed24_fraction20',training_source='board',
        fixture_id=x.FIXTURE,hp_volume=40,sample_rate_hz=x.RATE,bias=0,
        coefficients_q20=q.tolist(),coefficients=(q/2**20).tolist())
    path=base/'candidate-model.json';path.write_text(json.dumps(model),encoding='utf8')
    c=x.template();c.update(b_commit='b'*40,model_sha256=x.sha(path),coefficients_sha256=x.qhash(q),
        deployment_evidence='synthetic only',original_timeline_holdout='synthetic unshifted holdout',
        diagnostic_alignment='none, original trial coordinates',input_manifest_sha256='c'*64,
        gain_db=-14.,b_allowed_gains_db=[-14.],injection_rms_dbfs=-30.,b_injection_range_dbfs=[-30.,-24.],
        gain_and_injection_basis='test fixture; no site authorisation',
        bands=[dict(low_hz=300,high_hz=1000,minimum_signal_snr_db=0.,basis='synthetic test'),
               dict(low_hz=1000,high_hz=3000,minimum_signal_snr_db=100.,basis='deliberately invalid band')],
        prediction_and_failure_actions='test only, no acoustic prediction')
    scene=x.scene_template();scene.update(verified_by_A=True,plate_and_cotton_unchanged=True,control_and_cue_approved_by_A=True,
        a_allowed_gains_db=[-14.],a_injection_range_dbfs=[-30.,-20.],a_limits_basis='test fixture only',
        talker_to_microphone_cm=10,listener_position='synthetic position',microphone_preamp_gain='fixed marker',
        speaker_volume_knob='fixed marker',fixed_speech_source='synthetic source only',recorder_gain='fixed marker',agc_disabled=True)
    return path,c,scene


class Runner:
    def __init__(self,fail=None): self.calls=[];self.fail=fail
    def __call__(self,path,fixture,model,source,**kw):
        if not kw['before_start'](): raise RuntimeError('operator_cancel')
        n=int(kw['seconds']*x.RATE);first=max(0,n-16384)
        q=np.asarray(json.loads(Path(model).read_text(encoding='utf8'))['coefficients_q20'],dtype=np.int64)
        if kw['zero_coeff']: q[:]=0
        gain=0 if kw['direct_only'] else int(np.floor(4096*10**(kw['gain_db']/20)+.5))
        ref=np.zeros(n,dtype=np.int64);ref[:len(source)]=source.astype(np.int64)*256
        t=np.arange(n)/x.RATE
        # Known algebraic signal: quiet is low noise, direct tone is delayed input.
        target=np.rint(200*(np.sin(2*np.pi*700*t)+np.sin(2*np.pi*1500*t))).astype(np.int64)
        if len(source)>1:
            count=min(len(source),n-125)
            target[125:125+count]+=source[:count].astype(np.int64)*128
        ref[2:]+=gain_pcm(target[:-2],gain)
        pred=rounded_shift(np.convolve(ref,np.r_[np.int64(0),q])[:n],20)
        mic=target+pred;raw=np.column_stack((ref,mic,pred,target))[first:]
        verify=verify_replay(raw,q,False,gain,source,first)
        m=dict(capture_id=path.stem,evidence_kind='synthetic_only',driver_evidence_version='a-replay-evidence-v2',
            first_frame=first,completed_frames=n,frames=n-first,sample_rate_hz=x.RATE,fixture_id=fixture,
            hp_volume=40,gain_q12=gain,bypass=False,zero_coeff=kw['zero_coeff'],bit_sha256=x.BIT,
            model_sha256=x.sha(model),coefficients_sha256=x.qhash(q),logical_taps=512,loaded_taps=512,
            coefficient_status=(512<<4)|10,source_frames=len(source),source_end_frame_exclusive=len(source),
            source_schedule_verified=True,source_pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest(),
            verification=verify,early_stop=False,stop_reason='completed',clip_counts_raw=[0,0,0],
            prediction_saturations=0,residual_saturations=0,gain_saturations=0,mix_saturations=0)
        status=dict(recovery_ok=True,cleanup_errors=[],salvage_errors=[],save_error=None)
        trigger=self.fail and ('response-zero' in path.stem or 'runtime-scan-zero' in path.stem)
        if trigger:
            if self.fail=='protection':m.update(early_stop=True,stop_reason='guard',clip_counts_raw=[65536,0,0],residual_saturations=1)
            elif self.fail=='source_time':m['source_end_frame_exclusive']-=1
            elif self.fail=='drop':m['dropped_frames']=1
            elif self.fail=='identity':m['coefficients_sha256']='f'*64
            elif self.fail=='cleanup':status['recovery_ok']=False
            elif self.fail=='save':status['save_error']='injected write failure'
            elif self.fail=='clip':raw[-1,1]=2**23-1
        np.savez_compressed(path,reference=raw[:,0]/2**23,microphone=raw[:,1]/2**23,
            prediction_pcm=raw[:,2],residual_pcm=raw[:,3],coefficients_q20=q,source_pcm16=source,
            sample_rate_hz=x.RATE,metadata_json=json.dumps(m))
        path.with_suffix('.status.json').write_text(json.dumps(status),encoding='utf8')
        self.calls.append(path.stem)
        if trigger and self.fail=='protection': raise RuntimeError('guard; stopped before returning')
        return m


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'tmp').mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='layout-tests-')
        cls.prepared=Path(cls.temp.name)/'prepared'
        from assemble_experiment import assemble_layout
        assemble_layout(cls.prepared)
        cls.runtime=Path(cls.temp.name)/'runtime'
        assemble_layout(cls.runtime,'8a02757')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def work(self):return tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='layout-case-')
    def prepared_copy(self,base):
        shutil.copytree(self.prepared,base,dirs_exist_ok=True)
    def bound(self,base):
        self.prepared_copy(base);path,c,scene=inputs(base)
        for name,data in (('b.json',c),('a.json',scene)):(base/name).write_text(json.dumps(data),encoding='utf8')
        self.assertTrue(x.bind(base,path,base/'b.json',base/'a.json')['ready'])
    def execute(self,base,runner,listener='NO_AMPLIFICATION',start='START',live_runner=None):
        def answer(prompt):
            if 'FIELD_READY' in prompt:return 'FIELD_READY'
            if 'READY' in prompt:return 'READY'
            if 'START' in prompt:return start
            if 'LISTENER继续' in prompt:return 'LISTENER'
            if 'HEARD /' in prompt:return 'HEARD'
            if 'DISTINGUISHABLE /' in prompt:return listener
            if 'IMPROVED /' in prompt:return 'SIMILAR'
            if '一次填写' in prompt:return 'synthetic only'
            return ''
        with contextlib.redirect_stdout(io.StringIO()):return x.run(base,answer,runner,live_runner)
    def test_pending_is_complete_missing_list_and_never_calls_board(self):
        with self.work() as d:
            base=Path(d);self.prepared_copy(base);r=Runner();state=self.execute(base,r)
            self.assertEqual(r.calls,[]);self.assertEqual(state['status'],'stopped')
            self.assertIn('B:model_file_missing',state['stop_reason']);self.assertIn('A:listener_position',state['stop_reason'])
            self.assertFalse((base/'model.json').exists())
    def test_binding_rejects_all_bad_identity_and_unsupported_ranges(self):
        with self.work() as d:
            base=Path(d);path,c,scene=inputs(base)
            self.assertEqual(x.prerequisites(c,scene,path),[])
            c.update(coefficients_sha256='a'*64,gain_db=-6,injection_rms_dbfs=-18,lag_first=2)
            scene['listener_position']='unknown'
            errors=x.prerequisites(c,scene,path)
            for expected in ('B:Q20_hash','B:gain_not_supported','A:gain_not_supported','B:injection_not_supported',
                             'A:injection_not_supported','B:incompatible:lag_first','A:unknown:listener_position'):
                self.assertIn(expected,errors)
    def test_low_snr_is_band_local_and_heard_is_not_amplification(self):
        with self.work() as d:
            base=Path(d);self.bound(base);r=Runner();s=self.execute(base,r)
            self.assertEqual(s['status'],'completed',s.get('stop_reason'))
            self.assertEqual(len(r.calls),14)
            self.assertEqual(s['grades']['listener_effect'],'failed')
            self.assertEqual(s['grades']['continuous_operation'],'not_tested')
            self.assertEqual(len(s['pairs']),2)
            for p in s['pairs']:
                self.assertTrue(p['configuration_valid'],p['reasons'])
                self.assertTrue(p['bands']['300-1000']['valid'])
                self.assertFalse(p['bands']['1000-3000']['valid'])
            report=x.review(next(base.rglob('return-results.zip')),base/'b-analysis.json')
            self.assertEqual(report['pairs'],s['pairs'])
            self.assertEqual(report['raw_quality_control']['status'],'completed')
            with zipfile.ZipFile(next(base.rglob('return-results.zip'))) as z:
                self.assertFalse(any('human' in n and n.endswith('.npz') or n.endswith('.wav') for n in z.namelist()))
                self.assertTrue(any('response' in n and n.endswith('.npz') for n in z.namelist()))
    def test_known_failures_stop_before_other_sound_and_keep_evidence(self):
        for failure in ('protection','source_time','drop','identity','cleanup','save','clip'):
            with self.subTest(failure=failure),self.work() as d:
                base=Path(d);self.bound(base);r=Runner(failure);s=self.execute(base,r)
                self.assertEqual(s['status'],'stopped')
                self.assertEqual(len(r.calls),4)
                self.assertFalse(any('human' in v for v in r.calls))
                self.assertTrue(s['inventory']);self.assertTrue(next(base.rglob('return-results.zip')).is_file())
                if failure=='protection':
                    row=s['trials'][-1];self.assertTrue(row['analysis']['event_flags']['protection'])
                    self.assertNotEqual(row['analysis']['category'],'observed_instability')
    def test_cancel_empty_and_invalid_start_never_run_human(self):
        for token in ('CANCEL','','MAYBE'):
            with self.subTest(token=token),self.work() as d:
                base=Path(d);self.bound(base);r=Runner();s=self.execute(base,r,start=token)
                self.assertEqual(s['status'],'stopped');self.assertEqual(len(r.calls),11)
    def test_stale_or_changed_frozen_payload_blocks_before_board(self):
        with self.work() as d:
            base=Path(d);self.bound(base)
            (base/'listener_metrics.py').write_text('changed',encoding='utf8')
            r=Runner();s=self.execute(base,r)
            self.assertFalse(r.calls);self.assertIn('package hash mismatch',s['stop_reason'])
    def test_notebook_saved_outputs_are_mutable_but_code_is_frozen(self):
        with self.work() as d:
            base=Path(d);self.bound(base);path=base/'layout.ipynb'
            nb=json.loads(path.read_text(encoding='utf8'));nb['cells'][1]['execution_count']=1
            nb['cells'][1]['outputs']=[dict(output_type='stream',name='stdout',text=['saved output'])]
            path.write_text(json.dumps(nb),encoding='utf8')
            self.assertTrue(x.check(base)['ready'])
            nb['cells'][1]['source'].append('print("changed")\n')
            path.write_text(json.dumps(nb),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'notebook code mismatch'):x.check(base)
    def test_continuous_review_reuses_explicit_bound_model(self):
        from sprint_selftest import SoftwareContinuousRunner
        with self.work() as d:
            base=Path(d);self.bound(base)
            data=x.check(base)['binding'];c=data['candidate']
            manifest=dict(hashes={'model.json':c['model_sha256'],'audio_replay.bit':x.BIT,'audio_replay.hwh':x.HWH},
                          coefficients_sha256=c['coefficients_sha256'])
            live=SoftwareContinuousRunner(manifest,base)
            s=self.execute(base,Runner(),listener='DISTINGUISHABLE',live_runner=live)
            self.assertEqual(s['grades']['continuous_operation'],'engineering_completed',s.get('continuous'))
            self.assertEqual(s['whole_run_acoustics'],'unknown')
            self.assertEqual(len(live.calls),1)
    def test_post_control_drift_rejects_pairs_without_erasing_other_facts(self):
        rows=[]
        for mode,q in (('zero',x.ZERO),('matched','a'*64)):
            rows.append(dict(role='response',repeat=1,mode=mode,coefficients_sha256=q,
                measurement_valid=True,spectrum=dict(first_frame=1,end_frame=2,frames=1),
                snr_bands={'a':dict(valid=True,signal_power=1)}))
        state=dict(trials=rows,positive_post=dict(passed=True,drift_db=2))
        self.assertFalse(x.result_pairs(state)[0]['configuration_valid'])
        self.assertEqual(len(state['trials']),2)
    def test_snr_definition_matches_analytic_truth(self):
        bands=[dict(low_hz=1,high_hz=2,minimum_signal_snr_db=0,basis='analytic')]
        out=x.snr_bands({'band_power':{'1-2':2}},{'band_power':{'1-2':1}},bands)
        self.assertEqual(out['1-2']['signal_snr_db'],0)
        self.assertTrue(out['1-2']['valid'])
    def test_positive_background_uses_the_same_global_window_as_tone(self):
        with self.work() as d:
            path=Path(d)/'quiet.npz';first=33420;end=49804
            samples=np.full(end-first,.25)
            samples[:14920]=np.tile([.001,-.001],7460)
            m=dict(first_frame=first,completed_frames=end)
            np.savez_compressed(path,microphone=samples,metadata_json=json.dumps(m))
            out=x.positive_background(path)
            self.assertEqual((out['first_frame'],out['end_frame'],out['frames']),(33420,48340,14920))
            self.assertAlmostEqual(out['rms_dbfs'],-60.,places=10)
            self.assertGreater(20*np.log10(np.std(samples)),-30)
    def test_actual_B_candidate_is_carried_and_only_A_field_facts_remain(self):
        with self.work() as d:
            base=Path(d)/'actual'
            shutil.copytree(self.runtime,base)
            report=json.loads((base/'candidate-compatibility.json').read_text(encoding='utf8'))
            self.assertTrue(report['identity_and_driver_compatibility'])
            self.assertEqual(report['model']['q20_sha256'],'e8757833a8c9f08e06c8a728dff1bbdc9bb8283ebdc10cbea0f54cbb18390961')
            self.assertEqual(report['serial_cycles'],1539)
            state=x.check(base);self.assertFalse(state['ready'])
            self.assertNotIn('B:model_file_missing',state['missing'])
            self.assertNotIn('B:Q20_hash',state['missing'])
            self.assertFalse(any(reason.startswith('B:') for reason in state['missing']),state['missing'])
            self.assertFalse((base/'model.json').exists())

    def test_runtime_scan_does_not_require_injection_or_optional_recordings(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True)
            r=Runner();s=self.execute(base,r)
            self.assertEqual(s['status'],'completed',s.get('stop_reason'))
            self.assertEqual(s['grades']['measurement'],'valid_runtime_pairs_available')
            self.assertEqual(s['grades']['listener_effect'],'failed')
            self.assertEqual(s['listener_measurement']['status'],'not_tested')
            self.assertEqual(len(r.calls),23)
            rows=[row for row in s['trials'] if row['role']=='runtime-scan']
            self.assertEqual(len(rows),16)
            self.assertEqual(sorted({row['gain_db_requested'] for row in rows}),list(range(-14,-7)))
            self.assertTrue(all(row['source_frames']==1 for row in rows))
            self.assertEqual(len(s['runtime_pairs']),8)
            self.assertTrue(all(pair['configuration_valid'] for pair in s['runtime_pairs']))
            self.assertEqual(s['signal_noise_conditions']['frequency_estimation'],'not_tested')
            self.assertIsNone(s['asg_db'])
            report=x.review(next(base.rglob('return-results.zip')),base/'intake.json')
            self.assertEqual(report['raw_quality_control']['status'],'completed',report)
            self.assertEqual(report['runtime_pairs'],s['runtime_pairs'])
            self.assertEqual(report['scan_summary']['zero']['acoustic_boundary'],'unknown')
            self.assertEqual([row['mode'] for row in report['human_switch']['trials']],['zero','matched'])

    def test_runtime_field_cancel_and_wrong_identity_never_activate_or_touch_board(self):
        for changed in (False,True):
            with self.subTest(changed=changed),self.work() as d:
                base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);r=Runner()
                if changed:
                    (base/'candidate-unbound.json').write_text('{}',encoding='utf8')
                with contextlib.redirect_stdout(io.StringIO()):
                    s=x.run(base,ask=lambda _: 'CANCEL',runner=r)
                self.assertEqual(s['status'],'stopped');self.assertFalse(r.calls)
                self.assertFalse((base/'model.json').exists())

    def test_runtime_protection_drop_and_failed_save_stop_all_later_sound(self):
        for failure in ('protection','drop','save'):
            with self.subTest(failure=failure),self.work() as d:
                base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);r=Runner(failure)
                s=self.execute(base,r)
                self.assertEqual(s['status'],'stopped');self.assertEqual(len(r.calls),3)
                self.assertFalse(any('human' in name for name in r.calls))
                self.assertTrue(next(base.rglob('return-results.zip')).is_file())
                self.assertIsNone(s['asg_db'])
                if failure=='protection':
                    row=s['trials'][-1];self.assertTrue(row['analysis']['event_flags']['protection'])
                    self.assertNotEqual(row['analysis']['category'],'observed_instability')

    def test_runtime_listener_success_keeps_continuous_engineering_separate_on_intake(self):
        from sprint_selftest import SoftwareContinuousRunner
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True)
            c=json.loads((base/'candidate-input.json').read_text(encoding='utf8'))
            manifest=dict(hashes={'model.json':c['model_sha256'],'audio_replay.bit':x.BIT,'audio_replay.hwh':x.HWH},
                coefficients_sha256=c['coefficients_sha256'])
            live=SoftwareContinuousRunner(manifest,base)
            s=self.execute(base,Runner(),listener='DISTINGUISHABLE',live_runner=live)
            self.assertEqual(s['status'],'completed',s.get('continuous'))
            self.assertEqual(s['grades']['continuous_operation'],'engineering_completed')
            report=x.review(next(base.rglob('return-results.zip')),base/'intake.json')
            self.assertEqual(report['raw_quality_control']['status'],'completed',report['raw_quality_control'])
            self.assertEqual(report['continuous']['acoustic_status'],'not_tested')
            self.assertIsNone(report['asg_db'])


if __name__=='__main__':unittest.main()
