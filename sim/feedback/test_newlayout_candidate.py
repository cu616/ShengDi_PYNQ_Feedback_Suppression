"""新布局候选的登记一致性：模型文件、清单条目、Q20 身份三者必须互相对得上。

这条正是之前出问题的缺口——板上跑的那套系数不在登记里，谁都无法从仓库判断它属于哪个场景。
三个测试分别钉住：文件身份、系数身份、能不能装进当前帧预算。
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_peak_margin import q20_sha256  # noqa: E402

MODEL_REL = "room_v1/newlayout_512_20261026.json"


def load():
    model_path = ROOT / "models" / MODEL_REL
    manifest = json.loads((ROOT / "models/manifest.json").read_bytes().decode("utf-8"))
    entry = next((m for m in manifest["models"] if m["file"] == MODEL_REL), None)
    model = json.loads(model_path.read_bytes().decode("utf-8"))
    return model_path, model, entry, manifest


class RegistryIdentityTest(unittest.TestCase):
    def test_entry_exists_and_file_sha_matches(self):
        path, model, entry, _manifest = load()
        self.assertIsNotNone(entry, "候选未登记进 models/manifest.json 的 models 数组")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(entry["sha256"], digest)
        self.assertEqual(entry["bytes"], path.stat().st_size)

    def test_metadata_and_q20_identity_agree(self):
        _path, model, entry, manifest = load()
        for field in ("taps", "lag_first", "sample_rate_hz", "fixture_id", "hp_volume"):
            self.assertEqual(model[field], entry[field], field)
        self.assertEqual(model["taps"], len(model["coefficients"]))
        self.assertEqual(model["taps"], len(model["coefficients_q20"]))
        self.assertEqual(model["coefficient_format"], "signed24_fraction20")
        self.assertEqual(model["lag_first"], 1)
        self.assertEqual(model["sample_rate_hz"], manifest["sample_rate_hz"])
        # fixture 必须是新布局自己的编号，不能沿用旧夹具
        self.assertEqual(model["fixture_id"], "room_v1_20261026")
        self.assertEqual(q20_sha256(model["coefficients_q20"]), entry["coefficients_sha256"])

    def test_q20_range_matches_float_and_fits_frame_budget(self):
        _path, model, entry, manifest = load()
        q20 = np.asarray([int(v) for v in model["coefficients_q20"]], dtype=np.int64)
        self.assertTrue(np.all(q20 >= -(1 << 23)))
        self.assertTrue(np.all(q20 <= (1 << 23) - 1))
        reencoded = q20.astype(float) / (1 << 20)
        delta = np.max(np.abs(np.asarray(model["coefficients"], float) - reencoded))
        self.assertLess(delta, 1e-6)
        self.assertAlmostEqual(delta, entry["float_q20_maxdiff"], places=15)
        self.assertEqual(int(np.max(np.abs(q20))), entry["q20_max_abs"])
        self.assertEqual(int(np.sum(np.abs(q20))), entry["l1_q20"])
        cycles = 3 * model["taps"] + 3
        self.assertEqual(cycles, entry["frames_needed_3N_plus_3"])
        self.assertLessEqual(cycles, manifest["frame_budget_cycles"])


if __name__ == "__main__":
    unittest.main()
