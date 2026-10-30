"""B 侧消费 C 的汇总 v3 的回归测试。

防的是三类错：把无效尾段的 0 当通过、把 256 补零当候选、把不同增益的两行配成一对。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import consume_summary_v3 as consumer  # noqa: E402

REG = consumer.load_registry(ROOT / "models")
BASE_SHA = "aea6dc0645be6677542d7bf167685123c6fd394b4ec6cfc59e58c67a3cab19f2"
CAND_SHA = "854fb75dbb6c6b46182ba6dc4c3fd73719d331f5f3b0555c78b71a7561de09bd"


def make_row(capture_id, role, model_sha, coef_sha, logical, loaded, gain=0):
    entry = REG[model_sha]
    return {
        "capture_id": capture_id, "gain_q12": gain, "hp_volume": 40,
        "bit_sha256": "8b2426f4" + "0" * 56, "coefficients_sha256": coef_sha,
        "model_sha256": model_sha, "model_role": role, "logical_taps": logical,
        "loaded_taps": loaded, "fixture_id": entry["fixture_id"],
        "sample_rate_hz": 48828.125, "source_pcm16_sha256": "1" * 64,
        "scene_sha256": "2" * 64, "session_id": "s", "comparison_id": "c",
        "repeat_id": 1, "bypass": False, "tail_valid": True, "tail_rms_dbfs": -40.0,
        "tail_slope_db_per_s": 0.0,
        "tail_residual_over_mic_db": {"300-1000": -3.0, "1000-3000": -4.0,
                                      "8200-8600": -18.0},
        "tail_reasons": [], "effect_eligible": False, "evidence_kind": "board_recording",
        "protection_triggered": False, "prediction_saturation": False,
        "residual_saturation": False, "gain_saturation": False, "mix_saturation": False,
        "microphone_clipping": False, "mute_during_observation": False,
        "tail_first_frame": 100, "tail_end_frame": 16484,
    }


def good_pair():
    base = make_row("b", "baseline", BASE_SHA, REG[BASE_SHA]["padded_512_sha256"], 256, 512)
    cand = make_row("c", "candidate", CAND_SHA, REG[CAND_SHA]["coefficients_sha256"], 512, 512)
    return base, cand


class SummaryV3ConsumerTest(unittest.TestCase):
    def check(self, rows, pairs=()):
        issues, gaps, stats = [], {}, {}
        for row in rows:
            consumer.check_row(row, REG, issues, gaps, stats)
        consumer.check_pairs(rows, list(pairs), issues)
        return issues

    def test_clean_pair_has_no_blocking_issue(self):
        base, cand = good_pair()
        self.assertEqual(self.check([base, cand]), [])

    def test_invalid_tail_must_not_report_zero(self):
        base, _ = good_pair()
        base["tail_valid"] = False
        base["tail_reasons"] = ["tail_too_short"]
        base["tail_residual_over_mic_db"] = {"300-1000": 0.0, "1000-3000": None,
                                             "8200-8600": None}
        issues = self.check([base])
        self.assertTrue(any("不能拿 0 当通过" in i for i in issues), issues)

    def test_padded_256_cannot_be_labelled_candidate(self):
        base, _ = good_pair()
        base["model_role"] = "candidate"
        issues = self.check([base])
        self.assertTrue(any("不得冒充 candidate" in i for i in issues), issues)

    def test_pair_with_different_gain_is_rejected(self):
        base, cand = good_pair()
        cand["gain_q12"] = 4096
        pair = {"comparison_id": "c", "baseline_capture_id": "b",
                "candidate_capture_id": "c", "gain_q12": 0, "effect_eligible": False,
                "evidence_kind": "board_recording", "asg_db": None}
        issues = self.check([base, cand], [pair])
        self.assertTrue(any("配对身份不一致" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
