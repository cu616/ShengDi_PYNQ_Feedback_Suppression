import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'board/audio_closed'))
from closed_batch import run_batch


class BatchTests(unittest.TestCase):
    def execute(self, answers, failure=None):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / 'tmp') as d:
            root = Path(d); model = root / 'model.json'; model.write_text('{}')
            calls = []
            def runner(path, fixture, model_path, **kw):
                if not kw['before_start']():
                    raise RuntimeError('cancelled before unmute')
                calls.append(kw)
                if failure == 'interrupt':
                    raise KeyboardInterrupt()
                result = dict(bit_sha256='bit', model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                              coefficients_sha256='q', fixture_id=fixture, hp_volume=40,
                              sample_rate_hz=48828.125, gain_q12=int(4096*10**(kw['gain_db']/20)+.5),
                              completed_frames=97656, sound_seconds_nominal=1.99999488,
                              bypass=kw['bypass'], zero_coeff=False, prediction_saturations=0,
                              residual_saturations=0, gain_saturations=0, mic_full_scale_samples=0,
                              verification=dict(bit_exact=True, prediction_mismatches=0,
                                                residual_mismatches=0, output_mismatches=0))
                if failure == 'clip': result['gain_saturations'] = 1
                if failure == 'mismatch': result['verification']['bit_exact'] = False
                if failure == 'config' and len(calls) == 2: result['bit_sha256'] = 'other'
                return result
            responses = iter(answers)
            with contextlib.redirect_stdout(io.StringIO()):
                state = run_batch(model_path=model, output_root=root/'out',
                                  runner=runner, ask=lambda _: next(responses))
            files = list((root/'out').glob('*/summary.json'))
            if state is None:
                self.assertFalse(files)
            else:
                self.assertEqual(json.loads(files[0].read_text(encoding='utf-8')), state)
                self.assertTrue(files[0].with_suffix('.csv').exists())
            return state, calls

    def test_complete_eight_trials_and_four_pairs(self):
        state, calls = self.execute(['READY'] + ['START', '1']*8)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(len(calls), 8)
        self.assertEqual(len(state['pairs']), 4)
        self.assertTrue(all(p['configuration_matches'] and p['asg_db'] is None for p in state['pairs']))
        self.assertEqual([c['bypass'] for c in calls], [True, False]*4)

    def test_no_initial_confirmation_no_trials(self):
        state, calls = self.execute(['q'])
        self.assertIsNone(state); self.assertEqual(calls, [])

    def test_cancel_at_ready_no_audio(self):
        state, calls = self.execute(['READY', 'q'])
        self.assertEqual(state['status'], 'stopped'); self.assertEqual(calls, [])

    def test_howl_stops_whole_batch(self):
        state, calls = self.execute(['READY', 'START', '3'])
        self.assertEqual(len(calls), 1); self.assertEqual(state['stop_reason'], 'howl_or_growth')

    def test_bad_result_and_interrupt_never_escalate(self):
        for failure in ('clip', 'mismatch', 'interrupt'):
            state, calls = self.execute(['READY', 'START'], failure)
            self.assertEqual(state['status'], 'stopped'); self.assertEqual(len(calls), 1)

    def test_pair_config_change_stops(self):
        state, calls = self.execute(['READY', 'START', '0', 'START'], 'config')
        self.assertEqual(len(calls), 2)
        self.assertIn('pair_configuration_mismatch', state['stop_reason'])


if __name__ == '__main__': unittest.main()
