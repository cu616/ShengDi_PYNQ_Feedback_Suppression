import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("residual_tools", ROOT / "board/audio_residual/residual_tools.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class ResidualChecks(unittest.TestCase):
    def test_hand_calculated_half_and_shift_mismatch(self):
        q = np.zeros(256, dtype=np.int64); q[0] = 2**19
        raw = np.zeros((1024, 4), dtype=np.int64)
        raw[:, 0] = np.resize([3, -3, 7, -7], 1024)
        pred = np.r_[0, np.resize([2, -2, 4, -4], 1024)[:-1]]
        raw[:, 1] = pred + 10; raw[:, 2] = pred; raw[:, 3] = 10
        result = tools.verify_residual(raw, q, 0.)
        self.assertTrue(result["bit_exact"])
        raw[:, 2] = np.roll(pred, 1)
        result = tools.verify_residual(raw, q, 0.)
        self.assertFalse(result["bit_exact"])
        self.assertIsNone(result["prediction_reduction_db"])

    def test_candidate_rejects_wrong_fixture_and_quantization(self):
        m = dict(taps=256, lag_first=1, coefficient_format="signed24_fraction20",
                 training_source="board", fixture_id="box", hp_volume=40,
                 sample_rate_hz=48828.125, coefficients=[.5]+[0]*255,
                 coefficients_q20=[2**19]+[0]*255, bias=0)
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as d:
            p = Path(d)/"model.json"; p.write_text(json.dumps(m))
            tools.load_candidate(p,"box",40,48828.125)
            with self.assertRaises(ValueError): tools.load_candidate(p,"other",40,48828.125)
            m["coefficients_q20"][0] += 1; p.write_text(json.dumps(m))
            with self.assertRaises(ValueError): tools.load_candidate(p,"box",40,48828.125)

    def test_invalid_pcm_rejected(self):
        with self.assertRaises(ValueError):
            tools.verify_residual(np.full((300,4),2**23,dtype=np.int64),np.zeros(256,dtype=np.int64),0)


if __name__ == "__main__": unittest.main()
