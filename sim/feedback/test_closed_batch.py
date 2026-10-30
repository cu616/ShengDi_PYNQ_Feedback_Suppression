import contextlib
import csv
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
        temporary_root = Path(__file__).resolve().parents[2] / 'tmp'
        temporary_root.mkdir(exist_ok=True)
        self.csv_rows = []
        with tempfile.TemporaryDirectory(dir=temporary_root) as d:
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
                if failure == 'gain' and len(calls) == 2: result['gain_q12'] += 1
                if failure == 'volume' and len(calls) == 2: result['hp_volume'] = 39
                if failure and failure.startswith('missing_'):
                    result.pop(failure.removeprefix('missing_'))
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
                with files[0].with_suffix('.csv').open(newline='', encoding='utf-8-sig') as stream:
                    self.csv_rows = list(csv.DictReader(stream))
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
        for key in ('gain_q12', 'hp_volume', 'bit_sha256'):
            self.assertIsNone(state['trials'][0][key])
            self.assertEqual(self.csv_rows[0][key], '')

    def test_howl_stops_whole_batch(self):
        state, calls = self.execute(['READY', 'START', '3'])
        self.assertEqual(len(calls), 1); self.assertEqual(state['stop_reason'], 'howl_or_growth')

    def test_bad_result_and_interrupt_never_escalate(self):
        for failure in ('clip', 'mismatch', 'interrupt'):
            state, calls = self.execute(['READY', 'START'], failure)
            self.assertEqual(state['status'], 'stopped'); self.assertEqual(len(calls), 1)

    def test_pair_config_change_stops(self):
        for failure, field in [('config', 'bit_sha256'), ('gain', 'gain_q12'),
                               ('volume', 'hp_volume')]:
            with self.subTest(field=field):
                state, calls = self.execute(['READY', 'START', '0', 'START'], failure)
                self.assertEqual(len(calls), 2)
                self.assertIn('pair_configuration_mismatch', state['stop_reason'])
                self.assertFalse(state['pairs'][0]['configuration_matches'])
                a, b = state['trials']
                self.assertNotEqual(a[field], b[field])
                self.assertEqual(a[field], a['metadata'][field])
                self.assertEqual(b[field], b['metadata'][field])
                self.assertEqual([r[field] for r in self.csv_rows],
                                 [str(a[field]), str(b[field])])

    def test_summary_exports_actual_config(self):
        state, _ = self.execute(['READY'] + ['START', '1']*8)
        self.assertEqual(state['schema_version'], 2)
        # Independent expected encodings for the fixed four requested gains.
        expected_gains = [130, 130, 258, 258, 516, 516, 1029, 1029]
        self.assertEqual([r['gain_q12'] for r in state['trials']], expected_gains)
        self.assertEqual([int(r['gain_q12']) for r in self.csv_rows], expected_gains)
        for row, csv_row in zip(state['trials'], self.csv_rows):
            self.assertEqual(row['hp_volume'], 40)
            self.assertEqual(row['bit_sha256'], 'bit')
            for key in ('gain_q12', 'hp_volume', 'bit_sha256'):
                self.assertEqual(row[key], row['metadata'][key])
                self.assertEqual(csv_row[key], str(row[key]))
        for a, b in zip(state['trials'][::2], state['trials'][1::2]):
            self.assertEqual(a['gain_q12'], b['gain_q12'])

    def test_missing_actual_config_stops_without_fabricating_fields(self):
        for key in ('gain_q12', 'hp_volume', 'bit_sha256'):
            with self.subTest(field=key):
                state, calls = self.execute(['READY', 'START'], 'missing_' + key)
                self.assertEqual(len(calls), 1)
                self.assertEqual(state['status'], 'stopped')
                self.assertIn('missing_configuration_metadata', state['stop_reason'])
                self.assertIsNone(state['trials'][0][key])
                self.assertEqual(self.csv_rows[0][key], '')
                self.assertEqual(state['pairs'], [])


if __name__ == '__main__': unittest.main()
