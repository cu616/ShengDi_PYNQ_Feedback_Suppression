"""Known synthetic paths and hand-calculated integer cases, no hardware."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from feedback.calibration import (Capture, fit_path, predict, evaluate_path,
                                  quantize_coefficients, fixed_fir, save_capture,
                                  load_capture, export_model)


def fixture(seed=1, h=None, noise=0.0, frames=4096):
    if h is None:
        h = np.r_[np.zeros(7), 0.42, -0.18, 0.09, np.zeros(22)]
    rng = np.random.default_rng(seed)
    u = rng.uniform(-0.15, 0.15, frames)
    # Independent direct convolution with an explicit leading causal delay.
    y = np.convolve(u, np.r_[0, h])[:frames] + 0.012
    y += rng.normal(0, noise, frames)
    return Capture(u, y, 48828.125,
                   {"schema_version": 1, "capture_id": "synthetic-%d" % seed,
                    "source": "synthetic", "forward_path_open": True,
                    "alignment": "same_i2s_frame", "dropped_frames": 0})


class CalibrationTests(unittest.TestCase):
    def test_hand_calculated_causality(self):
        np.testing.assert_array_equal(predict([2, 4, 8, 0], [0.5, -0.25]), [0, 1, 1.5, 3])

    def test_recover_delayed_path_and_bias(self):
        train = fixture()
        model = fit_path(train, 32, ridge=0)
        expected = np.r_[np.zeros(7), 0.42, -0.18, 0.09, np.zeros(22)]
        np.testing.assert_allclose(model["coefficients"], expected, atol=1e-12)
        self.assertAlmostEqual(model["bias"], 0.012, places=12)
        metrics = evaluate_path(model, fixture(2), train)
        self.assertLess(metrics["residual_rms"], 1e-12)

    def test_noise_and_changed_path(self):
        train = fixture(noise=0.0002)
        model = fit_path(train, 32)
        good = evaluate_path(model, fixture(2, noise=0.0002), train)
        bad = evaluate_path(model, fixture(3, h=-np.asarray(model["coefficients"])), train)
        self.assertGreater(good["prediction_reduction_db"], 35)
        self.assertLess(bad["prediction_reduction_db"], 0)

    def test_reject_single_tone_and_silence(self):
        for u in (np.zeros(4096), 0.1 * np.sin(np.arange(4096) * 0.13)):
            capture = fixture()
            capture.reference = u
            with self.assertRaisesRegex(ValueError, "excitation"):
                fit_path(capture, 32)

    def test_data_contract_failures(self):
        for key, value in (("dropped_frames", 1), ("forward_path_open", False),
                           ("alignment", "unknown"), ("source", "unknown")):
            c = fixture()
            c.metadata[key] = value
            with self.assertRaises(ValueError):
                fit_path(c, 32)
        for value in (np.nan, 1.0, -1.0):
            c = fixture()
            c.microphone[10] = value
            with self.assertRaises(ValueError):
                fit_path(c, 32)

    def test_reject_reused_validation_and_wrong_rate(self):
        train = fixture()
        model = fit_path(train, 32)
        with self.assertRaises(ValueError):
            evaluate_path(model, train, train)
        repeated = fixture()
        repeated.metadata["capture_id"] = "renamed"
        with self.assertRaises(ValueError):
            evaluate_path(model, repeated, train)
        wrong_rate = fixture(2)
        wrong_rate.sample_rate_hz = 48000
        with self.assertRaises(ValueError):
            evaluate_path(model, wrong_rate, train)

    def test_integer_rounding_and_saturation(self):
        result, clips = fixed_fir([1, -1, 3, -3, 0], [1 << 19])
        np.testing.assert_array_equal(result, [0, 1, -1, 2, -2])
        self.assertEqual(clips, 0)
        result, clips = fixed_fir([(1 << 23) - 1, -(1 << 23), 0], [2 << 20])
        np.testing.assert_array_equal(result, [0, (1 << 23) - 1, -(1 << 23)])
        self.assertEqual(clips, 2)
        with self.assertRaises(ValueError):
            quantize_coefficients([8.0])

    def test_board_gain_and_fixture_must_match(self):
        train, validation = fixture(), fixture(2)
        for c in (train, validation):
            c.metadata.update(source="board", fixture_id="synthetic-test-fixture", hp_volume=40)
        model = fit_path(train, 32)
        for key, value in (("fixture_id", "changed"), ("hp_volume", 30)):
            original = validation.metadata[key]
            validation.metadata[key] = value
            with self.assertRaises(ValueError):
                evaluate_path(model, validation, train)
            validation.metadata[key] = original

    def test_quantized_fir_against_float(self):
        rng = np.random.default_rng(4)
        u = rng.integers(-20000, 20000, 512)
        h = [0.0, 0.5, -0.25, 0.125]
        result, clips = fixed_fir(u, quantize_coefficients(h))
        expected = np.convolve(u, [0, *h])[:len(u)]
        self.assertLessEqual(float(np.max(np.abs(result - expected))), 0.5)
        self.assertEqual(clips, 0)

    def test_npz_and_model_round_trip(self):
        temporary_root = Path(__file__).resolve().parents[2] / "tmp"
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root, prefix="calibration-test-") as d:
            p = Path(d) / "capture.npz"
            save_capture(p, fixture())
            train = load_capture(p)
            model = fit_path(train, 32)
            metrics = evaluate_path(model, fixture(2), train)
            output = Path(d) / "model.json"
            export_model(output, model, metrics)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["status"], "offline_candidate_not_board_validated")
            self.assertEqual(len(saved["coefficients_q20"]), 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
