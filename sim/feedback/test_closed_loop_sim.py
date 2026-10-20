"""闭环参考模拟的验证：定点语义、帧调度、以及与理论起振增益的一致性。"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from feedback.closed_loop_sim import (FULL_SCALE, MAX_CODE, MIN_CODE,  # noqa: E402
                                      _gain_q12, _round_half_away, find_msg,
                                      simulate)

FS = 48828.125


def delay_room(delay=3, gain=0.5, length=16):
    room = np.zeros(length)
    room[delay] = gain
    return room


def coefficients(value, index=2, taps=256):
    """pred[n]=Σh[k]u[n-1-k]：要让 mic[n]=value·u[n-3]，系数放在 k=2。"""
    h = np.zeros(taps, dtype=np.int64)
    if value:
        h[index] = int(round(value * (1 << 20)))
    return h


def noise_source(frames=4096, dbfs=-60.0, seed=1):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(frames) * 10.0 ** (dbfs / 20.0)


class FixedPointTests(unittest.TestCase):
    def test_rounding_is_half_away_from_zero(self):
        np.testing.assert_array_equal(_round_half_away(np.array([0.5, -0.5, 1.5, -1.5])),
                                      np.array([1.0, -1.0, 2.0, -2.0]))

    def test_gain_saturates_at_24_bits(self):
        value, clipped = _gain_q12(np.array([MAX_CODE]), 32768)
        self.assertTrue(bool(clipped))
        self.assertEqual(int(value[0]), MAX_CODE)
        value, clipped = _gain_q12(np.array([MIN_CODE]), 32768)
        self.assertTrue(bool(clipped))
        self.assertEqual(int(value[0]), MIN_CODE)

    def test_unity_gain_is_transparent(self):
        values = np.array([0, 1, -1, 12345, -12345], dtype=np.int64)
        out, clipped = _gain_q12(values, 4096)
        np.testing.assert_array_equal(out.astype(np.int64), values)
        self.assertFalse(bool(clipped))

    def test_gain_range_is_enforced(self):
        with self.assertRaises(ValueError):
            simulate(delay_room(), noise_source(64), coefficients(0), 0, frames=64)
        with self.assertRaises(ValueError):
            simulate(delay_room(), noise_source(64), coefficients(0), 32769, frames=64)


class SchedulingTests(unittest.TestCase):
    def test_output_is_played_two_frames_later(self):
        """顶层是 played[n+2] = gain(residual[n])，这条关系错了就全错。"""
        frames = 512
        stats = simulate(delay_room(), noise_source(frames), coefficients(0),
                         gain_q12=4096, bypass=True, frames=frames, keep_signal=True)
        played = stats["played"]
        residual = stats["residual"]
        expected = np.concatenate([[0, 0], residual[:-2]])
        np.testing.assert_array_equal(played, expected.astype(np.int64))

    def test_bypass_ignores_model_and_keeps_microphone(self):
        frames = 256
        stats = simulate(delay_room(), noise_source(frames), coefficients(0.5),
                         gain_q12=4096, bypass=True, frames=frames, keep_signal=True)
        # 旁路时残差就是麦克风原样，且不因模型不同而改变。
        other = simulate(delay_room(), noise_source(frames), coefficients(0.0),
                         gain_q12=4096, bypass=True, frames=frames, keep_signal=True)
        np.testing.assert_array_equal(stats["residual"], other["residual"])


class MessageTests(unittest.TestCase):
    def test_bypass_threshold_matches_theory(self):
        room = delay_room(delay=3, gain=0.5)
        expected = -20.0 * np.log10(0.5)
        result = find_msg(room, coefficients(0), bypass=True, frames=4096,
                          low_db=-10.0, high_db=20.0)
        self.assertAlmostEqual(result["msg_db"], expected, delta=0.6)

    def test_partial_cancellation_matches_theory(self):
        """模型只抵掉一半路径时，剩余 0.25 → 起振增益应为 4 倍（12 dB）。"""
        room = delay_room(delay=3, gain=0.5)
        expected = -20.0 * np.log10(0.25)
        result = find_msg(room, coefficients(0.25), bypass=False, frames=4096,
                          low_db=-10.0, high_db=25.0)
        self.assertAlmostEqual(result["msg_db"], expected, delta=0.7)

    def test_perfect_model_survives_maximum_gain(self):
        room = delay_room(delay=3, gain=0.5)
        stats = simulate(room, noise_source(2048), coefficients(0.5), gain_q12=32768,
                         bypass=False, frames=2048)
        self.assertFalse(stats["diverged"])

    def test_stable_loop_does_not_report_divergence(self):
        room = delay_room(delay=3, gain=0.5)
        # 环路增益 0.5×0.9 < 1，应当稳定。
        stats = simulate(room, noise_source(2048), coefficients(0), gain_q12=3686,
                         bypass=True, frames=2048)
        self.assertFalse(stats["diverged"])


if __name__ == "__main__":
    unittest.main()
