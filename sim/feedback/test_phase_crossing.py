"""正实轴穿越判据的回归测试。

防三类错：
  1. 把相位 ±180° 的折返当成零相位穿越（独立复核给的 400/410 Hz 反例）；
  2. 跨过低相干缺口，把两个不相邻的频点连成一次穿越；
  3. 把"小增益 max|L|<1 是充分条件"说成必要条件。
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import diagnose_peak_margin as dpm  # noqa: E402


def loop_from(phases_deg, mags):
    ph = np.radians(np.asarray(phases_deg, dtype=float))
    return np.asarray(mags, dtype=float) * np.exp(1j * ph)


class PositiveRealCrossingTest(unittest.TestCase):
    def test_review_counterexample_179_to_minus179_is_not_a_crossing(self):
        """400/410 Hz、+179/-179°、|L|=0.5：Re<0，不是穿越，不能报 405 Hz/+6.02 dB。"""
        freqs = np.array([400.0, 410.0])
        loop = loop_from([179.0, -179.0], [0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs, np.array([True, True]),
                                             fmin=0.0)
        self.assertTrue(np.isinf(thr), "±180° 折返被误判成穿越，阈值 %r" % thr)
        self.assertTrue(np.isnan(hz))

    def test_true_positive_real_crossing_is_found(self):
        """-10°→+10°、|L|=0.5：真实的正实轴穿越。

        按"在 Im=0 处线性插值复数"的口径，Re = 0.5·(cos10°+cos10°)/2 = 0.4924，
        阈值 1/Re = +6.154 dB（不是 1/|L| 的 +6.02 dB——两者口径不同，不能混用）。
        """
        freqs = np.array([400.0, 410.0])
        loop = loop_from([-10.0, 10.0], [0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs, np.array([True, True]),
                                             fmin=0.0)
        self.assertAlmostEqual(thr, 6.1536, places=3)
        self.assertAlmostEqual(hz, 405.0, places=6)

    def test_does_not_interpolate_across_a_coherence_gap(self):
        """只有 400 与 420 过门控、410 被门控掉时，不能跨过去连成一次穿越。"""
        freqs = np.array([400.0, 410.0, 420.0])
        loop = loop_from([-10.0, 0.0, 10.0], [0.5, 0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs,
                                             np.array([True, False, True]), fmin=0.0)
        self.assertTrue(np.isinf(thr), "跨缺口插值仍报了阈值 %r" % thr)

    def test_small_gain_bound_is_only_sufficient(self):
        """小增益下界必须等于 1/max|L|，且与穿越估计分开返回，不能互相替代。"""
        freqs = np.arange(400.0, 430.0, 10.0)
        loop = loop_from([0.0, 40.0, 80.0], [0.2, 0.5, 0.3])
        gate = np.array([True, True, True])
        bound = -20 * np.log10(np.abs(loop[gate]).max())
        thr, _ = dpm.positive_real_crossing(loop, freqs, gate, fmin=0.0)
        self.assertAlmostEqual(bound, 6.0206, places=3)
        self.assertNotAlmostEqual(thr, bound)  # 两个口径不等价，必须分别报


if __name__ == "__main__":
    unittest.main()
