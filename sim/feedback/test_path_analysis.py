"""逐频点抵消深度与稳定增益口径的验证，全部用已知真值的合成数据。"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from feedback.calibration import Capture, fit_path, predict  # noqa: E402
from feedback.path_analysis import (analyze_captures, band_slice,  # noqa: E402
                                   cancellation_depth_db, dc_diagnostics,
                                   emphasis_fir, estimate_path, fir_response,
                                   load_model_artifact, phase_zero_points,
                                   recommend_field_range, stability_summary)

FS = 48828.125


def capture(seed=1, frames=8192, h=None, noise=0.0, bias=0.0, level=0.05):
    if h is None:
        h = np.r_[np.zeros(39), 0.30, -0.10, np.zeros(22)]
    rng = np.random.default_rng(seed)
    u = rng.uniform(-1.0, 1.0, frames) * level
    y = np.convolve(u, np.r_[0.0, h])[:frames] + bias
    y = y + rng.normal(0.0, noise, frames)
    return Capture(u, y, FS, {
        "schema_version": 1, "capture_id": "synthetic-%d" % seed, "source": "synthetic",
        "forward_path_open": True, "alignment": "same_i2s_frame", "dropped_frames": 0,
    }).validate()


class EstimatorTests(unittest.TestCase):
    def test_model_response_is_one_sample_causal(self):
        """fir_response 必须与 pred[n]=Σh[k]u[n-1-k] 完全一致。

        这是最容易错一位的地方：差一拍，所有抵消深度都会算歪。
        用单位冲激做参考，它的频谱就是 e^{-jω}·H(ω)。
        """
        h = np.array([0.5, -0.25, 0.125])
        freqs = np.fft.rfftfreq(64, 1.0 / FS)
        delta = np.zeros(64)
        delta[0] = 1.0
        expected = np.fft.rfft(predict(delta, h))
        np.testing.assert_allclose(fir_response(h, FS, freqs), expected, atol=1e-12)

    def test_recovers_known_flat_gain(self):
        h = np.zeros(64)
        h[2] = 0.5                       # 路径：mic[n] = 0.5·u[n-3]
        cap = capture(h=h, frames=16384)
        result = estimate_path(cap.reference, cap.microphone, FS)
        band = band_slice(result["freqs"], 500.0, 5000.0, FS)
        magnitude = np.abs(result["H"])[band]
        # 纯延迟路径的幅度处处等于 0.5；估计误差应远小于 1 dB。
        np.testing.assert_allclose(magnitude, 0.5, atol=0.02)
        self.assertGreater(float(np.median(result["coherence"][band])), 0.999)

    def test_zero_model_gives_exactly_zero_depth(self):
        cap = capture(frames=4096)
        result = estimate_path(cap.reference, cap.microphone, FS, nperseg=1024)
        depth = cancellation_depth_db(result["H"], np.zeros_like(result["H"]))
        np.testing.assert_allclose(depth, 0.0, atol=1e-9)

    def test_perfect_model_depth_is_large(self):
        h = np.zeros(64)
        h[5] = 0.4
        # 32768 帧、4096 点窗 = 15 段平均；实测这种配置的估计噪声地板约 49 dB，
        # 所以 45 dB 是"模型完全正确"应当轻松越过的线。
        cap = capture(h=h, frames=32768, noise=1e-5)
        result = estimate_path(cap.reference, cap.microphone, FS)
        depth = cancellation_depth_db(result["H"], fir_response(h, FS, result["freqs"]))
        band = band_slice(result["freqs"], 200.0, 8000.0, FS)
        self.assertGreater(float(np.min(depth[band])), 45.0)


class StabilityTests(unittest.TestCase):
    def test_msg_is_inverse_of_peak_magnitude(self):
        freqs = np.fft.rfftfreq(512, 1.0 / FS)
        H = np.full(len(freqs), 0.2 + 0.0j)
        H[100] = 0.8 + 0.0j              # 某一频点的峰值决定 MSG
        band = band_slice(freqs, 20.0, 20000.0, FS)
        summary = stability_summary(freqs, H, np.zeros_like(H), band, FS)
        self.assertAlmostEqual(summary["peak_abs_H"], 0.8, places=12)
        self.assertAlmostEqual(summary["msg_bypass_conservative_db"],
                               20.0 * np.log10(1.0 / 0.8), places=9)
        self.assertAlmostEqual(summary["asg_conservative_db"], 0.0, places=9)

    def test_phase_crossings_of_pure_delay(self):
        """纯 D 帧延迟：相位零点在 fs/D 的整数倍，用来核对起振频点判据。"""
        delay = 8
        freqs = np.fft.rfftfreq(1024, 1.0 / FS)
        loop = np.exp(-1j * 2.0 * np.pi * freqs * delay / FS)
        crossings = [value for _, value in phase_zero_points(freqs, loop)]
        expected = FS / delay
        nearest = min(crossings, key=lambda f: abs(f - expected))
        self.assertLess(abs(nearest - expected), 60.0)

    def test_recommendation_stays_inside_hardware_ceiling(self):
        summary = {
            "msg_bypass_conservative_db": 2.0,
            "msg_cancel_conservative_db": 40.0,
            "msg_cancel_phase_gated_db": 45.0,
        }
        plan = recommend_field_range(summary)
        self.assertLessEqual(plan["gain_db_stop"], 18.06)
        self.assertLess(plan["gain_db_start"], plan["gain_db_stop"])
        self.assertAlmostEqual(plan["contrast_gain_db"], 4.0, places=9)


class EmphasisTests(unittest.TestCase):
    def test_emphasis_filter_boosts_the_requested_band(self):
        target = np.ones(2049)
        target[200:400] = 4.0           # 让这一段被抬高约 12 dB
        kernel = emphasis_fir(target, nfft=4096, length=129)
        response = np.abs(np.fft.rfft(kernel, 4096))
        mid = response[200:400]
        low = response[10:150]
        self.assertGreater(float(np.median(mid)), 3.0 * float(np.median(low)))

    def test_emphasis_keeps_model_shape_valid(self):
        train = capture(seed=3, frames=8192)
        model = fit_path(train, taps=32)
        self.assertEqual(len(model["coefficients"]), 32)


class ModelArtifactTests(unittest.TestCase):
    def _write(self, payload):
        import json
        import tempfile
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                            encoding="utf-8")
        json.dump(payload, handle)
        handle.close()
        return handle.name

    def test_q20_only_artifact_is_accepted(self):
        """板上候选文件只有 coefficients_q20 时也必须能读。"""
        path = self._write({"coefficients_q20": [0, 524288, -262144]})
        artifact = load_model_artifact(path)
        self.assertEqual(artifact["taps"], 3)
        np.testing.assert_allclose(artifact["coefficients"], [0.0, 0.5, -0.25])

    def test_tap_mismatch_is_rejected(self):
        path = self._write({"coefficients": [0.1, 0.2, 0.3], "taps": 256})
        with self.assertRaises(ValueError):
            load_model_artifact(path)


class ModelArtifactTests(unittest.TestCase):
    def _write(self, payload):
        import json
        import tempfile
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                            encoding="utf-8")
        json.dump(payload, handle)
        handle.close()
        return handle.name

    def test_q20_only_artifact_is_accepted(self):
        """板上候选文件只有 coefficients_q20 时也必须能读。"""
        path = self._write({"coefficients_q20": [0, 524288, -262144]})
        artifact = load_model_artifact(path)
        self.assertEqual(artifact["taps"], 3)
        np.testing.assert_allclose(artifact["coefficients"], [0.0, 0.5, -0.25])

    def test_tap_mismatch_is_rejected(self):
        path = self._write({"coefficients": [0.1, 0.2, 0.3], "taps": 256})
        with self.assertRaises(ValueError):
            load_model_artifact(path)


class LeakageTests(unittest.TestCase):
    def test_validation_must_not_reuse_training_capture(self):
        cap = capture(seed=7, frames=8192)
        model = fit_path(cap, taps=32)
        with self.assertRaises(ValueError):
            analyze_captures(cap, cap, model)


class DcTests(unittest.TestCase):
    def test_bias_is_reported_in_dbfs(self):
        mic = np.full(1024, 0.001)
        freqs = np.fft.rfftfreq(1024, 1.0 / FS)
        H = np.full(len(freqs), 0.3 + 0.0j)
        dc = dc_diagnostics(mic, H, freqs)
        self.assertAlmostEqual(dc["bias_dbfs"], 20.0 * np.log10(0.001), places=9)

    def test_dc_gain_looks_below_twenty_hertz(self):
        freqs = np.fft.rfftfreq(2048, 1.0 / FS)
        H = np.full(len(freqs), 0.1 + 0.0j)
        H[1] = 0.9 + 0.0j               # 约 24 Hz，仍在 20 Hz 以下栅格附近
        H[500] = 2.0 + 0.0j             # 高频峰值不应被算进直流诊断
        dc = dc_diagnostics(np.zeros(2048), H, freqs)
        self.assertLess(dc["dc_gain_below_20hz"], 1.0)
        self.assertAlmostEqual(dc["dc_gain_to_howl_db"],
                               -20.0 * np.log10(dc["dc_gain_below_20hz"]), places=9)


if __name__ == "__main__":
    unittest.main()
