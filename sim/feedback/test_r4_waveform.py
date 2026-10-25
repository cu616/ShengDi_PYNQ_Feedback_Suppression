"""波形侧复核工具的回归（不依赖真实板端数据）。

覆盖三件容易出错的事：
  1. bypass 臂必须用 `mic` 当 residual、FIR-on 臂必须用 `clip(mic − prediction)`；
     这个分支取错时，out 会整段失配（本轮实际踩过：`cap.get("bypass")` 恒为 None）。
  2. 包完整性检查要能报出被改过的文件（sha256 与字节数两道）。
  3. 受迫响应窗必须按 `max(first+512, 0.2fs)` 与 `min(end, len(source)−0.01fs)` 截，
     14408 这类数字是这两条边决定的，不是随便取的。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import verify_r4_waveforms as vrw  # noqa: E402

RATE = 48828.125
SCALE = 2 ** 23


def build_trial(band, frames=4096, taps=64, bypass=False, seed=3):
    """按 RTL 的定义造一个自洽试次：played = source + g·residual[n−2]。"""
    rng = np.random.default_rng(seed)
    q = np.zeros(taps, dtype=np.int64)
    q[:8] = rng.integers(-2 ** 16, 2 ** 16, size=8)
    gain_q12 = 817

    # first_frame 之前也要有源，否则 injected 在后半段变 0、output 检查失效
    pcm16 = rng.integers(-2000, 2000, size=1000 + frames).astype("<i2")
    source_full = pcm16.astype(np.int64) * 256
    source = source_full[1000:]
    played = np.zeros(frames, dtype=np.int64)
    mic = np.zeros(frames, dtype=np.int64)
    pred = np.zeros(frames, dtype=np.int64)
    res = np.zeros(frames, dtype=np.int64)
    for n in range(frames):
        acc = sum(int(q[k]) * int(played[n - 1 - k]) for k in range(min(n, taps)))
        pred[n] = int(np.clip(vrw.rounded_shift(acc, 20), -SCALE, SCALE - 1))
        # 造一个稳定的"声学"麦克风：源泄漏 + 上一帧播放的弱耦合
        mic[n] = int(np.clip(source[n] * 0.5 + played[n - 1] * 0.05, -SCALE, SCALE - 1))
        res[n] = mic[n] if bypass else int(np.clip(mic[n] - pred[n], -SCALE, SCALE - 1))
        mix = int(np.clip(source[n] + vrw.gain_pcm(res[n - 2] if n >= 2 else 0, gain_q12),
                          -SCALE, SCALE - 1))
        played[n] = mix

    meta = dict(capture_id="synthetic-%s" % band, bypass=bypass, zero_coeff=False,
                gain_q12=gain_q12, gain_db_actual=float(20 * np.log10(gain_q12 / 4096)),
                hp_volume=40, sample_rate_hz=RATE, frames=frames, first_frame=1000,
                completed_frames=1000 + frames, source_frames=len(pcm16),
                source_end_frame_exclusive=len(pcm16), source_schedule_verified=True,
                prediction_saturations=0, residual_saturations=0,
                gain_saturations=0, mix_saturations=0,
                coefficients_sha256=hashlib.sha256(
                    q.astype("<i4").tobytes()).hexdigest())
    return dict(reference=played / SCALE, microphone=mic / SCALE,
                prediction_pcm=pred, residual_pcm=res, coefficients_q20=q,
                source_pcm16=pcm16,
                sample_rate_hz=np.float64(RATE),
                metadata_json=json.dumps(meta)), q, meta


class ArithmeticBranchTest(unittest.TestCase):
    def test_bypass_arm_uses_microphone_as_residual(self):
        cap, _q, meta = build_trial("off", bypass=True)
        out = vrw.arithmetic(cap, bypass=True)
        self.assertEqual(out["prediction_mismatches"], 0)
        self.assertEqual(out["residual_mismatches"], 0)
        self.assertEqual(out["output_mismatches"], 0)
        self.assertTrue(out["bit_exact"])

    def test_fir_on_arm_subtracts_prediction(self):
        cap, _q, meta = build_trial("on", bypass=False)
        out = vrw.arithmetic(cap, bypass=False)
        self.assertEqual(out["residual_mismatches"], 0)
        self.assertEqual(out["output_mismatches"], 0)

    def test_wrong_bypass_flag_is_detected(self):
        """bypass 臂按 FIR-on 算会整段失配——这正是本轮修掉的那个分支错误。"""
        cap, _q, _meta = build_trial("off", bypass=True)
        out = vrw.arithmetic(cap, bypass=False)
        self.assertGreater(out["residual_mismatches"], 0)
        self.assertFalse(out["bit_exact"])

    def test_history_frames_are_excluded(self):
        cap, q, _meta = build_trial("on", bypass=False)
        out = vrw.arithmetic(cap, bypass=False)
        self.assertEqual(out["history_excluded_frames"], len(q))
        self.assertEqual(out["prediction_evaluated_frames"], 4096 - len(q))


class PackageCheckTest(unittest.TestCase):
    def test_tampered_file_is_reported(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        payload = b"hello"
        (root / "a.npz").write_bytes(payload)
        (root / "manifest.json").write_text(json.dumps({"files": {
            "a.npz": {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}}}),
            encoding="utf-8")
        ok, rows = vrw.check_package(root)
        self.assertTrue(ok)
        self.assertEqual(rows[0]["status"], "ok")

        (root / "a.npz").write_bytes(b"hell0")
        ok, rows = vrw.check_package(root)
        self.assertFalse(ok)
        self.assertEqual(rows[0]["status"], "mismatch")
        tmp.cleanup()

    def test_missing_manifest_returns_none(self):
        tmp = tempfile.TemporaryDirectory()
        ok, rows = vrw.check_package(Path(tmp.name))
        self.assertIsNone(ok)
        self.assertEqual(rows[0]["status"], "missing")
        tmp.cleanup()


class ResponseWindowTest(unittest.TestCase):
    def test_window_edges_follow_the_two_clamps(self):
        """begin 由 first+512 与 0.2fs 的较大者决定；stop 由 end 与 len(source)−0.01fs 的较小者决定。"""
        meta = {"first_frame": 106662, "completed_frames": 123046, "source_frames": 122070}
        begin, stop, frames = vrw.response_window(meta, 122070, RATE)
        self.assertEqual(begin, max(106662 + 512, int(0.2 * RATE)))
        self.assertEqual(stop, min(123046, 122070 - int(0.01 * RATE)))
        self.assertEqual(frames, 14408)

    def test_short_ring_yields_zero_frames(self):
        meta = {"first_frame": 0, "completed_frames": 4096, "source_frames": 122070}
        _begin, _stop, frames = vrw.response_window(meta, 122070, RATE)
        self.assertEqual(frames, 0)


if __name__ == "__main__":
    unittest.main()
