#!/usr/bin/env python3
"""因果延迟一致性检查：时域预测、频域响应、RTL 索引三者必须对得上。

背景
----
本仓库的模型约定 `lag_first = 1`：

    p[n] = Σ_k h[k] · u[n−1−k]          时域（RTL 也是这个）
    Ĥ(f) = e^{−j·2πf/fs} · Σ_k h[k] e^{−j·2πfk/fs}   频域（多一个 z⁻¹）

如果频域脚本只算 Σ h[k] e^{−j2πfk/fs}，就漏掉那一帧。漏一帧在 8.4 kHz 上是
约 74° 的相位误差，会让 CD 的符号都翻掉，并且很容易被误诊成"RTL 的历史索引错了"。
所以这个检查是可执行的，不靠读代码确认。

四项检查
--------
1. 时域：`predict` 对脉冲的响应必须是 h 延迟 lag_first 帧。
2. 频域：`fir_response` 必须等于把 `predict` 的脉冲响应做 FFT。
3. 错误版本对照：漏掉那一帧后，各频点的相位误差与 CD 偏差有多大。
4. 拟合一致性：`history_matrix` 与 `predict` 用的是同一套索引（用已知冲激回代）。

    python scripts/check_causal_alignment.py
    python scripts/check_causal_alignment.py --taps 512
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from feedback.calibration import Capture, fit_path, history_matrix, predict  # noqa: E402
from feedback.path_analysis import fir_response  # noqa: E402

FS = 48828.125
PROBE_HZ = (1000.0, 4000.0, 8400.0)
TOL = 1e-10


def check_impulse_delay(taps):
    """predict 对脉冲的响应 = h 延迟 lag_first 帧。"""
    rng = np.random.default_rng(7)
    h = rng.standard_normal(taps) * 0.01
    n0 = 50
    u = np.zeros(4096)
    u[n0] = 1.0
    p = predict(u, h)
    # p[n0 + 1 + k] 应等于 h[k]
    got = p[n0 + 1:n0 + 1 + taps]
    err = float(np.max(np.abs(got - h)))
    lead = float(np.max(np.abs(p[:n0 + 1])))
    return err, lead


def check_freq_matches_time(taps):
    """fir_response 与 predict 的脉冲响应 FFT 必须一致。"""
    rng = np.random.default_rng(11)
    h = rng.standard_normal(taps) * 0.02
    n = 1 << 16
    u = np.zeros(n)
    u[0] = 1.0
    ir = predict(u, h)                      # predict 的实际冲激响应
    freqs = np.fft.rfftfreq(n, 1.0 / FS)
    spec = np.fft.rfft(ir)
    direct = fir_response(h, FS, freqs)
    return float(np.max(np.abs(spec - direct)))


def check_wrong_version(taps):
    """漏掉 z⁻¹ 的版本会造成多大误差。"""
    rng = np.random.default_rng(13)
    h = rng.standard_normal(taps) * 0.02
    freqs = np.array(PROBE_HZ)
    omega = 2.0 * np.pi * freqs / FS
    k = np.arange(taps)
    correct = np.exp(-1j * np.outer(omega, k + 1.0)) @ h
    wrong = np.exp(-1j * np.outer(omega, k)) @ h
    rows = []
    for f0, c, w in zip(freqs, correct, wrong):
        phase_err = float(np.degrees(np.angle(w / c)))
        cd_bias = float(20 * np.log10(max(abs(c), 1e-30) / max(abs(c - w), 1e-30)))
        rows.append((f0, phase_err, cd_bias, abs(w - c) / max(abs(c), 1e-30)))
    return rows


def check_fit_indexing(taps):
    """用已知冲激生成数据，拟合后回代：系数与重建误差都应很小。"""
    rng = np.random.default_rng(17)
    h = np.zeros(taps)
    h[3] = 0.40
    h[40] = -0.12
    u = rng.uniform(-1, 1, 30000) * 0.05
    y = predict(u, h) + rng.standard_normal(30000) * 1e-6
    md = {"schema_version": 1, "capture_id": "audit", "source": "synthetic",
          "forward_path_open": True, "alignment": "same_i2s_frame", "dropped_frames": 0}
    cap = Capture(u, y, FS, md).validate()
    model = fit_path(cap, taps=taps)
    coef = np.asarray(model["coefficients"])
    coef_err = float(np.max(np.abs(coef - h)))
    rebuild = predict(u, coef)
    resid = y - rebuild
    resid_db = 20 * np.log10(np.sqrt(np.mean(resid ** 2)) / np.sqrt(np.mean(y ** 2)))
    # history_matrix 的第 0 行必须是 [u[taps-1], ..., u[0]]
    row = history_matrix(u, taps)[0]
    row_ok = bool(np.allclose(row, u[taps - 1::-1][:taps]))
    return coef_err, resid_db, row_ok, model["lag_first"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taps", type=int, default=256)
    args = parser.parse_args(argv)
    taps = args.taps
    ok = True

    print("=== 1. 时域：predict 的因果延迟 ===")
    err, lead = check_impulse_delay(taps)
    print("  脉冲响应与 h 的最大偏差        : %.3e" % err)
    print("  脉冲之前是否提前有输出（应≈0） : %.3e" % lead)
    if err > TOL or lead > TOL:
        ok = False
        print("  判定: **FAIL** — 时域不是 p[n]=Σh[k]u[n-1-k]")
    else:
        print("  判定: PASS（lag_first=1）")

    print()
    print("=== 2. 频域：fir_response 与 predict 是否同一条 ===")
    d = check_freq_matches_time(taps)
    print("  |rfft(predict 冲激响应) − fir_response| 最大偏差: %.3e" % d)
    if d > TOL:
        ok = False
        print("  判定: **FAIL** — 频域漏了或多了相位，两者不可混用")
    else:
        print("  判定: PASS（频域含 z⁻¹，与时域一致）")

    print()
    print("=== 3. 若漏掉那一帧，会差多少（这就是要排除的分析错误）===")
    print("   频率 Hz   相位误差     造成的 CD 偏差     相对幅度误差")
    for f0, ph, cdb, rel in check_wrong_version(taps):
        print("  %7.0f   %+8.1f°   %+8.2f dB   %6.1f%%"
              % (f0, ph, cdb, 100 * rel))
    print("  读法：CD 偏差就是「错误版本会把正余量算成负余量」的幅度。")

    print()
    print("=== 4. 拟合与 predict 是否同一套索引 ===")
    coef_err, resid_db, row_ok, lag_first = check_fit_indexing(taps)
    print("  模型 lag_first                : %d" % lag_first)
    print("  history_matrix 首行语义正确   : %s" % ("是" if row_ok else "**否**"))
    print("  拟合系数与已知冲激的最大偏差  : %.3e" % coef_err)
    print("  回代残差 / 观测（应 < −60 dB）: %+.1f dB" % resid_db)
    if not row_ok or coef_err > 1e-3 or resid_db > -60:
        ok = False
        print("  判定: **FAIL** — 拟合与 predict 索引不一致")
    else:
        print("  判定: PASS")

    print()
    print("总结: %s" % ("四项全部一致，时域/频域/拟合可以混用同一套系数"
                   if ok else "存在不一致，先修正再引用任何 CD/ASG 数字"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
