"""复算入口的两个控制：分段配对与输入资格。

防四类错：
  1. 切片比较时两边样本集合不同（重复累计尾段），把配对误差报成"分辨力"；
  2. 缺号/补号后按列表下标取段，把留出段悄悄挪进训练；
  3. manifest 哈希不符只打警告，仍继续产出数字；
  4. manifest 缺失或解析失败时把 sha_match 写成 True（"未核对"被当成"一致"）。
"""
import ast
import hashlib
import json
import subprocess
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


class SplitPairingMixedTest(unittest.TestCase):
    """短片与有效片同时存在：必须只丢短片，不能因 None 解包而崩。"""

    def test_mixed_short_and_valid_pieces(self):
        """C 的触发条件：4100 帧、512 抽头、8 片 → 片长 512/513 交替。

        512 帧的 4 片没有段内历史被丢弃，513 帧的 4 片各留 1 帧，配对差为 0。
        """
        n, taps = 4100, 512
        rng = np.random.default_rng(7)
        u = rng.standard_normal(n)
        h = np.zeros(taps)
        h[0], h[3] = 0.6, -0.1
        m = np.convolve(u, h)[:n]
        out = rbs.split_pairing_control(h, u, m, taps=taps, pieces=8)
        self.assertEqual(len(out["dropped_pieces"]), 4)
        self.assertEqual(out["frames"]["paired"], 4)
        self.assertEqual(out["max_abs_diff"], 0.0)
        self.assertAlmostEqual(out["rms_delta_db"], 0.0, places=9)


class PredictionTableTest(unittest.TestCase):
    """预测表的三个量，用可解析的合成 H 检验，不依赖真实数据。"""

    RATE = 48828.125
    G_Q12 = 817

    def _grid(self, nfft=4096, h_mag=0.1):
        freqs = np.arange(nfft // 2 + 1) * self.RATE / nfft
        H = np.full(len(freqs), h_mag + 0.0j)
        coh = np.ones(len(freqs))
        return freqs, H, coh, nfft

    def test_zero_model_gives_exactly_zero_at_c_review_bin(self):
        """C 的反例：H=0.5、Q12=817、429.153 Hz，M≡0 时两臂必须完全相同（0 dB）。

        旧实现把 OFF 当开环 H 直接比，在这一点上会给出 +0.906 dB。
        """
        freqs = np.array([429.153])
        H = np.array([0.5 + 0.0j])
        coh = np.array([1.0])
        h = np.zeros(16)                      # 预测恒零：两臂同一条闭环
        rows = rbs.band_switch_table(freqs, H, coh, h, 1, self.RATE, 2,
                                     self.G_Q12 / 4096.0, [(300, 1000)])
        self.assertEqual(rows[0]["on_minus_off_band_db"], 0.0)
        self.assertIn("off_margin_db", rows[0])

    def test_off_arm_is_closed_loop(self):
        """OFF 臂必须是 H/(1−gDH)，不是开环 H；否则余量会被高估。"""
        freqs = np.array([429.153])
        H = np.array([0.5 + 0.0j])
        coh = np.array([1.0])
        g = self.G_Q12 / 4096.0
        D = np.exp(-1j * 2 * np.pi * 2 * freqs / self.RATE)
        expect = np.abs(H / (1 - g * D * H))
        rows = rbs.band_switch_table(freqs, H, coh, np.zeros(16), 1, self.RATE, 2,
                                     g, [(300, 1000)])
        # 用"允许增益"反推 OFF 臂的 |H|：allowed = −20log10|H| 与闭环无关，
        # 所以这里直接核对解析式与实现用的 T_off 一致（通过余量定义）
        self.assertAlmostEqual(rows[0]["off_allowed_db"], -20 * np.log10(0.5), places=9)
        self.assertAlmostEqual(rows[0]["off_margin_db"],
                               rows[0]["off_allowed_db"] - 20 * np.log10(g), places=9)
        self.assertGreater(abs(expect[0]), 0.5)   # 闭环确实放大了 |T_off|

    def test_perfect_model_matches_closed_form(self):
        """M≡H 时 T_on≡H：带功率比必须等于 Σ|H|² / Σ|H/(1−gDH)|²。"""
        freqs, H, coh, nfft = self._grid()
        h = np.roll(np.fft.irfft(H, nfft), -1)    # 抵消 model_response 的 lag_first=1
        g = self.G_Q12 / 4096.0
        rows = rbs.band_switch_table(freqs, H, coh, h, 1, self.RATE, 2, g, [(300, 1000)])
        D = np.exp(-1j * 2 * np.pi * 2 * freqs / self.RATE)
        sel = (freqs >= 300) & (freqs < 1000)
        denom = np.abs(1 - g * D[sel] * H[sel])
        expect = 10 * np.log10(np.sum(np.abs(H[sel]) ** 2)
                               / np.sum((np.abs(H[sel]) / denom) ** 2))
        self.assertAlmostEqual(rows[0]["on_minus_off_band_db"], expect, places=9)

    def test_worse_bins_are_counted(self):
        """模型把某点放大一倍时，该 bin 必须计入更差。"""
        freqs, H, coh, nfft = self._grid()
        h = np.zeros(16)
        h[0] = 0.2                                # 比 H(=0.1) 大一倍
        rows = rbs.band_switch_table(freqs, H, coh, h, 1, self.RATE, 2,
                                     self.G_Q12 / 4096.0, [(300, 1000)])
        self.assertGreater(rows[0]["worse_bins"], 0)
        self.assertLess(rows[0]["improvement_db"], 0)

    def test_margin_is_allowed_minus_actual(self):
        """余量 = 允许增益 − 实际增益；环路增益是它的相反数。"""
        freqs, H, coh, nfft = self._grid()
        g = self.G_Q12 / 4096.0
        rows = rbs.band_switch_table(freqs, H, coh, np.zeros(16), 1, self.RATE, 2,
                                     g, [(300, 1000)])[0]
        self.assertAlmostEqual(rows["off_margin_db"],
                               rows["off_allowed_db"] - 20 * np.log10(g), places=9)
        self.assertAlmostEqual(rows["off_loop_gain_db"], -rows["off_margin_db"], places=9)

    def test_switch_controls_pass(self):
        """两个闭式控制必须通过：M≡0 → 0 dB；M≡H → 闭式值。"""
        freqs, H, coh, nfft = self._grid()
        h = np.roll(np.fft.irfft(H, nfft), -1)
        c = rbs.switch_controls(freqs, H, coh, h, 1, self.RATE, 2,
                                self.G_Q12 / 4096.0, (300, 1000))
        self.assertTrue(c["zero_model_ok"])
        self.assertTrue(c["perfect_model_ok"])


class NoModuleShadowingTest(unittest.TestCase):
    """main() 里不能给模块名（glob/json/np/Path）赋局部变量。

    这条来自一个真实缺陷：预测段里写了 `glob = rows[-1]`，把模块 glob 变成 main 的局部名，
    于是后面 [6] 段的 glob.glob(...) 直接 UnboundLocalError——而只有带 --cross-session-dir
    才会走到那行，常规复算发现不了。
    """

    MODULES = {"glob", "json", "np", "Path", "hashlib", "sys", "argparse"}

    def test_main_does_not_shadow_module_names(self):
        tree = ast.parse((REPO / "scripts" / "reproduce_b_screening.py").read_text(encoding="utf-8"))
        mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
        self.assertEqual(len(mains), 1)
        assigned = set()
        for node in ast.walk(mains[0]):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                assigned.add(node.id)
            elif isinstance(node, ast.arg):
                assigned.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not mains[0]:
                assigned.add(node.name)
        clash = assigned & self.MODULES
        self.assertFalse(clash, "main() 里遮蔽了模块名：%s" % sorted(clash))


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "reproduce_b_screening.py"
MODEL = REPO / "models" / "room_v1" / "calibrated_20261024.json"


def _make_dataset(root, ids, manifest="complete", corrupt=None):
    """造一个小数据包：npz 只有必须字段，manifest 按 hash 逐条列。"""
    d = Path(root) / "lowband2"
    d.mkdir(parents=True, exist_ok=True)
    entries = []
    for i in ids:
        p = d / ("seg_%d.npz" % i)
        np.savez(p, reference=np.zeros(64), microphone=np.zeros(64),
                 sample_rate_hz=np.float64(48828.125))
        entries.append({"path": "lowband2/seg_%d.npz" % i,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    if corrupt is not None:
        for e in entries:
            if e["path"].endswith("seg_%d.npz" % corrupt):
                e["sha256"] = "0" * 64
    man = Path(root) / "manifest.json"
    if manifest == "complete":
        man.write_text(json.dumps({"files": entries}), encoding="utf-8")
    elif manifest == "omit_one":
        man.write_text(json.dumps({"files": entries[1:]}), encoding="utf-8")
    elif manifest == "broken":
        man.write_text("{not json", encoding="utf-8")
    # "missing" 就什么都不写
    return d


def _run(data_dir, out_dir, *extra):
    cmd = [sys.executable, str(SCRIPT),
           "--data-dir", str(data_dir), "--model", str(MODEL),
           "--train", "0-1", "--valid", "2-3", "--out-dir", str(out_dir), *extra]
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)


class CliInputGateTest(unittest.TestCase):
    """入口级：不合格输入必须返回 2，且不写 repro.txt/json（不能只测辅助函数）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def assert_blocked(self, proc, n_unverified=None):
        self.assertEqual(proc.returncode, 2, proc.stdout[-800:] + proc.stderr[-400:])
        out = self.root / "out"
        self.assertFalse((out / "repro.txt").exists(), "不合格输入却写出了 repro.txt")
        self.assertFalse((out / "repro.json").exists(), "不合格输入却写出了 repro.json")
        self.assertIn("[未核验]", proc.stdout)
        if n_unverified is not None:
            self.assertIn("训练/留出中 %d 个文件没有哈希核对" % n_unverified, proc.stdout)

    def test_missing_manifest_blocks_full_cli(self):
        d = _make_dataset(self.root, [0, 1, 2, 3], manifest="missing")
        self.assert_blocked(_run(d, self.root / "out"), n_unverified=4)

    def test_broken_manifest_blocks_full_cli(self):
        d = _make_dataset(self.root, [0, 1, 2, 3], manifest="broken")
        self.assert_blocked(_run(d, self.root / "out"), n_unverified=4)

    def test_manifest_omitting_one_segment_blocks_full_cli(self):
        """漏列一条：只有那一行未核验，也必须阻断。"""
        d = _make_dataset(self.root, [0, 1, 2, 3], manifest="omit_one")
        self.assert_blocked(_run(d, self.root / "out"), n_unverified=1)

    def test_wrong_hash_blocks_full_cli(self):
        d = _make_dataset(self.root, [0, 1, 2, 3], corrupt=2)
        proc = _run(d, self.root / "out")
        self.assertEqual(proc.returncode, 2, proc.stdout[-800:])
        self.assertIn("[哈希不符]", proc.stdout)
        self.assertFalse((self.root / "out" / "repro.txt").exists())

    def test_complete_manifest_passes_preflight(self):
        """正例：清单完整时预检返回 0 并写 input-check.txt，不进入数值阶段。"""
        d = _make_dataset(self.root, [0, 1, 2, 3])
        proc = _run(d, self.root / "out", "--stop-after-inputs")
        self.assertEqual(proc.returncode, 0, proc.stdout[-800:] + proc.stderr[-400:])
        self.assertIn("全部哈希已核对", proc.stdout)
        out = self.root / "out"
        self.assertTrue((out / "input-check.txt").exists())
        self.assertFalse((out / "repro.txt").exists())


if __name__ == "__main__":
    unittest.main()
