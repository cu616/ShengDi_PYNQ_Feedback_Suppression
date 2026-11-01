"""守住一键重标定的数值策略：四类判定、选点规则、激励档位身份。

这些函数一旦被判错，现场就会装错模型或宣布假通过，所以阈值和分支都钉死。
不依赖板卡、不读外部数据，全部合成。
"""
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))

from feedback import recal_policy as rp  # noqa: E402


def white(n=16384, level_db=-19.3, seed=7):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    x -= x.mean()
    return x / np.sqrt(np.mean(x * x)) * 10 ** (level_db / 20.0)


class ExcitationTest(unittest.TestCase):
    def test_levels_are_distinct(self):
        """三档必须给出三个不同序列；相同 PCM 不能当多个档位。"""
        levels = [rp.make_excitation(lv, 8192) for lv in rp.EXCITATION_LADDER_DBFS]
        ok, msg = rp.assert_distinct_levels(levels)
        self.assertTrue(ok, msg)
        self.assertEqual(len({s["sha256"] for s in levels}), len(levels))

    def test_old_normalise_then_cap_collapses_levels(self):
        """旧写法：先归一到目标 RMS 再按峰值上限缩放，三档塌成同一序列。"""

        def old(level, n=8192):
            rng = np.random.default_rng(4242)
            x = rng.standard_normal(n)
            x -= x.mean()
            x = x / np.sqrt(np.mean(x * x)) * 10 ** (level / 20.0)
            pk = np.abs(x).max()
            if pk > 0.8:
                x *= 0.8 / pk
            return np.rint(x * 32767).astype(np.int16)

        shas = {old(lv).tobytes() for lv in (-13.3, -7.3, -4.3)}
        self.assertLess(len(shas), 3)            # bug 复现：至少两档塌成同一序列
        # 新写法在同样三档上不会塌
        new = [rp.make_excitation(lv, 8192) for lv in (-13.3, -7.3, -4.3)]
        self.assertGreater(len({s["sha256"] for s in new}), 1)

    def test_unreachable_is_reported_not_silently_scaled(self):
        """目标超过上限时返回 reachable=False 与实际达成值，不伪装成达标。"""
        s = rp.make_excitation(0.0, 8192)
        self.assertFalse(s["reachable"])
        self.assertLess(s["achieved_rms_dbfs"], -10.0)
        self.assertAlmostEqual(s["achieved_rms_dbfs"], s["ceiling_dbfs"], places=3)

    def test_plan_is_bounded(self):
        """重试次数到顶后必须停，不无限提电平。"""
        bad = rp.check_capture(white() * 10, white() * 10, 48828.125)  # 满幅
        self.assertEqual(bad["status"], "REJECT_CLIP")
        decided = rp.plan_excitation(bad, attempt=0)
        self.assertEqual(decided["status"], "NO_ACTION")
        self.assertEqual(decided["action"]["kind"], "lower_input_gain")

        quiet = {"status": "REJECT_COHERENCE", "metrics": {"ref_rms_dbfs": -30.0},
                 "next": {"kind": "raise_excitation"}}
        first = rp.plan_excitation(quiet, attempt=0)
        self.assertEqual(first["status"], "RAISE_EXCITATION")
        self.assertGreater(first["action"]["target_rms_dbfs"], -30.0)
        exhausted = rp.plan_excitation(quiet, attempt=rp.MAX_ATTEMPTS)
        self.assertEqual(exhausted["status"], "EXHAUSTED")


class CaptureTest(unittest.TestCase):
    def test_clean_capture_passes(self):
        fs = 48828.125
        u = white(level_db=-19.3)
        # 造一个可相干、无削顶的 mic：延迟 + 增益 + 少量噪声
        h = np.zeros(200)
        h[183] = 0.9
        mic = np.convolve(u, h)[:len(u)] + white(level_db=-45.0, seed=11) * 0.05
        got = rp.check_capture(u, mic, fs, metadata={"dropped_frames": 0})
        self.assertEqual(got["status"], "OK")
        self.assertGreater(got["metrics"]["excitation_snr_db"], rp.MIN_EXCITATION_SNR_DB)

    def test_clip_rejected(self):
        fs = 48828.125
        u = white(level_db=-1.0)
        got = rp.check_capture(u, u * 0.5, fs)
        self.assertEqual(got["status"], "REJECT_CLIP")
        self.assertEqual(got["next"]["kind"], "lower_input_gain")

    def test_mic_without_coherent_signal_rejected(self):
        """麦克风里没有与参考相干的成分 -> 激励没进来（音响待机/接错路）。

        这条是 MIN_EXCITATION_SNR_DB 的兜底职责，不是主判据。
        历史同类：mic 全零的段 snr = -326 dB、门控 0%。
        """
        fs = 48828.125
        u = white(level_db=-19.3)
        mic = white(level_db=-34.0, seed=99)          # 电平正常，但与参考无关
        got = rp.check_capture(u, mic, fs)
        self.assertEqual(got["status"], "REJECT_EXCITATION")

    def test_high_floor_but_good_coherence_still_accepted(self):
        """真实场景：1 m 侧对下 snr 只有 4 dB，但相干 0.9、门控 73%（bind4）。

        这种数据支撑过已部署模型，不能因为全局信噪比低就拒收——
        否则判据会否掉部署模型自己的训练集。形态：低频段有强不相干功率，
        把全局比值拉低，但评价带里绝大多数 bin 仍然相干。
        """
        fs = 48828.125
        u = white(level_db=-19.3)
        h = np.zeros(260)
        h[183] = 0.9
        talked = np.convolve(u, h)[:len(u)]
        floor = white(level_db=-24.0, seed=13)
        F = np.fft.rfft(floor)
        F[np.fft.rfftfreq(len(floor), 1.0 / fs) > 320] = 0
        low = np.fft.irfft(F, len(floor))
        low *= 10 ** (-24.0 / 20.0) / np.sqrt(np.mean(low * low))
        got = rp.check_capture(u, talked + low, fs)
        self.assertLess(got["metrics"]["excitation_snr_db"], 6.0)
        self.assertGreaterEqual(got["metrics"]["coherence_gated_ratio"], rp.MIN_GATED_COHERENCE)
        self.assertEqual(got["status"], "OK")

    def test_sparse_lines_rejected(self):
        """多音（稀疏线）必须被拒——它会让互相关出现等高峰，延迟估计不可用。"""
        fs = 48828.125
        n = 16384
        t = np.arange(n) / fs
        x = np.zeros(n)
        for f0 in (199.7, 253.3, 324.8, 399.4, 634.8, 798.7):
            x += np.cos(2 * np.pi * f0 * t)
        x *= 10 ** (-19.3 / 20.0) / np.sqrt(np.mean(x * x))
        got = rp.check_capture(x, x * 0.3, fs)
        self.assertEqual(got["status"], "REJECT_REFERENCE")
        self.assertGreater(got["metrics"]["spectral_spread_db"], rp.SPARSE_LINE_DB)

    def test_reference_not_open_loop_rejected(self):
        """reference 不是纯源时拒收：反馈项可能仍在环内。"""
        fs = 48828.125
        u = white(level_db=-19.3)
        src = u.copy()
        u_bad = u + white(level_db=-40.0, seed=3)
        got = rp.check_capture(u_bad, u * 0.3, fs, source=src, metadata={"first_frame": 0})
        self.assertEqual(got["status"], "REJECT_REFERENCE")

    def test_short_capture_rejected(self):
        got = rp.check_capture(white(1024), white(1024), 48828.125)
        self.assertEqual(got["status"], "REJECT_INTEGRITY")


class SelectProbeTest(unittest.TestCase):
    def test_uses_open_loop_only_and_spaces_probes(self):
        fs = 48828.125
        f = np.linspace(0, fs / 2, 4097)
        H = np.exp(-1j * 2 * np.pi * f * 0.004) * (1.0 + np.exp(-((f - 400) / 120) ** 2))
        coh = np.where((f > 200) & (f < 8000), 0.95, 0.2)
        pts = rp.select_probe_frequencies(H, f, coh, gain_db=-8.0, n_probe=3)
        self.assertEqual(len(pts), 3)
        self.assertTrue(all(p["coherence"] >= rp.COHERENCE_FLOOR for p in pts))
        fs_hz = sorted(p["frequency_hz"] for p in pts)
        for a, b in zip(fs_hz, fs_hz[1:]):
            self.assertGreaterEqual(np.log2(b / a), 1.0 / 3.0 - 1e-9)

    def test_low_coherence_band_returns_empty(self):
        fs = 48828.125
        f = np.linspace(0, fs / 2, 4097)
        H = np.ones_like(f, dtype=complex)
        coh = np.full_like(f, 0.3)
        self.assertEqual(rp.select_probe_frequencies(H, f, coh, gain_db=-8.0), [])


class FitTest(unittest.TestCase):
    def _model(self, l1_target, taps=512, delay_tap=184):
        """造一个形状接近真实房间的模型：延迟后按 ~60 帧衰减，L1/max 约 50
        （历史部署 49.9、10-26 新布局 52.3）。"""
        rng = np.random.default_rng(3)
        k = np.arange(taps)
        env = np.exp(-np.maximum(k - (delay_tap - 1), 0) / 60.0)
        env[k < delay_tap - 1] = 0.0
        h = env * (1.0 + 0.05 * rng.standard_normal(taps))
        h *= l1_target / np.abs(h).sum()
        return np.rint(h * (1 << 20)).astype(np.int64)

    def test_deployable(self):
        q = self._model(2.29)
        got = rp.check_fit(q, 48828.125, expected_peak_tap=184)
        self.assertEqual(got["status"], "DEPLOYABLE_FIT")
        self.assertAlmostEqual(got["metrics"]["L1"], 2.29, places=3)

    def test_scale_rejection_differs_from_shape_rejection(self):
        """整体放大 -> REJECT_SCALE；形状变平 -> REJECT_SHAPE。两者处置不同。"""
        q = self._model(80.0)                    # 整体放大，L1/max 不变
        scale = rp.check_fit(q, 48828.125, expected_peak_tap=184)
        self.assertEqual(scale["status"], "REJECT_SCALE")

        flat = np.abs(np.random.default_rng(5).standard_normal(512))
        flat /= flat.sum() / 90.0                # L1=90，但 L1/max 远大于历史
        flat_q = np.rint(flat * (1 << 20)).astype(np.int64)
        shape = rp.check_fit(flat_q, 48828.125, expected_peak_tap=184)
        self.assertEqual(shape["status"], "REJECT_SHAPE")

    def test_peak_tap_mismatch_rejected(self):
        q = self._model(2.29, delay_tap=296)
        got = rp.check_fit(q, 48828.125, expected_peak_tap=184)
        self.assertEqual(got["status"], "REJECT_SHAPE")
        self.assertGreater(abs(got["metrics"]["peak_tap_delta"]), rp.PEAK_TAP_TOLERANCE)

    def test_relocated_fixture_is_not_a_rejection(self):
        """换摆位是正常用法：期望值取本轮实测延迟，不是上一个模型的峰位。

        实测：50 cm 侧放 127/128 帧，100 cm 侧对 183/184 帧。若拿旧模型峰位当基准，
        一次正确的重标定会被判成"换错了布置"（峰值差 -56 帧）。
        """
        q = self._model(2.29, delay_tap=128)          # 拟合跟随本轮延迟
        self.assertEqual(rp.check_fit(q, 48828.125, expected_peak_tap=128)["status"],
                         "DEPLOYABLE_FIT")
        # 同一份模型，若误用上一批的 184 当基准，会被拒——这条钉住"基准必须来自本轮"
        self.assertEqual(rp.check_fit(q, 48828.125, expected_peak_tap=184)["status"],
                         "REJECT_SHAPE")

    def test_legacy_keyword_still_works(self):
        """base_peak_tap 是旧名，语义等同，保留以免破坏既有调用方。"""
        q = self._model(2.29)
        self.assertEqual(rp.check_fit(q, 48828.125, base_peak_tap=184)["status"],
                         "DEPLOYABLE_FIT")


class ThreePointTest(unittest.TestCase):
    def test_pass(self):
        got = rp.check_three_point([
            {"frequency_hz": 322.0, "open_db": 45.44, "bypass_db": 49.19, "cancel_db": 44.43},
            {"frequency_hz": 480.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0},
        ])
        self.assertEqual(got["status"], "PASS")

    def test_negative_loop_boost_is_inapplicable_not_failure(self):
        """322 Hz 负环路提升：没有可收回的东西，判 INAPPLICABLE，不算失败也不算通过。"""
        got = rp.check_three_point([
            {"frequency_hz": 322.0, "open_db": 40.0, "bypass_db": 39.0, "cancel_db": 37.5},
            {"frequency_hz": 480.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0},
        ])
        self.assertEqual(got["points"][0]["status"], "INAPPLICABLE")
        self.assertEqual(got["points"][1]["status"], "PASS")
        # 只剩 1 个可判点，不够 MIN_PASSING_PROBES
        self.assertEqual(got["status"], "INCONCLUSIVE")
        self.assertEqual(got["cause"], "DATA_INSUFFICIENT")

    def test_two_passing_plus_one_inapplicable_still_passes(self):
        got = rp.check_three_point([
            {"frequency_hz": 322.0, "open_db": 40.0, "bypass_db": 39.0, "cancel_db": 37.5},
            {"frequency_hz": 480.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0},
            {"frequency_hz": 1200.0, "open_db": 40.0, "bypass_db": 43.5, "cancel_db": 39.2},
        ])
        self.assertEqual(got["status"], "PASS")

    def test_single_passing_probe_is_inconclusive(self):
        """只有 1 个点判 PASS，不够 MIN_PASSING_PROBES，属数据不足。"""
        got = rp.check_three_point([
            {"frequency_hz": 322.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0},
        ])
        self.assertEqual(got["status"], "INCONCLUSIVE")
        self.assertEqual(got["cause"], "DATA_INSUFFICIENT")

    def test_all_probes_without_loop_boost_is_measurement_inapplicable(self):
        """所有点都没有可收回的环路提升：是"测量不适用"，不是"数据不足"，也不是失败。"""
        got = rp.check_three_point([
            {"frequency_hz": 322.0, "open_db": 40.0, "bypass_db": 39.0, "cancel_db": 37.5},
        ])
        self.assertEqual(got["status"], "INCONCLUSIVE")
        self.assertEqual(got["cause"], "MEASUREMENT_INAPPLICABLE")

    def test_residual_positive_feedback_fails(self):
        """10-31 那轮的真实签名：cancel 比 bypass 还响 -> FAIL，归 MODEL_UNQUALIFIED。"""
        got = rp.check_three_point([
            {"frequency_hz": 322.0, "open_db": 45.44, "bypass_db": 47.42, "cancel_db": 47.63},
            {"frequency_hz": 480.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0},
        ])
        self.assertEqual(got["points"][0]["status"], "FAIL")
        self.assertEqual(got["status"], "FAIL")
        self.assertEqual(got["cause"], "MODEL_UNQUALIFIED")

    def test_hardware_error_short_circuits(self):
        got = rp.check_three_point(
            [{"frequency_hz": 322.0, "open_db": 1, "bypass_db": 2, "cancel_db": 1}],
            saturation_counts={"prediction": 3})
        self.assertEqual(got["status"], "FAIL")
        self.assertEqual(got["cause"], "HARDWARE_ERROR")

    def test_mixed_sources_inconclusive(self):
        got = rp.check_three_point(
            [{"frequency_hz": 322.0, "open_db": 40, "bypass_db": 44, "cancel_db": 39}],
            source_sha=["aaa", "bbb"])
        self.assertEqual(got["status"], "INCONCLUSIVE")
        self.assertEqual(got["cause"], "MEASUREMENT_INAPPLICABLE")

    def test_prediction_mismatch_downgrades_to_inconclusive(self):
        got = rp.check_three_point(
            [{"frequency_hz": 322.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0},
             {"frequency_hz": 480.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0}],
            gain_db=-8.0,
            h_complex=lambda f: 1.0 + 0j,
            hhat_complex=lambda f: -1.0 + 0j,          # 预测会差很远
        )
        self.assertEqual(got["status"], "INCONCLUSIVE")


class DecideTest(unittest.TestCase):
    def test_blocks_at_first_failed_step(self):
        bad = rp.check_capture(white() * 10, white() * 10, 48828.125)
        out = rp.decide(capture=bad)
        self.assertEqual(out["blocked_at"], "capture")
        self.assertEqual(out["decision"]["action"]["kind"], "lower_input_gain")

    def test_missing_three_point_is_inconclusive_not_installable(self):
        """采集合格 + 模型可部署 != 抵消有效。缺验证时必须 INCONCLUSIVE，不自动安装。"""
        fs = 48828.125
        u = white()
        path = np.zeros(200)
        path[183] = 0.9
        mic = np.convolve(u, path)[:len(u)] + white(level_db=-45.0, seed=11) * 0.05
        h = np.zeros(512)
        env = np.exp(-np.maximum(np.arange(512) - 183, 0) / 60.0)
        env[:183] = 0.0
        h = env / np.abs(env).sum() * 2.29
        model = np.rint(h * (1 << 20)).astype(np.int64)
        out = rp.decide(
            capture=rp.check_capture(u, mic, fs, metadata={"dropped_frames": 0}),
            fit=rp.check_fit(model, fs, expected_peak_tap=184),
        )
        self.assertEqual(out["decision"]["status"], "INCONCLUSIVE")
        self.assertEqual(out["decision"]["cause"], "DATA_INSUFFICIENT")
        self.assertEqual(out["blocked_at"], "three_point")
        self.assertEqual(out["steps"]["three_point"]["status"], "NOT_RUN")

    def test_offline_check_can_skip_three_point(self):
        """只做离线检查时显式传 require_three_point=False 才允许返回可安装。"""
        fs = 48828.125
        u = white()
        path = np.zeros(200)
        path[183] = 0.9
        mic = np.convolve(u, path)[:len(u)] + white(level_db=-45.0, seed=11) * 0.05
        out = rp.decide(capture=rp.check_capture(u, mic, fs, metadata={"dropped_frames": 0}),
                        require_three_point=False)
        self.assertEqual(out["decision"]["status"], "READY_TO_INSTALL")

    def test_ready_only_when_all_three_pass(self):
        fs = 48828.125
        u = white()
        path = np.zeros(200)
        path[183] = 0.9
        mic = np.convolve(u, path)[:len(u)] + white(level_db=-45.0, seed=11) * 0.05
        out = rp.decide(
            capture=rp.check_capture(u, mic, fs, metadata={"dropped_frames": 0}),
            three_point=rp.check_three_point(
                [{"frequency_hz": 322.0, "open_db": 45.44, "bypass_db": 49.19, "cancel_db": 44.43},
                 {"frequency_hz": 480.0, "open_db": 40.0, "bypass_db": 44.0, "cancel_db": 39.0}]),
        )
        self.assertEqual(out["decision"]["status"], "READY_TO_INSTALL")
        self.assertIsNone(out["blocked_at"])


if __name__ == "__main__":
    unittest.main()
