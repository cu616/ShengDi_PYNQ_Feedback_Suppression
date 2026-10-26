"""新布局 325 Hz 回答脚本的三个不变量。

防三类错：
  1. 逐段对齐把延迟小的那段**往前**挪（方向反了），整批差两帧，跨段交叉谱在高频被擦掉；
  2. 目标频点插值取错邻 bin（325 Hz 不落在 5.96 Hz 网格上，必须取两侧）；
  3. 陷波所需深度算反（应是 target − g_bin，不是 g_bin − target）。
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import answer_new_layout_325 as nla  # noqa: E402


def synthetic_segments(lags, n=4096, seed=1):
    """构造 ref/mic：mic 是 ref 延迟 lag 帧再混 8 个抽头的短拖尾。"""
    rng = np.random.default_rng(seed)
    u = rng.standard_normal(n)
    tail = np.zeros(8)
    tail[0], tail[3] = 1.0, 0.25
    src = np.convolve(u, tail)[:n]
    segs = []
    for lag in lags:
        m = np.concatenate([np.zeros(lag), src[:n - lag]])
        segs.append({"reference": u, "microphone": m})
    return segs


class AlignmentTest(unittest.TestCase):
    def test_delay_smaller_segment_is_delayed_not_advanced(self):
        """lag=180 的那段必须被**滞后**到 185，而不是把 185 那段往前挪。"""
        segs = synthetic_segments([185, 180])
        aligned, lags, target = nla.align_segments(segs)
        self.assertEqual(lags, [185, 180])
        self.assertEqual(target, 185)
        for (u, m) in aligned:
            self.assertEqual(nla.estimate_lag(u, m), 185)

    def test_alignment_does_not_shift_reference(self):
        """reference 一个样本都不许动：它必须与 source_pcm16 保持逐样本相同。"""
        segs = synthetic_segments([185, 180])
        aligned, _lags, _target = nla.align_segments(segs)
        for (u, _m), seg in zip(aligned, segs):
            np.testing.assert_array_equal(u, seg["reference"])

    def test_wrong_direction_is_detected(self):
        """反方向（把 180 那段往前挪）会让对齐后仍然差 10 帧——这条用来钉住方向。"""
        segs = synthetic_segments([185, 180])
        u = segs[1]["reference"]
        bad = np.concatenate([segs[1]["microphone"][5:], np.zeros(5)])
        self.assertEqual(nla.estimate_lag(u, bad), 175)


class TargetInterpolationTest(unittest.TestCase):
    def test_uses_the_two_straddling_bins(self):
        fs = 48828.125
        nfft = 8192
        freqs = np.arange(nfft // 2 + 1) * fs / nfft
        a_h, a_hat = 10 ** (6 / 20), 10 ** (-6 / 20)             # 两个同相实数量
        H = np.full(len(freqs), a_h, dtype=complex)
        H_hat = np.full(len(freqs), a_hat, dtype=complex)
        coh = np.ones(len(freqs))
        info = nla.at_target(H, H_hat, freqs, coh, 325.0)
        self.assertEqual(len(info["bins"]), 2)
        self.assertLess(info["bins_hz"][0], 325.0)
        self.assertGreater(info["bins_hz"][1], 325.0)
        self.assertAlmostEqual(info["magnitude_h_db"], 6.0, places=6)
        # 同相相减是 |a_h − a_hat|，不是幅度相加；插值后必须等于这两个 bin 的原值
        self.assertAlmostEqual(info["residual_db"], 20 * np.log10(a_h - a_hat), places=6)
        self.assertAlmostEqual(info["cd_db"], 20 * np.log10(a_h / (a_h - a_hat)), places=6)


class NotchArithmeticTest(unittest.TestCase):
    def _desc(self, freqs, g_values, binding_hz):
        gbin = np.full(len(freqs), np.nan)
        for k, value in g_values.items():
            gbin[k] = value
        return {"label": "synthetic", "_gbin": gbin, "binding_bin_hz": binding_hz}

    def test_required_depth_and_ceiling(self):
        freqs = np.arange(0, 500, 5.0)
        gate = freqs >= 300
        # 325 Hz 附近 −6 dB，其余两处 −2 dB 与 −9 dB
        g_values = {int(np.argmin(np.abs(freqs - h))): g
                    for h, g in ((310.0, -2.0), (325.0, -6.0), (420.0, -9.0))}
        desc = self._desc(freqs, g_values, 325.0)
        out = nla.notch_requirement(desc, freqs, np.ones(len(freqs)), gate, 0.0, 325.0)
        self.assertAlmostEqual(out["g_at_target_db"], -6.0, places=6)
        self.assertAlmostEqual(out["required_depth_at_target_db"], 6.0, places=6)
        # 挖掉 325±25 Hz 后最紧的是 420 Hz 的 −9 dB
        self.assertAlmostEqual(out["ceiling_outside_notch_db"], -9.0, places=6)
        self.assertFalse(out["reachable_by_notching_target"])

    def test_reachable_when_ceiling_is_high(self):
        freqs = np.arange(0, 500, 5.0)
        gate = freqs >= 300
        g_values = {int(np.argmin(np.abs(freqs - h))): g
                    for h, g in ((310.0, 4.0), (325.0, -6.0), (420.0, 3.0))}
        desc = self._desc(freqs, g_values, 325.0)
        out = nla.notch_requirement(desc, freqs, np.ones(len(freqs)), gate, 0.0, 325.0)
        self.assertAlmostEqual(out["required_depth_at_target_db"], 6.0, places=6)
        self.assertTrue(out["reachable_by_notching_target"])


if __name__ == "__main__":
    unittest.main()
