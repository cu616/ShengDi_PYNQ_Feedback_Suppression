"""Offline tests for A's new replay path; never connect to the board."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "board/audio_replay"))
from replay_tools import prepare_source, verify_replay, RATE
from replay_session import run_replay


def write_wave(path, silent=False):
    data = np.zeros(32000) if silent else .2 * np.sin(np.arange(32000) * 2*np.pi*317/16000)
    with wave.open(str(path), "wb") as f:
        f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        f.writeframes((data * 32767).astype("<i2").tobytes())


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wav = self.root / "source.wav"
        write_wave(self.wav)
        self.q = np.r_[np.int64(2**19), np.zeros(255, dtype=np.int64)]

    def test_prepare_preserves_estimated_headroom_and_determinism(self):
        a, info = prepare_source(self.wav, self.q*52, 73)
        b, info2 = prepare_source(self.wav, self.q*52, 73)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(info, info2)
        bound = np.max(np.abs(a.astype(float))) / 32768 * 26 / (1-73/4096*26)
        self.assertLessEqual(bound, .5)
        self.assertEqual(a[0], 0)
        self.assertEqual(a[-1], 0)
        self.assertEqual(len(a), int(2*RATE))

    def test_excess_gain_and_silent_clip_rejected(self):
        with self.assertRaises(ValueError):
            prepare_source(self.wav, self.q*52, 100)
        write_wave(self.wav, silent=True)
        with self.assertRaises(ValueError):
            prepare_source(self.wav, self.q, 73)

    def test_independent_recurrence_and_ring(self):
        def rnd(x, bits):
            return (1 if x >= 0 else -1) * ((abs(x)+(1 << (bits-1))) >> bits)
        def clip(x):
            return min(8388607, max(-8388608, x))
        source = (np.arange(400) % 41 - 20).astype("<i2")
        for bypass in (False, True):
            raw = np.zeros((1100, 4), dtype=np.int64)
            for i in range(len(raw)):
                s = int(source[i])*256 if i < len(source) else 0
                y = clip(s + (clip(rnd(int(raw[i-2, 3])*73, 12)) if i >= 2 else 0))
                pred = clip(rnd(int(raw[i-1, 0])*2**19, 20)) if i else 0
                mic = (i%97-48)*100
                raw[i] = [y, mic, pred, mic if bypass else clip(mic-pred)]
            self.assertTrue(verify_replay(raw, self.q, bypass, 73, source)["bit_exact"])
            self.assertTrue(verify_replay(raw[500:], self.q, bypass, 73, source, 500)["bit_exact"])
            raw[900, 0] += 1
            self.assertFalse(verify_replay(raw, self.q, bypass, 73, source)["bit_exact"])

    def session(self, answers, error=False, saturated=False):
        setup = self.root / "setup.json"
        scene = json.loads((ROOT / "board/audio_closed/field_setup_ready_to_edit.json").read_text(encoding="utf-8"))
        setup.write_text(json.dumps(scene), encoding="utf-8")
        model = self.root / "model.json"
        model.write_text(json.dumps(dict(taps=256, lag_first=1,
            coefficient_format="signed24_fraction20", training_source="board",
            fixture_id="box_v1_20261016", hp_volume=40, sample_rate_hz=RATE,
            bias=0, coefficients=(self.q/2**20).tolist(),
            coefficients_q20=self.q.tolist())), encoding="utf-8")
        calls = []
        def runner(path, fixture, model_path, pcm, **kw):
            if not kw["before_start"]():
                raise RuntimeError("operator cancelled before audio start")
            calls.append(kw)
            if error:
                raise KeyboardInterrupt()
            return dict(sound_seconds_nominal=kw["seconds"], verification={"bit_exact": True},
                gain_q12=0 if kw["direct_only"] else 73, hp_volume=40, bypass=kw["bypass"],
                source_pcm16_sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
                model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                bit_sha256="mock", coefficients_sha256="mock", sample_rate_hz=RATE,
                completed_frames=117186, fixture_id=fixture, mix_saturations=int(saturated))
        answers = iter(answers)
        state = run_replay(self.wav, setup, model, self.root / "out",
            ask=lambda _: next(answers), runner=runner, verify_package=False)
        saved = json.loads((self.root / "out" / state["run_id"] / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], state["status"])
        return state, calls

    def test_completed_pair_and_exact_modes(self):
        state, calls = self.session(["READY", "START", "1", "START", "1", "START", "1"])
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["pair_configuration_matches"])
        self.assertEqual([(c["bypass"], c["direct_only"]) for c in calls],
                         [(True, True), (True, False), (False, False)])

    def test_scene_cancel_does_not_call_runner(self):
        state, calls = self.session(["no"])
        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(calls, [])

    def test_inaudible_direct_stops_before_pair(self):
        state, calls = self.session(["READY", "START", "0"])
        self.assertEqual(state["stop_reason"], "direct:inaudible")
        self.assertEqual(len(calls), 1)

    def test_saturation_stops_without_hearing_prompt(self):
        state, calls = self.session(["READY", "START"], saturated=True)
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(len(calls), 1)

    def test_interrupt_is_saved_with_unknown_audio_duration(self):
        state, calls = self.session(["READY", "START"], error=True)
        self.assertEqual(state["status"], "stopped")
        self.assertTrue(state["sound_seconds_unknown_for_failed_trial"])


if __name__ == "__main__":
    unittest.main()
