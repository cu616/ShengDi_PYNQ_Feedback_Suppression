"""守住 recal_algorithm.evaluate 的契约分支与判据。

不读外部数据：房间、捕获、模型全部合成，结论与数值一起钉死。
真实数据的端到端复核在 report/verification/recalibration-algorithm-2026-11-01/。
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "board" / "audio_replay"))
sys.path.insert(0, str(REPO / "src"))

import recal_algorithm as ra  # noqa: E402
from feedback import recal_policy as rp  # noqa: E402

FS = 48828.125
FRAMES = 8192
DELAY = 180


def white(n=FRAMES, level_db=-19.3, seed=7):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    x -= x.mean()
    return x / np.sqrt(np.mean(x * x)) * 10 ** (level_db / 20.0)


def room_ir(taps=512, delay=DELAY, decay=45.0, seed=3, energy=0.029):
    """形状像真实房间、能量也对得上部署模型的冲激响应。

    energy=0.029 取自 rewired_512_20261026.json 的 Σh²，这样白噪卷积后 mic 落在
    −33 dBFS 量级，与实测一致；不归一化会得到十几倍满幅的假 mic。
    """
    rng = np.random.default_rng(seed)
    k = np.arange(taps)
    env = np.exp(-np.maximum(k - delay, 0) / decay)
    env[k < delay] = 0.0
    h = env * (1.0 + 0.05 * rng.standard_normal(taps))
    return h * np.sqrt(energy / np.sum(h * h))


def write_capture(run, name, ref, mic, first_frame=0, source=None):
    p = Path(run) / (name + ".npz")
    np.savez(p, reference=ref, microphone=mic, sample_rate_hz=FS,
             source_pcm16=(source if source is not None else ref),
             metadata_json=json.dumps({"first_frame": first_frame, "bit22": 0}))
    return {"capture_id": name, "path": str(p), "first_frame": first_frame,
            "source_sha256": hashlib.sha256(("src-" + name).encode()).hexdigest(),
            "content_kind": "onboard_excitation"}


class Fixture:
    """一套合成场景：真实房间 + 六段捕获（4 训练 / 2 验证）。"""

    def __init__(self, tmp, seeds=(1, 2, 3, 4, 5, 6), decoy_seed=99):
        self.run = tmp
        self.h_true = room_ir()
        self.decoy = room_ir(delay=60, decay=35.0, seed=decoy_seed)
        self.entries = []
        for i, s in enumerate(seeds):
            u = white(seed=s)
            mic = np.convolve(u, self.h_true)[:len(u)] + white(level_db=-42.0, seed=100 + i) * 0.03
            self.entries.append(write_capture(tmp, "seg%d" % i, u, mic))

    def base(self, **kw):
        req = dict(contract="recal-product-v1", request_id="r1", scene_id="s1",
                   run_dir=str(self.run), attempt=0, attempts_total=1,
                   identity={"hp_volume": 40, "gain_q12": 1631})
        req.update(kw)
        return req


class InputTest(unittest.TestCase):
    def test_clean_input_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            got = ra.evaluate(fx.base(phase="input", input=fx.entries[:2]))
            self.assertEqual(got["decision"], "valid_pass")
            self.assertEqual(got["contract"], "recal-product-v1")

    def test_clipped_input_is_data_insufficient(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            u = white(level_db=-1.0)
            e = write_capture(tmp, "hot", u, np.clip(u * 3, -1.0, 1.0))
            got = ra.evaluate({"contract": "recal-product-v1", "request_id": "r", "scene_id": "s",
                               "run_dir": tmp, "attempt": 0, "attempts_total": 1,
                               "phase": "input", "input": [e]})
            self.assertEqual(got["decision"], "data_insufficient")
            self.assertIn("满幅", got["reason"])

    def test_retry_only_when_attempt_left(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            u = white(level_db=-19.3)
            mic = white(level_db=-40.0, seed=55)          # 与参考无关 -> 激励没进来
            e = write_capture(tmp, "dead", u, mic)
            base = {"contract": "recal-product-v1", "request_id": "r", "scene_id": "s",
                    "run_dir": tmp, "phase": "input", "input": [e]}
            first = ra.evaluate(dict(base, attempt=0, attempts_total=2))
            last = ra.evaluate(dict(base, attempt=1, attempts_total=2))
            self.assertEqual(first["decision"], "retry")
            self.assertEqual(last["decision"], "data_insufficient")

    def test_missing_capture_file(self):
        got = ra.evaluate({"contract": "recal-product-v1", "request_id": "r", "scene_id": "s",
                           "run_dir": ".", "attempt": 0, "phase": "input",
                           "input": [{"capture_id": "x", "path": "nope.npz"}]})
        self.assertEqual(got["decision"], "data_insufficient")
        self.assertIn("不存在", got["reason"])


class FitTest(unittest.TestCase):
    def test_fit_then_validate_passes_on_clean_room(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fit = ra.evaluate(fx.base(phase="fit", training=fx.entries[:4],
                                      validation=fx.entries[4:]))
            self.assertEqual(fit["decision"], "valid_pass", fit.get("reason"))
            self.assertTrue(Path(fit["model_path"]).exists())
            self.assertEqual(ra._sha256_file(fit["model_path"]), fit["model_sha256"])

            val = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=fx.entries[4:],
                                      model_path=fit["model_path"],
                                      model_sha256=fit["model_sha256"]))
            self.assertEqual(val["decision"], "valid_pass", val.get("reason"))
            self.assertIs(val["qualifies_cancellation"], True)
            self.assertIsNotNone(val["evidence"])

    def test_fit_needs_two_captures(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            got = ra.evaluate(fx.base(phase="fit", training=fx.entries[:1],
                                      validation=fx.entries[1:]))
            self.assertEqual(got["decision"], "data_insufficient")

    def test_model_hash_mismatch_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fit = ra.evaluate(fx.base(phase="fit", training=fx.entries[:4],
                                      validation=fx.entries[4:]))
            got = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=fx.entries[4:],
                                      model_path=fit["model_path"], model_sha256="0" * 64))
            self.assertEqual(got["decision"], "model_rejected")
            self.assertIn("哈希", got["reason"])


class ValidateTest(unittest.TestCase):
    def _fit(self, fx):
        fit = ra.evaluate(fx.base(phase="fit", training=fx.entries[:4],
                                  validation=fx.entries[4:]))
        return fit

    def test_shared_capture_is_not_independent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fit = self._fit(fx)
            got = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=fx.entries[:2],
                                      model_path=fit["model_path"],
                                      model_sha256=fit["model_sha256"]))
            self.assertEqual(got["decision"], "data_insufficient")
            self.assertIn("重叠", got["reason"])

    def test_shared_source_sha_is_not_independent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fit = self._fit(fx)
            # 换个 capture_id，但沿用训练集的 source_sha256 —— 同一段源不算独立验证
            val = dict(fx.entries[4], source_sha256=fx.entries[0]["source_sha256"])
            got = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=[val],
                                      model_path=fit["model_path"],
                                      model_sha256=fit["model_sha256"]))
            self.assertEqual(got["decision"], "data_insufficient")
            self.assertIn("重叠", got["reason"])

    def test_wrong_room_model_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            q = ra.quantize_q20(fx.decoy)
            wrong = Path(tmp) / "wrong.json"
            wrong.write_bytes(json.dumps({"taps": 512, "lag_first": 1,
                                          "coefficients_q20": [int(v) for v in q]}).encode())
            got = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=fx.entries[4:],
                                      model_path=str(wrong),
                                      model_sha256=ra._sha256_file(wrong)))
            self.assertEqual(got["decision"], "model_rejected")
            self.assertIs(got["qualifies_cancellation"], False)

    def test_zero_model_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            zero = Path(tmp) / "zero.json"
            zero.write_bytes(json.dumps({"taps": 512, "lag_first": 1,
                                         "coefficients_q20": [0] * 512}).encode())
            got = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=fx.entries[4:],
                                      model_path=str(zero),
                                      model_sha256=ra._sha256_file(zero)))
            self.assertEqual(got["decision"], "model_rejected")


class ContractTest(unittest.TestCase):
    def test_every_reply_has_decision_and_reason(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            for req in (fx.base(phase="input", input=fx.entries[:1]),
                        fx.base(phase="nonsense"),
                        {"contract": "wrong", "phase": "fit"}):
                got = ra.evaluate(req)
                self.assertIn(got["decision"],
                              ("valid_pass", "data_insufficient", "model_rejected", "retry"))
                self.assertTrue(got.get("reason"))

    def test_envelope_is_echoed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            got = ra.evaluate(fx.base(phase="input", input=fx.entries[:1]))
            self.assertEqual(got["request_id"], "r1")
            self.assertEqual(got["scene_id"], "s1")

    def test_evidence_is_not_reported_as_asg(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fit = ra.evaluate(fx.base(phase="fit", training=fx.entries[:4],
                                      validation=fx.entries[4:]))
            val = ra.evaluate(fx.base(phase="validate", training=fx.entries[:4],
                                      validation=fx.entries[4:],
                                      model_path=fit["model_path"],
                                      model_sha256=fit["model_sha256"]))
            self.assertIs(val["evidence"]["not_asg"], True)
            self.assertNotIn("asg", val["reason"].lower())


class ParityWithPolicyTest(unittest.TestCase):
    """board 侧自包含实现与 src/feedback/recal_policy.py 必须同结论。"""

    def test_capture_verdicts_agree(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cases = []
            u = white(level_db=-19.3)
            cases.append(("clean", u, np.convolve(u, room_ir())[:len(u)]))
            cases.append(("clipped", white(level_db=-1.0),
                          np.clip(white(level_db=-1.0) * 3, -1.0, 1.0)))
            cases.append(("dead_mic", u, white(level_db=-40.0, seed=77)))
            cases.append(("short", u[:2000], u[:2000]))
            for name, ref, mic in cases:
                entry = write_capture(tmp, name, ref, mic)
                cap = ra.load_capture(entry)
                ok_b, status_b, _, _ = ra._check_capture(cap, source_expected=False)
                got_p = rp.check_capture(ref, mic, FS)
                self.assertEqual(status_b.replace("REJECT_", "").lower() in
                                 got_p["status"].replace("REJECT_", "").lower() or
                                 (status_b == "OK") == (got_p["status"] == "OK"),
                                 True, "%s: board=%s policy=%s" % (name, status_b, got_p["status"]))


if __name__ == "__main__":
    unittest.main()
