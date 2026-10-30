"""正实轴穿越判据的回归测试。

防五类错：
  1. 把相位 ±180° 的折返当成零相位穿越（独立复核给的 400/410 Hz 反例）；
  2. 跨过低相干缺口，把两个不相邻的频点连成一次穿越；
  3. 把"小增益 max|L|<1 是充分条件"说成必要条件；
  4. 虚部恰为 0 的 bin（区间的左端/右端/内部）被漏检（C 2026-10-25 的右端反例）；
  5. 端点穿越被相邻两对重复计数。
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

    def test_interior_crossing_is_interpolated_not_amplitude(self):
        """-10°→+10°、|L|=0.5：内部正实轴穿越。

        按"在 Im=0 处线性插值复数"的口径，Re = 0.5·cos10° = 0.492404，
        阈值 1/Re = +6.15357 dB（不是 1/|L| 的 +6.0206 dB——两者口径不同，不能混用）。
        """
        freqs = np.array([400.0, 410.0])
        loop = loop_from([-10.0, 10.0], [0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs, np.array([True, True]),
                                             fmin=0.0)
        self.assertAlmostEqual(thr, 6.15357, places=4)
        self.assertAlmostEqual(hz, 405.0, places=6)

    def test_right_endpoint_exactly_on_positive_real_axis(self):
        """C 的最小反例：f=[400,410]、L=0.5·exp(j·[10°,0°])。

        旧实现只判 ya·yb<0，右端虚部恰为 0 时漏检、返回 inf；
        正确结果应计入 410 Hz 且 Re=0.5，阈值 +6.0206 dB。
        """
        freqs = np.array([400.0, 410.0])
        loop = loop_from([10.0, 0.0], [0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs, np.array([True, True]),
                                             fmin=0.0)
        self.assertTrue(np.isfinite(thr), "右端正实轴被漏检（返回 %r）" % thr)
        self.assertAlmostEqual(thr, 6.0206, places=3)
        self.assertAlmostEqual(hz, 410.0, places=6)

    def test_left_endpoint_exactly_on_positive_real_axis(self):
        """镜像控制：L=0.5·exp(j·[0°,−10°])，左端 400 Hz 是穿越，+6.0206 dB。"""
        freqs = np.array([400.0, 410.0])
        loop = loop_from([0.0, -10.0], [0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs, np.array([True, True]),
                                             fmin=0.0)
        self.assertAlmostEqual(thr, 6.0206, places=3)
        self.assertAlmostEqual(hz, 400.0, places=6)

    def test_endpoint_crossing_is_counted_once(self):
        """三个相邻 bin 全在正实轴上：每处只计一次（端点不被相邻两对重复计数）。"""
        freqs = np.array([400.0, 410.0, 420.0])
        loop = loop_from([0.0, 0.0, 0.0], [0.2, 0.5, 0.3])
        hits = dpm.positive_real_crossing(loop, freqs, np.array([True, True, True]),
                                          fmin=0.0, return_all=True)
        self.assertEqual(len(hits), 3, "端点被重复计数：%r" % (hits,))
        self.assertAlmostEqual(hits[0][0], 0.5, places=6)      # 最大 Re 在 410 Hz
        self.assertAlmostEqual(hits[0][1], 410.0, places=6)

    def test_multiple_isolated_real_bins_are_all_counted(self):
        """C 的第二个反例：f=[400,410,420]、L=0.5·exp(j·[0°,10°,0°])、gate=[T,F,T]。

        400 与 420 都是合格正实轴采样，各计一次；不需要跨缺口插值。
        旧实现只在相邻对里判端点，两个端点都不在任何相邻对里，于是全部漏掉、返回 inf。
        """
        freqs = np.array([400.0, 410.0, 420.0])
        loop = loop_from([0.0, 10.0, 0.0], [0.5, 0.5, 0.5])
        gate = np.array([True, False, True])
        thr, hz = dpm.positive_real_crossing(loop, freqs, gate, fmin=0.0)
        self.assertAlmostEqual(thr, 6.0206, places=3)
        self.assertEqual({400.0, 420.0}.__contains__(hz), True)
        hits = dpm.positive_real_crossing(loop, freqs, gate, fmin=0.0, return_all=True)
        self.assertEqual(len(hits), 2, "孤立端点计数应为 2，实际 %r" % (hits,))
        self.assertAlmostEqual(max(h[0] for h in hits), 0.5, places=6)

    def test_isolated_real_bin_between_gapped_neighbours(self):
        """gate=[F,T,F]：只有中间那个 bin 过门控且恰在正实轴上，仍应计一次。"""
        freqs = np.array([400.0, 410.0, 420.0])
        loop = loop_from([10.0, 0.0, -10.0], [0.5, 0.4, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs, np.array([False, True, False]),
                                             fmin=0.0)
        self.assertAlmostEqual(thr, 7.9588, places=3)      # 1/0.4
        self.assertAlmostEqual(hz, 410.0, places=6)

    def test_does_not_interpolate_across_a_coherence_gap(self):
        """只有 400 与 420 过门控、410 被门控掉时，不能跨过去连成一次穿越。"""
        freqs = np.array([400.0, 410.0, 420.0])
        loop = loop_from([-10.0, 0.0, 10.0], [0.5, 0.5, 0.5])
        thr, hz = dpm.positive_real_crossing(loop, freqs,
                                             np.array([True, False, True]), fmin=0.0)
        self.assertTrue(np.isinf(thr), "跨缺口插值仍报了阈值 %r" % thr)

    def test_no_crossing_is_reported_as_inf_not_as_stability(self):
        """虚部同号（无过零）时报 inf，由调用方另报覆盖不足；不能解读为"物理上无限稳定"。"""
        freqs = np.array([400.0, 410.0, 420.0])
        loop = loop_from([10.0, 20.0, 30.0], [0.5, 0.5, 0.5])
        thr, _ = dpm.positive_real_crossing(loop, freqs, np.ones(3, dtype=bool), fmin=0.0)
        self.assertTrue(np.isinf(thr))

    def test_small_gain_bound_is_only_sufficient(self):
        """小增益下界必须等于 1/max|L|，且与穿越估计分开返回，不能互相替代。"""
        freqs = np.arange(400.0, 430.0, 10.0)
        loop = loop_from([0.0, 40.0, 80.0], [0.2, 0.5, 0.3])
        gate = np.array([True, True, True])
        bound = -20 * np.log10(np.abs(loop[gate]).max())
        thr, _ = dpm.positive_real_crossing(loop, freqs, gate, fmin=0.0)
        self.assertAlmostEqual(bound, 6.0206, places=3)
        self.assertNotAlmostEqual(thr, bound)  # 两个口径不等价，必须分别报


class DeployedModelEntryTest(unittest.TestCase):
    """生产入口必须按 Q20 复算，并与模型身份哈希绑定。"""

    MODEL = ROOT / "models" / "room_v1" / "calibrated_20261024.json"

    def test_response_comes_from_q20_not_float_array(self):
        model, coef, info = dpm.load_deployed_model(self.MODEL)
        self.assertEqual(info["source"], "coefficients_q20")
        expect = np.asarray(model["coefficients_q20"], dtype=float) / (1 << 20)
        np.testing.assert_allclose(coef, expect, rtol=0, atol=0)
        # 与浮点数组差别应在量化噪声量级，而不是 0（否则说明读的是浮点）
        flt = np.asarray(model["coefficients"], dtype=float)
        self.assertGreater(np.max(np.abs(flt - coef)), 0.0)

    def test_q20_identity_matches_contract(self):
        """C 的 RC0.1 身份：calibrated_20261024 的 Q20 哈希固定。"""
        _model, _coef, info = dpm.load_deployed_model(self.MODEL)
        self.assertEqual(
            info["q20_sha256"],
            "c9d3b1e658fd2ed8b731904eaa1f2bec62677b732f5bebe1acf34f1d96fa2160")
        self.assertEqual(
            info["file_sha256"],
            "c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a")

    def test_lag_first_applied_once(self):
        """lag_first=1 只由 model_response 加一次；再叠加 delay_samples=1 等于整体多延迟 1 拍。"""
        _model, coef, info = dpm.load_deployed_model(self.MODEL)
        nfft = 8192
        w = 2 * np.pi * np.arange(nfft // 2 + 1) / nfft
        base = dpm.model_response(coef, nfft, lag_first=info["lag_first"])
        one_more = dpm.model_response(coef, nfft, delay_samples=1,
                                      lag_first=info["lag_first"])
        np.testing.assert_allclose(one_more, base * np.exp(-1j * w), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
