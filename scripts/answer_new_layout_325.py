"""回答 A 的 2026-10-26 三个问题：325 Hz 的 |H| 与 CD、512 抽头在新布局的允许增益、单点陷波要多深。

数据：A 的提交 f45449d，`report/verification/audio-replay/b-request-2026-10-25/`（六份新布局 ref/mic
      + manifest 逐文件 SHA256），扫描边界见 `report/verification/audio-replay/gain-sweep-boundary-2026-10-26.json`。

口径：**不重新实现任何一条判据**。H 估计用 `diagnose_peak_margin.estimate_H`，模型响应用
      `model_response`，判据用 `reproduce_b_screening.thresholds`，拟合用 `segment_gram/solve_ridge`，
      正则 ridge=1e-9、lag_first=1、2 拍调度，全部与既有报告同源。

本脚本只多做一件前人没做过的事：**逐段对齐到统一的 ref→mic 整数延迟**。本批六个 capture 的延迟是
184/185 混排（差一帧），直接跨段累加交叉谱会把高频擦掉（8.4 kHz 上一帧 62°，足以把相位完全打散）。
对齐后 H 的相位仍包含完整的物理延迟，FIR 拟合也仍然按同一时间原点做（延迟落在第 185 个抽头上）。

用法：
  python scripts/answer_new_layout_325.py \
      --packet-dir D:/Always/QianSai/_inbox/2026-10-26_newlayout_side100cm/report/verification/audio-replay/b-request-2026-10-25 \
      --out-dir report/verification/newlayout-325-2026-10-26
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from diagnose_peak_margin import (  # noqa: E402
    estimate_H,
    model_response,
    positive_real_crossing,
    shift_coefficients,
)
from reproduce_b_screening import (  # noqa: E402
    predict_stream,
    segment_gram,
    solve_ridge,
    thresholds,
)

TAPS = 512
RIDGE = 1e-9
F_TARGET = 325.0
NOTCH_HALF_WIDTH = 25.0      # 单模陷波的保守阻带半宽（Hz）：±25 Hz 内视为被压掉
MEASURED_BOUNDARY_DB = -5.5  # A 的扫描：-6.0 稳、-5.0 叫，取中点


# ---------------------------------------------------------------- 基础工具

def dbfs(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-20)


def dblog(x):
    return 20 * np.log10(np.asarray(x, dtype=float) + 1e-30)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def estimate_lag(u, m):
    """整数 ref→mic 延迟：互相关峰位（本批只用它做对齐，不当物理量报）。"""
    n = len(u)
    R = np.fft.rfft(u, 2 * n)
    M = np.fft.rfft(m, 2 * n)
    cc = np.fft.irfft(M * np.conj(R))
    lag = int(np.argmax(np.abs(cc)))
    return lag - 2 * n if lag > n else lag


def load_packet(packet_dir):
    """读六份 npz 并按包内 manifest 逐文件校验；任何不一致直接退出，不产生数字。"""
    dirpath = Path(packet_dir)
    manifests = sorted(dirpath.glob("*.zip"))
    records = {}
    if manifests:
        with zipfile.ZipFile(manifests[0]) as zf:
            name = "manifest.json"
            if name in zf.namelist():
                payload = json.loads(zf.read(name).decode("utf-8"))
                records = payload.get("files", {})
    segs, failures = [], []
    for path in sorted(dirpath.glob("*.npz")):
        digest = sha256_file(path)
        declared = (records.get(path.name) or {}).get("sha256")
        if declared is None:
            failures.append({"file": path.name, "reason": "manifest 未列该文件"})
            continue
        if digest != declared:
            failures.append({"file": path.name, "reason": "sha256 不符",
                             "declared": declared, "actual": digest})
            continue
        cap = np.load(path, allow_pickle=True)
        meta = json.loads(str(cap["metadata_json"]))
        if meta.get("bypass") is not True or int(meta.get("gain_q12", -1)) != 0:
            failures.append({"file": path.name, "reason": "不是开环旁路捕获",
                             "bypass": meta.get("bypass"), "gain_q12": meta.get("gain_q12")})
            continue
        if meta.get("forward_path_open") is not True:
            failures.append({"file": path.name, "reason": "forward_path_open 不成立"})
            continue
        if not meta.get("verification", {}).get("bit_exact", False):
            failures.append({"file": path.name, "reason": "板上算术非 bit_exact"})
            continue
        for key in ("prediction_saturations", "residual_saturations", "mix_saturations"):
            if int(meta.get(key, 0)) != 0:
                failures.append({"file": path.name, "reason": "%s 非零" % key, "value": meta[key]})
                break
        ref = np.asarray(cap["reference"], float)
        mic = np.asarray(cap["microphone"], float)
        src = np.asarray(cap["source_pcm16"], float) / 32768.0
        first = int(meta["first_frame"])
        n_overlap = min(len(ref), len(src) - first)
        scale = 20 * np.log10(np.sqrt(np.mean(ref[:n_overlap] ** 2))
                              / np.sqrt(np.mean(src[first:first + n_overlap] ** 2)))
        segs.append({"path": path, "name": path.name, "meta": meta,
                     "reference": ref, "microphone": mic,
                     "fs": float(cap["sample_rate_hz"]),
                     "coef": np.asarray(cap["coefficients_q20"], float) / float(1 << 20),
                     "source_frames_in_window": int(n_overlap),
                     "reference_vs_source_db": float(scale),
                     "sha256": digest})
    if failures:
        print("输入不合格，停止：")
        for item in failures:
            print("  -", item)
        raise SystemExit(2)
    return segs, records


def align_segments(segs):
    """把每段 mic 对齐到本批最大的整数延迟；返回对齐后的 (u, m) 列表与延迟表。

    对齐只**滞后** mic（前面补零），不改 reference：H 的相位仍包含完整物理延迟，
    FIR 照常从同一原点拟合。方向必须写死——把延迟小的那段往前挪会让整批差两帧，
    时域残差和跨段累加的交叉谱都会立刻变差。
    """
    lags = [estimate_lag(s["reference"], s["microphone"]) for s in segs]
    target = max(lags)
    aligned = []
    for seg, lag in zip(segs, lags):
        shift = target - lag
        mic = seg["microphone"]
        if shift:
            mic = np.concatenate([np.zeros(shift), mic[:len(mic) - shift]])
        aligned.append((seg["reference"], mic))
    return aligned, lags, target


def write_aligned(aligned, fs, out_dir):
    """把对齐后的段写成 estimate_H 认识的 seg_*.npz（该函数只认 reference/microphone）。

    写到临时目录：对齐是确定性的，每次运行重新生成，不把 A 的数据再复制一份进仓库。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (u, m) in enumerate(aligned):
        p = out_dir / ("seg_%02d.npz" % i)
        np.savez(p, reference=u, microphone=m, sample_rate_hz=fs)
        paths.append(p)
    return paths


def residual_stats(h, aligned, taps, fs, band=(300.0, 460.0)):
    """时域残差 RMS：总体与指定带内；返回 (resid_db, signal_db, band_resid_db, band_signal_db)。"""
    tot, sig, n = 0.0, 0.0, 0
    bt, bs = 0.0, 0.0
    for u, m in aligned:
        y = predict_stream(h, u, taps)
        e = m[taps:] - y[taps:]
        ref = m[taps:]
        nfft = len(e)
        E = np.fft.rfft(e)
        R = np.fft.rfft(ref)
        freqs = np.fft.rfftfreq(nfft, 1.0 / fs)
        mask = (freqs >= band[0]) & (freqs < band[1])
        eb = np.fft.irfft(np.where(mask, E, 0), nfft)
        rb = np.fft.irfft(np.where(mask, R, 0), nfft)
        tot += float(np.sum(e ** 2))
        sig += float(np.sum(ref ** 2))
        bt += float(np.sum(eb ** 2))
        bs += float(np.sum(rb ** 2))
        n += len(e)
    return (10 * np.log10(tot / n + 1e-30), 10 * np.log10(sig / n + 1e-30),
            10 * np.log10(bt / n + 1e-30), 10 * np.log10(bs / n + 1e-30))


def gate_of(coh, freqs, coherence):
    return (coh >= coherence) & (freqs >= 300.0)


def crossing_list(loop, freqs, gate):
    """全部正实轴穿越点，按阈值从紧到松排序：[(阈值 dB, 频率 Hz)]。"""
    hits = positive_real_crossing(loop, freqs, gate, return_all=True)
    return [(-20 * np.log10(re), float(hz)) for re, hz in hits]


def per_bin(H, H_hat, freqs, gate):
    """逐频点允许增益 g_bin(f) = −20·log10|H−Ĥ|，只在过门控的 bin 上。"""
    E = np.abs(H - H_hat)
    values = np.where(gate, -dblog(E), np.nan)
    return E, values


def describe(H, H_hat, freqs, coh, gate, fs, delay_frames, label):
    E, gbin = per_bin(H, H_hat, freqs, gate)
    loop = (H - H_hat) * np.exp(-1j * 2 * np.pi * delay_frames * freqs / fs)
    thr = thresholds(H, H_hat, freqs, gate, fs, delay_frames)
    crosses = crossing_list(loop, freqs, gate)
    # 绑定 bin = 允许增益最小的那个，也就是残差最大的那个
    k1 = int(np.nanargmin(np.where(gate, gbin, np.nan)))
    return {
        "label": label,
        "small_gain_bound_db": thr["small_gain_bound_db"],
        "small_gain_at_hz": thr["small_gain_at_hz"],
        "positive_real_db": thr["positive_real_db"] if np.isfinite(thr["positive_real_db"]) else None,
        "positive_real_at_hz": thr["positive_real_at_hz"],
        "binding_bin_hz": float(freqs[k1]),
        "binding_bin_coherence": float(coh[k1]),
        "binding_bin_residual_db": float(dblog(E[k1])),
        "crossings": [{"threshold_db": t, "hz": h} for t, h in crosses[:6]],
        "_E": E, "_gbin": gbin,
    }


def at_target(H, H_hat, freqs, coh, target_hz):
    """目标频率上的 |H|、|Ĥ|、残差与 CD：取两侧相邻 bin，在对数幅度上线性插值。"""
    k = int(np.argmin(np.abs(freqs - target_hz)))
    if freqs[k] < target_hz and k + 1 < len(freqs):
        a, b = k, k + 1
    elif freqs[k] > target_hz and k >= 1:
        a, b = k - 1, k
    else:
        a = b = k
    t = 0.0 if freqs[b] == freqs[a] else (target_hz - freqs[a]) / (freqs[b] - freqs[a])
    la = dblog(np.abs(H[a])) * (1 - t) + dblog(np.abs(H[b])) * t
    lb = dblog(np.abs(H_hat[a])) * (1 - t) + dblog(np.abs(H_hat[b])) * t
    ra = dblog(np.abs(H[a] - H_hat[a])) * (1 - t) + dblog(np.abs(H[b] - H_hat[b])) * t
    return {
        "target_hz": float(target_hz),
        "bins_hz": [float(freqs[a]), float(freqs[b])],
        "coherence": [float(coh[a]), float(coh[b])],
        "magnitude_h_db": float(la),
        "magnitude_model_db": float(lb),
        "residual_db": float(ra),
        "cd_db": float(la - ra),
        "allowed_gain_db": float(-ra),
        "bins": [{"hz": float(freqs[i]),
                  "magnitude_h_db": float(dblog(np.abs(H[i]))),
                  "magnitude_model_db": float(dblog(np.abs(H_hat[i]))),
                  "residual_db": float(dblog(np.abs(H[i] - H_hat[i]))),
                  "cd_db": float(dblog(np.abs(H[i])) - dblog(np.abs(H[i] - H_hat[i]))),
                  "coherence": float(coh[i])} for i in (a, b)],
    }


def notch_requirement(desc, freqs, coh, gate, target_db, target_hz,
                      half_width=NOTCH_HALF_WIDTH, window=(300.0, 460.0)):
    """单模陷波要多深才能把允许增益推到 target_db，以及推上去之后天花板在哪。

    口径：陷波在目标频点上是乘性的，|N·(H−Ĥ)| 把该 bin 的 g_bin 抬高 A dB（A = 陷波深度）。
    - `required_depth_at_target`：在 target_hz 上要压多少（=target − g_bin(target_hz)）；
    - `ceiling_outside_notch`：把 target_hz ± half_width 整段挖掉后，剩余过门控 bin 里最紧的那个；
      它决定"只压这一点"到底够不够。
    """
    gbin = desc["_gbin"]
    sel = gate & (freqs >= window[0]) & (freqs < window[1])
    idx = np.where(sel)[0]
    kt = int(np.argmin(np.abs(freqs - target_hz)))
    g_target = float(np.interp(target_hz, freqs[max(0, kt - 1):kt + 2],
                               gbin[max(0, kt - 1):kt + 2]))
    outside = sel & (np.abs(freqs - target_hz) > half_width)
    if outside.any():
        k_out = int(np.nanargmin(np.where(outside, gbin, np.nan)))
        ceiling = float(gbin[k_out])
        ceiling_hz = float(freqs[k_out])
    else:
        ceiling, ceiling_hz = None, None
    return {
        "model": desc["label"],
        "target_hz": float(target_hz),
        "target_db": float(target_db),
        "g_at_target_db": g_target,
        "required_depth_at_target_db": float(target_db - g_target),
        "ceiling_outside_notch_db": ceiling,
        "ceiling_hz": ceiling_hz,
        "reachable_by_notching_target": bool(ceiling is not None and ceiling >= target_db),
        "binding_hz": desc["binding_bin_hz"],
        "binding_g_db": float(np.nanmin(np.where(gate, gbin, np.nan))),
        "excluded_band_hz": [target_hz - half_width, target_hz + half_width],
        "bin_table_300_460": " ".join("%.0f:%+.1f" % (freqs[k], gbin[k]) for k in idx),
    }


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--nfft", type=int, default=8192)
    ap.add_argument("--nfft-sens", type=int, default=4096,
                    help="分辨率敏感性：绑定点落在单 bin 上时必须看这一档")
    ap.add_argument("--coherence", type=float, default=0.8)
    ap.add_argument("--delay-frames", type=int, default=2)
    ap.add_argument("--taps", type=int, default=TAPS)
    ap.add_argument("--target-hz", type=float, default=F_TARGET)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="align325_"))
    result = {"schema_version": 1, "f_target_hz": args.target_hz,
              "coherence_gate": args.coherence, "nfft": args.nfft,
              "nfft_sensitivity": args.nfft_sens, "delay_frames": args.delay_frames,
              "taps": args.taps, "ridge": RIDGE}

    # ---- [0] 资格 ----------------------------------------------------
    segs, records = load_packet(args.packet_dir)
    fs = segs[0]["fs"]
    print("[0] 资格：%d/%d 份通过（manifest sha256、开环旁路、bit_exact、零饱和）"
          % (len(segs), len(records)))
    for s in segs:
        print("    %s  延迟前身份 ok  mic %.2f dBFS  源/参考差 %.4f dB"
              % (s["name"], dbfs(s["microphone"][:s["source_frames_in_window"]]),
                 s["reference_vs_source_db"]))
    coef_by_hash = {s["meta"]["coefficients_sha256"] for s in segs}
    print("    板上系数哈希 %s（%d 个）" % (sorted(h[:12] for h in coef_by_hash), len(coef_by_hash)))
    result["qualification"] = {
        "files_ok": len(segs), "files_listed": len(records),
        "sample_rate_hz": fs,
        "board_coefficient_sha256": sorted(coef_by_hash),
        "reference_equals_source_pcm16": all(abs(s["reference_vs_source_db"]) < 1e-3 for s in segs),
    }

    # ---- [1] 对齐与噪声 ----------------------------------------------
    aligned, lags, lag_target = align_segments(segs)
    print("\n[1] 对齐：逐段 ref→mic 延迟 %s → 统一到 %d 帧（%.2f ms）；32 位浮点不改样本"
          % (lags, lag_target, 1000 * lag_target / fs))
    paths = write_aligned(aligned, fs, work)
    result["alignment"] = {"lags": lags, "aligned_to": lag_target,
                           "delay_ms": 1000 * lag_target / fs,
                           "tap_memory_ms": 1000 * args.taps / fs,
                           "memory_left_after_delay_ms": 1000 * (args.taps - lag_target) / fs}
    print("    %d 抽头 = %.2f ms 记忆，其中 %.2f ms 是纯传播延迟，真正可用的拖尾记忆只有 %.2f ms"
          % (args.taps, 1000 * args.taps / fs, 1000 * lag_target / fs,
             1000 * (args.taps - lag_target) / fs))

    # ---- [2] H 与覆盖 ------------------------------------------------
    freqs, H, coh, _Suu, _n, fsx = estimate_H(paths, nperseg=args.nfft)
    gate = gate_of(coh, freqs, args.coherence)
    inside = freqs >= 300.0
    print("\n[2] H 与覆盖（nfft=%d，bin %.2f Hz）" % (args.nfft, freqs[1] - freqs[0]))
    print("    门控（相干 ≥%.2f 且 ≥300 Hz）：%d / %d bin = %.1f%%"
          % (args.coherence, int(gate.sum()), int(inside.sum()),
             100.0 * gate.sum() / max(1, inside.sum())))
    bands = [(300, 460), (460, 1000), (1000, 3000), (3000, 8200),
             (8200, 8600), (8600, 10250)]
    band_rows = []
    for lo, hi in bands:
        sel = (freqs >= lo) & (freqs < hi)
        if not sel.any():
            continue
        row = {"band": "%d-%d" % (lo, hi),
               "coherence_median": float(np.median(coh[sel])),
               "magnitude_median_db": float(dblog(np.median(np.abs(H[sel])))),
               "magnitude_max_db": float(dblog(np.abs(H[sel]).max())),
               "magnitude_max_hz": float(freqs[sel][np.argmax(np.abs(H[sel]))]),
               "gated_bins": int((sel & gate).sum())}
        band_rows.append(row)
        print("    %-10s 相干中位 %.2f  |H| 中位 %6.2f 最大 %6.2f @%6.1f Hz  门控 %d bin"
              % (row["band"], row["coherence_median"], row["magnitude_median_db"],
                 row["magnitude_max_db"], row["magnitude_max_hz"], row["gated_bins"]))
    result["coverage"] = {"gated_bins": int(gate.sum()), "bins_above_300": int(inside.sum()),
                          "coverage_ratio": float(gate.sum() / max(1, inside.sum())),
                          "bands": band_rows}
    k_all = int(np.argmax(np.abs(H) * inside))
    print("    门控内 max|H| = %.2f dB @ %.1f Hz（相干 %.2f）"
          % (dblog(np.abs(H[gate]).max()), freqs[gate][np.argmax(np.abs(H[gate]))],
             coh[gate][np.argmax(np.abs(H[gate]))]))
    result["max_abs_H"] = {
        "db": float(dblog(np.abs(H[gate]).max())),
        "hz": float(freqs[gate][np.argmax(np.abs(H[gate]))]),
        "coherence": float(coh[gate][np.argmax(np.abs(H[gate]))]),
    }

    # 分半噪声底线：两半各自的 H 差多少，就是 |H−Ĥ| 无法分辨的下限
    _fa, H_a, _ca, _sa, _na, _fsa = estimate_H(paths[0::2], nperseg=args.nfft)
    _fb, H_b, _cb, _sb, _nb, _fsb = estimate_H(paths[1::2], nperseg=args.nfft)
    split = np.abs(H_a - H_b)
    kt = int(np.argmin(np.abs(freqs - args.target_hz)))
    print("    分半噪声：|H_a−H_b| 中位 %.2f dB；目标频点两侧 %.2f / %.2f dB"
          % (dblog(np.median(split)), dblog(split[max(0, kt - 1)]), dblog(split[kt])))
    result["split_half"] = {
        "median_db": float(dblog(np.median(split))),
        "at_target_db": float(dblog(split[kt])),
    }

    # ---- 各候选 Ĥ ----------------------------------------------------
    deployed = segs[0]["coef"]
    G, b, rows_train = segment_gram([s["path"] for s in segs], taps=args.taps)
    h_fit = solve_ridge(G, b)
    Ga, ba, _ra = segment_gram([s["path"] for s in segs[0::2]], taps=args.taps)
    Gb, bb, _rb = segment_gram([s["path"] for s in segs[1::2]], taps=args.taps)
    h_a = solve_ridge(Ga, ba)
    h_b = solve_ridge(Gb, bb)
    print("    拟合：%d 行，ridge=%g，||h||=%.4f" % (rows_train, RIDGE, float(np.linalg.norm(h_fit))))
    result["fit"] = {"rows": int(rows_train), "norm": float(np.linalg.norm(h_fit)),
                     "cv_norms": [float(np.linalg.norm(h_a)), float(np.linalg.norm(h_b))]}

    candidates = [
        ("deployed_old_layout", model_response(deployed, args.nfft, lag_first=1), deployed),
        ("refit_512_in_sample", model_response(h_fit, args.nfft, lag_first=1), h_fit),
        ("refit_512_cv_a", model_response(h_a, args.nfft, lag_first=1), h_a),
        ("refit_512_cv_b", model_response(h_b, args.nfft, lag_first=1), h_b),
        ("no_model", np.zeros_like(H), None),
    ]

    # ---- [3] (a) 目标频点 --------------------------------------------
    noise_floor = float(dblog(max(split[max(0, kt - 1)], split[kt])))
    print("\n[3] (a) %.1f Hz 处（对数幅度插值，两侧 bin 并列；分半噪声上限 %.2f dB）"
          % (args.target_hz, noise_floor))
    rows_a = []
    for name, Hh, _c in candidates:
        info = at_target(H, Hh, freqs, coh, args.target_hz)
        info["model"] = name
        info["split_half_noise_db"] = noise_floor
        info["residual_over_noise_db"] = info["residual_db"] - noise_floor
        rows_a.append(info)
        print("    %-22s |H| %6.2f  |Ĥ| %6.2f  残差 %6.2f  CD %6.2f  g_bin %6.2f  相干 %.2f/%.2f  残差高出噪声 %5.2f dB"
              % (name, info["magnitude_h_db"], info["magnitude_model_db"], info["residual_db"],
                 info["cd_db"], info["allowed_gain_db"], info["coherence"][0], info["coherence"][1],
                 info["residual_over_noise_db"]))
    result["question_a"] = rows_a

    # ---- [4] (b) 允许最大增益 ----------------------------------------
    print("\n[4] (b) 允许最大数字增益（两个判据分开报；实测边界 %.1f dB）" % MEASURED_BOUNDARY_DB)
    descs = []
    for name, Hh, _c in candidates:
        d = describe(H, Hh, freqs, coh, gate, fsx, args.delay_frames, name)
        descs.append(d)
        delta = (d["small_gain_bound_db"] - MEASURED_BOUNDARY_DB)
        print("    %-22s 小增益界 %6.2f dB @%6.1f  正实轴 %s @%s  与实测差 %+6.2f dB"
              % (name, d["small_gain_bound_db"], d["small_gain_at_hz"],
                 ("%.2f" % d["positive_real_db"]) if d["positive_real_db"] is not None else "  无",
                 ("%.1f" % d["positive_real_at_hz"]) if d["positive_real_at_hz"] else "  -",
                 delta))
        if d["crossings"]:
            print("        穿越点（紧→松）：" + "，".join(
                "%.2f dB@%.1f Hz" % (c["threshold_db"], c["hz"]) for c in d["crossings"][:4]))
    result["question_b"] = [{k: v for k, v in d.items() if not k.startswith("_")} for d in descs]
    result["measured_boundary_db"] = MEASURED_BOUNDARY_DB

    # ---- [5] (c) 陷波深度 --------------------------------------------
    print("\n[5] (c) 单模陷波（阻带 %.0f Hz ±%.0f Hz）要把允许增益推到目标值需要多深"
          % (args.target_hz, NOTCH_HALF_WIDTH))
    notch_rows = []
    for d in descs:
        if d["label"] == "no_model":
            continue
        for target in (0.0, 6.0):
            r = notch_requirement(d, freqs, coh, gate, target, args.target_hz)
            notch_rows.append(r)
            print("    %-22s → %+5.1f dB：%.1f Hz 处要压 %6.2f dB；"
                  "挖掉该段后天花板 %s dB @ %s，%s"
                  % (d["label"], target, args.target_hz, r["required_depth_at_target_db"],
                     ("%.2f" % r["ceiling_outside_notch_db"])
                     if r["ceiling_outside_notch_db"] is not None else "未知",
                     ("%.1f Hz" % r["ceiling_hz"]) if r["ceiling_hz"] else "-",
                     "可达" if r["reachable_by_notching_target"] else "不可达"))
    result["question_c"] = notch_rows
    print("    300–460 Hz 逐 bin 允许增益（用来判断是一个点还是一整片）：")
    for d in descs:
        if d["label"] == "no_model":
            continue
        gbin = d["_gbin"]
        sel = gate & (freqs >= 300) & (freqs < 460)
        cells = " ".join("%.0f:%+.1f" % (freqs[k], gbin[k]) for k in np.where(sel)[0])
        print("      %-22s %s" % (d["label"], cells))

    # ---- [6] 长记忆假说 ----------------------------------------------
    print("\n[6] A 的长记忆假说：抽头数扫描（时域残差 + 小增益界；in-sample 与 3/3 交叉验证）")
    sweep = []
    for taps in (256, 512, 680, 1024, 2048):
        Gs, bs, _ = segment_gram([s["path"] for s in segs], taps=taps)
        hs = solve_ridge(Gs, bs)
        r_in, sig_in, br_in, bsig = residual_stats(hs, aligned, taps, fs)
        Ga2, ba2, _ = segment_gram([s["path"] for s in segs[0::2]], taps=taps)
        Gb2, bb2, _ = segment_gram([s["path"] for s in segs[1::2]], taps=taps)
        ha2, hb2 = solve_ridge(Ga2, ba2), solve_ridge(Gb2, bb2)
        ra, _sa, bra, _ = residual_stats(ha2, aligned[1::2], taps, fs)
        rb, _sb, brb, _ = residual_stats(hb2, aligned[0::2], taps, fs)
        r_cv = 10 * np.log10((10 ** (ra / 10) + 10 ** (rb / 10)) / 2)
        br_cv = 10 * np.log10((10 ** (bra / 10) + 10 ** (brb / 10)) / 2)
        t_in = thresholds(H, model_response(hs, args.nfft, lag_first=1), freqs, gate, fsx,
                          args.delay_frames)
        b_cv = [thresholds(H, model_response(hh, args.nfft, lag_first=1), freqs, gate, fsx,
                           args.delay_frames)["small_gain_bound_db"] for hh in (ha2, hb2)]
        row = {"taps": taps, "memory_ms": 1000 * taps / fs,
               "usable_memory_ms": 1000 * (taps - lag_target) / fs,
               "residual_in_db": r_in, "gain_in_db": sig_in - r_in,
               "residual_cv_db": r_cv, "gain_cv_db": sig_in - r_cv,
               "signal_db": sig_in,
               "band_residual_in_db": br_in, "band_gain_in_db": bsig - br_in,
               "band_residual_cv_db": br_cv, "band_gain_cv_db": bsig - br_cv,
               "bound_in_db": t_in["small_gain_bound_db"],
               "bound_in_hz": t_in["small_gain_at_hz"],
               "bound_cv_db": min(b_cv), "bound_cv_both_db": b_cv,
               "crossing_in_db": t_in["positive_real_db"],
               "crossing_in_hz": t_in["positive_real_at_hz"]}
        sweep.append(row)
        print("    %5d 抽头（%5.2f ms，可用 %5.2f ms）总体 in %5.2f / cv %5.2f；"
              "300–460 in %5.2f / cv %5.2f；界 %6.2f（CV %6.2f）"
              % (taps, row["memory_ms"], row["usable_memory_ms"],
                 row["gain_in_db"], row["gain_cv_db"],
                 row["band_gain_in_db"], row["band_gain_cv_db"],
                 row["bound_in_db"], row["bound_cv_db"]))
    result["long_memory_sweep"] = sweep

    # ---- [7] 延迟错配的分解：纯平移能不能救回板上那套系数 ------------------
    print("\n[7] 板上系数为什么在低频是负 CD：纯延迟平移扫描（不动其它任何东西）")
    peak_dev = int(np.argmax(np.abs(deployed))) + 1
    peak_fit = int(np.argmax(np.abs(h_fit))) + 1
    print("    冲激响应峰位：板上 %d（=滞后 %d）/ 新拟合 %d（=滞后 %d）/ 实测路径延迟 %d"
          % (peak_dev, peak_dev, peak_fit, peak_fit, lag_target))
    shift_rows = []
    for shift in (0, 20, 30, 40, 50, 55, 58, 60, 62, 64, 68, 80):
        hs = shift_coefficients(deployed, shift)
        Hh = model_response(hs, args.nfft, lag_first=1)
        t = thresholds(H, Hh, freqs, gate, fsx, args.delay_frames)
        info = at_target(H, Hh, freqs, coh, args.target_hz)
        row = {"shift_taps": shift,
               "small_gain_bound_db": t["small_gain_bound_db"],
               "small_gain_at_hz": t["small_gain_at_hz"],
               "positive_real_db": t["positive_real_db"] if np.isfinite(t["positive_real_db"]) else None,
               "positive_real_at_hz": t["positive_real_at_hz"],
               "cd_at_target_db": info["cd_db"],
               "residual_at_target_db": info["residual_db"]}
        shift_rows.append(row)
        print("    shift %+3d：界 %6.2f @%6.1f  穿越 %6.2f @%6.1f  目标点 CD %6.2f"
              % (shift, row["small_gain_bound_db"], row["small_gain_at_hz"],
                 row["positive_real_db"] if row["positive_real_db"] is not None else float("nan"),
                 row["positive_real_at_hz"] or float("nan"), row["cd_at_target_db"]))
    best = max(shift_rows, key=lambda r: r["cd_at_target_db"])
    result["delay_shift_decomposition"] = {
        "impulse_peak_deployed": peak_dev,
        "impulse_peak_refit": peak_fit,
        "path_delay_frames": lag_target,
        "rows": shift_rows,
        "best_by_cd": best,
    }

    # ---- 结论 --------------------------------------------------------
    dep = next(d for d in descs if d["label"] == "deployed_old_layout")
    fit = next(d for d in descs if d["label"] == "refit_512_in_sample")
    nomodel = next(d for d in descs if d["label"] == "no_model")
    cv_bounds = [next(d for d in descs if d["label"] == "refit_512_cv_a")["small_gain_bound_db"],
                 next(d for d in descs if d["label"] == "refit_512_cv_b")["small_gain_bound_db"]]
    result["conclusion"] = {
        "deployed_bound_db": dep["small_gain_bound_db"],
        "deployed_crossing_db": dep["positive_real_db"],
        "deployed_crossing_hz": dep["positive_real_at_hz"],
        "measured_boundary_db": MEASURED_BOUNDARY_DB,
        "deployed_crossing_minus_measured_db":
            None if dep["positive_real_db"] is None else dep["positive_real_db"] - MEASURED_BOUNDARY_DB,
        "no_model_bound_db": nomodel["small_gain_bound_db"],
        "no_model_crossing_db": nomodel["positive_real_db"],
        "refit_bound_db": fit["small_gain_bound_db"],
        "refit_cv_bounds_db": cv_bounds,
        "refit_crossing_db": fit["positive_real_db"],
        "gap_deployed_minus_refit_db": fit["small_gain_bound_db"] - dep["small_gain_bound_db"],
    }
    payload = out_dir / "answer.json"
    payload.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n[8] 结构化结果：%s" % payload)
    print("    部署系数：界 %.2f / 穿越 %s（实测 %.1f，差 %s）"
          % (dep["small_gain_bound_db"],
             ("%.2f" % dep["positive_real_db"]) if dep["positive_real_db"] is not None else "无",
             MEASURED_BOUNDARY_DB,
             ("%+.2f" % (dep["positive_real_db"] - MEASURED_BOUNDARY_DB))
             if dep["positive_real_db"] is not None else "无"))
    print("    新拟合 512：界 %.2f（CV %.2f / %.2f） / 穿越 %.2f"
          % (fit["small_gain_bound_db"], cv_bounds[0], cv_bounds[1], fit["positive_real_db"]))
    print("    不装模型：界 %.2f / 穿越 %.2f"
          % (nomodel["small_gain_bound_db"], nomodel["positive_real_db"]))


if __name__ == "__main__":
    main()
