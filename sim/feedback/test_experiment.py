"""Batch failure recovery and saved evidence; fake runner emits no sound."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'))
import experiment as ex


class ExperimentTests(unittest.TestCase):
    def work(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=ROOT/'tmp')

    def test_incomplete_package_never_calls_driver(self):
        with self.work() as d:
            base=Path(d)
            (base/'experiment-manifest.json').write_text(json.dumps(dict(status='offline_only',missing=['model','A fix'])))
            with contextlib.redirect_stdout(io.StringIO()):
                state=ex.run_package(base,ask=lambda p:self.fail('must not ask for audio'),
                                     runner=lambda *a,**k:self.fail('must not call driver'))
            self.assertEqual(state['status'],'stopped')
            self.assertIn('PACKAGE_INCOMPLETE',state['stop_reason'])
            packet=list(base.rglob('return-results.zip'))[0]
            with zipfile.ZipFile(packet) as z: self.assertIn('summary.json',z.namelist())

    def test_operator_cancel_and_interrupt_preserve_packet(self):
        for failure in ('cancel','interrupt','communication'):
            with self.work() as d:
                base=Path(d)
                def validator(p): return {'hashes':{}},{'fixture_id':'box_v1_20261016'}
                def runner(*a,**kw):
                    if failure=='interrupt': raise KeyboardInterrupt()
                    raise OSError('communication interrupted')
                with contextlib.redirect_stdout(io.StringIO()):
                    state=ex.run_package(base,ask=lambda p:'q' if failure=='cancel' else 'READY',
                                         runner=runner,validator=validator)
                self.assertEqual(state['status'],'cancelled' if failure=='cancel' else 'stopped')
                self.assertEqual(len(state['trials']),0 if failure=='cancel' else 1)
                self.assertTrue(list(base.rglob('return-results.zip')))

    def test_collect_write_failure_is_visible(self):
        with self.work() as d:
            base=Path(d)
            def invalid(p): raise ValueError('missing assets')
            stream=io.StringIO()
            with patch.object(ex,'collect',side_effect=OSError('disk full')),contextlib.redirect_stdout(stream):
                state=ex.run_package(base,validator=invalid)
            self.assertIn('RESULT_SAVE_FAILED',stream.getvalue())
            self.assertEqual(state['status'],'stopped')

    def test_positive_control_delay_independent_known_shift(self):
        with self.work() as d:
            rng=np.random.default_rng(9)
            ref=rng.normal(size=2048)*.01
            mic=np.r_[np.zeros(19),ref[:-19]]
            p=Path(d)/'control.npz'; np.savez(p,reference=ref,microphone=mic)
            result=ex.positive_control(p)
            self.assertTrue(result['passed'])
            self.assertEqual(result['delay_frames'],19)

    def test_full_schedule_keeps_versions_and_no_raw_export(self):
        from evaluation import sha
        with self.work() as d:
            base=Path(d); (base/'model.json').write_text('{}')
            def validator(p):
                return {'hashes':{'model.json':sha(base/'model.json'),'audio_replay.bit':'bit'}},{'fixture_id':'box_v1_20261016'}
            def runner(path,fixture,model,pcm,**kw):
                self.assertTrue(kw['before_start']())
                rate=48828.125; count=int(kw['seconds']*rate); first=count-16384
                t=np.arange(count)/rate
                mic=np.rint(2**23*.01*np.sin(2*np.pi*1000*t)).astype(np.int64)
                gain=0 if kw['direct_only'] else int(np.floor(4096*10**(kw['gain_db']/20)+.5))
                from closed_tools import gain_pcm
                ref=np.zeros(count,dtype=np.int64); ref[:len(pcm)]=pcm.astype(np.int64)*256
                ref[2:]+=gain_pcm(mic[:-2],gain)
                import hashlib
                m=dict(driver_evidence_version='a-replay-evidence-v2',frames=16384,first_frame=first,
                       completed_frames=count,source_frames=len(pcm),source_end_frame_exclusive=len(pcm),
                       source_schedule_verified=True,transition_frames=2442,fixture_id=fixture,
                       bit_sha256='bit',model_sha256=sha(model),coefficients_sha256=hashlib.sha256(np.zeros(512,dtype='<i4').tobytes()).hexdigest(),
                       source_pcm16_sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
                       hp_volume=40,sample_rate_hz=rate,bypass=kw['bypass'],gain_q12=gain,
                       clip_counts_raw=[0,0,0],prediction_saturations=0,residual_saturations=0,
                       gain_saturations=0,mix_saturations=0,verification={'bit_exact':True})
                np.savez(path,reference=ref[first:]/2**23,microphone=mic[first:]/2**23,
                         prediction_pcm=np.zeros(16384,dtype=np.int64),residual_pcm=mic[first:],
                         coefficients_q20=np.zeros(512,dtype=np.int64),source_pcm16=pcm,
                         metadata_json=json.dumps(m),sample_rate_hz=rate)
                path.with_suffix('.status.json').write_text(json.dumps({'recovery_ok':True}))
                return m
            def answer(p): return 'READY' if 'READY' in p else 'START' if 'START' in p else '1'
            with patch.object(ex,'positive_control',return_value={'passed':True,'rms_dbfs':-30.,'delay_frames':19}), \
                 contextlib.redirect_stdout(io.StringIO()):
                state=ex.run_package(base,ask=answer,runner=runner,validator=validator)
            self.assertEqual(state['status'],'completed',state.get('stop_reason'))
            self.assertEqual(len(state['trials']),18)
            self.assertEqual(len(state['pairs']),4)
            self.assertIsNone(state['asg_db'])
            self.assertTrue(state['normal_mic_amplification_demonstrated'])
            with zipfile.ZipFile(list(base.rglob('return-results.zip'))[0]) as z:
                self.assertFalse(any(n.endswith('.npz') for n in z.namelist()))
            self.assertEqual(state['trials'][-1]['analysis']['category'],'unknown')


if __name__=='__main__': unittest.main()
