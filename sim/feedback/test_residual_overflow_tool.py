"""残差越界分析工具的边界用例：对齐 RTL 的钳位、舍入、历史前缀与身份核对。

这些用例对应 C 提的五类边界检查：
  1 合法负满幅（−2^23 不能被判成越界）
  2 负数舍入（乘增益后是半值远离零，不是向下取整）
  3 未知历史前缀（前 taps+1 帧不能当有效帧判余量/首次越界）
  4 Q20 身份（模型与抓包系数不同就必须停止归因）
  5 实际时间范围（增长窗口按真实采样率报时长，覆盖不足记未知）

另外补三类：越界个数与板上计数不符、字段缺失、文件不存在 → 必须显式失败退出。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import analyze_residual_overflow as tool  # noqa: E402

FS = 48828.125
GAIN_Q12 = 1631            # −8 dB（4096*10^(-8/20) 取整）


def candidate_q20():
    m = json.loads((REPO / "models/room_v1/rewired_512_20261026.json").read_bytes().decode("utf-8"))
    return np.asarray(m["coefficients_q20"], dtype=np.int64)


def _negative_runs(mask, min_len):
    d = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]
    return [(int(a), int(b)) for a, b in zip(starts, ends) if b - a >= min_len]


def build_fixture(tmp: Path, q20, n=2048, n_overflow=8, overflow_at="tail",
                  record_res_sat=None, name="fx.npz"):
    """造一份与 RTL 自洽的抓包：pred 由整数重放算出，宽残差与钳位残差都按 RTL 口径。

    参考用 150 Hz 低正弦：pred 会连续若干十帧同号，才能在"pred 为负"的位置造出
    宽残差越界（mic 已是 +满幅，只有 pred 为负才可能超 +满幅）。
    """
    t = np.arange(n)
    ref_float = 0.03 * np.sin(2 * np.pi * 150.0 * t / FS) + 1e-4 * np.random.default_rng(7).standard_normal(n)
    ref_codes = np.rint(ref_float * tool.SCALE).astype(np.int64)
    pred, _sat = tool.rtl_predict(q20, ref_codes)
    taps = len(q20)
    valid_start = taps + 1

    mic = np.rint(np.random.default_rng(11).standard_normal(n) * 0.02 * tool.SCALE).astype(np.int64)
    runs_all = _negative_runs(pred < -1000, n_overflow)
    if overflow_at == "tail":
        runs = [r for r in runs_all if r[0] >= valid_start]
        assert runs, "参考信号没有足够长的负段，fixture 造不出来"
        k = runs[len(runs) // 2][0]
    else:
        runs = [r for r in runs_all if r[1] <= valid_start]
        assert runs, "历史区没有足够长的负段"
        k = runs[0][0]
    mic[k:k + n_overflow] = tool.MAX24          # mic 已到 +满幅，越界只能来自 pred 为负

    wide = mic - pred
    resid = tool.clamp24(wide)
    sat = int(tool.over24(wide).sum())

    meta = {
        "schema_version": 1, "fixture_id": "fixture_test", "bypass": False,
        "gain_q12": GAIN_Q12, "first_frame": 1000, "stop_reason": "guard",
        "prediction_saturations": 0,
        "residual_saturations": sat if record_res_sat is None else record_res_sat,
        "gain_saturations": 0, "mix_saturations": 0,
        "bit_sha256": "0" * 64,
    }
    path = tmp / name
    np.savez(path, reference=ref_codes / tool.SCALE, microphone=mic / tool.SCALE,
             prediction_pcm=pred, residual_pcm=resid, coefficients_q20=q20,
             sample_rate_hz=FS, metadata_json=json.dumps(meta))
    return path, k, sat


class RailBoundaryTest(unittest.TestCase):
    def test_negative_full_scale_is_legal(self):
        x = np.array([[-tool.SCALE], [tool.MAX24], [-tool.SCALE + 1], [tool.SCALE]])
        # −2^23 合法；+2^23−1 合法；超出一格才算越界
        self.assertFalse(bool(tool.over24(x)[0, 0]))
        self.assertFalse(bool(tool.over24(x)[1, 0]))
        self.assertFalse(bool(tool.over24(x)[2, 0]))
        self.assertTrue(bool(tool.over24(x)[3, 0]))

    def test_over_both_directions(self):
        x = np.array([[tool.MAX24 + 1], [-tool.SCALE - 1]])
        self.assertTrue(bool(tool.over24(x).all()))

    def test_clamp_keeps_negative_rail(self):
        x = np.array([-tool.SCALE, tool.MAX24, tool.MAX24 + 5, -tool.SCALE - 5])
        y = tool.clamp24(x)
        self.assertEqual(int(y[0]), -tool.SCALE)
        self.assertEqual(int(y[1]), tool.MAX24)
        self.assertEqual(int(y[2]), tool.MAX24)
        self.assertEqual(int(y[3]), -tool.SCALE)


class GainRoundingTest(unittest.TestCase):
    def test_half_value_away_from_zero_negative(self):
        """RTL：(|p|+2048)>>12 再恢复符号。−2048 应得 −1，Python 向下取整会得 0。"""
        out = tool.rtl_gain(np.array([-1]), 2048)
        self.assertEqual(int(out[0]), -1)

    def test_half_value_away_from_zero_positive(self):
        out = tool.rtl_gain(np.array([1]), 2048)
        self.assertEqual(int(out[0]), 1)

    def test_sign_symmetry(self):
        x = np.array([12345, -12345, 8388607, -8388608])
        y = tool.rtl_gain(x, GAIN_Q12)
        self.assertTrue(np.array_equal(y, -tool.rtl_gain(-x, GAIN_Q12)))

    def test_floor_would_differ(self):
        """证明这里确实不是向下取整：同一组值两种算法结果不同。"""
        x = np.array([-1, -2049, -4095])
        rtl = tool.rtl_gain(x, 2048)
        floor = (x * 2048 + 2048) >> 12
        self.assertFalse(np.array_equal(rtl, floor))


class AnalyzeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q20 = candidate_q20()
        cls.tmp = Path(tempfile.mkdtemp(prefix="ro_test_"))

    def test_tail_event_is_located_and_survives_the_gain(self):
        path, k, sat = build_fixture(self.tmp, self.q20, name="tail.npz")
        self.assertEqual(sat, 8)
        r = tool.analyze(path, None, None, None)
        p = r["primary_capture_only"]
        self.assertEqual(p["overflow_samples"], 8)
        self.assertEqual(p["first_overflow_index"], k)
        self.assertEqual(p["first_overflow_global_frame"], 1000 + k)
        # 宽残差乘 −8 dB 之后不应再越界，且远低于满幅
        self.assertEqual(r["post_gain"]["overflow_samples"], 0)
        self.assertLess(r["post_gain"]["max_abs"], 0.5)
        self.assertAlmostEqual(r["post_gain"]["residual_ceiling_x"], 4096 / GAIN_Q12, places=6)
        self.assertTrue(r["attribution"]["allowed"], r["attribution"]["reasons"])

    def test_history_prefix_is_excluded(self):
        path, k, sat = build_fixture(self.tmp, self.q20, overflow_at="history", name="hist.npz")
        r = tool.analyze(path, None, None, None)
        p = r["primary_capture_only"]
        self.assertGreaterEqual(p["overflow_in_history_region"], 8)
        # 历史区里的越界不能被当成"有效窗口内的首次越界"
        self.assertEqual(p["overflow_in_valid_window"], 0)
        self.assertEqual(p["first_overflow_index"], -1)
        self.assertEqual(r["valid_start_index"], len(self.q20) + 1)

    def test_forged_counter_stops_attribution(self):
        _p0, _k0, sat = build_fixture(self.tmp, self.q20, name="forged_base.npz")
        path, _k, _sat = build_fixture(self.tmp, self.q20, record_res_sat=sat + 3, name="forged.npz")
        r = tool.analyze(path, None, None, None)
        self.assertFalse(r["attribution"]["allowed"])
        self.assertTrue(any("residual_saturations" in s for s in r["attribution"]["reasons"]))

    def test_substituted_model_stops_attribution(self):
        path, _k, _sat = build_fixture(self.tmp, self.q20, name="subst.npz")
        other = self.q20.copy()
        other[0] += 1                      # Q20 身份不同
        r = tool.analyze(path, other, "other.json", None)
        self.assertFalse(r["attribution"]["allowed"])
        self.assertTrue(r["attribution"]["model_substituted"])

    def test_growth_coverage_is_reported_in_ms(self):
        path, k, _sat = build_fixture(self.tmp, self.q20, name="grow.npz")
        r = tool.analyze(path, None, None, None)
        g = r["growth"]
        self.assertAlmostEqual(g["window_ms"], round(1000 * 256 / FS, 2), places=2)
        self.assertLess(g["covered_ms"], 100)
        self.assertIn("未知", g["note"])

    def test_valid_window_in_ms(self):
        path, _k, _sat = build_fixture(self.tmp, self.q20, name="win.npz")
        r = tool.analyze(path, None, None, None)
        expect = round(1000 * (2048 - (len(self.q20) + 1)) / FS, 2)
        self.assertAlmostEqual(r["valid_window_ms"], expect, places=2)


class FailureExitTest(unittest.TestCase):
    def test_missing_file_exits_2(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/analyze_residual_overflow.py"),
             "--npz", str(Path(tempfile.gettempdir()) / "does_not_exist_xyz.npz")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("FAILED", proc.stdout)

    def test_missing_field_exits_2(self):
        tmp = Path(tempfile.mkdtemp(prefix="ro_bad_"))
        path = tmp / "bad.npz"
        np.savez(path, reference=np.zeros(4096), microphone=np.zeros(4096),
                 sample_rate_hz=FS)          # 缺 prediction_pcm / residual_pcm / 系数 / metadata
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/analyze_residual_overflow.py"), "--npz", str(path)],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("缺必需字段", proc.stdout)

    def test_no_frames_exits_2(self):
        tmp = Path(tempfile.mkdtemp(prefix="ro_empty_"))
        q20 = candidate_q20()
        path = tmp / "empty.npz"
        np.savez(path, reference=np.zeros(0), microphone=np.zeros(0),
                 prediction_pcm=np.zeros(0, dtype=np.int64),
                 residual_pcm=np.zeros(0, dtype=np.int64), coefficients_q20=q20,
                 sample_rate_hz=FS, metadata_json=json.dumps({"gain_q12": GAIN_Q12}))
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/analyze_residual_overflow.py"), "--npz", str(path)],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
