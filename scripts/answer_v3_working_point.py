"""v3 演示工作点与 bypass/cancel 对照设计：只从 A 的三点实测反推，不引入新数据。

输入全部来自 A 的 evidence.json（`steady_state_tone_three_point`）：
  * 322 Hz 纯音、同一源电平 0.15 FS、g = −8 dB、Codec 40、候选系数已装
  * open（数字增益强制 0）：322 Hz 45.44 dB
  * bypass（环路闭合、候选未减）：49.19 dB
  * cancel（减法生效）：44.43 dB
  * |H| 峰 +4.40 dB @ 321.9 Hz（2026-10-23 本夹具重标定）

三个量各自是什么，本脚本先把它们分开：
  1. **CD(322) = 6.37 dB**  —— 残差深度：bypass 的 residual 与 cancel 的 residual 之比。
     它衡量**模型对路径的拟合程度**，是 cancel 这条支路真正被最小化的量。
  2. **环路提升 = bypass − open = 3.75 dB** —— 闭环把 322 Hz 抬高了多少。
     这是"抵消最多能收回多少"的**上限**。
  3. **声学差 = bypass − cancel = 4.76 dB** —— 两臂的麦电平差，
     它 = 环路提升 3.75 + cancel 相对 open 的过冲 1.01。

**关键**：第 3 项不能整笔当收益。cancel 比 open 还低 1.01 dB 属于"抵消干净或略过抵消"，
不是可听收益的一部分；真实可听收益的量级是第 2 项。

用法：
    python scripts/answer_v3_working_point.py [--json-out <路径>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

FS = 48828.125

# ---- A 的实测（evidence.json）
OPEN_DB = 45.44
BYPASS_DB = 49.19
CANCEL_DB = 44.43
CD_DB = 6.37                    # A 报的残差深度
GAIN_DB = -8.0                  # 本次三点的数字增益
H_PEAK_DB = 4.40                # |H| 峰，321.9 Hz
H_PEAK_HZ = 321.9

# ---- 模型层面的界（来自 report/verification/rewired-candidate-2026-10-26）
BOUND_ZERO_DB = -4.40           # 零系数：−20log10 max|H|
BOUND_CAND_DB = 0.68            # 候选：−20log10 max|H−Ĥ|


def db(x: float) -> float:
    return 20 * np.log10(x)


def lin(d: float) -> float:
    return 10 ** (d / 20)


def solve_phase(g: float, h: float, boost_db: float) -> float:
    """由实测环路提升反推 H 在该点的相位。

    |mic/source| / |H| = 1/|1 − g·H|，实测 boost = 20log10(1/|1−g·H|)。
    |1 − gH∠φ|² = 1 + (g|H|)² − 2g|H|cosφ  → 解 cosφ。
    """
    target = lin(-boost_db)                 # |1 − gH|
    x = g * h
    cos_phi = (1 + x * x - target * target) / (2 * x)
    if not -1.0 <= cos_phi <= 1.0:
        return float("nan")
    return float(np.degrees(np.arccos(cos_phi)))


def boost_at(g_db: float, h_mag: float, phi_deg: float) -> float:
    """给定 g 与 H 的相位，闭环相对无环路的提升（dB）。可正可负。"""
    g = lin(g_db)
    H = h_mag * np.exp(1j * np.radians(phi_deg))
    den = abs(1 - g * H)
    return float(-db(den)) if den > 0 else float("inf")


def played_over_source(g_db: float, h_mag: float, phi_deg: float) -> float:
    """零臂（Ĥ ≡ 0）的 played/source：闭环把输入放大成出声的倍数。

    played(1 − gH) = source → played/source = 1/|1 − gH|。
    **这就是"音响比输入响多少 dB"，不是"提 g 换来多少响度"**——
    它在 g|H| = cosφ 处见顶，之后随 g 增大反而下降（相位差造成的）。
    """
    g = lin(g_db)
    H = h_mag * np.exp(1j * np.radians(phi_deg))
    den = abs(1 - g * H)
    return float(1.0 / den) if den > 0 else float("inf")


def main() -> int:
    h_mag = lin(H_PEAK_DB)
    g = lin(GAIN_DB)

    print("=" * 78)
    print("v3 演示工作点：从 A 的 322 Hz 三点反推（不引入新数据）")
    print("=" * 78)

    # ---------------- [1] 三个量分开 ----------------
    print("\n[1] 三个量各自是什么（先把口径分开，别混着报）")
    loop_boost = BYPASS_DB - OPEN_DB
    acoustic = BYPASS_DB - CANCEL_DB
    overshoot = OPEN_DB - CANCEL_DB
    print("    CD(322)        残差深度（A 报的 %.2f dB）" % CD_DB)
    print("                     = cancel 支路真正被最小化的量，衡量**模型拟合程度**")
    print("    环路提升        bypass − open = %.2f − %.2f = **%+.2f dB**"
          % (BYPASS_DB, OPEN_DB, loop_boost))
    print("                     = 闭环把这一带抬高了多少，**抵消最多能收回这么多**")
    print("    声学差          bypass − cancel = %.2f − %.2f = %+.2f dB"
          % (BYPASS_DB, CANCEL_DB, acoustic))
    print("                     = 环路提升 %+.2f + cancel 过冲 %+.2f = %+.2f（自洽）"
          % (loop_boost, overshoot, loop_boost + overshoot))
    print("    → **可听收益的量级是第 2 项（%+.2f dB），不是 CD，也不是声学差。**" % loop_boost)
    print("      声学差多出来的 %.2f dB 是 cancel 比 open 还低，属过抵消/估计误差，不能计入收益。"
          % overshoot)

    # ---------------- [2] 反推 H 的相位 ----------------
    phi = solve_phase(g, h_mag, loop_boost)
    print("\n[2] 由实测提升反推 322 Hz 处 H 的相位（这决定后面所有外推）")
    print("    |H| = 10^(%.2f/20) = %.4f（线性）" % (H_PEAK_DB, h_mag))
    print("    g   = 10^(%.1f/20) = %.4f，故 g|H| = %.4f（环路幅度 %.2f dB）"
          % (GAIN_DB, g, g * h_mag, db(g * h_mag)))
    print("    |1 − gH| = 10^(−%.2f/20) = %.4f" % (loop_boost, lin(-loop_boost)))
    if np.isnan(phi):
        print("    !! 解不出相位：实测提升与 |H| 不自洽，需先查两点")
    else:
        print("    → cosφ = %.4f，**φ = ±%.1f°**" % (np.cos(np.radians(phi)), phi))
        print("    → 322 Hz 处 H **不在正实轴**（差 %.0f°），所以 g+|H| 的 dB 相加只对**幅度界**成立，"
              % phi)
        print("      不能用来推「提 1 dB 增益换多少响度」。")

    # ---------------- [3] 临界 g ----------------
    print("\n[3] 临界 g（同一个 |H|，两种口径）")
    g_crit = 1.0 / h_mag
    print("    零系数：g|H| = 1 → g = 1/%.4f = %.4f = **%+.2f dB**（幅度界 %+.2f，一致）"
          % (h_mag, g_crit, db(g_crit), BOUND_ZERO_DB))
    print("    候选  ：g·max|H−Ĥ| = 1 → max|H−Ĥ| = 1/10^(%.2f/20) = %.4f，"
          % (BOUND_CAND_DB, lin(-BOUND_CAND_DB)))
    print("            故 g ≤ %.4f = **%+.2f dB**" % (1 / lin(-BOUND_CAND_DB), BOUND_CAND_DB))
    print("    → 稳定裕度差 = %+.2f − (%+.2f) = **%.2f dB**（这是界差，不是实测 ASG）"
          % (BOUND_CAND_DB, BOUND_ZERO_DB, BOUND_CAND_DB - BOUND_ZERO_DB))

    # ---------------- [4] 提 g 到底能换多少响度 ----------------
    print("\n[4] 零臂的 played/source（= 音响比输入响多少），以及提 g 能换到什么")
    print("     g(dB)  环路幅度dB  played/source dB   候选 g·|H−Ĥ|  候选余量dB")
    rows = []
    for gdb in (-14.0, -12.0, -10.0, -8.0, -6.7, -6.0, -5.0, -4.4, -4.0, -3.0, 0.0, 0.68):
        g = lin(gdb)
        loop_mag = db(g * h_mag)
        ratio = played_over_source(gdb, h_mag, phi) if not np.isnan(phi) else float("nan")
        cand_loop = g * lin(-BOUND_CAND_DB)
        margin = -db(cand_loop) if cand_loop > 0 else float("inf")
        rows.append({"gain_db": float(gdb), "loop_mag_db": float(loop_mag),
                     "played_over_source_db": (float(db(ratio)) if not np.isnan(ratio) else None),
                     "candidate_g_times_error": float(cand_loop),
                     "candidate_margin_db": float(margin),
                     "zero_arm_linear_model_valid": bool(loop_mag < 0.0),
                     "candidate_ok": bool(cand_loop < 1.0)})
        print("    %+6.1f   %+7.2f      %+8.2f          %.3f        %+7.2f"
              % (gdb, loop_mag, db(ratio) if not np.isnan(ratio) else float("nan"),
                 cand_loop, margin))
    print("    ⚠ 三点必须看清：")
    g_at_peak = np.cos(np.radians(phi)) / h_mag          # played/source 的峰在 g|H| = cosφ
    print("      · played/source 在 **g = %+.1f dB 见顶 %.2f dB**，之后提 g 反而更小——"
          % (db(g_at_peak), db(played_over_source(db(g_at_peak), h_mag, phi))))
    print("        因为 φ≈%.0f°，|1−gH| 的增长快于 g。**−8 dB 时的 3.75 dB 已经贴近这个顶。**" % phi)
    print("      · g ≥ %+.2f dB 之后零臂已自激，线性模型不再适用（那几行只是外推，不可达）。"
          % BOUND_ZERO_DB)
    print("      · 候选那 5.08 dB 增益余量**换算成多少输出，离线算不出**——见 [5]。")

    # ---------------- [5] 各自取自己的最大可用 g ----------------
    print("\n[5] 候选能多开 5 dB 增益，但换成多少输出：离线未知（这条要如实写）")
    print("    零臂：played/source = 1/|1 − gH|，H 已知（幅度 + 相位由 [2] 反解）→ 可算。")
    print("    候选：played/source = 1/|1 − g(H−Ĥ)|，需要 **H−Ĥ 的幅度与相位**。")
    print("          幅度有（max %.4f），**相位没有**：离线只有 |H−Ĥ| 的逐点模，没有它的辐角。" % lin(-BOUND_CAND_DB))
    print("          若同相，g 逼近临界时它会发散；若反相，它会小于 1。区间太宽，等于没有。")
    print("    → **所以「候选能不能开得更大声」在离线只能记未知，必须现场同 g 对照测。**")
    print("      能写进报告的只有：候选的稳定裕度比零臂高 %.2f dB（界差，非实测 ASG）。"
          % (BOUND_CAND_DB - BOUND_ZERO_DB))

    # ---------------- [6] 判据建议 ----------------
    print("\n[6] bypass vs cancel 对照：建议的量与阈值（同 g、同源、同距离）")
    print("    主判据（现场可做、可复算）：")
    print("      322 Hz 三点复测，同一 g 下报三个数：")
    print("        · 环路提升 = bypass − open      （本次 %+.2f dB）" % loop_boost)
    print("        · 声学差   = bypass − cancel    （本次 %+.2f dB）" % acoustic)
    print("        · 过冲     = open − cancel      （本次 %+.2f dB，应≈0）" % overshoot)
    print("      判读：声学差 ≥ 环路提升 − 1.5 dB 且过冲在 ±1.5 dB 内 → 抵消在该点成立。")
    print("    语音臂（唯一能说「可听」的量）：同一句话、同一距离、同一 g，两臂各 3 遍；")
    print("      读数 = 300–460 Hz 能量占比 + 宽带 RMS；听感由听众两次、顺序随机判断。")
    print("    必须同时满足才判这一臂有效：bit22=0、四类饱和计数 0、峰值 ≤ −6 dBFS、completed。")

    payload = {
        "schema_version": 1,
        "source": "report/verification/audio-replay/wide-residual-v3/evidence.json"
                  "#steady_state_tone_three_point",
        "measured": {"open_db": OPEN_DB, "bypass_db": BYPASS_DB, "cancel_db": CANCEL_DB,
                     "cd_db": CD_DB, "gain_db": GAIN_DB,
                     "h_peak_db": H_PEAK_DB, "h_peak_hz": H_PEAK_HZ},
        "decomposition": {"loop_boost_db": loop_boost, "acoustic_diff_db": acoustic,
                          "cancel_overshoot_db": overshoot},
        "inferred": {"h_mag_linear": h_mag, "g_linear": g, "g_times_h_mag": g * h_mag,
                     "phase_deg": None if np.isnan(phi) else abs(phi),
                     "phase_sign_ambiguous": True},
        "bounds": {"zero_arm_gain_db": BOUND_ZERO_DB, "candidate_gain_db": BOUND_CAND_DB,
                   "max_abs_H_minus_Hhat": lin(-BOUND_CAND_DB),
                   "margin_gap_db": BOUND_CAND_DB - BOUND_ZERO_DB},
        "gain_sweep": rows,
        "loudness_caveat": "g/|1-gH| 只用于同频点相对比较；不是绝对声压，不分频带。",
        "not_proven": ["ASG", "宽带可听收益", "语音条件下的稳定性", "12 cm 下的合格候选臂"],
    }
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
        print("\n结构化结果写入 %s" % args.json_out)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    raise SystemExit(main())
