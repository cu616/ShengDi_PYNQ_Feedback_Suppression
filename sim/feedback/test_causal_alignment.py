"""因果约定回归测试：时域、频域、拟合必须用同一套 lag_first=1 索引。

这几个断言防的是一类具体错误：只算 FFT(h) 而不补那一帧 z⁻¹，
在 8.4 kHz 上是约 62° 相位误差，会让 CD 的符号都翻掉。
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path, history_matrix, predict  # noqa: E402
from feedback.path_analysis import fir_response  # noqa: E402

FS = 48828.125


def _h(taps, seed=3):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(taps) * 0.02


class CausalDelayTests(unittest.TestCase):
    def test_predict_delays_by_one_frame(self):
        h = _h(64)
        n0 = 40
        u = np.zeros(2048)
        u[n0] = 1.0
        p = predict(u, h)
        np.testing.assert_allclose(p[n0 + 1:n0 + 1 + len(h)], h, atol=1e-15)
        self.assertEqual(float(np.max(np.abs(p[:n0 + 1]))), 0.0)

    def test_frequency_response_matches_predict(self):
        h = _h(256)
        n = 1 << 15
        u = np.zeros(n)
        u[0] = 1.0
        ir = predict(u, h)
        freqs = np.fft.rfftfreq(n, 1.0 / FS)
        np.testing.assert_allclose(np.fft.rfft(ir), fir_response(h, FS, freqs),
                                   atol=1e-12)

    def test_missing_one_frame_is_a_large_error(self):
        """漏掉 z⁻¹ 的实现在 4 kHz 以上偏差必须显著，防止"看起来只差一点"。"""
        h = _h(256)
        freqs = np.array([4000.0, 8400.0])
        omega = 2.0 * np.pi * freqs / FS
        k = np.arange(len(h))
        correct = np.exp(-1j * np.outer(omega, k + 1.0)) @ h
        wrong = np.exp(-1j * np.outer(omega, k)) @ h
        rel = np.abs(wrong - correct) / np.abs(correct)
        self.assertGreater(float(rel.min()), 0.3)

    def test_history_matrix_first_row_uses_u_of_taps_minus_one(self):
        u = np.arange(50, dtype=float)
        row = history_matrix(u, 4)[0]
        np.testing.assert_array_equal(row, np.array([3.0, 2.0, 1.0, 0.0]))

    def test_fit_recovers_known_path_with_predict(self):
        taps = 32
        h = np.zeros(taps)
        h[2] = 0.4
        h[20] = -0.15
        rng = np.random.default_rng(9)
        u = rng.uniform(-1, 1, 6000) * 0.05
        y = predict(u, h) + rng.standard_normal(6000) * 1e-7
        md = {"schema_version": 1, "capture_id": "t", "source": "synthetic",
              "forward_path_open": True, "alignment": "same_i2s_frame",
              "dropped_frames": 0}
        model = fit_path(Capture(u, y, FS, md).validate(), taps=taps)
        np.testing.assert_allclose(model["coefficients"], h, atol=1e-5)
        self.assertEqual(model["lag_first"], 1)


if __name__ == "__main__":
    unittest.main()
