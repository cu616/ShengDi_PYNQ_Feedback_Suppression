import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'board/audio_closed'))
from closed_tools import trial_parameters, gain_pcm, verify_closed


class ClosedToolsTests(unittest.TestCase):
    def test_rounding_and_clipping(self):
        np.testing.assert_array_equal(gain_pcm([-3, -1, 1, 3], 2048), [-2, -1, 1, 2])
        np.testing.assert_array_equal(gain_pcm([-8388608, 8388607], 32768), [-8388608, 8388607])
        self.assertEqual(trial_parameters(0, 10), (4096, 488281))
        for gain, duration in [(float('nan'), 1), (19, 1), (0, 11), (0, 0)]:
            with self.assertRaises(ValueError):
                trial_parameters(gain, duration)

    def test_actual_output_history_and_truncated_ring(self):
        # Independent scalar recurrence: h[0]=1/2, h[2]=1/4; two-frame DAC schedule.
        raw = np.zeros((1200, 4), dtype=np.int64)
        q = np.zeros(256, dtype=np.int64); q[0] = 1 << 19; q[2] = 1 << 18
        for n in range(len(raw)):
            raw[n, 0] = raw[n-2, 3] if n >= 2 else 0
            acc = (raw[n-1, 0]*2 if n >= 1 else 0) + (raw[n-3, 0] if n >= 3 else 0)
            pred = (1 if acc >= 0 else -1) * ((abs(int(acc))+2)//4)
            raw[n, 1] = 12345 if n % 3 else -6789
            raw[n, 2] = pred
            raw[n, 3] = raw[n, 1]-pred
        self.assertTrue(verify_closed(raw, q, False, 4096)['bit_exact'])
        self.assertTrue(verify_closed(raw[-600:], q, False, 4096, 600)['bit_exact'])
        broken = raw.copy(); broken[1000, 0] += 1
        self.assertGreater(verify_closed(broken, q, False, 4096)['output_mismatches'], 0)

    def test_zero_coefficients_both_modes(self):
        raw = np.zeros((600, 4), dtype=np.int64)
        raw[:, 1] = raw[:, 3] = np.arange(600)-300
        raw[2:, 0] = raw[:-2, 3]
        for bypass in (True, False):
            self.assertTrue(verify_closed(raw, np.zeros(256, dtype=np.int64), bypass, 4096)['bit_exact'])


if __name__ == '__main__':
    unittest.main()
