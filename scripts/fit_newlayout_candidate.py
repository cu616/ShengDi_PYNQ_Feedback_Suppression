"""新布局 512 抽头候选：从六份 ref/mic 拟合、量化、评价，并生成可直接加载的模型包。

本轮只做一件事：交付**一个**候选，固定训练/开发/验证划分，不调参、不扩架构。

口径（全部复用既有实现，不另写判据）：
  - 拟合：`reproduce_b_screening.segment_gram/solve_ridge`，ridge=1e-9，窗口不跨段，
    y[n]=Σ h[k]·u[n−1−k]（`lag_first=1`）。
  - 时域残差：`predict_stream`，跳过前 taps 帧（历史不足）。
  - 频域：`diagnose_peak_margin.estimate_H`（Welch 交叉谱，nfft=8192），相干 ≥0.8 且 ≥300 Hz 才进门控；
    界与穿越用 `reproduce_b_screening.thresholds`。
  - 量化：`feedback.calibration.quantize_coefficients`（有符号 24 位 / 20 位小数）。
  - 评价一律用**量化后**系数重算；浮点只作对照。

划分（固定，先定后算，不因结果调整）：
  - train = 时间序前 4 段（seg_00…03），dev = seg_04，val = seg_05。
  - 交付模型在 train+dev 上拟合；val 只在最后评价一次，不参与任何选择。
  - 另报 even/odd 3/3 交叉验证作第二估计；标注同场、非独立新场。

用法：
  python scripts/fit_newlayout_candidate.py \
      --packet-dir D:/Always/QianSai/_inbox/2026-10-26_newlayout_side100cm \
      --out-model models/room_v1/newlayout_512_20261026.json \
      --out-dir report/verification/newlayout-candidate-2026-10-26
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from answer_new_layout_325 import (  # noqa: E402
    align_segments,
    load_packet,
    write_aligned,
)
from diagnose_peak_margin import (  # noqa: E402
    estimate_H,
    model_response,
    q20_sha256,
)
from feedback.calibration import quantize_coefficients  # noqa: E402
from reproduce_b_screening import (  # noqa: E402
    predict_stream,
    segment_gram,
    solve_ridge,
    thresholds,
)

TAPS = 512
RIDGE = 1e-9
DEFAULT_FIXTURE_ID = "room_v1_20261026"
NFFT = 8192
COHERENCE = 0.8
BANDS = [(300, 460), (460, 1000), (1000, 3000), (3000, 8200),
         (8200, 8600), (8600, 10250)]
TARGET_BINS_HZ = (321.87, 327.83, 423.19, 429.15)


def db(x):
    return 20 * np.log10(np.asarray(x, dtype=float) + 1e-30)


def fractional_lag(u, m):
    """整数互相关峰 + 三点抛物线插值 → 亚采样延迟。只用于判"184/185 是取整还是路径变化"。"""
    n = len(u)
    R = np.fft.rfft(u, 2 * n)
    M = np.fft.rfft(m, 2 * n)
    cc = np.abs(np.fft.irfft(M * np.conj(R)))
    k = int(np.argmax(cc))
    if 0 < k < len(cc) - 1:
        a, b, c = cc[k - 1], cc[k], cc[k + 1]
        denom = a - 2 * b + c
        frac = 0.5 * (a - c) / denom if denom != 0 else 0.0
    else:
        frac = 0.0
    return (k - (2 * n if k > n else 0)) + float(frac)


def residual_of(h, pairs, taps=TAPS, band=None, fs=48828.125):
    """残差 RMS（dB，相对满幅）与信号 RMS（dB）。band 给定时返回带内残差。

    pairs 必须已经**截到源有效的帧数**：每份 capture 尾部 977 帧源已停，只剩底噪；
    把它们算进残差会把结果拖向噪声底，属于已知的口径错误。
    """
    tot = sig = 0.0
    n = 0
    btot = bsig = 0.0
    for u, m in pairs:
        y = predict_stream(h, u, taps)
        e = m[taps:] - y[taps:]
        ref = m[taps:]
        tot += float(np.sum(e ** 2))
        sig += float(np.sum(ref ** 2))
        n += len(e)
        if band is not None:
            nfft = len(e)
            E = np.fft.rfft(e)
            R = np.fft.rfft(ref)
            f = np.fft.rfftfreq(nfft, 1.0 / fs)
            mask = (f >= band[0]) & (f < band[1])
            btot += float(np.sum(np.fft.irfft(np.where(mask, E, 0), nfft) ** 2))
            bsig += float(np.sum(np.fft.irfft(np.where(mask, R, 0), nfft) ** 2))
    out = {"frames": int(n),
           "residual_db": float(10 * np.log10(tot / n + 1e-30)),
           "signal_db": float(10 * np.log10(sig / n + 1e-30))}
    out["reduction_db"] = out["signal_db"] - out["residual_db"]
    if band is not None:
        out["band_residual_db"] = float(10 * np.log10(btot / n + 1e-30))
        out["band_signal_db"] = float(10 * np.log10(bsig / n + 1e-30))
        out["band_reduction_db"] = out["band_signal_db"] - out["band_residual_db"]
    return out


def spectral(V, H, coh, tapz, label):
    """在固定门控下给零系数基线与候选的两套判据与逐带残差。"""
    gate = (coh >= COHERENCE) & (V >= 300.0)
    rows = {}
    for name, Hh in (("zero_model", np.zeros_like(H)), ("candidate", Hh_of(tapz, H))):
        t = thresholds(H, Hh, V, gate, 48828.125, 2)
        E = np.abs(H - Hh)
        rows[name] = {
            "small_gain_bound_db": t["small_gain_bound_db"],
            "small_gain_at_hz": t["small_gain_at_hz"],
            "positive_real_db": t["positive_real_db"] if np.isfinite(t["positive_real_db"]) else None,
            "positive_real_at_hz": t["positive_real_at_hz"],
            "max_abs_E_db": t["max_abs_E_db"],
            "max_abs_E_at_hz": t["max_abs_E_at_hz"],
            "gated_bins": int(gate.sum()),
            "coverage_ratio": float(t["coverage_ratio"]),
        }
        bands = {}
        for lo, hi in BANDS:
            sel = gate & (V >= lo) & (V < hi)
            if not sel.any():
                bands["%d-%d" % (lo, hi)] = {"gated": 0, "max_abs_E_db": None,
                                             "cd_worst_db": None}
                continue
            k = int(np.argmax(E[sel]))
            bands["%d-%d" % (lo, hi)] = {
                "gated": int(sel.sum()),
                "max_abs_E_db": float(db(E[sel][k])),
                "at_hz": float(V[sel][k]),
                "cd_worst_db": float(db(np.abs(H[sel][k]) / E[sel][k])),
                "coherence": float(coh[sel][k]),
            }
        rows[name]["bands"] = bands
        pb = {}
        for f0 in TARGET_BINS_HZ:
            k = int(np.argmin(np.abs(V - f0)))
            pb["%.2f" % V[k]] = {
                "magnitude_h_db": float(db(np.abs(H[k]))),
                "magnitude_model_db": float(db(np.abs(Hh[k]))),
                "residual_db": float(db(E[k])),
                "cd_db": float(db(np.abs(H[k]) / E[k])) if E[k] > 0 else None,
                "coherence": float(coh[k]),
                "gated": bool(gate[k]),
            }
        rows[name]["probe_bins"] = pb
    rows["label"] = label
    return rows


def Hh_of(q20, H):
    return model_response(np.asarray(q20, float) / (1 << 20), NFFT, lag_first=1)


def impulse_peak_of(H):
    """频域 H 的冲激响应峰位（帧）：用来看模型是否落在真实到达上，比相位斜率稳。"""
    h = np.fft.irfft(H, NFFT)
    return int(np.argmax(np.abs(h))), float(np.max(np.abs(h)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet-dir", required=True)
    ap.add_argument("--out-model", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--taps", type=int, default=TAPS)
    ap.add_argument("--fixture-id", default=DEFAULT_FIXTURE_ID,
                    help="本批采集对应的夹具编号；不要沿用旧编号")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {"schema_version": 1, "fixture_id": args.fixture_id, "taps": args.taps,
              "ridge": RIDGE, "lag_first": 1, "nfft": NFFT, "coherence": COHERENCE}

    # ---- [1] 资格与对齐依据 ------------------------------------------
    segs, records = load_packet(args.packet_dir)
    fs = segs[0]["fs"]
    print("[1] 资格：%d/%d 份通过 manifest 与开环旁路身份" % (len(segs), len(records)))
    raw_pairs = [(s["reference"], s["microphone"]) for s in segs]
    frac = [fractional_lag(u, m) for u, m in raw_pairs]
    aligned, lags, target = align_segments(segs)
    shifts = [target - L for L in lags]
    # 源有效帧数：每份尾部 977 帧源已停，统计一律截这里，不把底噪算成残差
    n_valid = min(int(s["source_frames_in_window"]) for s in segs)
    aligned_valid = [(u[:n_valid], m[:n_valid]) for u, m in aligned]
    raw_valid = [(u[:n_valid], m[:n_valid]) for u, m in raw_pairs]
    print("    逐段延迟：整数 %s；亚采样 %s" % (lags, [round(f, 3) for f in frac]))
    print("    亚采样离散度：均值 %.3f，极差 %.3f 采样" % (float(np.mean(frac)), float(np.ptp(frac))))
    print("    对齐位移（补零数）：%s → 统一 %d 帧（%.2f ms）" % (shifts, target, 1000 * target / fs))
    for s, sh in zip(segs, shifts):
        ns = s["source_frames_in_window"]
        print("      %s  first_frame=%d 源窗口=%d 帧  尾零=%d 帧"
              % (s["name"], s["meta"]["first_frame"], ns, len(s["reference"]) - ns))
    print("    段内一致性：每段前半/后半整数延迟见 answer_new_layout_325 的[1]节（本批全部一致，无漂移）")
    result["alignment"] = {
        "integer_lags": lags, "fractional_lags": [float(f) for f in frac],
        "fractional_mean": float(np.mean(frac)), "fractional_spread": float(np.ptp(frac)),
        "aligned_to": target, "zero_pad_per_segment": shifts,
        "delay_ms": 1000 * target / fs,
        "first_frame": int(segs[0]["meta"]["first_frame"]),
        "pll_readback": sorted({s["meta"].get("pll_readback") for s in segs}),
        "fixture_id_in_metadata": sorted({s["meta"].get("fixture_id") for s in segs}),
    }
    paths = write_aligned(aligned_valid, fs, Path(tempfile.mkdtemp(prefix="fitnl_")))

    # ---- [2] 固定划分 ------------------------------------------------
    order = list(range(len(segs)))
    train, dev, val = order[:4], [order[4]], [order[5]]
    even, odd = order[0::2], order[1::2]
    print("\n[2] 固定划分（时间序，先定后算）：train=%s dev=%s val=%s；另报 3/3 CV even=%s odd=%s"
          % (train, dev, val, even, odd))
    print("    同场划分，不是独立新场次；val 只评价一次，不参与任何选择")

    def gram(idx, taps):
        return segment_gram([paths[i] for i in idx], taps=taps)

    def fit(idx, taps):
        G, b, rows = gram(idx, taps)
        return solve_ridge(G, b), rows

    h_tr, rows_tr = fit(train, args.taps)
    h_trdev, rows_trdev = fit(train + dev, args.taps)

    # ---- [3] 时域：float 与量化分列 ----------------------------------
    print("\n[3] 时域残差（跳过前 %d 帧；band=300–460 Hz）" % args.taps)
    q_trdev = quantize_coefficients(h_trdev)
    q_tr = quantize_coefficients(h_tr)
    hq = np.asarray(q_trdev, float) / (1 << 20)
    print("    量化：%d 个系数，Q20 范围 [%d, %d]，float↔Q20 最大差 %.3e"
          % (len(q_trdev), int(q_trdev.min()), int(q_trdev.max()),
             float(np.max(np.abs(h_trdev - hq)))))

    time_rows = {}
    for name, model, idx in (("train_fit_train", h_tr, train),
                             ("train_fit_dev", h_tr, dev),
                             ("traindev_fit_train", h_trdev, train),
                             ("traindev_fit_dev", h_trdev, dev),
                             ("q20_traindev_train", hq, train),
                             ("q20_traindev_dev", hq, dev),
                             ("q20_traindev_val", hq, val),
                             ("zero_model_val", np.zeros(args.taps), val)):
        pairs = [aligned_valid[i] for i in idx]
        time_rows[name] = residual_of(model, pairs, args.taps, band=(300.0, 460.0))
        print("    %-20s 总体抑制 %6.2f dB（信号 %6.2f / 残差 %6.2f）；300–460 抑制 %6.2f dB"
              % (name, time_rows[name]["reduction_db"], time_rows[name]["signal_db"],
                 time_rows[name]["residual_db"], time_rows[name]["band_reduction_db"]))
    result["time_domain"] = time_rows

    # 3/3 CV（第二估计，量化后）
    h_even, _ = fit(even, args.taps)
    h_odd, _ = fit(odd, args.taps)
    cv = {}
    for name, model, idx in (("cv_even_on_odd", quantize_coefficients(h_even), odd),
                             ("cv_odd_on_even", quantize_coefficients(h_odd), even)):
        m = np.asarray(model, float) / (1 << 20)
        cv[name] = residual_of(m, [aligned_valid[i] for i in idx], args.taps, band=(300.0, 460.0))
        print("    %-20s 总体抑制 %6.2f dB；300–460 抑制 %6.2f dB"
              % (name, cv[name]["reduction_db"], cv[name]["band_reduction_db"]))
    result["cross_validation_3v3"] = cv

    # ---- [4] 部署轴核对 ----------------------------------------------
    peak = int(np.argmax(np.abs(hq))) + 1          # 1-indexed tap → 实际滞后 k
    frac_aligned = float(np.mean([f + s for f, s in zip(frac, shifts)]))
    V, H, coh, _S, _n, fsx = estimate_H(paths, nperseg=NFFT)
    peak_H, _amp = impulse_peak_of(H)
    peak_Hh, _amp2 = impulse_peak_of(model_response(np.asarray(q_trdev, float) / (1 << 20),
                                                    NFFT, lag_first=1))
    print("\n[4] 部署轴核对")
    print("    lag_first=1：tap k ↔ 实际滞后 k 帧（RTL 读 u[n−1−k]）")
    print("    实测 H 的冲激响应峰第 %d 帧；模型的冲激响应峰第 %d 帧；模型抽头峰第 %d 个（滞后 %d）"
          % (peak_H, peak_Hh, peak, peak))
    print("    对齐后实测亚采样延迟 %.2f 帧；整数峰位差 %+0.2f 帧属亚采样残差，整数抽头消不掉"
          % (frac_aligned, peak - frac_aligned))
    print("    抽头 %d → 3N+3 = %d 拍（帧预算 2048）；无需补零（logical=loaded=%d）"
          % (args.taps, 3 * args.taps + 3, args.taps))
    print("    bias 不装载（RTL 无偏置项），评价按 bias=0；模型文件里的 bias 只作离线参考")
    result["deployment_axis"] = {
        "impulse_peak_tap": peak,
        "measured_H_impulse_peak_frame": peak_H,
        "model_impulse_peak_frame": peak_Hh,
        "measured_fractional_delay_aligned": frac_aligned,
        "peak_minus_measured": float(peak - frac_aligned),
        "cycles_3n_plus_3": 3 * args.taps + 3, "frame_budget": 2048,
        "zero_padded": False, "logical_taps": args.taps, "loaded_taps": args.taps,
        "bias_loaded": False,
    }

    # ---- [5] 频域：零系数基线 vs 候选 --------------------------------
    spec = spectral(V, H, coh, q_trdev, "aligned_6seg")
    gate = (coh >= COHERENCE) & (V >= 300.0)
    print("\n[5] 频域（对齐后 6 段合并 H，nfft=%d，门控 %d/%d = %.1f%%）"
          % (NFFT, int(gate.sum()), int((V >= 300).sum()),
             100 * gate.sum() / max(1, int((V >= 300).sum()))))
    for name in ("zero_model", "candidate"):
        r = spec[name]
        print("    %-10s 小增益界 %6.2f dB @%6.1f；正实轴 %s @%s"
              % (name, r["small_gain_bound_db"], r["small_gain_at_hz"],
                 ("%.2f" % r["positive_real_db"]) if r["positive_real_db"] is not None else "  无",
                 ("%.1f" % r["positive_real_at_hz"]) if r["positive_real_at_hz"] else "  -"))
        for f0, row in r["probe_bins"].items():
            print("        %8s Hz |H| %6.2f  |H−Ĥ| %6.2f  CD %6.2f  相干 %.2f  门控 %s"
                  % (f0, row["magnitude_h_db"], row["residual_db"],
                     row["cd_db"] if row["cd_db"] is not None else float("nan"),
                     row["coherence"], "是" if row["gated"] else "否"))
    result["spectral"] = spec

    # ---- [6] 未对齐（部署口径）复核 ----------------------------------
    print("\n[6] 不对齐、直接跑原始六份（部署口径：现场没有「对齐」这一步）")
    raw_rows = {}
    for i, (u, m) in enumerate(raw_pairs):
        r = residual_of(hq, [raw_valid[i]], args.taps, band=(300.0, 460.0))
        raw_rows["%s_lag%d" % (segs[i]["name"], lags[i])] = r
        print("    %-28s lag %d  总体抑制 %6.2f dB；300–460 抑制 %6.2f dB"
              % (segs[i]["name"][:28], lags[i], r["reduction_db"], r["band_reduction_db"]))
    vals = [r["reduction_db"] for r in raw_rows.values()]
    bands = [r["band_reduction_db"] for r in raw_rows.values()]
    print("    逐段范围：总体 %+0.2f…%+0.2f（中位 %+0.2f）；300–460 %+0.2f…%+0.2f（中位 %+0.2f）"
          % (min(vals), max(vals), float(np.median(vals)),
             min(bands), max(bands), float(np.median(bands))))
    result["unaligned_deployment"] = {
        "per_capture": raw_rows,
        "overall_min": float(min(vals)), "overall_max": float(max(vals)),
        "overall_median": float(np.median(vals)),
        "band_min": float(min(bands)), "band_max": float(max(bands)),
        "band_median": float(np.median(bands)),
    }

    # ---- [7] 写模型文件 ----------------------------------------------
    model = {
        "schema_version": 1,
        "sample_rate_hz": fs,
        "lag_first": 1,
        "taps": int(args.taps),
        "coefficients": [float(v) for v in h_trdev],
        "bias": 0.0,
        "ridge": RIDGE,
        "training_capture_id": "newlayout-6captures-train4-dev1",
        "training_source": "board",
        "fixture_id": args.fixture_id,
        "hp_volume": 40,
        "validation": {
            "validation_capture_id": segs[val[0]]["meta"]["capture_id"],
            "validation_source": "board",
            "evaluated_frames": int(time_rows["q20_traindev_val"]["frames"]),
            "target_rms": float(10 ** (time_rows["q20_traindev_val"]["signal_db"] / 20)),
            "residual_rms": float(10 ** (time_rows["q20_traindev_val"]["residual_db"] / 20)),
            "prediction_reduction_db": float(time_rows["q20_traindev_val"]["reduction_db"]),
            "interpretation": "same-session held-out open-loop prediction only; not ASG, not new-session validation",
        },
        "coefficient_format": "signed24_fraction20",
        "coefficients_q20": [int(v) for v in q_trdev],
        "status": "offline_candidate_not_board_validated",
    }
    out_model = Path(args.out_model)
    out_model.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(model, indent=1, ensure_ascii=False) + "\n"
    out_model.write_bytes(text.encode("utf-8"))
    file_sha = hashlib.sha256(out_model.read_bytes()).hexdigest()
    q_sha = q20_sha256(q_trdev)
    m_sha = sha256_of_array(h_trdev)
    print("\n[7] 模型文件：%s" % out_model)
    print("    file_sha256 %s" % file_sha)
    print("    coefficients_sha256(Q20 int32 LE) %s" % q_sha)
    print("    coefficients_float_sha256 %s" % m_sha)
    result["model_file"] = {
        "path": str(out_model).replace("\\", "/"),
        "file_sha256": file_sha,
        "q20_sha256": q_sha,
        "float_sha256": m_sha,
        "bytes": len(text.encode("utf-8")),
        "q20_min": int(q_trdev.min()), "q20_max": int(q_trdev.max()),
    }
    result["split"] = {"train": train, "dev": dev, "val": val,
                       "cv_even": even, "cv_odd": odd}
    result["data_identity"] = [
        {"file": s["name"], "sha256": s["sha256"],
         "capture_id": s["meta"]["capture_id"], "first_frame": s["meta"]["first_frame"]}
        for s in segs
    ]
    payload = out_dir / "metrics.json"
    payload.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("    结构化结果：%s" % payload)


def sha256_of_array(values):
    arr = np.asarray([float(v) for v in values], dtype="<f8")
    return hashlib.sha256(arr.tobytes()).hexdigest()


if __name__ == "__main__":
    main()
