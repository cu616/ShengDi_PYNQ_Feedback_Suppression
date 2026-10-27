"""PS 拓扑的残差裕量：钉住"残差在增益之前被钳"这个设计缺陷的定量依据。

钉三件事：
1. 在 −8 dB 下，残差相对麦克风最多放大到 ≈1.84 倍（发生在 390–401 Hz），
   所以麦克风峰值 ≈ −5.3 dBFS 就足以让残差碰满幅。
2. 现场门限是 −6 dBFS 峰值（0.501），此时残差已经到满幅的 92%——只剩 0.7 dB 余量。
   这条不是"偶发"，是余量设计。
3. 宽残差（保留到增益之后再钳）在 −8 dB 下输出/麦克风上界 < 1，即永远不会越输出。

推导（单频、线性、含调度）：
    pred[n] = Σ h[k]·u[n−1−k]        → 一拍
    u[n]    = g·residual[n−2]        → 两拍
    residual = mic − pred
  ⇒ residual/mic = 1 / (1 + g·e^{−j3ω}·H_raw(ω))
  分母只取决于模型和增益，与真实路径 H 无关，所以可以直接判"残差会不会越界"。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
MODEL = REPO / "models/room_v1/rewired_512_20261026.json"
FS = 48828.125
NFFT = 1 << 15


def ps_denominator(gain_db: float) -> tuple[np.ndarray, np.ndarray]:
    """返回 (频率轴, |1 + g·e^{-j3ω}·H_raw|)，300–10250 Hz 之外为 inf。"""
    model = json.loads(MODEL.read_bytes().decode("utf-8"))
    h = np.asarray(model["coefficients_q20"], dtype=float) / (1 << 20)
    freqs = np.arange(NFFT // 2 + 1) * FS / NFFT
    w = 2 * np.pi * freqs / FS
    g = 10 ** (gain_db / 20)
    den = np.abs(1 + g * np.fft.rfft(h, NFFT) * np.exp(-3j * w))
    sel = (freqs >= 300) & (freqs <= 10250)
    return freqs, np.where(sel, den, np.inf)


class ResidualHeadroomTest(unittest.TestCase):
    def test_worst_case_denominator_at_minus_8_db(self):
        freqs, den = ps_denominator(-8.0)
        k = int(np.argmin(den))
        self.assertAlmostEqual(den[k], 0.544, places=3)
        self.assertTrue(390.0 <= freqs[k] <= 401.0, f"最差点应在 390–401 Hz，实际 {freqs[k]:.1f}")
        self.assertAlmostEqual(1 / den[k], 1.84, places=2)   # 残差/麦克风

    def test_gate_leaves_less_than_one_db_of_margin(self):
        _f, den = ps_denominator(-8.0)
        gate_peak = 10 ** (-6 / 20)          # 现场门限：麦克风峰值 < −6 dBFS
        worst = gate_peak / den.min()        # 门限内残差峰值 / 满幅
        self.assertLess(worst, 1.0, "门限内应当还没越界，否则门限本身失效")
        self.assertGreater(worst, 0.85, "但余量不到 1 dB —— 这就是缺陷，别把它当偶发")
        margin_db = -20 * np.log10(worst)
        self.assertLess(margin_db, 1.0)

    def test_wide_residual_never_overflows_output_at_minus_8_db(self):
        _f, den = ps_denominator(-8.0)
        g = 10 ** (-8 / 20)
        out_over_mic = g / den.min()
        self.assertLess(out_over_mic, 1.0,
                        "宽残差下 −8 dB 的输出/麦克风上界必须 < 1，方案才成立")
        # 麦克风满幅也不越界
        self.assertLess(out_over_mic * 1.0, 1.0)

    def test_minus_6_db_needs_an_input_bound(self):
        _f, den = ps_denominator(-6.0)
        g = 10 ** (-6 / 20)
        out_over_mic = g / den.min()
        self.assertGreater(out_over_mic, 1.0, "−6 dB 档不能无条件保证，必须同时限制输入")
        # 但门限内的输入仍然安全
        self.assertLess(out_over_mic * 10 ** (-6 / 20), 1.0)

    def test_zero_model_is_exactly_unity(self):
        """Ĥ ≡ 0 时余量比值恒为 1：这正是零系数臂不受本次改动影响的原因。"""
        h = np.zeros(512)
        w = 2 * np.pi * np.arange(NFFT // 2 + 1) / NFFT
        den = np.abs(1 + 0.398 * np.fft.rfft(h, NFFT) * np.exp(-3j * w))
        self.assertTrue(np.allclose(den, 1.0))


if __name__ == "__main__":
    unittest.main()
