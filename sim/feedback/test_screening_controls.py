"""复算入口的两个控制：分段配对与输入资格。

防四类错：
  1. 切片比较时两边样本集合不同（重复累计尾段），把配对误差报成"分辨力"；
  2. 缺号/补号后按列表下标取段，把留出段悄悄挪进训练；
  3. manifest 哈希不符只打警告，仍继续产出数字；
  4. manifest 缺失或解析失败时把 sha_match 写成 True（"未核对"被当成"一致"）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import reproduce_b_screening as rbs  # noqa: E402


def synth(n=1024, taps=64, seed=0):
    rng = np.random.default_rng(seed)
    u = rng.standard_normal(n)
    h = np.zeros(taps)
    h[0], h[7], h[taps - 1] = 0.5, -0.2, 0.05
    m = np.convolve(u, h)[:n] + 0.01 * rng.standard_normal(n)
    return u, m, h


class SplitPairingTest(unittest.TestCase):
    def test_paired_frames_are_bit_identical_with_whole_run(self):
        """每片都有 >= taps 帧历史时，逐片复位与整条跑在配对帧上完全相同。"""
        u, m, h = synth(n=1024, taps=64)
        out = rbs.split_pairing_control(h, u, m, taps=64, pieces=8)
        self.assertEqual(out["frames"]["paired"], 8 * (128 - 64))
        self.assertEqual(out["max_abs_diff"], 0.0)
        self.assertAlmostEqual(out["rms_delta_db"], 0.0, places=9)

    def test_short_pieces_are_dropped_and_reported(self):
        """片长 <= taps 的片没有段内历史，必须两边同时剔除并如实报出。"""
        u, m, h = synth(n=256, taps=64)
        out = rbs.split_pairing_control(h, u, m, taps=64, pieces=8)
        self.assertEqual(len(out["dropped_pieces"]), 8)
        self.assertEqual(out["frames"]["paired"], 0)
        self.assertIsNone(out["max_abs_diff"])

    def test_frame_counts_differ_only_for_window_variant(self):
        """不同样本集合的差只能记在 window_only_delta_db，配对差必须是 0。"""
        u, m, h = synth(n=2048, taps=128, seed=3)
        out = rbs.split_pairing_control(h, u, m, taps=128, pieces=4)
        self.assertEqual(out["frames"]["whole"], 2048 - 128)
        self.assertEqual(out["frames"]["piece"], 4 * (512 - 128))
        self.assertNotEqual(out["frames"]["whole"], out["frames"]["piece"])
        self.assertAlmostEqual(out["rms_delta_db"], 0.0, places=9)
        self.assertIsNotNone(out["window_only_delta_db"])


class InputQualificationTest(unittest.TestCase):
    def paths(self, ids):
        return ["/x/seg_%d.npz" % i for i in ids]

    def test_missing_id_stops_instead_of_shifting_by_index(self):
        """缺 seg_5、补 seg_16（总数仍是 16）：必须报缺号，且 seg_10 不能进训练。"""
        ids = [i for i in range(16) if i != 5] + [16]
        res = rbs.resolve_segment_ids(self.paths(ids), list(range(10)), list(range(10, 16)))
        self.assertEqual(res["missing"], [5])
        self.assertEqual(res["unexpected"], [16])
        self.assertTrue(res["failures"])
        self.assertEqual([rbs.parse_seg_id(p) for p in res["train"]],
                         [i for i in range(10) if i != 5])
        self.assertNotIn(10, [rbs.parse_seg_id(p) for p in res["train"]])

    def test_duplicate_id_is_failure(self):
        ids = list(range(10)) + [4]
        res = rbs.resolve_segment_ids(self.paths(ids), list(range(6)), list(range(6, 10)))
        self.assertEqual(res["duplicates"], [4])
        self.assertTrue(any("重号" in f for f in res["failures"]))

    def test_overlapping_train_and_valid_is_failure(self):
        res = rbs.resolve_segment_ids(self.paths(range(10)), list(range(8)), list(range(6, 10)))
        self.assertTrue(any("重叠" in f for f in res["failures"]))

    def test_clean_set_has_no_failures(self):
        res = rbs.resolve_segment_ids(self.paths(range(16)), list(range(10)), list(range(10, 16)))
        self.assertEqual(res["failures"], [])
        self.assertEqual(len(res["train"]), 10)
        self.assertEqual(len(res["valid"]), 6)
        self.assertEqual(res["unexpected"], [])


class ManifestQualificationTest(unittest.TestCase):
    def test_missing_manifest_maps_to_none_not_true(self):
        """清单缺失 → 映射为 None；调用方据此写 sha_match=None（未核对），不是 True。"""
        man, status = rbs.load_manifest_hashes("/definitely/not/here/manifest.json")
        self.assertIsNone(man)
        self.assertIn("缺失", status)

    def test_broken_manifest_maps_to_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text("{not json", encoding="utf-8")
            man, status = rbs.load_manifest_hashes(p)
            self.assertIsNone(man)
            self.assertIn("解析失败", status)

    def test_manifest_without_files_list_maps_to_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps({"package": "x"}), encoding="utf-8")
            man, status = rbs.load_manifest_hashes(p)
            self.assertIsNone(man)
            self.assertIn("无 files", status)

    def test_manifest_hashes_are_read_by_basename(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps({"files": [
                {"path": "lowband2/seg_3.npz", "sha256": "a" * 64},
                {"path": "seg_4.npz", "sha256": "b" * 64},
            ]}), encoding="utf-8")
            man, status = rbs.load_manifest_hashes(p)
            self.assertEqual(man, {"seg_3.npz": "a" * 64, "seg_4.npz": "b" * 64})
            self.assertIn("已读取 2 条", status)


if __name__ == "__main__":
    unittest.main()
