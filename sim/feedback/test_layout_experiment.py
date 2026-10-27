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


def repair_claim(candidate):
    return dict(capture_manifest_sha256=x.REPAIRED_CAPTURE_MANIFEST,capture_set_sha256=x.REPAIRED_CAPTURE_SET,
        wire_state='repaired',model_sha256=candidate['model_sha256'],coefficients_sha256=candidate['coefficients_sha256'],
        b_commit=candidate['b_commit'],basis_ref='SYNTHETIC SOFTWARE FIXTURE ONLY; not an actual B qualification')


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
        talker_to_microphone_cm=25,listener_position='synthetic position',microphone_preamp_gain='fixed marker',
        speaker_volume_knob='fixed marker',fixed_speech_source='synthetic source only',recorder_gain='fixed marker',agc_disabled=True)
    c['wire_repair_binding']=repair_claim(c)
    return path,c,scene


class Runner:
    def __init__(self,fail=None): self.calls=[];self.requests=[];self.fail=fail
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
        if 'human' in path.stem:target*=getattr(self,'human_scale',1)
        if 'human-input-original' in path.stem and self.fail in ('original_peak','original_clipped','original_bad_restore','original_clipped_bad_restore','original_clipped_bad_schedule'):
            amplitude=1.2 if self.fail in ('original_clipped','original_clipped_bad_restore','original_clipped_bad_schedule') else .7
            target=np.clip(np.rint(amplitude*2**23*np.sin(2*np.pi*700*t)),-2**23,2**23-1).astype(np.int64)
        if 'human-input-original' in path.stem and self.fail=='original_flat':target.fill(round(.3*2**23))
        if self.fail=='precheck_peak' and 'mic-precheck' in path.stem:
            target.fill(round(10**(-4.2/20)*2**23))
        if self.fail=='human_peak' and 'mic-precheck-human' in path.stem:
            target.fill(round(.6*2**23))
        if len(source)>1 and not (self.fail=='positive_missing' and 'positive' in path.stem):
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
        if self.fail=='original_clipped_bad_schedule' and 'human-input-original' in path.stem:m['source_end_frame_exclusive']-=1
        if self.fail in ('original_bad_restore','original_clipped_bad_restore') and 'human-input-original' in path.stem:status['recovery_ok']=False
        trigger=self.fail and 'mic-precheck' not in path.stem and ('response-zero' in path.stem or 'runtime-scan-zero' in path.stem)
        if trigger:
            if self.fail=='protection':m.update(early_stop=True,stop_reason='guard',clip_counts_raw=[65536,0,0],residual_saturations=1)
            elif self.fail=='source_time':m['source_end_frame_exclusive']-=1
            elif self.fail=='drop':m['dropped_frames']=1
            elif self.fail=='identity':m['coefficients_sha256']='f'*64
            elif self.fail=='cleanup':status['recovery_ok']=False
            elif self.fail=='save':status['save_error']='injected write failure'
            elif self.fail=='clip':raw[-1,1]=2**23-1
        candidate_guard=self.fail=='candidate_protection' and 'human-candidate-matched' in path.stem
        if candidate_guard:m.update(early_stop=True,stop_reason='guard',clip_counts_raw=[65536,0,0],residual_saturations=1)
        np.savez_compressed(path,reference=raw[:,0]/2**23,microphone=raw[:,1]/2**23,
            prediction_pcm=raw[:,2],residual_pcm=raw[:,3],coefficients_q20=q,source_pcm16=source,
            sample_rate_hz=x.RATE,metadata_json=json.dumps(m))
        path.with_suffix('.status.json').write_text(json.dumps(status),encoding='utf8')
        self.calls.append(path.stem)
        self.requests.append(dict(file=path.stem,direct_only=kw['direct_only'],zero_coeff=kw['zero_coeff'],
            source_zero=not bool(np.any(source)),seconds=kw['seconds']))
        if candidate_guard:raise RuntimeError('synthetic candidate guard; stopped before return')
        if trigger and self.fail=='protection': raise RuntimeError('guard; stopped before returning')
        return m


class ReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from assemble_experiment import assemble_layout
        (ROOT/'tmp').mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='success-reproduction-')
        cls.prepared=Path(cls.temp.name)/'prepared'
        assemble_layout(cls.prepared,'254b8e9',baseline_first=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def work(self):return tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='success-case-')
    def execute(self,base,failure=None,verdict='AMPLIFIED_CLEAR',path='TONE_HEARD',cancel=None):
        from sprint_selftest import SoftwareContinuousRunner
        runner=Runner(failure);runner.human_scale=20;events=[]
        class Record:
            def __call__(self,*args,**kwargs):events.append(Path(args[0]).stem);return runner(*args,**kwargs)
        manifest=dict(hashes={'audio_replay.bit':x.BIT,'audio_replay.hwh':x.HWH},coefficients_sha256=x.ZERO)
        live=SoftwareContinuousRunner(manifest,base)
        class Live:
            def __call__(self,*args,**kwargs):events.append('LIVE_HUMAN_60');return live(*args,**kwargs)
        def answer(prompt):
            if cancel and cancel in prompt:return 'CANCEL'
            if 'REPRO_READY|' in prompt:return 'REPRO_READY|synthetic-talker|synthetic phrase|SAME'
            if 'DISTANCE|' in prompt:return 'DISTANCE|20'
            if 'INPUT_RESPONDS /' in prompt:return 'INPUT_RESPONDS'
            if 'SOURCES_STOPPED' in prompt:return 'SOURCES_STOPPED'
            if 'TONE_HEARD /' in prompt:return path
            if 'MIC_READY' in prompt:return 'MIC_READY'
            if 'START' in prompt:return 'START'
            if 'HEARD /' in prompt:return 'HEARD'
            if 'AMPLIFIED_CLEAR' in prompt:return verdict
            if 'CLEAR_THROUGHOUT /' in prompt:return 'CLEAR_THROUGHOUT'
            if 'IMPROVED /' in prompt:return 'IMPROVED'
            if 'COMPARABLE /' in prompt:return 'COMPARABLE'
            return 'synthetic report only'
        with contextlib.redirect_stdout(io.StringIO()):result=x.run(base,ask=answer,runner=Record(),live_runner=Live())
        return result,runner,live,events
    def prepare(self,base):shutil.copytree(self.prepared,base,dirs_exist_ok=True)
    def test_success_is_zero_baseline_first_then_human_60_then_same_gain_candidate(self):
        with self.work() as d:
            base=Path(d);self.prepare(base);s,r,live,events=self.execute(base)
            self.assertEqual(s['status'],'completed',s.get('stop_reason'))
            self.assertEqual(s['baseline_result']['usable'],'supported')
            self.assertEqual(s['baseline_result']['reproduction'],'recorded_settings_reproduced')
            self.assertEqual(s['candidate_result']['improvement'],'qualitative_improvement_reported')
            self.assertEqual(len(s['baseline_result']['repeats']),2)
            ons=[t for t in s['trials'] if t['role']=='human-baseline-on']
            self.assertTrue(all(t['zero_coeff'] and t['requested_seconds']==9.5 and t['actual_talker_distance_cm']==5 for t in ons))
            self.assertLess(events.index('LIVE_HUMAN_60'),next(i for i,e in enumerate(events) if 'human-candidate' in e))
            self.assertTrue(s['human_continuous']['report']['driver_status']['zero_coeff'])
            self.assertEqual(len(live.calls),1)
            report=x.review(next(base.rglob('return-results.zip')),base/'intake.json')
            self.assertEqual(report['raw_quality_control']['issues'],[],report)
            self.assertEqual(report['baseline_result'],s['baseline_result'])
            self.assertEqual(report['candidate_result'],s['candidate_result'])
            with zipfile.ZipFile(next(base.rglob('return-results.zip'))) as z:
                self.assertFalse(any('human' in n and n.endswith('.npz') for n in z.namelist()))
            self.assertFalse(report['field_effect_claims_allowed'])
            with zipfile.ZipFile(next(base.rglob('return-results.zip'))) as z:files={n:z.read(n) for n in z.namelist()}
            forged=json.loads(files['summary.json']);forged['baseline_result']['usable']='not_supported'
            files['summary.json']=json.dumps(forged).encode('utf8')
            manifest=json.loads(files['return-manifest.json']);manifest['hashes']['summary.json']=hashlib.sha256(files['summary.json']).hexdigest()
            files['return-manifest.json']=json.dumps(manifest).encode('utf8')
            altered=base/'altered.zip'
            with zipfile.ZipFile(altered,'w') as z:
                for name,data in files.items():z.writestr(name,data)
            rejected=x.review(altered,base/'rejected.json')
            self.assertEqual(rejected['raw_quality_control']['status'],'discrepancies')
            self.assertEqual(rejected['baseline_result']['usable'],'unknown')
    def test_missing_candidate_does_not_block_baseline_or_human_use(self):
        with self.work() as d:
            base=Path(d);self.prepare(base);(base/'candidate-unbound.json').unlink()
            s,r,live,events=self.execute(base)
            self.assertEqual(s['baseline_result']['usable'],'supported',s.get('stop_reason'))
            self.assertEqual(s['candidate_result']['improvement'],'not_tested')
            self.assertTrue(s['candidate_result']['unavailable_reasons'])
            self.assertEqual(len(live.calls),1)
            self.assertFalse(any('human-candidate' in e for e in events))
    def test_original_peak_refusal_allows_only_one_distance_variant(self):
        for fault in ('original_peak','original_clipped'):
            with self.subTest(fault=fault),self.work() as d:
                base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,failure=fault)
                self.assertEqual(s['baseline_result']['usable'],'supported',s.get('stop_reason'))
                self.assertEqual(s['baseline_result']['reproduction'],'changed_distance_usable')
                self.assertTrue(s['original_input_refused'])
                self.assertTrue(all(t['actual_talker_distance_cm']==20 for t in s['trials'] if t['role']=='human-baseline-on'))
                self.assertEqual(sum('DISTANCE|' in p['prompt'] for p in s['prompt_log']),1)
    def test_stuck_input_and_unverified_recovery_do_not_enter_distance_or_closed_loop(self):
        for fault in ('original_flat','original_bad_restore','original_clipped_bad_restore','original_clipped_bad_schedule'):
            with self.subTest(fault=fault),self.work() as d:
                base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,failure=fault)
                self.assertEqual(s['status'],'stopped');self.assertFalse(live.calls)
                self.assertFalse(any('human-baseline-on' in e for e in events))
                self.assertFalse(any('DISTANCE|' in p['prompt'] for p in s['prompt_log']))
    def test_unknown_tone_estimate_does_not_erase_confirmed_io_baseline(self):
        with self.work() as d:
            base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,failure='positive_missing')
            self.assertFalse(s['path_pre']['relative']['passed'])
            self.assertTrue(s['path_pre']['confirmed'])
            self.assertEqual(s['baseline_result']['usable'],'supported',s.get('stop_reason'))
            self.assertIsNone(s['candidate_result']['tone_transfer_drift_db'])
    def test_output_route_unknown_stops_before_any_closed_baseline(self):
        for value in ('NOT_HEARD','UNKNOWN'):
            with self.subTest(value=value),self.work() as d:
                base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,path=value)
                self.assertEqual(s['status'],'stopped')
                self.assertFalse(any('human-baseline-on' in e for e in events))
                self.assertEqual(s['baseline_result']['usable'],'unknown')
    def test_real_action_cancellation_never_generates_listener_success(self):
        for prompt in ('REPRO_READY|','SOURCES_STOPPED'):
            with self.subTest(prompt=prompt),self.work() as d:
                base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,cancel=prompt)
                self.assertEqual(s['status'],'stopped');self.assertFalse(s['baseline_repeats'])
                self.assertFalse(live.calls);self.assertFalse(any('human-baseline-on' in e for e in events))
    def test_candidate_protection_preserves_previously_supported_baseline(self):
        with self.work() as d:
            base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,failure='candidate_protection')
            self.assertEqual(s['status'],'stopped')
            self.assertEqual(s['baseline_result']['usable'],'supported')
            self.assertEqual(s['candidate_result']['improvement'],'execution_failed_effect_unknown')
            self.assertFalse(s.get('path_post'))
    def test_two_negative_baseline_reports_preserve_history_and_do_not_extend(self):
        with self.work() as d:
            base=Path(d);self.prepare(base);s,r,live,events=self.execute(base,verdict='CLEAR_NO_IMPROVEMENT')
            self.assertEqual(s['baseline_result']['usable'],'not_supported')
            self.assertEqual(len(s['baseline_repeats']),2);self.assertFalse(live.calls)
            self.assertEqual(len(s['historical_listener_feedback']),2)
            self.assertFalse(any('human-candidate' in e for e in events))


class RelativePositiveTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='relative-positive-')
        self.base=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def captures(self,amplitude=.008,ambient=0.,seed=13,louder_noise=1.):
        n=int(1.02*x.RATE);first=n-16384;t=np.arange(first,n)/x.RATE
        rng=np.random.default_rng(seed);tone=np.sin(2*np.pi*1000*t)
        quiet=.03*rng.normal(size=len(t))+ambient*tone
        active=.03*louder_noise*rng.normal(size=len(t))+(ambient+amplitude)*tone
        source=x.sources(None)[0];ref=np.zeros(n);ref[:len(source)]=source.astype(float)/32768
        paths=[]
        for name,mic,reference in (('quiet',quiet,np.zeros(len(t))),('active',active,ref[first:])):
            meta=dict(first_frame=first,completed_frames=n,frames=n-first,
                source_schedule_verified=True,source_end_frame_exclusive=len(source) if name=='active' else 1)
            path=self.base/(name+'.npz')
            np.savez_compressed(path,microphone=mic,reference=reference,metadata_json=json.dumps(meta))
            paths.append(path)
        return paths
    def test_narrow_tone_below_broadband_noise_is_detected_without_dominance(self):
        quiet,active=self.captures()
        result=x.relative_positive_control(active,quiet)
        self.assertTrue(result['passed'],result)
        old=x.gate_metrics(active,x.positive_background(quiet)['rms_dbfs'])
        self.assertFalse(old['passed']);self.assertLess(result['tonal_fraction'],.8)
        self.assertLess(result['rms_dbfs']-result['background_rms_dbfs'],6.)
        self.assertEqual((result['first_frame'],result['end_frame'],result['frames']),(33420,48340,14920))
        delta=result['detection_contrast_db']
        self.assertAlmostEqual(result['signal_snr_estimate_db'],10*np.log10(10**(delta/10)-1),places=8)
    def test_noise_only_stationary_tone_and_broadband_level_change_do_not_pass(self):
        for options in ([dict(amplitude=0.,seed=k) for k in range(16)]+
                        [dict(amplitude=0.,ambient=.15),dict(amplitude=0.,louder_noise=5.)]):
            with self.subTest(options=options):
                quiet,active=self.captures(**options)
                result=x.relative_positive_control(active,quiet)
                self.assertFalse(result['passed'],result)
    def test_missing_reference_bad_schedule_and_missing_frames_are_rejected(self):
        for fault in ('reference','schedule','drop','short'):
            with self.subTest(fault=fault):
                quiet,active=self.captures()
                with np.load(active,allow_pickle=False) as z:data={k:z[k] for k in z.files}
                m=json.loads(str(data['metadata_json'].item()))
                if fault=='reference':data['reference']=np.zeros_like(data['reference'])
                elif fault=='schedule':m['source_end_frame_exclusive']-=1
                elif fault=='drop':m['dropped_frames']=1
                else:m['first_frame']=m['completed_frames']-10
                data['metadata_json']=json.dumps(m);np.savez_compressed(active,**data)
                self.assertFalse(x.relative_positive_control(active,quiet)['passed'])
    def test_post_control_uses_tone_transfer_and_rejects_large_drift(self):
        quiet,active=self.captures(amplitude=.008)
        before=x.relative_positive_control(active,quiet);self.assertTrue(before['passed'])
        quiet,active=self.captures(amplitude=.032)
        after=x.relative_positive_control(active,quiet,before)
        self.assertFalse(after['passed']);self.assertGreater(after['drift_db'],5.)
        self.assertIn('positive_transfer_drift_exceeds_5_db',after['reasons'])


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'tmp').mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='layout-tests-')
        cls.prepared=Path(cls.temp.name)/'prepared'
        from assemble_experiment import assemble_layout
        assemble_layout(cls.prepared)
        cls.runtime=Path(cls.temp.name)/'runtime'
        assemble_layout(cls.runtime,'b6bcfb2')
        cls.pending_runtime=Path(cls.temp.name)/'pending-runtime'
        shutil.copytree(cls.runtime,cls.pending_runtime)
        # Withdrawn source identity is an explicit negative control; shipped candidate is real B.
        cp=cls.pending_runtime/'candidate-input.json';c=json.loads(cp.read_text(encoding='utf8'))
        c.update(b_commit=x.OBSOLETE_B_COMMIT,wire_repair_binding=None)
        cp.write_text(json.dumps(c),encoding='utf8')
        mp=cls.pending_runtime/'layout-manifest.json';m=json.loads(mp.read_text(encoding='utf8'))
        m['hashes']['candidate-input.json']=x.sha(cp)
        mp.write_text(json.dumps(m),encoding='utf8')
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
        runner.prompts=[]
        def answer(prompt):
            runner.prompts.append(prompt)
            if 'FIELD_READY' in prompt:return 'FIELD_READY|25|synthetic.wav|5 of 15|25 cm, speaker to mic'
            if 'MIC_READY' in prompt:return 'MIC_READY'
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
            self.assertIn('B:model_file_missing',state['stop_reason'])
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
            self.assertEqual(len(r.calls),28)
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
                self.assertEqual(len(r.calls),8)
                self.assertFalse(any('human' in v for v in r.calls))
                self.assertTrue(s['inventory']);self.assertTrue(next(base.rglob('return-results.zip')).is_file())
                if failure=='protection':
                    row=s['trials'][-1];self.assertTrue(row['analysis']['event_flags']['protection'])
                    self.assertNotEqual(row['analysis']['category'],'observed_instability')
    def test_cancel_empty_and_invalid_start_never_run_human(self):
        for token in ('CANCEL','','MAYBE'):
            with self.subTest(token=token),self.work() as d:
                base=Path(d);self.bound(base);r=Runner();s=self.execute(base,r,start=token)
                self.assertEqual(s['status'],'stopped');self.assertEqual(len(r.calls),23)
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
    def test_withdrawn_B_source_identity_never_qualifies_for_repaired_wire_state(self):
        with self.work() as d:
            base=Path(d)/'actual'
            shutil.copytree(self.pending_runtime,base)
            report=json.loads((base/'candidate-compatibility.json').read_text(encoding='utf8'))
            self.assertTrue(report['identity_and_driver_compatibility'])
            self.assertEqual(report['model']['q20_sha256'],'6118e85df7d9765bd5ae93fc204a32301135666b188bcc0fcf61e1447f6e8927')
            self.assertEqual(report['serial_cycles'],1539)
            state=x.check(base);self.assertFalse(state['ready'])
            self.assertNotIn('B:model_file_missing',state['missing'])
            self.assertNotIn('B:Q20_hash',state['missing'])
            self.assertIn('B:pre_repair_candidate_not_qualified',state['missing'])
            r=Runner();result=self.execute(base,r)
            self.assertEqual(result['status'],'stopped');self.assertFalse(r.calls)
            self.assertFalse((base/'model.json').exists())

    def test_runtime_scan_does_not_require_injection_or_optional_recordings(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True)
            r=Runner();s=self.execute(base,r)
            self.assertEqual(s['status'],'completed',s.get('stop_reason'))
            self.assertEqual(s['grades']['measurement'],'valid_runtime_pairs_available')
            self.assertEqual(s['grades']['listener_effect'],'failed')
            self.assertEqual(s['listener_measurement']['status'],'not_tested')
            self.assertEqual(len(r.calls),38)
            rows=[row for row in s['trials'] if row['role']=='runtime-scan']
            self.assertEqual(len(rows),12)
            self.assertEqual(sorted({row['gain_db_requested'] for row in rows}),[-14,-12,-10,-8,-6])
            self.assertTrue(all(row['source_frames']==1 for row in rows))
            self.assertEqual(len(s['runtime_pairs']),6)
            self.assertTrue(all(pair['configuration_valid'] for pair in s['runtime_pairs']))
            self.assertEqual(s['signal_noise_conditions']['frequency_estimation'],'not_tested')
            self.assertIsNone(s['asg_db'])
            report=x.review(next(base.rglob('return-results.zip')),base/'intake.json')
            self.assertEqual(report['raw_quality_control']['status'],'completed',report)
            self.assertEqual(report['runtime_pairs'],s['runtime_pairs'])
            self.assertEqual(report['scan_summary']['zero']['acoustic_boundary'],'unknown')
            self.assertEqual([row['mode'] for row in report['human_switch']['trials']],['zero','matched'])

    def test_relative_positive_failure_stops_before_scan_and_is_recomputed_on_intake(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);runner=Runner('positive_missing')
            result=self.execute(base,runner)
            self.assertEqual(result['status'],'stopped');self.assertEqual(len(runner.calls),4)
            self.assertIn('positive_tone_below_relative_floor',result['stop_reason'])
            self.assertFalse(any('runtime-scan' in name or 'human' in name for name in runner.calls))
            report=x.review(next(base.rglob('return-results.zip')),base/'intake.json')
            self.assertFalse(report['positive_control']['passed'])
            self.assertEqual(report['raw_quality_control']['status'],'completed',report)
            self.assertFalse(report['runtime_pairs']);self.assertIsNone(report['asg_db'])

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
                self.assertEqual(s['status'],'stopped');self.assertEqual(len(r.calls),6)
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

    def test_absolute_peak_limit_is_strict_and_includes_constant_ADC_offset(self):
        with self.work() as d:
            path=Path(d)/'peak.npz';limit=10**(-6/20)
            for amplitude,passed in ((.5,True),(limit,False),(.51,False),(10**(-4.2/20),False)):
                with self.subTest(amplitude=amplitude):
                    np.savez_compressed(path,microphone=np.full(100,amplitude),
                        metadata_json=json.dumps(dict(first_frame=0,completed_frames=100,frames=100)))
                    value=x.microphone_headroom(path,True)
                    self.assertEqual(value['passed'],passed)
                    self.assertAlmostEqual(value['peak_dbfs'],20*np.log10(amplitude))
            np.savez_compressed(path,microphone=np.full(100,.1),
                metadata_json=json.dumps(dict(first_frame=50,completed_frames=150,frames=100)))
            self.assertFalse(x.microphone_headroom(path,True)['passed'])
            self.assertTrue(x.microphone_headroom(path,False)['passed'])

    def test_high_precheck_peak_stops_before_first_tone_and_is_not_protection(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);r=Runner('precheck_peak')
            s=self.execute(base,r)
            self.assertEqual(s['status'],'stopped');self.assertEqual(len(r.calls),1)
            self.assertTrue(r.requests[0]['direct_only']);self.assertTrue(r.requests[0]['source_zero'])
            row=s['trials'][0];self.assertFalse(row['microphone_headroom']['passed'])
            self.assertAlmostEqual(row['microphone_headroom']['peak_dbfs'],-4.2,places=5)
            self.assertTrue(row['analysis']['evaluation_metadata']['verification']['bit_exact'])
            self.assertFalse(row['analysis']['event_flags']['protection'])
            report=x.review(next(base.rglob('return-results.zip')),base/'intake.json')
            self.assertEqual(report['raw_quality_control']['status'],'completed')

    def test_human_input_peak_failure_keeps_prior_runtime_data_but_blocks_formal_voice(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);r=Runner('human_peak')
            s=self.execute(base,r)
            self.assertEqual(s['status'],'stopped');self.assertEqual(len(r.calls),31)
            self.assertEqual(s['trials'][-1]['role'],'mic-precheck-human-zero')
            self.assertFalse(any(row['role']=='human-zero' for row in s['trials']))
            self.assertTrue(any(pair['configuration_valid'] for pair in s['runtime_pairs']))
            self.assertEqual(s['listener_measurement']['status'],'not_tested')

    def test_every_main_step_has_zero_output_full_capture_precheck_and_no_WAV_prompt(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);r=Runner()
            s=self.execute(base,r)
            self.assertEqual(s['status'],'completed',s.get('stop_reason'))
            for pre,main in zip(r.requests[::2],r.requests[1::2]):
                self.assertIn('mic-precheck',pre['file'])
                self.assertTrue(pre['direct_only'] and pre['zero_coeff'] and pre['source_zero'])
                self.assertEqual(pre['seconds'],.3)
                self.assertNotIn('mic-precheck',main['file'])
            self.assertTrue(all(row['microphone_headroom']['full_capture'] for row in s['trials'] if row['is_input_precheck']))
            self.assertEqual(s['human_switch']['talker_to_microphone_cm'],25)
            self.assertEqual(s['listener_measurement']['status'],'not_tested')
            self.assertTrue(s['listener_measurement']['quantitative_disabled'])
            self.assertFalse(any('四WAV' in prompt for prompt in r.prompts))

    def test_assembly_rejects_wrong_capture_identity_despite_matching_coefficients(self):
        from unittest.mock import patch
        from assemble_experiment import assemble_layout
        original=subprocess.check_output
        def changed(command,*args,**kwargs):
            raw=original(command,*args,**kwargs)
            if command[:2]==['git','show'] and command[2].endswith('rewired-candidate-2026-10-26/metrics.json'):
                data=json.loads(raw);data['data_identity'][0]['sha256']='0'*64
                return json.dumps(data).encode('utf8')
            return raw
        with self.work() as d:
            with patch('assemble_experiment.subprocess.check_output',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'six repaired A captures'):
                    assemble_layout(Path(d)/'wrong-capture','b6bcfb2')

    def test_repaired_capture_binding_mismatch_is_rejected_and_A_scene_is_exact(self):
        with self.work() as d:
            base=Path(d);path,c,scene=inputs(base)
            c['wire_repair_binding']['capture_set_sha256']='0'*64
            self.assertIn('B:wire_repair_binding:capture_set_sha256',x.prerequisites(c,scene,path))
            raw=json.loads((self.pending_runtime/'scene-input.json').read_text(encoding='utf8'))
            self.assertEqual(raw['talker_to_microphone_cm'],25)
            self.assertEqual(raw['a_allowed_gains_db'],[-14,-12,-10,-8,-6])
            self.assertIsInstance(raw['agc_disabled'],str)
            self.assertTrue(raw['agc_disabled'].startswith('unknown'))
            original_path=self.pending_runtime/'a-scene-input-original.json'
            self.assertEqual(original_path.read_bytes(),subprocess.check_output(['git','show',x.SCENE_COMMIT+':report/verification/audio-replay/scene-input-2026-10-26.json'],cwd=ROOT))
            original=json.loads(original_path.read_text(encoding='utf8'))
            self.assertEqual(raw['fixture_id'],x.FIXTURE)
            self.assertEqual(raw['fixture_provenance']['original_scene_fixture'],original['fixture_id'])
            self.assertEqual({k:v for k,v in raw.items() if k not in ('fixture_id','fixture_provenance')},
                {k:v for k,v in original.items() if k!='fixture_id'})
            for name in ('field-config','live-round','mic-fault-impact','usable-point'):
                self.assertIsInstance(json.loads((self.pending_runtime/('a-'+name+'-original.json')).read_text(encoding='utf8')),dict)

    def test_withdrawn_5cm_distance_cannot_be_reactivated_by_field_ready(self):
        with self.work() as d:
            base=Path(d);shutil.copytree(self.runtime,base,dirs_exist_ok=True);r=Runner()
            with contextlib.redirect_stdout(io.StringIO()):
                state=x.run(base,ask=lambda _: 'FIELD_READY|5|synthetic.wav|5 of 15|25 cm',runner=r)
            self.assertEqual(state['status'],'stopped');self.assertFalse(r.calls)
            self.assertIn('talker_distance_15_to_30cm_after_repair',state['stop_reason'])
            self.assertFalse((base/'model.json').exists())


if __name__=='__main__':unittest.main()
