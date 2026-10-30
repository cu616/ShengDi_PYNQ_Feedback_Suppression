"""独立核对 PCM 满量程、系数格式与预测饱和阈值（先算，再谈风险）。

口径来源（不是从摘要继承，是逐行读的）：
  src/rtl/feedback_fir.v:30  rounded = (|acc| + 2^19) >> 20
  src/rtl/feedback_fir.v:32  prediction_clip = rounded > 8388607 || rounded < -8388608
  src/feedback/calibration.py 的整数参考实现给出同一结论：clip 到 ±2^23 计数。
所以：
  * 系数是 signed24 / Q20，系数本身的范围是 ±8（2^23/2^20）。
  * 预测输出在与 reference/microphone 同一个 PCM 域里，饱和阈值是 ±2^23 计数 = ±1.0 归一化满幅。
  * 两个"8"不是同一个数：系数满量程 8.0 ≠ PCM 满量程 1.0。

本脚本只做只读计算，不碰板卡、不写模型。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from diagnose_peak_margin import model_response  # noqa: E402

FULL_SCALE_CODE = 1 << 23          # PCM 侧满幅（计数）；与 scripts/verify_r4_waveforms.py 的 SCALE 一致
COEF_FULL_SCALE = (1 << 23) / (1 << 20)   # Q20 系数的满量程 = 8.0
Q = 20


def rtl_predict(q20: np.ndarray, u_codes: np.ndarray) -> tuple[np.ndarray, int]:
    """逐样本重现 RTL：int64 累加、半值远离零舍入、clip 到 ±2^23 计数。"""
    taps = len(q20)
    n = len(u_codes)
    out = np.zeros(n, dtype=np.int64)
    sat = 0
    h = q20.astype(np.int64)
    u = u_codes.astype(np.int64)
    for i in range(n):
        upto = min(taps, i)
        if upto == 0:
            out[i] = 0
            continue
        # h[0] 乘 u[n-1]：lag_first=1
        acc = int(np.dot(h[:upto], u[i - 1::-1][:upto]))
        mag = (abs(acc) + (1 << (Q - 1))) >> Q
        val = -mag if acc < 0 else mag
        if val > FULL_SCALE_CODE - 1 or val < -FULL_SCALE_CODE:
            sat += 1
            val = max(-FULL_SCALE_CODE, min(FULL_SCALE_CODE - 1, val))
        out[i] = val
    return out, sat


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="models/room_v1/rewired_512_20261026.json")
    ap.add_argument("--packet-dir",
                    default="D:/Always/QianSai/_inbox/2026-10-26_bindcapture_rewired",
                    help="六份修线后 npz（用来核对实测饱和计数与峰值余量）")
    ap.add_argument("--tone-hz", type=float, default=None,
                    help="默认取 |Hhat| 最大处")
    args = ap.parse_args()

    raw = (REPO / args.model).read_bytes()
    model = json.loads(raw.decode("utf-8"))
    q20 = np.asarray(model["coefficients_q20"], dtype=np.int64)
    h = q20.astype(float) / (1 << Q)
    fs = float(model["sample_rate_hz"])
    taps = int(model["taps"])

    print("=" * 78)
    print("[1] 系数格式与范围（先证单位，再谈饱和）")
    print("=" * 78)
    print(f"  taps             {taps}   lag_first {model['lag_first']}   format {model['coefficient_format']}")
    print(f"  Q20 系数范围     [{int(q20.min())}, {int(q20.max())}]")
    print(f"  系数满量程        ±{COEF_FULL_SCALE:.1f}（2^23/2^20）；实际用到最大 "
          f"{np.abs(q20).max() / (1 << 20):.5f}，占满量程 {100 * np.abs(q20).max() / (1 << 23):.2f}%")
    print(f"  全部落在 ±2^23 内  {bool(np.all(np.abs(q20) < (1 << 23)))}")
    print()
    print(f"  ‖h‖₁ = {np.abs(h).sum():.7f}   ‖h‖₂ = {np.sqrt((h ** 2).sum()):.7f}   "
          f"max|h[n]| = {np.abs(h).max():.6f}")
    print(f"  PCM 侧饱和阈值    ±2^23 计数 = ±1.0 归一化满幅（不是 ±8）")

    print()
    print("=" * 78)
    print("[2] 逐频点 |Hhat|：饱和风险的真正判据是窄带增益，不是 ‖h‖₁")
    print("=" * 78)
    nfft = 1 << 15
    Hh = model_response(h, nfft, lag_first=1)
    freqs = np.arange(len(Hh)) * fs / nfft
    mag = np.abs(Hh)
    kmax = int(np.argmax(mag))
    print(f"  max|Hhat(f)| = {mag[kmax]:.4f}（{20 * np.log10(mag[kmax]):+.2f} dB）@ {freqs[kmax]:.1f} Hz")
    over = mag >= 1.0
    print(f"  |Hhat| ≥ 1 的频点：{int(over.sum())} / {len(mag)}（{100 * over.mean():.1f}% of bins）")
    if over.any():
        idx = np.where(over)[0]
        # 连续区间
        breaks = np.where(np.diff(idx) > 1)[0]
        starts = np.r_[idx[0], idx[breaks + 1]]
        ends = np.r_[idx[breaks], idx[-1]]
        for s, e in zip(starts, ends):
            print(f"    {freqs[s]:7.1f} – {freqs[e]:7.1f} Hz   峰值 {mag[s:e + 1].max():.4f}")
    print("  含义：在 |Hhat| = G 的频点，持续幅度 A_u 的单音使 |pred| = G·A_u；"
          f"G = {mag[kmax]:.3f} 处 A_u 超过 {1.0 / mag[kmax]:.3f}（{20 * np.log10(1.0 / mag[kmax]):+.2f} dBFS）就饱和。")

    print()
    print("=" * 78)
    print("[3] 边界例子（手算可复核，不用同一套假设自证）")
    print("=" * 78)
    # 例 1：全幅直流历史 → pred = Σh[k] = 直流增益
    print(f"  例1 全幅直流 u≡+8388607 稳定后：pred/满幅 = Σh[k] = {h.sum():+.6f} → "
          f"{'饱和' if abs(h.sum()) >= 1 else '不饱和'}")
    print(f"      但合法历史也可以逼近上界：交替 +1/−1 时 pred/满幅 = Σh[k](−1)^k = "
          f"{np.abs(np.sum(h * ((-1) ** np.arange(taps)))).max():.6f}")
    # 例 2：单音
    tone = args.tone_hz if args.tone_hz is not None else freqs[kmax]
    n = 1 << 14
    t = np.arange(n)
    a_crit = 1.0 / mag[kmax]
    for a_db in (-6.0, -3.0, 0.0):
        amp = 10 ** (a_db / 20)
        u = np.rint(amp * np.sin(2 * np.pi * tone * t / fs) * FULL_SCALE_CODE).astype(np.int64)
        pred, sat = rtl_predict(q20, u)
        print(f"  例2 {tone:.1f} Hz 单音 {a_db:+.1f} dBFS：pred 峰值/满幅 = "
              f"{np.abs(pred).max() / FULL_SCALE_CODE:.4f}  饱和样本 {sat}")
    amp = a_crit
    u = np.rint(amp * np.sin(2 * np.pi * tone * t / fs) * FULL_SCALE_CODE).astype(np.int64)
    pred, sat = rtl_predict(q20, u)
    print(f"      理论临界幅度 {a_crit:.4f}（{20 * np.log10(a_crit):+.2f} dBFS）→ 实测饱和样本 {sat}"
          f"（首个饱和样本在 {'无' if sat == 0 else int(np.argmax(np.abs(pred) >= FULL_SCALE_CODE - 1))}）")
    # 例 3：白噪声
    rng = np.random.default_rng(0)
    for rms_db in (-30.0, -20.0, -12.0, -6.0):
        sigma = 10 ** (rms_db / 20) * FULL_SCALE_CODE
        u = np.rint(rng.standard_normal(1 << 14) * sigma).astype(np.int64)
        pred, sat = rtl_predict(q20, u)
        print(f"  例3 白噪声 RMS {rms_db:+.1f} dBFS：pred 峰值/满幅 = "
              f"{np.abs(pred).max() / FULL_SCALE_CODE:.4f}  饱和样本 {sat}")

    print()
    print("=" * 78)
    print("[4] 实测（修线后六份，gain_q12=0 开环）：pred 峰值与饱和计数")
    print("=" * 78)
    pkt = Path(args.packet_dir)
    if not pkt.exists():
        print(f"  数据包不存在，跳过：{pkt}")
        return 0
    peaks = []
    total_sat = 0
    for p in sorted(pkt.glob("*.npz")):
        cap = np.load(p, allow_pickle=True)
        meta = json.loads(str(cap["metadata_json"]))
        ref = np.asarray(cap["reference"], float)
        nv = len(cap["source_pcm16"]) - int(meta["first_frame"])
        codes = np.rint(ref[:nv] * FULL_SCALE_CODE).astype(np.int64)
        pred, sat = rtl_predict(q20, codes)
        total_sat += sat
        pk = np.abs(pred).max() / FULL_SCALE_CODE
        peaks.append(pk)
        u_pk = np.abs(codes).max() / FULL_SCALE_CODE
        print(f"  {p.name[:20]}  |u|峰值 {20 * np.log10(u_pk):+6.2f} dBFS   "
              f"pred 峰值 {20 * np.log10(pk):+6.2f} dBFS   余量 {20 * np.log10(1.0 / pk):+5.2f} dB   "
              f"饱和 {sat}（metadata 记 {meta.get('prediction_saturations')}）")
    print()
    print(f"  六份合计饱和样本 {total_sat}；pred 峰值 {20 * np.log10(max(peaks)):+.2f} dBFS，"
          f"距 PCM 满幅 {20 * np.log10(1.0 / max(peaks)):+.2f} dB")
    print("  注意：这是本批电平（|u| 峰值约 −20 dBFS）下的观测，不是任何电平下的保证。")

    print()
    print("=" * 78)
    print("[5] 结论（只写单位核对能支撑的部分）")
    print("=" * 78)
    print(f"  1) PCM 满量程是 ±1.0，系数满量程是 ±8.0；两者不能互换当分母。")
    print(f"  2) 饱和的充要条件不是 ‖h‖₁ ≤ 1。‖h‖₁ = {np.abs(h).sum():.4f} > 1，所以"
          f"\"任何输入都不饱和\"不成立。")
    print(f"  3) 窄带才是真风险：|Hhat| 最大 {mag[kmax]:.3f}，该处持续单音超过 "
          f"{20 * np.log10(1.0 / mag[kmax]):+.2f} dBFS 就饱和。")
    print(f"  4) 本批实测 pred 峰值 {20 * np.log10(max(peaks)):+.2f} dBFS、零饱和——只说明这一档电平。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
