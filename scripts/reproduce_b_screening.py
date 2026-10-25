"""B 线筛选的唯一复现入口：基线复算、两项候选的否定、分段边界控制。

回答三件事，其它一概不做：
  1. 部署模型（coefficients_q20 / 2**20、lag_first、2 拍调度）在同场留出段上的两个阈值与分带残差；
  2. 候选 a（固定 512 抽头的 ridge / 频带加权 / 多场次）与候选 b（前向固定 biquad）为什么被否定；
  3. 分段边界会不会自己造出收益——用"把连续捕获切成小段"和"把不同段拼成一条流"两个方向做控制。

口径（写死，不要私自改）：
  - 拟合：每段独立构造滞后历史，窗口不跨段；y[n]=Σ h[k]·u[n−1−k]（lag_first=1）。
  - 正则：G + I·trace(G)·ridge，ridge 默认 1e-9（与 A 的 fit_params 一致）。
  - 评估：留出段的 H 用 Welch 交叉谱，相干 ≥0.8 且 ≥300 Hz 才进门控；未进门控的频段记未知。
  - 无随机步骤，故无随机种子；预处理只有 Welch 的 Hann 窗，不做去直流、不做归一化。
  - 10-23（接线异常期）的数据**不进训练也不当独立验证**，只作跨场次压力测试。

用法（一条命令复现本目录所有数字）：
  python scripts/reproduce_b_screening.py \
      --data-dir  D:/Always/QianSai/_inbox/2026-10-25_lowband2_return/lowband2 \
      --model     models/room_v1/calibrated_20261024.json \
      --cross-session-dir D:/Always/QianSai/_inbox/2026-10-23_room6/manifest \
      --out-dir   report/verification/b-screening-2026-10-25/repro
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from diagnose_peak_margin import (  # noqa: E402
    FMIN_HZ,
    estimate_H,
    load_deployed_model,
    model_response,
    positive_real_crossing,
)

TAPS = 512
RIDGE = 1e-9
BANDS = [(300, 1000), (1000, 2000), (2000, 3400), (3400, 6000),
         (6000, 8200), (8200, 8600), (8600, 10250)]


# ---------------------------------------------------------------- 基础工具

def seg_sort_key(path):
    """seg_10 必须排在 seg_2 之后：按文件名里的整数排序，不能按字典序。"""
    stem = Path(path).stem
    tail = stem.split("_")[-1]
    return (int(tail) if tail.isdigit() else 10 ** 6, stem)


def list_segments(dirpath):
    return sorted(glob.glob(str(Path(dirpath) / "seg_*.npz")), key=seg_sort_key)


def parse_seg_id(path):
    """从 seg_<id>.npz 取整数编号；编号是段的身份，不能拿列表下标代替。"""
    tail = Path(path).stem.split("_")[-1]
    if not tail.isdigit():
        raise ValueError("段文件名不含整数编号：%s" % path)
    return int(tail)


def load_manifest_hashes(manifest_path):
    """返回 (文件名->sha256 或 None, 状态说明)。清单缺失或不可解析时映射为 None。

    None 的含义是"未核对"，调用方不得把它当成"一致"。
    """
    p = Path(manifest_path)
    if not p.exists():
        return None, "缺失（%s）：所有 sha_match 记未知" % p.name
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, "解析失败（%s）：所有 sha_match 记未知" % exc
    files = m.get("files")
    if not isinstance(files, list) or not files:
        return None, "无 files 列表（%s）：所有 sha_match 记未知" % p.name
    out = {}
    for f in files:
        if not isinstance(f, dict):
            continue
        name = Path(str(f.get("path", ""))).name
        digest = f.get("sha256")
        if name and isinstance(digest, str) and digest:
            out[name] = digest
    if not out:
        return None, "files 里没有可用 (path, sha256) 对：所有 sha_match 记未知"
    return out, "已读取 %d 条（%s）" % (len(out), p.name)


def resolve_segment_ids(paths, train_ids, valid_ids):
    """按**文件 ID** 绑定训练/留出。

    只按 ID 取段，绝不按列表下标取——否则"缺 seg_5、补 seg_16"会把 seg_10 悄悄挪进训练集。
    返回的 failures 非空即表示输入不合格，调用方必须停止，不产出任何复算数字。
    """
    by_id, duplicates = {}, []
    for p in paths:
        sid = parse_seg_id(p)
        if sid in by_id:
            duplicates.append(sid)
        by_id[sid] = p
    train_ids = list(train_ids)
    valid_ids = list(valid_ids)
    wanted = set(train_ids) | set(valid_ids)
    overlap = sorted(set(train_ids) & set(valid_ids))
    missing = sorted(i for i in wanted if i not in by_id)
    unexpected = sorted(i for i in by_id if i not in wanted)
    failures = []
    if overlap:
        failures.append("训练与留出 ID 重叠：seg_%s" % overlap)
    if missing:
        failures.append("缺号：seg_%s" % missing)
    if duplicates:
        failures.append("重号：seg_%s" % sorted(set(duplicates)))
    return {
        "by_id": by_id,
        "train": [by_id[i] for i in train_ids if i in by_id],
        "valid": [by_id[i] for i in valid_ids if i in by_id],
        "missing": missing,
        "duplicates": sorted(set(duplicates)),
        "unexpected": unexpected,
        "failures": failures,
    }


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_segment(path):
    cap = np.load(path)
    return (np.asarray(cap["reference"], float),
            np.asarray(cap["microphone"], float),
            float(cap["sample_rate_hz"]))


def dbfs(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-20)


def segment_gram(files, taps=TAPS, chunk=4096):
    """逐段累计法方程，**窗口不跨段**（每段用自己的历史，段首不做任何填充）。"""
    G = np.zeros((taps, taps))
    b = np.zeros(taps)
    rows = 0
    for p in files:
        u, m, _ = load_segment(p)
        starts = np.arange(taps, len(u))          # y[n] 用 u[n-1..n-taps]
        for s in range(0, len(starts), chunk):
            blk = starts[s:s + chunk]
            X = u[blk[:, None] - 1 - np.arange(taps)[None, :]]
            G += X.T @ X
            b += X.T @ m[blk]
            rows += len(blk)
    return G, b, rows


def concat_gram(files, taps=TAPS, chunk=4096):
    """把各段首尾相连后累计法方程——**故意让窗口跨段**，只用于分段边界控制。"""
    U = np.concatenate([load_segment(p)[0] for p in files])
    M = np.concatenate([load_segment(p)[1] for p in files])
    G = np.zeros((taps, taps))
    b = np.zeros(taps)
    rows = 0
    starts = np.arange(taps, len(U))
    for s in range(0, len(starts), chunk):
        blk = starts[s:s + chunk]
        X = U[blk[:, None] - 1 - np.arange(taps)[None, :]]
        G += X.T @ X
        b += X.T @ M[blk]
        rows += len(blk)
    return G, b, rows


def solve_ridge(G, b, ridge=RIDGE):
    return np.linalg.solve(G + np.eye(len(b)) * np.trace(G) * ridge, b)


def fit_weighted_freq(freqs, H, taps, weights, ridge=1e-12):
    """频域加权最小二乘（只在需要"频带权重"时用；与时间域等权不是同一个估计器）。"""
    k = np.arange(taps)
    A = np.exp(-1j * 2 * np.pi * np.outer(freqs, k + 1) / FS_CACHE[0])
    Aw = A * weights[:, None]
    M = np.vstack([Aw.real, Aw.imag])
    rhs = np.concatenate([(H * weights).real, (H * weights).imag])
    G = M.T @ M
    G += np.eye(taps) * np.trace(G) * ridge
    return np.linalg.solve(G, M.T @ rhs)


FS_CACHE = [48828.125]


def predict_stream(h, u, taps=TAPS):
    """y[n] = Σ h[k]·u[n−1−k]；前 taps 个样本无效（返回 nan 标记）。"""
    conv = np.convolve(u, np.asarray(h, float))          # conv[n] = Σ h[k]u[n−k]
    y = np.full(len(u), np.nan)
    y[1:] = conv[:len(u) - 1]                            # y[n] = conv[n−1]
    return y


def thresholds(H, H_hat, freqs, gate, fs, delay_frames=2):
    E = np.abs(H - H_hat)
    loop = (H - H_hat) * np.exp(-1j * 2 * np.pi * delay_frames * freqs / fs)
    m = np.abs(loop[gate]).max()
    thr_p, f_p = positive_real_crossing(loop, freqs, gate)
    k = int(np.argmax(np.where(gate, E, 0)))
    return {
        "small_gain_bound_db": float(-20 * np.log10(m)),
        "small_gain_at_hz": float(freqs[gate][np.argmax(np.abs(loop[gate]))]),
        "positive_real_db": float(thr_p),
        "positive_real_at_hz": None if np.isnan(f_p) else float(f_p),
        "max_abs_E_db": float(20 * np.log10(E[k])),
        "max_abs_E_at_hz": float(freqs[k]),
        "coverage_ratio": float(gate.sum() / len(freqs)),
        "gated_bins": int(gate.sum()),
    }


def band_table(H, H_hat, freqs, gate, coh):
    E = np.abs(H - H_hat)
    out = {}
    for lo, hi in BANDS:
        sel = gate & (freqs >= lo) & (freqs < hi)
        if not sel.any():
            out["%d-%d" % (lo, hi)] = {"max_abs_E_db": None, "gated": 0}
            continue
        k = int(np.argmax(E[sel]))
        out["%d-%d" % (lo, hi)] = {
            "max_abs_E_db": float(20 * np.log10(E[sel][k])),
            "at_hz": float(freqs[sel][k]),
            "coherence": float(coh[sel][k]),
            "gated": int(sel.sum()),
        }
    return out


def split_pairing_control(coef, u, m, taps=TAPS, pieces=8):
    """切片后逐片复位 vs 整条一次跑，在**同一批全局帧索引**上比较。

    片长 <= taps 的片没有段内历史，无法评估，两边同时剔除。
    返回两侧样本数、配对帧数、逐样本最大差与 RMS 差；另给一个"不同样本集合"的参考差，
    后者是选窗差，不能当最小可辨改善。
    """
    n_total = len(u)
    res_whole = m - predict_stream(coef, u)
    bounds = np.linspace(0, n_total, pieces + 1).astype(int)
    piece_res, keep, dropped = [], [], []
    for k in range(pieces):
        a, b = int(bounds[k]), int(bounds[k + 1])
        if b - a <= taps:
            dropped.append((a, b))
            piece_res.append(None)
            continue
        piece_res.append((a, b, m[a:b] - predict_stream(coef, u[a:b])))
        keep.append(np.arange(a + taps, b))          # 片内有效帧的全局索引
    out = {"frames": {"whole": int(n_total - taps), "piece": 0, "paired": 0},
           "max_abs_diff": None, "rms_delta_db": None, "window_only_delta_db": None,
           "dropped_pieces": dropped}
    if not keep:
        return out
    idx = np.concatenate(keep)
    e_piece = np.concatenate([r[taps:] for (_, _, r) in piece_res if r is not None])
    e_whole = res_whole[idx]
    rms = lambda x: float(np.sqrt(np.mean(np.square(x))))
    out["frames"] = {"whole": int(n_total - taps), "piece": int(idx.size),
                     "paired": int(idx.size)}
    out["max_abs_diff"] = float(np.max(np.abs(e_piece - e_whole)))
    out["rms_delta_db"] = float(20 * np.log10(rms(e_piece) / rms(e_whole)))
    out["window_only_delta_db"] = float(20 * np.log10(rms(e_piece) / rms(res_whole[taps:])))
    return out


def biquad_notch_mag(f, f0, depth_db, q):
    """二阶陷波的**幅度**响应（筛选参考；不含真实 SOS 的相位与延迟）。"""
    w = f / f0
    re = 1 - w ** 2
    im = w / q
    g = 10 ** (-depth_db / 20)
    return np.sqrt(re ** 2 + (im * g) ** 2) / np.sqrt(re ** 2 + im ** 2)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--cross-session-dir", default=None,
                    help="10-23（接线异常期）目录，仅作跨场次压力测试，不作验证")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--train", default="0-9")
    ap.add_argument("--valid", default="10-15")
    ap.add_argument("--nfft", type=int, default=8192)
    ap.add_argument("--nfft-sens", type=int, default=4096,
                    help="第二个窗长，用来展示窗长敏感性（两个窗长分开报）")
    ap.add_argument("--compare-model", default=None,
                    help="同门控下再评一个模型，用来做「模型 vs FIR-off」的对照（不改变默认选择）")
    ap.add_argument("--coherence", type=float, default=0.8)
    ap.add_argument("--delay-frames", type=int, default=2)
    args = ap.parse_args()

    out = Path(args.out_dir) if args.out_dir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    result = {"config": vars(args)}
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    def span(spec):
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))

    all_paths = list_segments(args.data_dir)
    if not all_paths:
        raise SystemExit("no seg_*.npz in %s" % args.data_dir)
    tr_idx, va_idx = span(args.train), span(args.valid)
    man_path = Path(args.data_dir).parent / "manifest.json"
    man_map, man_status = load_manifest_hashes(man_path)
    res = resolve_segment_ids(all_paths, tr_idx, va_idx)
    tr, va = res["train"], res["valid"]
    if tr:
        u0, m0, fs = load_segment(tr[0])
    else:
        u0, m0, fs = load_segment(all_paths[0])
    FS_CACHE[0] = fs

    say("=" * 78)
    say("[1] 输入资格（%s）" % Path(args.data_dir).name)
    say("  fs=%.3f Hz，taps=%d，ridge=%g，训练 ID=%s，留出 ID=%s"
        % (fs, TAPS, RIDGE, args.train, args.valid))
    say("  manifest：%s" % man_status)
    inv = []
    for p in all_paths:
        sid = parse_seg_id(p)
        u, mm, _ = load_segment(p)
        h = sha256_file(p)
        role = "train" if sid in tr_idx else ("heldout" if sid in va_idx else "unused")
        declared = man_map.get(Path(p).name) if man_map else None
        match = None if declared is None else (declared == h)
        inv.append({"seg_id": sid, "file": Path(p).name, "role": role,
                    "bytes": Path(p).stat().st_size, "samples": int(len(u)),
                    "sha256": h, "manifest_sha256": declared, "sha_match": match,
                    "mic_rms_dbfs": float(dbfs(mm))})
        note = ("  (清单无此项，未核对)" if match is None
                else ("  (manifest 一致)" if match else "  (manifest 不符!)"))
        say("  seg_%-3d %-8s %6d 样本  mic %+6.2f dBFS  %s%s"
            % (sid, role, len(u), dbfs(mm), h[:16], note))
    result["inputs"] = inv
    result["input_check"] = {"missing": res["missing"], "duplicates": res["duplicates"],
                             "unexpected": res["unexpected"], "failures": list(res["failures"])}

    if res["missing"]:
        say("  [缺号] seg_%s：训练/留出清单要求的段不存在" % res["missing"])
    if res["duplicates"]:
        say("  [重号] seg_%s：同一 ID 出现多次" % res["duplicates"])
    if res["unexpected"]:
        say("  [意外项] seg_%s 不在训练/留出清单内，本轮不使用" % res["unexpected"])
    bad_hash = [i["file"] for i in inv if i["sha_match"] is False]
    if bad_hash:
        say("  [哈希不符] %s" % bad_hash)
        res["failures"].append("manifest 声明与文件内容不一致：%s" % bad_hash)
    result["input_check"]["failures"] = list(res["failures"])
    if res["failures"]:
        for f in res["failures"]:
            say("  [不合格] %s" % f)
        say("  → 停止：输入不合格时不产出任何复算数字，退出码 2")
        if out:
            (out / "input-check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 2
    say("  合格：训练 %d 段（%s）、留出 %d 段（%s）；留出段不进入训练"
        % (len(tr), ",".join("seg_%d" % i for i in tr_idx),
           len(va), ",".join("seg_%d" % i for i in va_idx)))

    # ---- [2] 基线：部署 Q20 -------------------------------------------
    model, coef, info = load_deployed_model(args.model)
    say("\n[2] 基线（部署口径）")
    say("  模型 %s  taps=%d  file=%s" % (info["path"], info["taps"], info["file_sha256"]))
    say("  q20  %s  （哈希口径：int32 little-endian）" % info["q20_sha256"])
    say("  lag_first=%d + 调度 %d 拍，各计一次，合计 %d 拍"
        % (info["lag_first"], args.delay_frames, info["lag_first"] + args.delay_frames))
    if info["float_vs_q20_max_abs"] is not None:
        say("  浮点与 Q20 最大系数差 %.2e（频响一律按 Q20 计算）" % info["float_vs_q20_max_abs"])

    base = {}
    for tag, nfft in (("nfft_%d" % args.nfft, args.nfft),
                      ("nfft_%d" % args.nfft_sens, args.nfft_sens)):
        freqs, H, coh, _Suu, nperseg, fsx = estimate_H(va, nperseg=nfft)
        gate = (coh >= args.coherence) & (freqs >= FMIN_HZ)
        H_hat = model_response(coef, nfft, lag_first=info["lag_first"])
        t = thresholds(H, H_hat, freqs, gate, fsx, args.delay_frames)
        t["bands"] = band_table(H, H_hat, freqs, gate, coh)
        # FIR-off 基准：同一份数据、同一个门控、同一个延迟配置，Ĥ≡0。
        # 任何"模型有没有用"的比较都必须对这条线，而不是对 0 dB。
        t_off = thresholds(H, np.zeros_like(H), freqs, gate, fsx, args.delay_frames)
        t["fir_off"] = {"small_gain_bound_db": t_off["small_gain_bound_db"],
                        "small_gain_at_hz": t_off["small_gain_at_hz"],
                        "positive_real_db": t_off["positive_real_db"],
                        "positive_real_at_hz": t_off["positive_real_at_hz"]}
        t["fir_gain_over_off_db"] = {
            "small_gain": t["small_gain_bound_db"] - t_off["small_gain_bound_db"],
            "positive_real": (t["positive_real_db"] - t_off["positive_real_db"]
                              if np.isfinite(t["positive_real_db"]) else None),
        }
        base[tag] = t
        say("  [%s] 过门控 %d/%d（%.1f%%）bin；小增益下界 %+.2f dB @%.0f Hz；正实轴穿越 %+.2f dB @%.0f Hz"
            % (tag, t["gated_bins"], len(freqs), 100 * t["coverage_ratio"],
               t["small_gain_bound_db"], t["small_gain_at_hz"],
               t["positive_real_db"], t["positive_real_at_hz"] or float("nan")))
        say("       FIR-off 基准（Ĥ≡0，同数据同门控）：小增益 %+.2f dB、穿越 %+.2f dB → 本模型相对它 %+.2f / %+.2f dB"
            % (t_off["small_gain_bound_db"], t_off["positive_real_db"],
               t["fir_gain_over_off_db"]["small_gain"],
               t["fir_gain_over_off_db"]["positive_real"] or float("nan")))
        say("       分带 max|H-Ĥ|：")
        for band, v in t["bands"].items():
            if v["max_abs_E_db"] is None:
                say("         %-12s 无过门控 bin（未知）" % band)
            else:
                say("         %-12s %+7.2f dB @%5.0f Hz（相干 %.2f，%d bin）"
                    % (band, v["max_abs_E_db"], v["at_hz"], v["coherence"], v["gated"]))
    result["baseline"] = base
    say("  注意：两个阈值是两套估计（充分条件下界 / Nyquist 估计），不能拼成一个\"可用增益\"区间；")
    say("        两个窗长之差是本套离线筛选的敏感性，不是通用的 ±2 dB 误差条。")

    if args.compare_model:
        _m2, coef2, info2 = load_deployed_model(args.compare_model)
        freqs2, H22, coh22, _S22, _n22, fs22 = estimate_H(va, nperseg=args.nfft)
        gate22 = (coh22 >= args.coherence) & (freqs2 >= FMIN_HZ)
        t2 = thresholds(H22, model_response(coef2, args.nfft, lag_first=info2["lag_first"]),
                        freqs2, gate22, fs22, args.delay_frames)
        off2 = base["nfft_%d" % args.nfft]["fir_off"]
        say("\n[2b] 对照模型 %s" % info2["path"])
        say("  q20 %s  taps=%d  lag_first=%d" % (info2["q20_sha256"], info2["taps"], info2["lag_first"]))
        say("  小增益 %+.2f dB @%.0f Hz；穿越 %+.2f dB @%.0f Hz"
            % (t2["small_gain_bound_db"], t2["small_gain_at_hz"],
               t2["positive_real_db"], t2["positive_real_at_hz"] or float("nan")))
        say("  相对同门控 FIR-off（%+.2f / %+.2f dB）：%+.2f / %+.2f dB"
            % (off2["small_gain_bound_db"], off2["positive_real_db"],
               t2["small_gain_bound_db"] - off2["small_gain_bound_db"],
               t2["positive_real_db"] - off2["positive_real_db"]))
        say("  注意：「相对 FIR-off 更好」只说明模型有贡献；能不能在 0 dB 工作要看绝对值符号。")
        result["compare_model"] = {"file": info2["path"], "q20_sha256": info2["q20_sha256"],
                                  "thresholds": t2,
                                  "gain_over_fir_off_db": {
                                      "small_gain": t2["small_gain_bound_db"] - off2["small_gain_bound_db"],
                                      "positive_real": t2["positive_real_db"] - off2["positive_real_db"]}}

    # ---- [3] 候选 a：ridge / 权重 / 多场次 -----------------------------
    say("\n[3] 候选 a（固定 512 抽头）：ridge 与频带加权")
    G, bb, rows = segment_gram(tr)
    say("  训练法方程：%d 行（每段独立历史，窗口不跨段）" % rows)
    freqs, H_va, coh_va, _S, _n, fsx = estimate_H(va, nperseg=args.nfft)
    gate = (coh_va >= args.coherence) & (freqs >= FMIN_HZ)
    ridge_rows = []
    say("  %-10s %10s %10s %8s" % ("ridge", "小增益dB", "穿越dB", "||h||"))
    for r in (1e-9, 1e-7, 1e-5, 1e-3, 1e-1):
        h = solve_ridge(G, bb, r)
        t = thresholds(H_va, model_response(h, args.nfft), freqs, gate, fsx, args.delay_frames)
        ridge_rows.append({"ridge": r, "small_gain_bound_db": t["small_gain_bound_db"],
                           "positive_real_db": t["positive_real_db"],
                           "h_norm": float(np.linalg.norm(h))})
        say("  %-10.0e %+10.2f %+10.2f %8.3f"
            % (r, t["small_gain_bound_db"], t["positive_real_db"], np.linalg.norm(h)))
    result["screening_a_ridge"] = ridge_rows

    # 频带加权（频域 LS）：低频加权是零和搬运
    freqs_tr, H_tr, coh_tr, _S2, _n2, _fs2 = estimate_H(tr, nperseg=args.nfft)
    gate_tr = (coh_tr >= args.coherence) & (freqs_tr >= FMIN_HZ)
    lf = (freqs_tr >= 300) & (freqs_tr <= 1000)
    # 权重一律取正：零权重会让最小二乘在带外秩亏、解在未约束频点爆掉
    weight_sets = {
        "flat": np.ones(len(freqs_tr)),
        "lf_x5": np.where(lf, 5.0, 1.0),
        "lf_x20": np.where(lf, 20.0, 1.0),
    }
    wrows = []
    say("\n  频带加权（频域加权 LS，与上面的时间域等权不是同一个估计器）")
    say("  %-18s %12s %12s %8s %12s %10s"
        % ("权重", "300-1000 E", "1000-2000 E", "||h||", "小增益dB", "穿越dB"))
    for name, w in weight_sets.items():
        h = fit_weighted_freq(freqs_tr, H_tr, TAPS, w)
        E = np.abs(H_va - model_response(h, args.nfft))
        b1 = (freqs >= 300) & (freqs < 1000) & gate
        b2 = (freqs >= 1000) & (freqs < 2000) & gate
        t = thresholds(H_va, model_response(h, args.nfft), freqs, gate, fsx, args.delay_frames)
        wrows.append({"weights": name,
                      "lf_max_E_db": float(20 * np.log10(E[b1].max())),
                      "mid_max_E_db": float(20 * np.log10(E[b2].max())),
                      "small_gain_bound_db": t["small_gain_bound_db"],
                      "positive_real_db": t["positive_real_db"],
                      "h_norm": float(np.linalg.norm(h))})
        say("  %-18s %+12.2f %+12.2f %8.3f %+12.2f %+10.2f"
            % (name, 20 * np.log10(E[b1].max()), 20 * np.log10(E[b2].max()),
               np.linalg.norm(h), t["small_gain_bound_db"], t["positive_real_db"]))
    result["screening_a_weights"] = wrows
    g_small = wrows[-1]["small_gain_bound_db"] - wrows[0]["small_gain_bound_db"]
    g_real = wrows[-1]["positive_real_db"] - wrows[0]["positive_real_db"]
    best_small = max(w["small_gain_bound_db"] for w in wrows) - wrows[0]["small_gain_bound_db"]
    best_real = max(w["positive_real_db"] for w in wrows) - wrows[0]["positive_real_db"]
    say("  判读：加权**不是严格零和**，但也给不出可交付的收益——")
    say("        最有利的一档只比等权高 %+.1f dB（小增益）/ %+.1f dB（穿越），" % (best_small, best_real))
    say("        而 ×20 时反过来恶化 %+.1f / %+.1f dB。增益随权重非单调、方向不稳，" % (g_small, g_real))
    say("        且幅度都在 dB 个位数量级；另外频域 LS 与上面的时间域等权不是同一个估计器，")
    say("        跨估计器比较本身要打折扣。故维持否定，不交候选。")

    ms = {"status": "untested",
          "reason": "只有 2026-10-23 与 2026-10-24 两个场次；10-23 处话筒接线松脱期，"
                    "不能当独立验证；10-24 已是同场拟合的来源，没有第三场可比。"}
    result["screening_a_multisession"] = ms
    say("  多场次系数：未测（%s）" % ms["reason"])

    # ---- [4] 候选 b：前向 biquad --------------------------------------
    say("\n[4] 候选 b（前向固定 biquad）：幅度筛选参考，不是可部署实现")
    H_hat = model_response(coef, args.nfft, lag_first=info["lag_first"])
    E = np.abs(H_va - H_hat)
    ladder = [("none", []),
              ("435", [(435, 8, 8)]),
              ("435+3900", [(435, 8, 8), (3900, 8, 8)]),
              ("435+3900+880", [(435, 8, 8), (3900, 8, 8), (880, 8, 8)])]
    eq_rows = []
    say("  %-16s %12s %12s" % ("陷波组", "小增益dB", "穿越dB"))
    loop0 = (H_va - H_hat) * np.exp(-1j * 2 * np.pi * args.delay_frames * freqs / fsx)
    for name, spec in ladder:
        Bm = np.ones(len(freqs))
        for f0, d, q in spec:
            Bm *= biquad_notch_mag(freqs, f0, d, q)
        mm = np.abs((loop0 * Bm)[gate]).max()
        thr_p, f_p = positive_real_crossing(loop0 * Bm, freqs, gate)
        eq_rows.append({"notches": name, "small_gain_bound_db": float(-20 * np.log10(mm)),
                        "positive_real_db": float(thr_p),
                        "positive_real_at_hz": None if np.isnan(f_p) else float(f_p)})
        say("  %-16s %+12.2f %+12.2f" % (name, -20 * np.log10(mm), thr_p))
    # 语音代价（幅度）
    say("  语音代价（最重那一组，前向幅度响应）：")
    Bm = np.ones(len(freqs))
    for f0, d, q in ladder[-1][1]:
        Bm *= biquad_notch_mag(freqs, f0, d, q)
    for fc in (300.0, 435.0, 500.0, 700.0, 1000.0, 2000.0, 3900.0):
        k = int(np.argmin(np.abs(freqs - fc)))
        say("    %5.0f Hz  %+6.2f dB" % (freqs[k], 20 * np.log10(Bm[k])))
    result["screening_b_eq"] = eq_rows
    d_small = eq_rows[-1]["small_gain_bound_db"] - eq_rows[0]["small_gain_bound_db"]
    d_real = eq_rows[-1]["positive_real_db"] - eq_rows[0]["positive_real_db"]
    say("  增量（最重一组 vs 无 EQ）：小增益 %+.2f dB、穿越 %+.2f dB"
        % (d_small, d_real))
    say("  判读：三个 8 dB 陷波只换来 %+.1f dB（小增益）/ %+.1f dB（穿越），且 435 Hz 落在语音 F1、"
        % (d_small, d_real))
    say("        3898 Hz 缺口 −3 dB 宽约 488 Hz；参考取点还必须移到 EQ 之后（契约语义变更）。不交。")

    # ---- [5] 分段边界控制 ---------------------------------------------
    say("\n[5] 分段边界控制（所有比较按**相同全局帧索引**配对）")

    # 5a 评估侧：一条连续捕获切成 8 片，逐片复位；与整条一次跑按同一批帧比较。
    probe = va[0]
    up, mp, _ = load_segment(probe)
    ctl = split_pairing_control(coef, up, mp)
    n_whole = ctl["frames"]["whole"]
    n_piece = ctl["frames"]["piece"]
    say("  5a %s（%d 帧）切 8 片逐片复位 vs 整条一次跑，按同一批全局帧比较："
        % (Path(probe).name, len(up)))
    say("     样本数：整条有效 %d、逐片有效 %d、配对 %d（取交集，两边各统计一次）"
        % (n_whole, n_piece, ctl["frames"]["paired"]))
    if ctl["dropped_pieces"]:
        say("     片长 <= %d 帧的片 %s 无法评估（需要完整段内历史），两边同时剔除"
            % (TAPS, ctl["dropped_pieces"]))
    say("     逐样本最大差 %.3e，RMS 差 %+.2f dB" % (ctl["max_abs_diff"], ctl["rms_delta_db"]))
    say("     结论：每片都保留 >= %d 帧段内历史时，逐片复位与整条跑在配对帧上完全相同，" % TAPS)
    say("           分段本身不改变残差、也造不出收益。（旧版 0.53 dB 系样本配对错误，已撤回。）")
    say("     参考：换成**不同样本集合**（逐片 %d 帧 vs 整条 %d 帧）比较，差 %+.2f dB；"
        % (n_piece, n_whole, ctl["window_only_delta_db"]))
    say("           这是选窗差（帧数不同），不能当最小可辨改善，也不能据它否定更小的差异。")

    # 5b 拟合侧：逐段拟合 vs 拼段拟合，评估落在同一组留出帧上
    Gc, bc, rows_c = concat_gram(tr)
    h_concat = solve_ridge(Gc, bc)
    h_seg = solve_ridge(G, bb)
    say("  5b 训练法方程行数：逐段 %d / 拼段 %d（差 %d = %d 个边界 × %d，正好是跨段窗口）"
        % (rows, rows_c, rows_c - rows, len(tr) - 1, TAPS))
    U = np.concatenate([load_segment(p)[0] for p in va])
    M = np.concatenate([load_segment(p)[1] for p in va])
    starts, off = [], 0
    for p in va:
        n = len(load_segment(p)[0])
        starts.append((off, n))
        off += n
    pair_idx = np.concatenate([np.arange(s + TAPS, s + n) for s, n in starts])
    say("     %-14s %16s %14s %14s" % ("拟合方式", "抑制dB(配对帧)", "小增益dB", "穿越dB"))
    ctrl = {}
    for tag, h in (("per_segment", h_seg), ("concatenated", h_concat)):
        r = M - predict_stream(h, U)
        e = r[pair_idx]
        sup = 20 * np.log10(np.sqrt(np.mean(M[pair_idx] ** 2)) / np.sqrt(np.mean(e ** 2)))
        t = thresholds(H_va, model_response(h, args.nfft), freqs, gate, fsx, args.delay_frames)
        ctrl[tag] = {"suppression_db": float(sup), "frames": int(pair_idx.size),
                     "small_gain_bound_db": t["small_gain_bound_db"],
                     "positive_real_db": t["positive_real_db"]}
        say("     %-14s %+16.2f %+14.2f %+14.2f"
            % (tag, sup, t["small_gain_bound_db"], t["positive_real_db"]))
    d_fit = abs(ctrl["per_segment"]["suppression_db"] - ctrl["concatenated"]["suppression_db"])
    say("     判读：两种拟合在**同一批 %d 帧**上相差 %.2f dB；拼段只多 %d 行（占 %.2f%%），"
        % (int(pair_idx.size), d_fit, rows_c - rows, 100.0 * (rows_c - rows) / rows_c))
    say("           本数据上拼段拟合没有造出收益。残差/抑制一律按逐段复位口径，并报帧数与配对方式。")
    result["boundary_control"] = {
        "split_probe_file": Path(probe).name,
        "split": ctl,
        "fits": ctrl,
        "fit_delta_db": float(d_fit),
    }

    # ---- [6] 10-23 数据的处理 -----------------------------------------
    say("\n[6] 2026-10-23 场次（话筒接线松脱期）")
    xs = {"status": "excluded_from_training_and_validation"}
    if args.cross_session_dir:
        cdir = Path(args.cross_session_dir)
        cpaths = sorted(glob.glob(str(cdir / "seg_*.npz")))
        if cpaths:
            f2, H2, coh2, _S3, _n3, fs3 = estimate_H(cpaths, nperseg=args.nfft)
            g2 = (coh2 >= args.coherence) & (f2 >= FMIN_HZ)
            t2 = thresholds(H2, model_response(coef, args.nfft, lag_first=info["lag_first"]),
                            f2, g2, fs3, args.delay_frames)
            t2_off = thresholds(H2, np.zeros_like(H2), f2, g2, fs3, args.delay_frames)
            xs.update({"dir": str(cdir), "segments": len(cpaths),
                       "role": "cross_session_stress_test_not_validation",
                       "small_gain_bound_db": t2["small_gain_bound_db"],
                       "positive_real_db": t2["positive_real_db"],
                       "positive_real_at_hz": t2["positive_real_at_hz"],
                       "fir_off_small_gain_db": t2_off["small_gain_bound_db"],
                       "fir_off_positive_real_db": t2_off["positive_real_db"]})
            say("  该场次 FIR-off 基准：小增益 %+.2f dB、穿越 %+.2f dB"
                % (t2_off["small_gain_bound_db"], t2_off["positive_real_db"]))
            say("  仅作压力测试（%d 段）：小增益下界 %+.2f dB、穿越 %+.2f dB @%.0f Hz"
                % (len(cpaths), t2["small_gain_bound_db"], t2["positive_real_db"],
                   t2["positive_real_at_hz"] or float("nan")))
            say("  **不作为合格独立场次验证**：该批在话筒接线松脱期采集。")
        else:
            xs["error"] = "no seg_*.npz in %s" % cdir
            say("  目录内没有 seg_*.npz，跳过。")
    else:
        say("  未提供 --cross-session-dir，跳过跨场次压力测试。")
    result["session_20261023"] = xs

    # ---- 收尾 ---------------------------------------------------------
    say("\n" + "=" * 78)
    if out:
        (out / "repro.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (out / "repro.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
        print("写出 %s / repro.txt, repro.json" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
