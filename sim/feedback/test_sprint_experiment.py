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
        row=dict(seconds=1.02,source_frames=48828,transition_frames=2442,
                 capture_frames=16384,window_frames=14920,ok=True)
        valid=dict(all_ok=True,policy=sprint.POLICY,evidence_kind='software_fixture',
                   a_assets=sprint.A_ASSETS,
                   source_commits=manifest['source_commits'],payload_hashes={'model.json':'m'},
                   trials=[dict(row) for _ in range(13)])
        sprint.validate_preflight(manifest,valid)
        for patch_value in ({'all_ok':False},{'payload_hashes':{'model.json':'stale'}},
                            {'source_commits':{'C':'old'}},{'a_assets':{'contract':'v2'}},{'trials':[]}):
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
                 recovery_ok=True,gate_mic_over_ref_db=-10.,tail_valid=True)
        b=dict(a,bypass=False)
        self.assertTrue(sprint.pair_check(a,b)['window_comparison_valid'])
        for field in sprint.PAIR_FIELDS:
            bad=dict(b);bad[field]='changed'
            self.assertFalse(sprint.pair_check(a,bad)['configuration_matches'],field)
        self.assertFalse(sprint.pair_check(a,dict(b,gate_mic_over_ref_db=-8.4))['window_comparison_valid'])
        self.assertFalse(sprint.pair_check(a,dict(b,protection=True))['window_comparison_valid'])

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

    def execute(self,base,runner,ready=True,observation='PROXY'):
        setup(base)
        # A's mock emits all-zero coefficients; no borrowed golden detector.
        (base/'model.json').write_bytes((base/'models/candidate_512.json').read_bytes())
        (base/'eq.json').write_text('{"type":"identity"}')
        manifest=dict(source_commits={'C':'test'},coefficients_sha256=qhash(np.zeros(512,dtype=int)),
                      hashes={'audio_replay.bit':BIT,'model.json':sha(base/'model.json')})
        def answer(prompt):
            if 'HUMAN_LIVE_AND_LISTENING' in prompt:return observation
            if 'READY' in prompt:return 'READY' if ready else 'CANCEL'
            if 'SAME_SCENE' in prompt:return 'SAME_SCENE'
            if 'SOURCE_OFF' in prompt:return 'SOURCE_OFF'
            if '一次填写' in prompt:return 'fixed test layout; software fixture only'
            if 'START' in prompt:return 'START'
            if 'CLEAR' in prompt:return 'CLEAR'
            return ''
        with contextlib.redirect_stdout(io.StringIO()):
            return sprint.run_sprint(base,answer,runner,lambda _:manifest)

    def test_complete_bounded_schedule_preserves_unmeasured_60s_and_private_audio(self):
        with self.work() as d:
            base=Path(d);runner=Runner();state=self.execute(base,runner)
            self.assertEqual(state['status'],'completed_with_unmeasured_requirements',state.get('stop_reason'))
            self.assertEqual(len(runner.calls),13)
            self.assertEqual(len(state['fir_pairs']),2)
            self.assertTrue(all(p['window_comparison_valid'] for p in state['fir_pairs']))
            self.assertEqual(state['checks']['continuous_60s']['status'],'not_tested')
            self.assertEqual(state['checks']['listener']['status'],'not_tested')
            self.assertEqual(state['checks']['real_voice']['status'],'not_tested')
            self.assertEqual(state['observation_kind'],'proxy')
            self.assertIsNone(state['asg_db'])
            for row in state['trials']:
                original=row['analysis']['original_metadata']
                self.assertEqual(row['frames'],16384)
                self.assertEqual(row['first_frame'],original['first_frame'])
                self.assertEqual(row['completed_frames'],original['completed_frames'])
                if row['role']=='path-gate':
                    self.assertEqual(row['gate_status'],'passed')
                    gate=row['path_gate']
                    self.assertEqual(gate['end_frame']-gate['first_frame'],14920)
                    self.assertEqual(row['analysis']['tail_analysis_window']['frames'],16384)
                if row['role'] in ('fir-off','fir-on'):
                    window=row['analysis']['tail_analysis_window']
                    self.assertEqual(row['source_frames'],91308)
                    self.assertEqual(window['frames'],16384)
                    self.assertGreaterEqual(window['first_frame'],row['source_frames']+2442)
            with zipfile.ZipFile(next(base.rglob('return-results.zip'))) as archive:
                self.assertFalse(any(n.endswith(('.npz','.wav')) for n in archive.namelist()))
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

    def test_partial_fir_analysis_does_not_overwrite_original_capture_extent(self):
        # Start of a saved ring overlaps the transition, so only analysis crops.
        burst,tone=sprint.sources()
        longer=np.pad(burst,(0,int(2.18*sprint.RATE)-len(burst)))
        with self.work() as d,patch.object(sprint,'sources',return_value=(longer,tone)):
            state=self.execute(Path(d),Runner())
            row=next(r for r in state['trials'] if r['role']=='fir-off')
            window=row['analysis']['tail_analysis_window']
            self.assertEqual(row['frames'],16384)
            self.assertEqual(row['first_frame'],row['analysis']['original_metadata']['first_frame'])
            self.assertGreater(window['first_frame'],row['first_frame'])
            self.assertLess(window['frames'],row['frames'])

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
                self.assertEqual(state['checks']['stop_recovery']['status'],'failed')
                self.assertTrue(list(Path(d).rglob('return-results.zip')))

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
