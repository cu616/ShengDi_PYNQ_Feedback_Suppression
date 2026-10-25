"""回答"512 抽头能不能在最差频段给到 15 dB 抑制"的增益预算（只读，不改模型）。

口径（全部沿用 r4 修订 1，不新增定义）：
    D(f)      = e^{−jω·2}                      两帧调度延迟
    L(f)      = (H(f) − Ĥ(f)) · D(f)           抵消后的环路（Ĥ 含 lag_first=1）
    采样网格小增益界 = −20·log10 max|L|        充分条件下的上界，不是"最大允许增益"
    该 bin 的抑制 CD = 20·log10(|H|/|H−Ĥ|)
    工作点是否安全: g_dB + |H−Ĥ|_dB < 0

判据只在这批过门控 bin 上成立；未覆盖频段一律记未知。

用法：
  python scripts/answer_gain_budget.py --data-dir <lowband2> \
      --model models/room_v1/calibrated_20261024.json --out-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose_peak_margin import (  # noqa: E402
    FMIN_HZ,
    estimate_H,
    load_deployed_model,
    model_response,
)

BANDS = [(300, 1000), (1000, 3000), (3000, 6000), (6000, 8200), (8200, 8600), (8600, 10250)]
FS_DEFAULT = 48828.125
RIDGE = 1e-12


def seg_key(path):
    tail = Path(path).stem.split("_")[-1]
    return int(tail) if tail.isdigit() else 10 ** 6


def list_segments(directory):
    return sorted(glob.glob(str(Path(directory) / "seg_*.npz")), key=seg_key)


def log_db(x):
    return float(20 * np.log10(max(float(x), 1e-30)))


def per_band(freqs, H, E, L, gate, g_db):
    """逐带给出绑定 bin 的 |H|、|H−Ĥ|、CD 与允许增益。"""
    rows = []
    for lo, hi in BANDS:
        sel = gate & (freqs >= lo) & (freqs < hi)
        row = {"band": "%d-%d" % (lo, hi), "gated": int(sel.sum()),
               "bins": int(((freqs >= lo) & (freqs < hi)).sum())}
        if not sel.any():
            row["note"] = "无过门控 bin（未知）"
            rows.append(row)
            continue
        # 绑定 bin：抵消后环路最大处（不是 |H| 最大处——两者可以不同）
        idx = np.where(sel)[0]
        k = int(idx[np.argmax(np.abs(L[idx]))])
        amp_h, amp_e = float(np.abs(H[k])), float(np.abs(E[k]))
        cd = 20 * np.log10(amp_h / max(amp_e, 1e-30))
        row.update(binding_hz=float(freqs[k]),
                   h_db=log_db(amp_h), e_db=log_db(amp_e), cd_db=float(cd),
                   allowed_gain_db=float(-log_db(float(np.abs(L[k])))),
                   needed_cd_at_g_db=float(g_db + log_db(amp_h)),
                   margin_db=float(cd - (g_db + log_db(amp_h))))
        rows.append(row)
    return rows


def fit_segmentwise(paths, taps, ridge=RIDGE):
    """逐段构造法方程（段间不共享历史），与 reproduce_b_screening 的拟合口径一致。"""
    gram = None
    rhs = None
    for p in paths:
        with np.load(p) as cap:
            u = np.asarray(cap["reference"], dtype=np.float64)
            m = np.asarray(cap["microphone"], dtype=np.float64)
        x = np.lib.stride_tricks.sliding_window_view(u, taps)[:-1, ::-1]
        y = m[taps:]
        g = x.T @ x
        b = x.T @ y
        gram = g if gram is None else gram + g
        rhs = b if rhs is None else rhs + b
    gram = gram + np.eye(taps) * np.trace(gram) * ridge
    return np.linalg.solve(gram, rhs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", default="models/room_v1/calibrated_20261024.json")
    ap.add_argument("--nfft", type=int, default=8192)
    ap.add_argument("--coherence", type=float, default=0.8)
    ap.add_argument("--delay-frames", type=int, default=2)
    ap.add_argument("--train", default="0-9")
    ap.add_argument("--valid", default="10-15")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out = Path(args.out_dir) if args.out_dir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    lines = []

    def say(text=""):
        print(text)
        lines.append(text)

    def span(spec):
        lo, hi = spec.split("-")
        return list(range(int(lo), int(hi) + 1))

    paths = list_segments(args.data_dir)
    by_id = {seg_key(p): p for p in paths}
    tr = [by_id[i] for i in span(args.train) if i in by_id]
    va = [by_id[i] for i in span(args.valid) if i in by_id]
    if not tr or not va:
        raise SystemExit("训练/留出段不足：train=%d valid=%d" % (len(tr), len(va)))

    model, coef, info = load_deployed_model(args.model)
    freqs, H, coh, _S, nfft, fs = estimate_H(va, nperseg=args.nfft)
    gate = (coh >= args.coherence) & (freqs >= FMIN_HZ)
    E = H - model_response(coef, nfft, lag_first=info["lag_first"])
    L = E * np.exp(-1j * 2 * np.pi * args.delay_frames * freqs / fs)

    say("=" * 78)
    say("[1] 输入")
    say("  数据 %s：训练 seg_%s（%d 段）/ 留出 seg_%s（%d 段）"
        % (Path(args.data_dir).name, args.train, len(tr), args.valid, len(va)))
    say("  模型 %s  taps=%d  lag_first=%d  q20=%s"
        % (Path(args.model).name, info["taps"], info["lag_first"], info["q20_sha256"][:16]))
    say("  nfft=%d（bin %.2f Hz），过门控 %d/%d bin（%.1f%%），延迟 %d 拍"
        % (nfft, fs / nfft, gate.sum(), len(freqs), 100.0 * gate.sum() / len(freqs),
           args.delay_frames))

    say("\n[2] 最差频段：512 抽头在这批数据上的实际抑制深度")
    say("  %-10s %6s %10s %9s %9s %8s %10s %8s"
        % ("频带", "门控", "绑定Hz", "|H|dB", "|H-Ĥ|dB", "CD dB", "小增益界", "余量dB"))
    rows = per_band(freqs, H, E, L, gate, 6.0)
    for r in rows:
        if r.get("note"):
            say("  %-10s %6s %s" % (r["band"], "%d/%d" % (0, r["bins"]), r["note"]))
            continue
        say("  %-10s %6s %10.0f %+9.2f %+9.2f %8.2f %+10.2f %+8.2f"
            % (r["band"], "%d/%d" % (r["gated"], r["bins"]), r["binding_hz"],
               r["h_db"], r["e_db"], r["cd_db"], r["allowed_gain_db"], r["margin_db"]))

    # 2b 逐频查表：A 拿到自己的 |H(f)| 后，直接查这一列就知道该点 512 能给多少 CD
    say("\n[2b] 逐频查表（最近邻 bin；未过门控记未知）—— A 用自己曲线的峰值频点查这一列")
    say("  %8s %9s %9s %9s %10s %10s"
        % ("f Hz", "|H|dB", "|H−Ĥ|dB", "CD dB", "该点小增益界", "g=+6时差"))
    grid = []
    for fc in (300, 350, 400, 435, 500, 600, 700, 850, 1000, 1200, 1500, 1800, 2000,
               2500, 3000, 3500, 3900, 4500, 5000, 6000, 7000, 8000, 8300, 8400, 8800,
               9000, 9500, 10000):
        k = int(np.argmin(np.abs(freqs - fc)))
        if not gate[k]:
            say("  %8.0f %9s %9s %9s %10s %10s" % (fc, "—", "—", "未知", "未知", "未知"))
            grid.append({"hz": float(freqs[k]), "gated": False})
            continue
        amp_h, amp_e = float(np.abs(H[k])), float(np.abs(E[k]))
        cd = 20 * np.log10(amp_h / max(amp_e, 1e-30))
        gap = cd - (6.0 + log_db(amp_h))
        grid.append({"hz": float(freqs[k]), "gated": True, "h_db": log_db(amp_h),
                     "e_db": log_db(amp_e), "cd_db": float(cd),
                     "allowed_gain_db": float(-log_db(float(np.abs(L[k])))),
                     "gap_at_g6_db": float(gap)})
        say("  %8.0f %+9.2f %+9.2f %9.2f %+10.2f %+10.2f"
            % (freqs[k], log_db(amp_h), log_db(amp_e), cd, -log_db(float(np.abs(L[k]))), gap))

    k0 = int(np.where(gate)[0][np.argmax(np.abs(L[gate]))])
    h0, e0 = float(np.abs(H[k0])), float(np.abs(E[k0]))
    cd0 = 20 * np.log10(h0 / max(e0, 1e-30))
    gmax = -log_db(float(np.abs(L[k0])))
    say("\n[3] 全局绑定 bin：%.1f Hz（相干 %.3f）" % (freqs[k0], coh[k0]))
    say("  |H| = %+.2f dB，|H−Ĥ| = %+.2f dB，抑制 CD = %.2f dB" % (log_db(h0), log_db(e0), cd0))
    say("  → 512 抽头在这份数据上的采样网格小增益界 = %+.2f dB（上界估计，不是最大允许增益）" % gmax)
    say("\n  预算（同一个 bin）：")
    say("  %-12s %12s %12s %10s %10s" % ("数字增益", "需要 CD", "现有 CD", "差", "结果"))
    budget = []
    for g_db in (0.0, 3.0, 6.0):
        need = g_db + log_db(h0)
        row = {"gain_db": g_db, "needed_cd_db": float(need), "achieved_cd_db": float(cd0),
               "gap_db": float(cd0 - need)}
        budget.append(row)
        say("  %+8.1f dB %+12.2f %+12.2f %+10.2f %10s"
            % (g_db, need, cd0, cd0 - need,
               "够" if cd0 >= need else "不够（环路 %+.1f dB）" % (need - cd0)))
    say("  注：%s" % ("+6 dB 时环路仍为 %+.1f dB，必然啸叫" % (log_db(h0) - cd0 + 6.0)))

    say("\n[4] 抽头数能不能补上：逐段重拟合（训练 seg_%s，评估留出 seg_%s）"
        % (args.train, args.valid))
    say("  %6s %12s %12s %12s %10s" % ("抽头", "全局绑定Hz", "|H−Ĥ|dB", "CD@绑定", "小增益界"))
    sweep = []
    for taps in (256, 512, 680):
        h = fit_segmentwise(tr, taps)
        E2 = H - model_response(h, nfft, lag_first=1)
        L2 = E2 * np.exp(-1j * 2 * np.pi * args.delay_frames * freqs / fs)
        k = int(np.where(gate)[0][np.argmax(np.abs(L2[gate]))])
        cd2 = 20 * np.log10(float(np.abs(H[k])) / max(float(np.abs(E2[k])), 1e-30))
        sweep.append({"taps": taps, "binding_hz": float(freqs[k]),
                      "e_db": log_db(float(np.abs(E2[k]))), "cd_db": float(cd2),
                      "allowed_gain_db": float(-log_db(float(np.abs(L2[k]))))})
        say("  %6d %12.0f %+12.2f %12.2f %+10.2f"
            % (taps, freqs[k], sweep[-1]["e_db"], cd2, sweep[-1]["allowed_gain_db"]))
    say("  硬件上限 681 抽头（单 MAC 每抽头 3 拍 + 3 收尾，帧预算 2048），且 512 时 BRAM 已 80%%。")

    say("\n[5] 结论")
    say("  · 512 抽头在最差 bin 上的抑制是 **%.1f dB**，该点采样网格小增益界 **%+.2f dB**；"
        % (cd0, gmax))
    say("  · 要 +6 dB 数字增益，需要该 bin 的 CD ≥ **%.1f dB**；差 **%.1f dB**。"
        % (6.0 + log_db(h0), 6.0 + log_db(h0) - cd0))
    say("  · 因此\"512 抽头在最差频段给 15 dB\"在本批数据上**不成立**（差 %.1f dB）。"
        % (15.0 - cd0))
    say("  · 加抽头也补不上：%s。" % "、".join(
        "%d→CD %.1f/界 %+.1f" % (s["taps"], s["cd_db"], s["allowed_gain_db"]) for s in sweep))
    say("  · 这些数只在 300–10250 Hz、过门控 %.1f%% 的 bin 上成立；其余频段未知。"
        % (100.0 * gate.sum() / len(freqs)))
    say("  · 边界：本批是旧布局；小增益界不是\"最大允许增益\"，也不能证明别的布局做不到。")

    payload = {"data": str(args.data_dir), "model": args.model, "q20_sha256": info["q20_sha256"],
               "nfft": nfft, "coherence": args.coherence, "delay_frames": args.delay_frames,
               "gate_ratio": float(gate.sum()) / len(freqs),
               "bands": rows, "binding": {"hz": float(freqs[k0]), "h_db": log_db(h0),
                                          "e_db": log_db(e0), "cd_db": float(cd0),
                                          "allowed_gain_db": float(gmax)},
               "budget": budget, "tap_sweep": sweep, "frequency_grid": grid,
               "scope": "只在这批过门控 bin 上成立；未覆盖频段未知；不含听感与全程声学"}
    if out:
        (out / "gain-budget.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
        (out / "gain-budget.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        say("\n输出：%s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
