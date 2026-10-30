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
import shutil
import subprocess
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


def make_model(taps=16, seed=11):
    rng = np.random.default_rng(seed)
    q = np.zeros(taps, dtype=np.int64)
    q[:6] = rng.integers(-2 ** 16, 2 ** 16, size=6)
    return q


def build_trial(band, frames=4096, taps=64, bypass=False, seed=3, q=None):
    """按 RTL 的定义造一个自洽试次：played = source + g·residual[n−2]。

    `q` 给了就用它（整包必须共用同一条模型，否则模型绑定一列就对不上）。
    """
    rng = np.random.default_rng(seed)
    if q is None:
        q = np.zeros(taps, dtype=np.int64)
        q[:8] = rng.integers(-2 ** 16, 2 ** 16, size=8)
    taps = len(q)
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
                    q.astype("<i4").tobytes()).hexdigest(),
                logical_taps=int(len(q)), loaded_taps=int(len(q)))
    cap = dict(reference=played / SCALE, microphone=mic / SCALE,
               prediction_pcm=pred, residual_pcm=res, coefficients_q20=q,
                source_pcm16=pcm16,
                sample_rate_hz=np.float64(RATE),
               metadata_json=json.dumps(meta))
    cap["_capture_id"] = meta["capture_id"]     # 只在测试内部用，写盘前剔除
    return cap, q, meta


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


# --------------------------------------------------------------------------
# 入口级判定：整包正例必须 0，五种坏输入必须非 0（C 的 D2/D3/D4 反例）
# --------------------------------------------------------------------------

SCRIPT = REPO / "scripts" / "verify_r4_waveforms.py"
TRIAL_NAMES = [("07-fir-off.npz", True), ("09-fir-on.npz", False),
               ("11-fir-on.npz", False), ("13-fir-off.npz", True)]
TAIL_NAME = "15-continuous-60s.npz"


def write_npz(path, cap):
    """写盘时去掉测试内部用的 `_` 前缀键（npz 里不该出现它们）。"""
    np.savez(path, **{k: v for k, v in cap.items() if not k.startswith("_")})


def build_pack(root, frames=11000):
    """造一个"五件齐全、模型绑定一致、算术全对"的包，外加配套模型/汇总/复核。"""
    q = make_model()
    pack = Path(root) / "pack"
    pack.mkdir(parents=True)
    caps = {}
    for index, (name, bypass) in enumerate(TRIAL_NAMES):
        cap, _q, _meta = build_trial(name, frames=frames, bypass=bypass,
                                     seed=101 + index, q=q)
        caps[name] = cap
        write_npz(pack / name, cap)
    # 60 s 尾环：不带 source_pcm16 / coefficients_q20 / sample_rate_hz
    rng = np.random.default_rng(21)
    played = (rng.standard_normal(frames) * 2000).astype(np.int64)
    mic = (rng.standard_normal(frames) * 1500).astype(np.int64)
    acc = np.convolve(played, np.r_[np.int64(0), q])[:frames]
    pred = np.clip(vrw.rounded_shift(acc, 20), -SCALE, SCALE - 1)
    res = np.clip(mic - pred, -SCALE, SCALE - 1)
    tail_meta = dict(label="run", bypass=False, zero_coeff=False, gain_db=-14.0, gain_q12=817,
                     hp_volume=40, sample_rate_hz=RATE, frames_requested=200000,
                     first_frame=1000, completed_frames=1000 + frames,
                     coefficients_sha256=hashlib.sha256(q.astype("<i4").tobytes()).hexdigest(),
                     timeline=[[0.0, 1, 0, 0, 0, 0, 0]])
    caps[TAIL_NAME] = dict(reference=played / SCALE, microphone=mic / SCALE,
                           prediction_pcm=pred, residual_pcm=res,
                           metadata_json=json.dumps(tail_meta))
    write_npz(pack / TAIL_NAME, caps[TAIL_NAME])

    # 清单
    entries = {}
    for name in caps:
        raw = (pack / name).read_bytes()
        entries[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    (pack / "manifest.json").write_text(json.dumps({"files": entries}), encoding="utf-8")

    # 模型
    model = {"coefficients": (q / 2 ** 20).tolist(), "coefficients_q20": q.tolist(),
             "taps": int(len(q)), "lag_first": 1}
    model_path = Path(root) / "model.json"
    model_path.write_text(json.dumps(model), encoding="utf-8")

    # 汇总与复核：都用同一套场景数（真实场景里就是 C 侧算出来的那批）
    responses = {}
    for name, _b in TRIAL_NAMES:
        meta = json.loads(vrw.as_text(caps[name]["metadata_json"]))
        responses[name] = vrw.response_metrics(caps[name], meta)
    pairs = []
    for repeat, (off_name, _), (on_name, _) in ((1, TRIAL_NAMES[0], TRIAL_NAMES[1]),
                                                (2, TRIAL_NAMES[3], TRIAL_NAMES[2])):
        off, on = responses[off_name], responses[on_name]
        pairs.append({
            "repeat": repeat, "repeat_id": repeat,
            "off_capture_id": caps[off_name]["_capture_id"],
            "on_capture_id": caps[on_name]["_capture_id"],
            "gain_q12": 817,
            "on_minus_off_response_rms_db": on["rms_dbfs"] - off["rms_dbfs"],
            "on_minus_off_band_response_db": {k: on["bands_dbfs"][k] - off["bands_dbfs"][k]
                                              for k in on["bands_dbfs"]},
            "configuration_matches": True, "window_comparison_valid": True})
    summary_path = Path(root) / "summary-v3.json"
    summary_path.write_text(json.dumps({"fir_switch_pairs": pairs}), encoding="utf-8")

    review_files = []
    for name, _b in TRIAL_NAMES:
        review_files.append({"file": name,
                             "response_rms_dbfs": responses[name]["rms_dbfs"],
                             "response_bands_dbfs": responses[name]["bands_dbfs"],
                             "independent_arithmetic_mismatches":
                                 {"prediction": 0, "residual": 0, "output": 0}})
    review_files.append({"file": TAIL_NAME, "response_rms_dbfs": 0.0, "response_bands_dbfs": {},
                         "independent_arithmetic_mismatches":
                             {"prediction": 0, "residual": 0, "output": 0}})
    review_path = Path(root) / "c-review.json"
    review_path.write_text(json.dumps({"files": review_files}), encoding="utf-8")
    return pack, model_path, summary_path, review_path, q


def run_cli(pack, model, summary, review, out):
    cmd = [sys.executable, str(SCRIPT), "--pack", str(pack), "--model", str(model),
           "--summary-v3", str(summary), "--c-review", str(review), "--out-dir", str(out)]
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)


class CliVerdictTest(unittest.TestCase):
    """整包判定：文件齐全 + 模型绑定 + 算术 + 显式对照，四项都过才退出 0。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.base = cls.root / "base"          # 基准包单独放一层，复制时不会把自己拷进去
        cls.pack, cls.model, cls.summary, cls.review, cls.q = build_pack(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fresh(self, tag):
        """每个用例复制一份整包，避免相互污染。"""
        dst = self.root / tag
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(self.base, dst)
        return (dst / "pack", dst / "model.json", dst / "summary-v3.json",
                dst / "c-review.json", dst / "out")

    def repack(self, pack, name):
        """改过 npz 之后必须同步 manifest，否则会被完整性门先挡掉。"""
        man = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        raw = (pack / name).read_bytes()
        man["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        (pack / "manifest.json").write_text(json.dumps(man), encoding="utf-8")

    def test_positive_pack_passes(self):
        pack, model, summary, review, out = self.fresh("pos")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 0, proc.stdout[-1200:] + proc.stderr[-400:])
        self.assertIn("判定：**合格**", proc.stdout)
        data = json.loads((out / "waveform.json").read_text(encoding="utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(data["failures"], [])

    def test_prediction_off_by_one_is_rejected(self):
        """D4：prediction_pcm 改一帧，manifest 同步更新也必须被算术门挡下。"""
        pack, model, summary, review, out = self.fresh("d4arith")
        cap = {k: np.load(pack / "07-fir-off.npz")[k] for k in
               np.load(pack / "07-fir-off.npz").files}
        cap["prediction_pcm"][1024] += 1
        write_npz(pack / "07-fir-off.npz", cap)
        self.repack(pack, "07-fir-off.npz")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("arithmetic", proc.stdout)

    def test_missing_sixty_second_file_is_rejected(self):
        """D3：删 60 s 原件并从清单漏列，只剩 4 件也必须被角色门挡下。"""
        pack, model, summary, review, out = self.fresh("d3miss")
        (pack / TAIL_NAME).unlink()
        man = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        del man["files"][TAIL_NAME]
        (pack / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("package_incomplete", proc.stdout)

    def test_frozen_model_drift_is_rejected(self):
        """D2：模型 Q20 首项改 1，哈希就对不上，必须挡下。"""
        pack, model, summary, review, out = self.fresh("d2model")
        data = json.loads(Path(model).read_text(encoding="utf-8"))
        data["coefficients_q20"][0] += 1
        Path(model).write_text(json.dumps(data), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("model_binding", proc.stdout)

    def test_summary_difference_is_rejected(self):
        """D4：汇总里第一组差分改 1 dB，本来只打印差异，现在必须挡下。"""
        pack, model, summary, review, out = self.fresh("d4sum")
        data = json.loads(Path(summary).read_text(encoding="utf-8"))
        data["fir_switch_pairs"][0]["on_minus_off_response_rms_db"] += 1.0
        Path(summary).write_text(json.dumps(data), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("summary_mismatch", proc.stdout)

    def test_used_file_unlisted_is_rejected(self):
        """D3/D2：文件仍在磁盘上、也被读取，只是从清单删掉——必须挡下（不能被"未核验"绕过）。"""
        pack, model, summary, review, out = self.fresh("d3used")
        man = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        del man["files"]["09-fir-on.npz"]
        (pack / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("unverified_file", proc.stdout)

    def test_model_lag_first_drift_is_rejected(self):
        """D4：只改 lag_first（Q20 不变）也必须挡下——因果约定是模型身份的一部分。"""
        pack, model, summary, review, out = self.fresh("d4lag")
        data = json.loads(Path(model).read_text(encoding="utf-8"))
        data["lag_first"] = 2
        Path(model).write_text(json.dumps(data), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("model_convention", proc.stdout)

    def test_summary_capture_identity_is_rejected(self):
        """D4：汇总的 off_capture_id 换成别的 id，数值与 valid 标记不动也必须挡下。"""
        pack, model, summary, review, out = self.fresh("d4cap")
        data = json.loads(Path(summary).read_text(encoding="utf-8"))
        data["fir_switch_pairs"][0]["off_capture_id"] = "different-capture-not-the-original"
        Path(summary).write_text(json.dumps(data), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("pair_identity", proc.stdout)

    def test_summary_arm_swap_is_rejected(self):
        """把某一组的 off/on 对调：数值会变，但更早的身份检查就该报臂别不符。"""
        pack, model, summary, review, out = self.fresh("d4arm")
        data = json.loads(Path(summary).read_text(encoding="utf-8"))
        row = data["fir_switch_pairs"][0]
        row["off_capture_id"], row["on_capture_id"] = row["on_capture_id"], row["off_capture_id"]
        Path(summary).write_text(json.dumps(data), encoding="utf-8")
        proc = run_cli(pack, model, summary, review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("pair_identity", proc.stdout)

    def test_missing_explicit_summary_is_rejected(self):
        """D3：显式指定一个不存在的汇总，不能"跳过"就算过。"""
        pack, model, _summary, review, out = self.fresh("d3nosum")
        proc = run_cli(pack, model, Path(self.root) / "nope.json", review, out)
        self.assertEqual(proc.returncode, 2, proc.stdout[-1200:])
        self.assertIn("summary_missing", proc.stdout)


if __name__ == "__main__":
    unittest.main()
