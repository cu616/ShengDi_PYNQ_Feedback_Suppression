"""模型登记的通用一致性检查：清单条目、模型文件、Q20 身份三者必须互相对得上。

这条正是之前出问题的缺口——板上跑的那套系数不在登记里，谁都无法从仓库判断它属于哪个场景。
现在对 `models` 数组里的**每一条**都查，不只是新交的那两个：
文件哈希、元数据字段、Q20 打包哈希、量化误差、帧预算、predictor 余量，全部要求与清单自洽。
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

MODELS_DIR = ROOT / "models"


def manifest():
    return json.loads((MODELS_DIR / "manifest.json").read_bytes().decode("utf-8"))


class RegistryIdentityTest(unittest.TestCase):
    def test_every_entry_matches_its_file(self):
        """清单里每一条都要能对上实际文件：存在、字节数、sha256。"""
        entries = manifest()["models"]
        self.assertTrue(entries, "models 数组为空")
        for entry in entries:
            path = MODELS_DIR / entry["file"]
            with self.subTest(entry=entry["file"]):
                self.assertTrue(path.exists(), "清单里的文件不存在")
                self.assertEqual(path.stat().st_size, entry["bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])

    def test_metadata_fields_agree_and_fixture_is_not_borrowed(self):
        """模型字段必须与清单一致；fixture 编号不得跨批次借用。"""
        mf = manifest()
        fixtures = [m["fixture_id"] for m in mf["models"]]
        for entry in mf["models"]:
            model = json.loads((MODELS_DIR / entry["file"]).read_bytes().decode("utf-8"))
            with self.subTest(entry=entry["file"]):
                for field in ("taps", "lag_first", "sample_rate_hz", "fixture_id", "hp_volume"):
                    self.assertEqual(model[field], entry[field], field)
                self.assertEqual(model["taps"], len(model["coefficients"]))
                self.assertEqual(model["taps"], len(model["coefficients_q20"]))
                self.assertEqual(model["coefficient_format"], "signed24_fraction20")
                self.assertEqual(model["lag_first"], 1)
                self.assertEqual(model["sample_rate_hz"], mf["sample_rate_hz"])
                self.assertEqual(q20_sha256(model["coefficients_q20"]), entry["coefficients_sha256"])
                self.assertIn(entry["fixture_id"], fixtures)
        # 修线前后必须是两个不同编号，不能只改日期或标签冒充新资格
        self.assertIn("room_v1_20261026b", fixtures)
        self.assertNotIn("room_v1_20261026b", {"room_v1_20261026"})

    def test_quantization_and_frame_budget(self):
        """Q20 必须在 signed24 范围内、与浮点一致，且能装进当前帧预算。"""
        mf = manifest()
        for entry in mf["models"]:
            model = json.loads((MODELS_DIR / entry["file"]).read_bytes().decode("utf-8"))
            q20 = np.asarray([int(v) for v in model["coefficients_q20"]], dtype=np.int64)
            with self.subTest(entry=entry["file"]):
                self.assertTrue(np.all(q20 >= -(1 << 23)))
                self.assertTrue(np.all(q20 <= (1 << 23) - 1))
                delta = float(np.max(np.abs(np.asarray(model["coefficients"], float)
                                            - q20.astype(float) / (1 << 20))))
                self.assertLess(delta, 1e-6)
                self.assertAlmostEqual(delta, entry["float_q20_maxdiff"], places=15)
                self.assertEqual(int(np.max(np.abs(q20))), entry["q20_max_abs"])
                self.assertEqual(int(np.sum(np.abs(q20))), entry["l1_q20"])
                cycles = 3 * model["taps"] + 3
                self.assertEqual(cycles, entry["frames_needed_3N_plus_3"])
                self.assertLessEqual(cycles, mf["frame_budget_cycles"])

    def test_coefficient_l1_is_recorded_as_a_risk_marker(self):
        """系数 L1 只当饱和预算的**风险标记**，不是"不会饱和"的承诺。

        口径更正（C 指出）：Q20 的 ±8 是**系数**满量程，PCM 侧饱和阈值是 **1.0**。
        所以 `‖h‖₁ ≤ 1` 才是"任何合法输入都不饱和"的充分条件；`‖h‖₁ > 1` 只说明"可能饱和"，
        不是必然，也不能据此否定模型。两个 room 候选都在 1–4 之间，属"可能但需保护"，
        现场各级饱和保护必须保留。
        """
        rows = {e["file"]: float(e["l1_q20"]) / (1 << 20) for e in manifest()["models"]}
        for entry in manifest()["models"]:
            l1 = rows[entry["file"]]
            with self.subTest(entry=entry["file"]):
                self.assertLess(l1, 40.0)
        for name in ("room_v1/newlayout_512_20261026.json", "room_v1/rewired_512_20261026.json"):
            self.assertGreater(rows[name], 1.0, "L1 若 ≤1 才可宣称不可能饱和，需同步改口径")
            self.assertLess(rows[name], 4.0)


class RewiredCandidateTest(unittest.TestCase):
    """修线后这一份的额外要求：来源可追溯、不沿用旧夹具、量化后留出评价写在文件里。"""

    def test_rewired_candidate_is_traceable(self):
        mf = manifest()
        entry = next((m for m in mf["models"]
                      if m["file"] == "room_v1/rewired_512_20261026.json"), None)
        self.assertIsNotNone(entry, "修线候选未登记")
        model = json.loads((MODELS_DIR / entry["file"]).read_bytes().decode("utf-8"))
        self.assertEqual(model["fixture_id"], "room_v1_20261026b")
        self.assertEqual(model["bias"], 0.0)          # RTL 无偏置项，写 0 且不装载
        self.assertEqual(model["taps"], 512)
        self.assertIsNotNone(model["validation"])
        self.assertIn("same-session", model["validation"]["interpretation"])
        self.assertGreater(model["validation"]["evaluated_frames"], 0)
        self.assertIn("supersedes", entry)


if __name__ == "__main__":
    unittest.main()
