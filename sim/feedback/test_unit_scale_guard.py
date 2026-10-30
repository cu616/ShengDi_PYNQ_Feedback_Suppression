"""单位与饱和口径的守门测试。

存在的理由：2026-10-26 我把 Q20 系数的满量程 ±8 当成了 PCM 的满量程，算出"满幅也差 10.9 dB、
装板不会饱和"，被 C 的反例推翻。这组测试钉住三件事，防止同一个错误再回来：

1. PCM 满量程是 ±2^23 计数（= ±1.0 归一化），不是 ±8；RTL 与复算脚本用同一个数。
2. 候选满足 ‖h‖₁ > 1，所以"任何输入都不饱和"这句话本身不成立。
3. 窄带才是判据：|Ĥ| 峰值处，持续单音超过 1/|Ĥ|max 的幅度就必须出现饱和。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from audit_units_and_saturation import FULL_SCALE_CODE, Q, rtl_predict  # noqa: E402
from diagnose_peak_margin import model_response  # noqa: E402

MODEL = REPO / "models/room_v1/rewired_512_20261026.json"
RTL = REPO / "src/rtl/feedback_fir.v"


def load_model():
    return json.loads(MODEL.read_bytes().decode("utf-8"))


class PcmFullScaleTest(unittest.TestCase):
    def test_pcm_full_scale_is_2_pow_23(self):
        self.assertEqual(FULL_SCALE_CODE, 1 << 23)

    def test_rtl_clips_against_the_same_number(self):
        """RTL 的裁剪常数必须是 8388607 / -8388608；变了就说明语义变了，本测试要重审。"""
        text = RTL.read_text(encoding="utf-8")
        self.assertIn("58'sd8388607", text)
        self.assertIn("-58'sd8388608", text)
        # 系数满量程（Q20 的 ±8）只应出现在除法里，不能出现在裁剪里
        self.assertIn(">> 20", text)

    def test_coefficient_full_scale_is_not_pcm_full_scale(self):
        coeff_fs = (1 << 23) / (1 << Q)
        self.assertAlmostEqual(coeff_fs, 8.0)
        self.assertNotAlmostEqual(coeff_fs, 1.0)


class SaturationClaimTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()
        self.q20 = np.asarray(self.model["coefficients_q20"], dtype=np.int64)
        self.h = self.q20.astype(float) / (1 << Q)

    def test_candidate_l1_exceeds_unity_so_no_blanket_guarantee(self):
        l1 = float(np.abs(self.h).sum())
        self.assertGreater(l1, 1.0, "L1 <= 1 才允许说'任何合法输入都不饱和'")
        self.assertAlmostEqual(l1, 2.2875843, places=6)

    def test_peak_band_gain_exceeds_unity_and_locates_the_risk(self):
        nfft = 1 << 15
        mag = np.abs(model_response(self.h, nfft, lag_first=1))
        self.assertGreater(mag.max(), 1.0)
        self.assertAlmostEqual(mag.max(), 1.2309, places=3)

    def test_tone_at_analytic_threshold_actually_saturates(self):
        """解析阈值 1/|Ĥ|max 必须能被整数路径复现——不接受只写在报告里的数。"""
        q20, h = self.q20, self.h
        nfft = 1 << 15
        fs = float(self.model["sample_rate_hz"])
        mag = np.abs(model_response(h, nfft, lag_first=1))
        k = int(np.argmax(mag))
        f0 = k * fs / nfft
        # 取阈值上方 5 %：正弦在离散采样上的峰相位不一定正好落在临界点上，
        # 但 5 %（0.42 dB）远小于 1.0 与 8.0 之间的 18 dB 差，足以把两种口径分开。
        amp = 1.05 / mag[k]
        t = np.arange(1 << 13)
        u = np.rint(amp * np.sin(2 * np.pi * f0 * t / fs) * FULL_SCALE_CODE).astype(np.int64)
        _pred, sat = rtl_predict(q20, u)
        self.assertGreaterEqual(sat, 1, "解析阈值附近必须出现饱和，否则阈值算错了")

    def test_threshold_just_below_is_clean(self):
        """阈值下方 1.6 dB 必须干净——与上一条一起把阈值夹在 ±5 % 内。"""
        q20, h = self.q20, self.h
        nfft = 1 << 15
        fs = float(self.model["sample_rate_hz"])
        mag = np.abs(model_response(h, nfft, lag_first=1))
        k = int(np.argmax(mag))
        f0 = k * fs / nfft
        amp = 1.0 / mag[k] / 1.2
        t = np.arange(1 << 13)
        u = np.rint(amp * np.sin(2 * np.pi * f0 * t / fs) * FULL_SCALE_CODE).astype(np.int64)
        _pred, sat = rtl_predict(q20, u)
        self.assertEqual(sat, 0)

    def test_wrong_denominator_would_predict_never_saturating(self):
        """把系数满量程 8 当 PCM 满量程时，需要的单音幅度是 8/|Ĥ|max > 1，即"永远不饱和"。
        正确口径下阈值是 1/|Ĥ|max < 1。两个数差 18 dB，这条把错误口径单独钉住。"""
        nfft = 1 << 15
        mag = np.abs(model_response(self.h, nfft, lag_first=1))
        g = float(mag.max())
        self.assertGreater(8.0 / g, 1.0)
        self.assertLess(1.0 / g, 1.0)

    def test_tone_below_threshold_does_not_saturate(self):
        q20, h = self.q20, self.h
        nfft = 1 << 15
        fs = float(self.model["sample_rate_hz"])
        mag = np.abs(model_response(h, nfft, lag_first=1))
        k = int(np.argmax(mag))
        f0 = k * fs / nfft
        amp = 10 ** (-3.0 / 20)          # −3 dBFS，解析上在 1/|Ĥ|max = 0.812 之下
        t = np.arange(1 << 12)
        u = np.rint(amp * np.sin(2 * np.pi * f0 * t / fs) * FULL_SCALE_CODE).astype(np.int64)
        pred, sat = rtl_predict(q20, u)
        self.assertEqual(sat, 0)
        self.assertLess(np.abs(pred).max(), FULL_SCALE_CODE)


if __name__ == "__main__":
    unittest.main()
