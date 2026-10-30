"""Project sprint decisions, analytic levels, and real driver mock orchestration."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
import sprint_experiment as sprint
from evaluation import classify, sha
from model_comparison import qhash
from closed_tools import gain_pcm
from test_room_experiment import Runner as RoomRunner, setup, BIT
from test_evaluation import metadata, tone, FS


class Runner(RoomRunner):
    """Three stationary tones 14 dB above the old room fixture's level.

    This clears the independently frozen -37.8+6 dB floor; gain remains unity.
    """
    def __call__(self,path,fixture,model,source,**kw):
        result=super().__call__(path,fixture,model,source,**kw)
        if not kw['direct_only'] and not self.clip and not self.calls[-1].get('boosted'):
            with np.load(path,allow_pickle=False) as capture:
                data={k:np.array(capture[k]) for k in capture.files}
            mic=data['microphone']*5
            if np.max(abs(mic))<1:
                first=result['first_frame'];idx=np.arange(len(mic))+first
                injection=np.zeros(len(mic));mask=idx<len(source)
                injection[mask]=source[idx[mask]].astype(float)/32768
                data['reference']=(data['reference']-injection)*5+injection
                data['microphone']=mic;data['residual_pcm']=np.rint(mic*2**23).astype(np.int64)
                # Scaling after a rounded gain is equivalent only at unity.
                # Construct the fixture's real n-2 schedule at the requested Q12.
                data['reference'][2:]=injection[2:]+gain_pcm(data['residual_pcm'][:-2],result['gain_q12'])/2**23
                np.savez_compressed(path,**data)
        return result


class SprintTests(unittest.TestCase):
    def test_preflight_rejects_failure_stale_payload_and_missing_trial_fields(self):
        manifest=dict(source_commits={'C':'fixture'},a_assets=sprint.A_ASSETS,hashes={'model.json':'m','preflight.json':'p'})
        row=dict(seconds=1.02,source_frames=48828,transition_frames=2442,driver_input_ok=True,
                 capture_frames=16384,window_frames=14920,ok=True)
        valid=dict(all_ok=True,policy=sprint.POLICY,evidence_kind='software_fixture',
                   a_assets=sprint.A_ASSETS,
                   source_commits=manifest['source_commits'],payload_hashes={'model.json':'m'},
                   checks=dict(real_driver_rejects_equal_source_budget=True,continuous_workflow_passed=True),
                   trials=[dict(row) for _ in range(15)])
        sprint.validate_preflight(manifest,valid)
        for patch_value in ({'all_ok':False},{'payload_hashes':{'model.json':'stale'}},
                            {'source_commits':{'C':'old'}},{'a_assets':{'contract':'v2'}},{'assets':{}},{'trials':[]}):
            with self.assertRaisesRegex(ValueError,'PREFLIGHT_FAIL'):
                sprint.validate_preflight(manifest,dict(valid,**patch_value))
        for field,value in [('ok',False),('window_frames',0),('window_frames',20000),('seconds',float('nan'))]:
            bad=copy.deepcopy(valid);bad['trials'][0][field]=value
            with self.assertRaisesRegex(ValueError,'PREFLIGHT_FAIL'):
                sprint.validate_preflight(manifest,bad)
        for field in ('seconds','source_frames','transition_frames','capture_frames','window_frames','ok'):
            bad=copy.deepcopy(valid);del bad['trials'][0][field]
            with self.assertRaisesRegex(ValueError,'PREFLIGHT_FAIL'):
                sprint.validate_preflight(manifest,bad)

    def work(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=ROOT/'tmp')

    def test_interrupt_recovery_failure_and_early_stop_cannot_pass_a_stable_tail(self):
        for change in ({'error':'link lost'},{'recovery_ok':False},{'early_stop':True}):
            m=metadata();m.update(change)
            out=classify(m,tone(),FS)
            self.assertEqual(out['category'],'unknown')
            m['guard_tripped']=True
            self.assertEqual(classify(m,tone(),FS)['category'],'protection')
            self.assertEqual(classify(m,tone(60),FS)['category'],'observed_instability')

    def test_single_speech_peak_and_clipping_are_not_growth(self):
        x=tone();x[1000]=2**23-1
        out=classify(metadata(),x,FS)
        self.assertFalse(out['event_flags']['instability_growth'])
        self.assertNotEqual(out['category'],'observed_instability')

    def test_pair_only_bypass_may_change(self):
        a={k:'same' for k in sprint.PAIR_FIELDS}
        a.update(bypass=True,category='no_instability_observed_in_window',protection=False,
                 recovery_ok=True,gate_mic_over_ref_db=-10.,source_response={'valid':True},
                 measurement_kind='forced_source_response')
        b=dict(a,bypass=False)
        self.assertTrue(sprint.pair_check(a,b)['window_comparison_valid'])
        for field in sprint.PAIR_FIELDS:
            bad=dict(b);bad[field]='changed'
            self.assertFalse(sprint.pair_check(a,bad)['configuration_matches'],field)
        self.assertFalse(sprint.pair_check(a,dict(b,gate_mic_over_ref_db=-8.4))['window_comparison_valid'])
        self.assertFalse(sprint.pair_check(a,dict(b,protection=True))['window_comparison_valid'])
        known=dict(b,category='unknown',analysis={'reasons':['source_or_transition_overlap']})
        self.assertTrue(sprint.pair_check(a,known)['window_comparison_valid'])
        self.assertFalse(sprint.pair_check(a,dict(known,analysis={'reasons':['execution_interrupted']}))['window_comparison_valid'])
        self.assertFalse(sprint.pair_check(a,dict(known,source_response={'valid':False}))['window_comparison_valid'])

    def test_default_is_same_calibration_and_failure_does_not_start_a_bypass_trial(self):
        path=ROOT/'models/room_v1/calibrated_20261024.json'
        self.assertEqual(sha(path),sprint.DEFAULT_MODEL['file_sha256'])
        data=json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(qhash(data['coefficients_q20']),sprint.DEFAULT_MODEL['coefficients_sha256'])
        with self.work() as d:
            runner=Runner(drift_gate=3);state=self.execute(Path(d),runner)
            self.assertEqual(state['status'],'stopped')
            self.assertIn('path_gate_failed',state['stop_reason'])
            # gate, voice, listener-off, failed second gate; no listener-on or FIR.
            self.assertEqual(len(runner.calls),4)
            self.assertFalse(any(c['bypass'] for c in runner.calls))
            self.assertFalse(state['failure_action']['automatic_bypass'])

    def execute(self,base,runner,ready=True,observation='PROXY',continuous_factory=None,workflow='full',hearing='CLEAR'):
        setup(base)
        # A's mock emits all-zero coefficients; no borrowed golden detector.
        (base/'model.json').write_bytes((base/'models/candidate_512.json').read_bytes())
        (base/'eq.json').write_text('{"type":"identity"}')
        import shutil
        for name in ('audio_replay.bit','audio_replay.hwh'):
            shutil.copy2(ROOT/'board/audio_replay'/name,base/name)
        manifest=dict(source_commits={'C':'test'},workflow=workflow,coefficients_sha256=qhash(np.zeros(512,dtype=int)),
                      hashes={name:sha(base/name) for name in ('audio_replay.bit','audio_replay.hwh','model.json')})
        from sprint_selftest import SoftwareContinuousRunner
        continuous=(continuous_factory or SoftwareContinuousRunner)(manifest)
        def answer(prompt):
            if 'HUMAN_LIVE_AND_LISTENING' in prompt:return observation
            if 'READY' in prompt:return 'READY' if ready else 'CANCEL'
            if 'SAME_SCENE' in prompt:return 'SAME_SCENE'
            if 'SOURCE_OFF' in prompt:return 'SOURCE_OFF'
            if '一次填写' in prompt:return 'fixed test layout; software fixture only'
            if 'START' in prompt:return 'START'
            if 'CLEAR' in prompt:return hearing
            return ''
        with contextlib.redirect_stdout(io.StringIO()):
            return sprint.run_sprint(base,answer,runner,lambda _:manifest,continuous_runner=continuous)

    def test_complete_schedule_separates_continuous_engineering_from_acoustics(self):
        with self.work() as d:
            base=Path(d);runner=Runner();state=self.execute(base,runner)
            self.assertEqual(state['status'],'completed_with_unmeasured_requirements',state.get('stop_reason'))
            self.assertEqual(len(runner.calls),14)
            self.assertEqual(len(state['trials']),15)
            self.assertEqual(len(state['fir_pairs']),2)
            self.assertTrue(all(p['window_comparison_valid'] for p in state['fir_pairs']))
            self.assertEqual(state['checks']['continuous_60s']['status'],'passed')
            self.assertEqual(state['checks']['continuous_60s']['acoustic_status'],'not_tested')
            self.assertEqual(state['full_trial_stability'],'unknown')
            self.assertEqual(state['checks']['listener']['status'],'not_tested')
            self.assertEqual(state['checks']['real_voice']['status'],'not_tested')
            self.assertEqual(state['observation_kind'],'proxy')
            self.assertIsNone(state['asg_db'])
            for row in state['trials']:
                original=row['analysis']['original_metadata']
                self.assertEqual(row['frames'],16384)
                self.assertEqual(row['first_frame'],original['first_frame'])
                self.assertEqual(row['completed_frames'],original['frames_completed'] if row['role']=='continuous-60s' else original['completed_frames'])
                if row['role']=='path-gate':
                    self.assertEqual(row['gate_status'],'passed')
                    gate=row['path_gate']
                    self.assertEqual(gate['end_frame']-gate['first_frame'],14920)
                    self.assertEqual(row['analysis']['tail_analysis_window']['frames'],16384)
                if row['role'] in ('fir-off','fir-on'):
                    window=row['source_response']
                    self.assertEqual(row['source_frames'],122070)
                    self.assertEqual(window['frames'],14408)
                    self.assertEqual(window['first_frame'],row['first_frame']+512)
                    self.assertEqual(window['end_frame'],row['source_frames']-488)
                    self.assertTrue(window['valid'])
                    self.assertFalse(row['tail_valid'])
                    self.assertEqual(row['category'],'unknown')
            with zipfile.ZipFile(next(base.rglob('return-results.zip'))) as archive:
                self.assertFalse(any(n.endswith(('.npz','.wav','.bit','.hwh')) for n in archive.namelist()))
                self.assertIn('return-manifest.json',archive.namelist())

    def test_proxy_clear_cannot_pass_voice_but_explicit_human_fixture_can(self):
        for observation,expected in [('PROXY','not_tested'),('','not_tested'),('HUMAN_LIVE_AND_LISTENING','passed')]:
            with self.work() as d:
                state=self.execute(Path(d),Runner(),observation=observation)
                self.assertEqual(state['status'],'completed_with_unmeasured_requirements',state.get('stop_reason'))
                self.assertEqual(state['checks']['real_voice']['status'],expected)
                row=next(r for r in state['trials'] if r['role']=='real-voice')
                self.assertEqual(row['hearing_reported_code'],'CLEAR')
                self.assertEqual(row['hearing_code'],'CLEAR' if expected=='passed' else 'PROXY')

    def test_human_session_stops_before_any_hardware_for_proxy(self):
        with self.work() as d:
            runner=Runner();state=self.execute(Path(d),runner,workflow='human_only')
            self.assertEqual(state['status'],'stopped')
            self.assertFalse(runner.calls)
            self.assertIn('requires_live_speech_and_human_listening',state['stop_reason'])

    def test_human_session_has_only_five_trials_and_does_not_inherit_old_passes(self):
        with self.work() as d:
            runner=Runner();state=self.execute(Path(d),runner,workflow='human_only',observation='HUMAN_LIVE_AND_LISTENING')
            self.assertEqual(state['status'],'completed_with_unmeasured_requirements',state.get('stop_reason'))
            self.assertEqual([r['role'] for r in state['trials']],['path-gate','real-voice','listener-off','path-gate','listener-on'])
            self.assertEqual(len(runner.calls),5)
            self.assertEqual(state['checks']['real_voice']['status'],'passed')
            for name in ('fir_comparison','continuous_60s','listener','independent_reproduction'):
                self.assertEqual(state['checks'][name]['status'],'not_tested',name)

    def test_negative_human_outcome_is_failed_and_stops_at_voice(self):
        for hearing in ('DISTORTED','NO_AMPLIFICATION','HOWL'):
            with self.work() as d:
                state=self.execute(Path(d),Runner(),workflow='human_only',observation='HUMAN_LIVE_AND_LISTENING',hearing=hearing)
                self.assertEqual(state['status'],'stopped')
                self.assertEqual(len(state['trials']),2)
                self.assertEqual(state['checks']['real_voice']['status'],'failed')
                self.assertEqual(state['checks']['real_voice']['hearing_code'],hearing)

    def test_reduced_point_is_fixed_without_changing_direct_gate_or_thresholds(self):
        self.assertEqual(sprint.PLAN['gain_db'],-14.)
        self.assertEqual(sprint.PLAN['gain_q12'],int(np.floor(4096*10**(-14/20)+.5)))
        with self.work() as d:
            state=self.execute(Path(d),Runner())
            self.assertTrue(all(r['gain_q12']==(0 if r['role'] in ('path-gate','listener-off') else 817)
                                for r in state['trials']))
            self.assertEqual(state['checks']['path_gate']['status'],'passed')
            self.assertFalse(sprint.PLAN['automatic_gain_escalation'])

    def test_literal_gate_source_has_samples_at_1p02s_but_none_at_1p6s(self):
        # Use the unchanged gate function with actual source and ring geometry.
        source=sprint.sources()[1]
        with self.work() as d:
            for seconds,passed in ((1.02,True),(1.6,False)):
                count=int(seconds*sprint.RATE);first=count-16384
                indices=np.arange(first,count);signal=np.zeros(len(indices))
                mask=indices<len(source)
                signal[mask]=source[indices[mask]].astype(float)/32768
                path=Path(d)/('gate-'+str(seconds)+'.npz')
                np.savez_compressed(path,microphone=signal,reference=signal,
                    metadata_json=json.dumps(dict(first_frame=first,completed_frames=count,
                                                  source_end_frame_exclusive=len(source))))
                gate=sprint.gate_metrics(path,-37.8)
                self.assertEqual(gate['passed'],passed)
                if not passed:self.assertEqual(gate['reasons'],['gate_source_on_window_too_short'])

    def test_low_tone_fraction_stops_without_a_second_trial_and_keeps_reason(self):
        class Contaminated(Runner):
            def __call__(self,path,*args,**kw):
                result=super().__call__(path,*args,**kw)
                with np.load(path,allow_pickle=False) as capture:
                    data={k:np.array(capture[k]) for k in capture.files}
                indices=np.arange(result['first_frame'],result['completed_frames'])
                mic=data['microphone']+.2*np.sin(2*np.pi*700*indices/sprint.RATE)
                # Direct-only: residual equals mic; do not hide arithmetic errors.
                data['microphone']=mic
                data['residual_pcm']=np.rint(mic*2**23).astype(np.int64)
                np.savez_compressed(path,**data)
                return result
        with self.work() as d:
            runner=Contaminated();state=self.execute(Path(d),runner)
            self.assertEqual(len(runner.calls),1)
            self.assertEqual(state['status'],'stopped')
            self.assertIn('path_gate_failed:gate_tone_not_observed',state['stop_reason'])
            self.assertLess(state['trials'][0]['path_gate']['tonal_fraction'],.8)
            self.assertEqual(state['trials'][0]['frames'],16384)

    def test_source_on_comparison_does_not_overwrite_original_capture_extent(self):
        with self.work() as d:
            state=self.execute(Path(d),Runner())
            row=next(r for r in state['trials'] if r['role']=='fir-off')
            window=row['source_response']
            self.assertEqual(row['frames'],16384)
            self.assertEqual(row['first_frame'],row['analysis']['original_metadata']['first_frame'])
            self.assertGreater(window['first_frame'],row['first_frame'])
            self.assertLess(window['frames'],row['frames'])

    def test_quiet_tail_is_not_fixed_by_waiting_and_does_not_qualify_for_forced_response(self):
        # Independent absolute levels: -38 dBFS remains below -37.8+6 dB.
        from tail_metrics import tail_statistics
        for frames in (16384,32768):
            x=np.rint(2**23*np.sqrt(2)*10**(-38/20)*np.sin(np.arange(frames)*.2)).astype(np.int64)
            m=dict(first_frame=100000,completed_frames=100000+frames,frames=frames,
                source_end_frame_exclusive=90000,source_frames=90000,source_schedule_verified=True,
                external_source_off_verified=True,noise_floor_dbfs=-37.8)
            value=tail_statistics(x,x,m,sprint.RATE)
            self.assertFalse(value['tail_valid'])
            self.assertEqual(value['tail_reasons'],['tail_below_signal_floor'])

    def test_forced_response_rejects_quiet_unverified_mismatched_and_short_windows(self):
        from sprint_selftest import SoftwareRunner
        with self.work() as d:
            base=Path(d);setup(base)
            model=base/'models/candidate_512.json';source=sprint.comparison_source();path=base/'response.npz'
            runner=SoftwareRunner({'hashes':{'audio_replay.bit':BIT}})
            runner(path,sprint.PLAN['fixture_id'],model,source,direct_only=False,bypass=True,
                   gain_db=-14.,seconds=2.52,hp_volume=40,before_start=lambda:True)
            self.assertTrue(sprint.source_response(path,source,True)['valid'])
            self.assertEqual(sprint.source_response(path,source,False)['reasons'],['external_source_off_unverified'])
            self.assertEqual(sprint.source_response(path,source[:-1],True)['reasons'],['forcing_source_mismatch'])
            with np.load(path,allow_pickle=False) as capture:original={k:np.array(capture[k]) for k in capture.files}
            quiet=dict(original,microphone=original['microphone']*.01)
            np.savez_compressed(path,**quiet)
            self.assertEqual(sprint.source_response(path,source,True)['reasons'],['response_below_signal_floor'])
            short=dict(original);m=json.loads(str(short['metadata_json'].item()))
            m['source_schedule_verified']=False;short['metadata_json']=json.dumps(m)
            np.savez_compressed(path,**short)
            self.assertEqual(sprint.source_response(path,source,True)['reasons'],['forcing_schedule_unverified'])
            m['source_schedule_verified']=True;m['frames']=1000;m['first_frame']=m['completed_frames']-1000
            short['microphone']=original['microphone'][-1000:];short['metadata_json']=json.dumps(m)
            np.savez_compressed(path,**short)
            self.assertEqual(sprint.source_response(path,source,True)['reasons'],['response_window_too_short'])

    def test_reset_fir_matches_whole_record_on_the_same_valid_samples(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from audit_sprint import matched_boundary_control
        frames=np.arange(8192)
        u=.1*np.sin(.13*frames)
        mic=.01*(1+frames/8192)*np.sin(.17*frames)
        q=np.zeros(512);q[0]=.125;q[200]=-.25
        out=matched_boundary_control(({'reference':u,'microphone':mic},{}),q)
        self.assertEqual(out['matched_frames'],4096)
        self.assertEqual(out['reset_frames'],4096)
        self.assertEqual(out['matched_residual_max_difference'],0.)
        self.assertEqual(out['matched_delta_db'],0.)
        self.assertGreater(out['b_unbounded_suffix_frames'],out['matched_frames'])

    def test_clipping_stops_all_later_trials_and_cancel_does_not_call_driver(self):
        with self.work() as d:
            runner=Runner(clip_first_closed=True);state=self.execute(Path(d),runner)
            self.assertEqual(state['status'],'stopped')
            self.assertEqual(len(runner.calls),2)
            self.assertFalse(state['fir_pairs'])
        with self.work() as d:
            runner=Runner();state=self.execute(Path(d),runner,False)
            self.assertFalse(runner.calls)
            self.assertEqual(state['status'],'stopped')

    def test_execution_and_missing_sidecar_stop_with_return_package(self):
        for kind in ('communication','save','recovery','keyboard'):
            with self.work() as d:
                def failing(*args,**kwargs):
                    if kind=='keyboard':raise KeyboardInterrupt()
                    raise RuntimeError(kind+' failure')
                state=self.execute(Path(d),failing)
                self.assertEqual(state['status'],'stopped')
                self.assertEqual(len(state['trials']),1)
                self.assertEqual(state['checks']['stop_recovery']['status'],'not_tested')
                self.assertEqual(state['checks']['stop_recovery']['unverified_trials'],[1])
                self.assertTrue(list(Path(d).rglob('return-results.zip')))

    def test_exact_a_entry_rejects_equal_budget_and_one_frame_headroom(self):
        from sprint_continuous import driver_request
        base=ROOT/'board/audio_replay';n=int(2.5*sprint.RATE)
        for headroom in (0,1,2):
            source=np.zeros(n-headroom,dtype='<i2')
            if headroom<2:
                with self.assertRaisesRegex(ValueError,'invalid source PCM16 or insufficient duration'):
                    driver_request(base,'replay_trial','unused.npz','unused','unused',source,seconds=2.5,
                        speaker_confirmed=True,local_capture_confirmed=True)
            else:
                result=driver_request(base,'replay_trial','unused.npz','unused','unused',source,seconds=2.5,
                    speaker_confirmed=True,local_capture_confirmed=True)
                self.assertEqual(result['headroom_frames'],2)
        result=driver_request(base,'replay_trial','unused.npz','unused','unused',sprint.comparison_source(),seconds=2.52,
            speaker_confirmed=True,local_capture_confirmed=True)
        self.assertEqual(result['headroom_frames'],976)
        self.assertNotIn('pynq',sys.modules)

    def test_continuous_protection_early_stop_hash_and_cleanup_fail_closed(self):
        from sprint_selftest import SoftwareContinuousRunner
        changes=({'counts':dict(prediction=1,residual=0,gain=0,mix=0)},
                 {'stop_reason':'operator_stop_file'}, {'model_sha256':'wrong'}, {'mute_ok':False,'recovered':False})
        for change in changes:
            class Changed(SoftwareContinuousRunner):
                def __call__(self,path,*args,**kwargs):
                    out=super().__call__(path,*args,**kwargs)
                    out.update(change)
                    path.with_suffix('.status.json').write_text(json.dumps(out),encoding='utf8')
                    return out
            with self.work() as d:
                state=self.execute(Path(d),Runner(),continuous_factory=Changed)
                self.assertEqual(state['status'],'stopped')
                self.assertEqual(state['checks']['continuous_60s']['status'],'failed')
                self.assertEqual(state['full_trial_stability'],'unknown')

    def test_listener_analytic_gain_and_agc_refusal(self):
        with self.work() as d:
            p=Path(d);t=np.arange(8000)/8000
            for mode,amplitude in [('off',1000),('on',2000)]:
                for kind in ('speech','noise'):
                    x=np.rint(amplitude*np.sin(2*np.pi*1000*t)).astype('<i2') if kind=='speech' else np.zeros(8000,dtype='<i2')
                    with wave.open(str(p/(mode+'-'+kind+'.wav')),'wb') as stream:
                        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(x.tobytes())
            result=sprint.listener_metrics(p,'FIXED_SOURCE_FIXED_GAIN_NO_AGC')
            self.assertEqual(result['status'],'passed')
            self.assertAlmostEqual(result['relative_speech_change_db'],20*np.log10(2),places=2)
            self.assertIsNone(result['absolute_spl'])
            self.assertEqual(sprint.listener_metrics(p,'AGC')['status'],'not_tested')


if __name__=='__main__':unittest.main()
