"""成功点 vs 削顶点：先把"耦合"和"环路裕量"的口径分开，再看模型能不能解释 A 的增益台阶。

回答的问题（只回答这一个）：
  为什么两次零系数近讲能清晰扩声，后续所谓相同条件却输入削顶？

做法：
  [1] 输入资格（复用已验收的 load_packet：逐文件 sha256 + 实际数据判开环）
  [2] 同一份 H，五种都叫"耦合"的统计量 —— 用来把 A 的三个数各自归位
  [3] 环路裕量按增益台阶算，与 A 的实测台阶逐档对照
  [4] 候选能把台阶推多少（离线界差，不是现场收益）
  [5] 那两个解释各自的可检验预言

不加载模型、不碰板卡、不发声。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from answer_new_layout_325 import align_segments, load_packet, write_aligned  # noqa: E402
from diagnose_peak_margin import estimate_H, model_response  # noqa: E402
from reproduce_b_screening import thresholds  # noqa: E402

DB = lambda x: 20 * np.log10(np.abs(x) + 1e-30)  # noqa: E731
CANDIDATE = REPO / "models/room_v1/rewired_512_20261026.json"

# A 的实测台阶（scene-input-2026-10-26.json 的 a_limits_basis，原话）
A_LADDER = [
    (0.0, "满幅啸叫（oscilates at full scale）"),
    (-4.0, "响但浑（loud but muddy），主频占比 0.68"),
    (-6.0, "接近再生的掩蔽（near-regeneration masking），占比 0.37–0.70"),
    (-8.0, "稳定（stable），331 Hz 占比 0.12–0.16"),
]

# 历史成功点与削顶点（usable-point / mic-fault-impact 原值）
SUCCESS = {
    "gain_db": -8.0, "talker_cm": 5,
    "mic_rms_dbfs": [-27.9, -24.3], "mic_peak_dbfs": [-11.3, -12.0],
    "mode_hz": [253, 298], "mode_share": [0.36, 0.42],
}
CLIP = {"gain_db": -8.0, "talker_cm": 5, "mic_rms_dbfs": -4.0, "mic_peak_dbfs": 0.0}


def coupling_definitions(H, freqs, coh, gate, mic, ref):
    """同一个 H，五种都被叫过"耦合"的数字。口径写清，避免互相替换。"""
    g = gate & (freqs >= 300.0)
    inside = g & (freqs <= 10250.0)
    return {
        "A_时间域电平比_db": 20 * np.log10(np.sqrt(np.mean(mic ** 2)) / np.sqrt(np.mean(ref ** 2))),
        "B_带内能量平均_db": 10 * np.log10(np.mean(np.abs(H[inside]) ** 2)),
        "C_带内幅度中位_db": float(np.median(DB(H[inside]))),
        "D_带内幅度峰值_db": float(np.max(DB(H[inside]))),
        "E_峰值处频率_hz": float(freqs[inside][int(np.argmax(np.abs(H[inside])))]),
        "覆盖门控bin": int(inside.sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet-dir", default="D:/Always/QianSai/_inbox/2026-10-26_bindcapture_rewired")
    ap.add_argument("--nfft", type=int, default=8192)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    print("=" * 78)
    print("[1] 输入资格（实际数据判，不看摘要标签）")
    print("=" * 78)
    segs, records = load_packet(args.packet_dir)
    fs = segs[0]["fs"]
    for s in segs:
        m = s["meta"]
        print(f"  {s['name'][:20]}  gain_q12={m['gain_q12']}  bypass={m['bypass']}  "
              f"ref-vs-source {s['reference_vs_source_db']:+.4f} dB  "
              f"bit_exact={m['verification']['bit_exact']}  sat={m['prediction_saturations']}/"
              f"{m['residual_saturations']}")
    print(f"  → {len(segs)} 份全部通过；reference 与 source_pcm16/32768 逐样本相同 ⇒ 真开环")

    print()
    print("=" * 78)
    print(f"[2] 同一份 H，五种\"耦合\"口径（nfft={args.nfft}，bin {fs / args.nfft:.2f} Hz）")
    print("=" * 78)
    aligned, lags, target = align_segments(segs)
    nv = min(int(s["source_frames_in_window"]) for s in segs)
    aligned = [(u[:nv], m[:nv]) for u, m in aligned]
    paths = write_aligned(aligned, fs, Path(tempfile.mkdtemp(prefix="xclip_")))
    freqs, H, coh, _S, _n, fsx = estimate_H(paths, nperseg=args.nfft)
    gate = (coh >= 0.8) & (freqs >= 300.0)
    mic_all = np.concatenate([m[512:] for _u, m in aligned])
    ref_all = np.concatenate([u[512:] for u, _m in aligned])

    defs = coupling_definitions(H, freqs, coh, gate, mic_all, ref_all)
    for k, v in defs.items():
        unit = "bin" if k.startswith("覆盖") else ("Hz" if k.endswith("hz") else "dB")
        print(f"  {k:<22} {v:9.2f} {unit}" if unit != "bin" else f"  {k:<22} {v:9d} {unit}")
    peak_hz = defs["E_峰值处频率_hz"]
    print()
    print(f"  → A 记的\"宽带开环耦合 −10…−12 dB\"对应 {defs['B_带内能量平均_db']:+.2f} dB（口径 B）")
    print(f"  → A 记的四次重复性 −5.5/−2.5/−5.6/−4.5 dB 与口径 B 同量级，属同一定义下的波动")
    print(f"  → **稳定性用的是峰值，不是平均值**：口径 D {defs['D_带内幅度峰值_db']:+.2f} dB @ {peak_hz:.1f} Hz")

    print()
    print("=" * 78)
    print("[3] 环路裕量逐档：g + 20log10|H|峰值 vs A 的实测台阶")
    print("=" * 78)
    print("  增益dB   环路增益dB(峰值)   小增益余量dB    A 实测")
    observed = dict(A_LADDER)
    for g in (0.0, -4.0, -6.0, -8.0, -10.0, -12.0, -14.0):
        loop = g + defs["D_带内幅度峰值_db"]
        note = observed.get(g, "（未测）")
        print(f"  {g:+6.1f}   {loop:+14.2f}   {-loop:12.2f}    {note}")
    print()
    print("  判读：A 记的 \"loop gain = −8 + (−11) = −19 dB，远低于 1\" 用的是能量平均（口径 B）。")
    print("  峰值口径下 −8 dB 的环路增益是 "
          f"{-8.0 + defs['D_带内幅度峰值_db']:+.2f} dB，不是 −19 dB；两者差 "
          f"{defs['D_带内幅度峰值_db'] - defs['B_带内能量平均_db']:.1f} dB。")
    print("  实测台阶（0 dB 满幅 / −4 浑 / −6 近再生 / −8 稳）与峰值口径逐档一致，与 −19 dB 不自洽。")

    print()
    print("=" * 78)
    print("[4] 候选能把这套台阶推多少（离线，不是现场收益）")
    print("=" * 78)
    model = json.loads(CANDIDATE.read_bytes().decode("utf-8"))
    hq = np.asarray(model["coefficients_q20"], float) / (1 << 20)
    zero_t = thresholds(H, np.zeros_like(H), freqs, gate, fsx, 2)
    cand_t = thresholds(H, model_response(hq, args.nfft, lag_first=1), freqs, gate, fsx, 2)
    shift = cand_t["small_gain_bound_db"] - zero_t["small_gain_bound_db"]
    print(f"  零系数 小增益界 {zero_t['small_gain_bound_db']:+.2f} dB @ {zero_t['small_gain_at_hz']:.1f} Hz")
    print(f"  候选   小增益界 {cand_t['small_gain_bound_db']:+.2f} dB @ {cand_t['small_gain_at_hz']:.1f} Hz")
    print(f"  差 {shift:+.2f} dB（同一 FFT 网格、同一门控规则下的离线界差；不是现场保底）")
    print()
    print("  按\"台阶整体平移\"给预测（平移量 = 上面的界差，仍是假设）：")
    print("    零系数刻度          候选预测刻度")
    for g, label in ((-8.0, "稳"), (-6.0, "近再生"), (-4.0, "浑"), (0.0, "满幅")):
        print(f"    g={g:+5.1f} {label:<4}  →  g≈{g + shift:+5.1f} 出现同类现象")
    print()
    print("  → 也就是说：候选若兑现，允许的增益档从 −8 上移到约 "
          f"{(-8.0 + shift):+.1f} → 允许的五档（−14…−6）内应当全部干净。")

    # 静音源台阶（A 的 ab-stale-vs-nomodel，零系数）：实测自激边界
    print()
    print("  静音源台阶（A 的 ab-stale-vs-nomodel 记录，零系数）：")
    silent = [(-4.0, -36.6, 0.19, "stable"), (-3.0, -35.2, 0.47, "marginal"),
              (-2.0, -14.3, 1.00, "howling"), (-1.0, -7.4, 1.00, "howling"),
              (0.0, -6.4, 1.00, "howling")]
    for g, mic, share, verdict in silent:
        print(f"    g={g:+5.1f} dB  mic {mic:+6.1f} dBFS  {328} Hz 占比 {share:.2f}  {verdict}")
    print(f"    → 实测自激边界在 −3 与 −2 之间（≈ −2.5 dB）；小增益界给 {zero_t['small_gain_bound_db']:+.2f} dB，")
    print(f"      即界比实测保守约 {(-2.5) - zero_t['small_gain_bound_db']:.1f} dB。界是充分条件，保守是正常的。")
    print()
    print("  328 Hz 共振抬升（线性估计，boost = −20log10|1−g·|H||）：")
    print("    增益dB  零系数 loop/boost      候选 loop/boost      差dB")
    for g in (-14.0, -12.0, -10.0, -8.0, -6.0):
        gv = 10 ** (g / 20)
        zl = gv * 10 ** (defs["D_带内幅度峰值_db"] / 20)
        cl = gv * 10 ** (-cand_t["small_gain_bound_db"] / 20)
        zb = -20 * np.log10(1 - zl) if zl < 1 else float("nan")
        cb = -20 * np.log10(1 - cl) if cl < 1 else float("nan")
        print(f"    {g:+6.1f}   {20 * np.log10(zl):+6.2f} dB / {zb:+6.1f} dB"
              f"    {20 * np.log10(cl):+6.2f} dB / {cb:+6.1f} dB    {zb - cb:+5.1f}")
    print("    → 允许的五档内两臂都不会自激，差别只体现在\"源还在放时 328 Hz 一带被抬高多少\"。")
    print("      候选@−6（loop "
          f"{20 * np.log10(10 ** (-6 / 20) * 10 ** (-cand_t['small_gain_bound_db'] / 20)):+.2f} dB）"
          f"应与零系数@−12（loop "
          f"{20 * np.log10(10 ** (-12 / 20) * 10 ** (defs['D_带内幅度峰值_db'] / 20)):+.2f} dB）同量级。")

    print()
    print("=" * 78)
    print("[5] 两个解释各自的可检验预言（用来定夺 24 dB 缺口）")
    print("=" * 78)
    cf = [SUCCESS["mic_peak_dbfs"][i] - SUCCESS["mic_rms_dbfs"][i] for i in range(2)]
    print(f"  成功两次：mic RMS {SUCCESS['mic_rms_dbfs']} dBFS，peak {SUCCESS['mic_peak_dbfs']} dBFS，"
          f"波峰因数 {cf[0]:.1f}/{cf[1]:.1f} dB（语音正常，未削顶）")
    cf_clip = CLIP["mic_peak_dbfs"] - CLIP["mic_rms_dbfs"]
    print(f"  削顶一次：mic RMS {CLIP['mic_rms_dbfs']} dBFS，peak {CLIP['mic_peak_dbfs']} dBFS，"
          f"波峰因数 {cf_clip:.1f} dB（削平）")
    print(f"  同一位置 5 cm，两次成功比削顶低 "
          f"{CLIP['mic_rms_dbfs'] - SUCCESS['mic_rms_dbfs'][0]:.1f}/"
          f"{CLIP['mic_rms_dbfs'] - SUCCESS['mic_rms_dbfs'][1]:.1f} dB")
    print()
    print("  解释一（输入链当时更不灵敏）：环路增益也一起低 20–24 dB → 近讲那次几乎没有反馈，")
    print("    听到的是\"无环路的放大\"。预言：成功那两次若真在 5 cm，谱的低频近讲抬升应很明显；")
    print("    且主频应由语句决定（两次不同 = 253/298 Hz），不应固定在环路模态上。")
    print("  解释二（当时实际距离远大于 5 cm）：链路灵敏度未变，只是声学距离不同。")
    print("    预言：成功那两次的谱形应接近 25–80 cm 的远场（低频无明显近讲抬升），")
    print("    且 331 Hz 一带应与当前 −8 dB 的状态同强（环路一直是活的）。")
    print()
    print("  现有摘要能给的唯一线索：两次成功的主频是 253 与 298 Hz，两次不同；")
    print("  而当前同一几何下的环路模态在 "
          f"{peak_hz:.0f} Hz 附近（失败固定不动）。主频随时间变 ⇒ 更像语句谱峰，不像环路模态。")
    print("  这条只是倾向，不能定案：还要成功那两次的原件看低频倾斜和语音间隙的衰减。")

    print()
    print("=" * 78)
    print("[6] 两个解释对\"明天第一次测量\"的预言（两种解释给出同一个数）")
    print("=" * 78)
    for d_cm in (25.0, 40.0):
        # 解释一：当时 5 cm + 链路低 24 dB → 灵敏度差 23.9 dB；到 25/40 cm 再降距离项
        lv1 = CLIP["mic_rms_dbfs"] - 20 * np.log10(d_cm / 5.0)
        # 解释二：链路灵敏度不变，当时实际距离 ≈ 5*10^(23.9/20) ≈ 79 cm
        d_was = 5.0 * 10 ** (abs(CLIP["mic_rms_dbfs"] - SUCCESS["mic_rms_dbfs"][0]) / 20)
        lv2 = SUCCESS["mic_rms_dbfs"][0] + 20 * np.log10(d_was / d_cm)
        print(f"  {d_cm:4.0f} cm：解释一预言 RMS {lv1:+6.2f} dBFS ｜ 解释二（当时实际 ≈ {d_was:.0f} cm）"
              f"预言 {lv2:+6.2f} dBFS  → 两条路径同一个数，明天这一步不能区分解释")
        pk = lv1 + cf[0]
        print(f"          若波峰因数回到 {cf[0]:.1f} dB，峰值 ≈ {pk:+.1f} dBFS；"
              f"现场门槛是峰值 < −6 dBFS → {'不合格' if pk > -6 else '合格'}"
              f"（需要 RMS ≤ {-6 - cf[0]:.1f} dBFS）")
    print()
    print("  → 要让峰值过 −6 dBFS，RMS 必须 ≤ −22.6 dBFS（按 16.6 dB 波峰因数）；")
    print("    按上面的预测，25 cm 的 RMS 约 −18 dBFS，还差约 4.6 dB → 距离要到 40 cm 量级，或降源电平。")
    print("    这是算术推断，不是测量；手机源本身的电平和 AGC 都未知，以现场实测为准。")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps({"coupling_definitions": defs,
                        "zero_bound_db": zero_t["small_gain_bound_db"],
                        "zero_bound_hz": zero_t["small_gain_at_hz"],
                        "candidate_bound_db": cand_t["small_gain_bound_db"],
                        "candidate_bound_hz": cand_t["small_gain_at_hz"],
                        "bound_shift_db": shift,
                        "lags": lags, "aligned_to": int(target),
                        "nfft": args.nfft, "gated_bins": int(gate.sum())},
                       indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\n结构化结果写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
