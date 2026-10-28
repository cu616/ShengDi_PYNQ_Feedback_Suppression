"""钉住 v3 工作点那套反推的算术：三点分解、相位反解、临界 g、响度上限。

这些数字会进冻结后的性能声明与演示配置，算错一次就会被写进报告，所以单独守。
"""

import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import answer_v3_working_point as wp  # noqa: E402


class DecompositionTest(unittest.TestCase):
    def test_three_numbers_add_up(self):
        """声学差 = 环路提升 + cancel 过冲；三个数必须自洽，否则口径就错了。"""
        boost = wp.BYPASS_DB - wp.OPEN_DB
        overshoot = wp.OPEN_DB - wp.CANCEL_DB
        acoustic = wp.BYPASS_DB - wp.CANCEL_DB
        self.assertAlmostEqual(acoustic, boost + overshoot, places=9)
        self.assertAlmostEqual(boost, 3.75, places=6)
        self.assertAlmostEqual(overshoot, 1.01, places=6)
        self.assertAlmostEqual(acoustic, 4.76, places=6)

    def test_cd_is_not_the_benefit(self):
        """CD 6.37 与可听收益 3.75 是两个量，不能互相代替。"""
        self.assertGreater(abs(wp.CD_DB - (wp.BYPASS_DB - wp.OPEN_DB)), 2.0)


class PhaseInversionTest(unittest.TestCase):
    def test_recovers_phase_from_measured_boost(self):
        """由 bypass−open 反解 322 Hz 的相位：约 ±40°，即 H 不在正实轴。"""
        h = wp.lin(wp.H_PEAK_DB)
        g = wp.lin(wp.GAIN_DB)
        boost = wp.BYPASS_DB - wp.OPEN_DB
        phi = wp.solve_phase(g, h, boost)
        self.assertFalse(np.isnan(phi))
        self.assertAlmostEqual(abs(phi), 39.8, delta=1.0)

    def test_round_trip_boost(self):
        """用反解出的相位正算回去，必须复现实测提升。"""
        h = wp.lin(wp.H_PEAK_DB)
        g = wp.lin(wp.GAIN_DB)
        boost = wp.BYPASS_DB - wp.OPEN_DB
        phi = wp.solve_phase(g, h, boost)
        self.assertAlmostEqual(wp.boost_at(wp.GAIN_DB, h, phi), boost, places=6)

    def test_in_phase_case_would_give_a_much_bigger_boost(self):
        """如果 phi=0，同样的 g|H| 会给 9.4 dB —— 说明 dB 相加只对幅度界成立。"""
        h = wp.lin(wp.H_PEAK_DB)
        in_phase = wp.boost_at(wp.GAIN_DB, h, 0.0)
        self.assertGreater(in_phase, 9.0)
        self.assertLess(in_phase, 10.0)


class CriticalGainTest(unittest.TestCase):
    def test_zero_arm_critical_matches_magnitude_bound(self):
        """零臂临界 1/|H| 必须与模型算出的幅度界一致到 0.05 dB。"""
        h = wp.lin(wp.H_PEAK_DB)
        self.assertAlmostEqual(wp.db(1.0 / h), wp.BOUND_ZERO_DB, delta=0.05)

    def test_candidate_margin_is_five_db(self):
        self.assertAlmostEqual(wp.BOUND_CAND_DB - wp.BOUND_ZERO_DB, 5.08, delta=0.02)


class PlayedOverSourceTest(unittest.TestCase):
    """322 Hz 上 played/source 有上限，提 g 换不到响度——这是演示叙事的依据。

    零臂：played/source = 1/|1 − gH|。H 的幅度与相位都由实测反解出来了，所以可算。
    候选：需要 H−Ĥ 的**相位**，离线只有逐点模 → 不可算，本类不假装能算。
    """

    @classmethod
    def setUpClass(cls):
        cls.h = wp.lin(wp.H_PEAK_DB)
        cls.g = wp.lin(wp.GAIN_DB)
        cls.phi = wp.solve_phase(cls.g, cls.h, wp.BYPASS_DB - wp.OPEN_DB)
        cls.measured = wp.BYPASS_DB - wp.OPEN_DB

    def test_matches_the_measured_boost_at_minus8(self):
        """played/source 在 −8 dB 必须等于实测的 bypass−open，否则反解就是错的。"""
        value = wp.db(wp.played_over_source(wp.GAIN_DB, self.h, self.phi))
        self.assertAlmostEqual(value, self.measured, places=6)

    def test_peak_is_near_minus6_7_and_under_four_db(self):
        """见顶点在 g·|H| = cosφ，值 = 1/sinφ；对本题是 −6.7 dB / 3.87 dB。"""
        g_peak = np.cos(np.radians(self.phi)) / self.h
        self.assertAlmostEqual(wp.db(g_peak), -6.7, delta=0.2)
        peak = wp.db(wp.played_over_source(wp.db(g_peak), self.h, self.phi))
        self.assertAlmostEqual(peak, 3.87, delta=0.05)

    def test_minus8_is_already_at_the_ceiling(self):
        """−8 dB 距上限不到 0.15 dB —— 所以"再提 g"在这个频点买不到东西。"""
        now = wp.db(wp.played_over_source(wp.GAIN_DB, self.h, self.phi))
        g_peak = np.cos(np.radians(self.phi)) / self.h
        peak = wp.db(wp.played_over_source(wp.db(g_peak), self.h, self.phi))
        self.assertLess(peak - now, 0.15)

    def test_boost_drops_again_beyond_the_peak(self):
        """越过见顶点后继续提 g，played/source 反而下降（相位差造成的）。"""
        low = wp.db(wp.played_over_source(-8.0, self.h, self.phi))
        high = wp.db(wp.played_over_source(-3.0, self.h, self.phi))
        self.assertLess(high, low)

    def test_phase_is_not_zero_so_db_addition_is_only_a_bound(self):
        """φ≈40°：同相口径会给 9.4 dB，实测 3.75 —— dB 相加只能当幅度界用。"""
        self.assertGreater(abs(self.phi), 20.0)
        self.assertGreater(wp.boost_at(wp.GAIN_DB, self.h, 0.0),
                           self.measured + 4.0)


if __name__ == "__main__":
    unittest.main()
