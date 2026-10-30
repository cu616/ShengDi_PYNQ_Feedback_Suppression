"""残差首次越界的静默分析：先按板上记录重建，再用模型整数重放交叉核对。

只做给定输入下的算术。不加载 overlay、不播放、不改配置、不导出音频。

为什么分两条路径：
  * **主路径**（不需要模型）：宽残差 = 抓包里的 mic − 板上记录的 prediction。
    这与 RTL 的 25 位减法逐样本一致，所以"首次越界、越界个数、余量"直接来自板上事实。
  * **辅路径**（需要模型）：用 coefficients_q20 整数重放 prediction，与板上记录比对。
    只有比对通过，才允许把结论归因到"当前系数 + 当前算术"；不通过就停止归因。

边界口径（与 RTL 逐条对齐，见 src/rtl/feedback_fir.v / audio_pl_replay.v）：
  * 24 位合法范围 [-2^23, 2^23-1]；**-2^23 是合法负满幅**，越界判据是
    `x > 2^23-1 或 x < -2^23`，不是 `|x| >= 2^23`。
  * 乘增益后按 **半值远离零** 舍入：`(|p|+2^11)>>12`，再恢复符号；不是 Python 的向下取整。
  * 前 taps+1 帧历史是空的（RTL 从零开始填），这一段不能用来判"余量"或"首次越界"。

退出码：0 正常；2 输入不合格 / 身份不符 / 无可分析帧（此时不给"通过"结论）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
Q = 20
SCALE = 1 << 23                 # PCM 满幅（计数）
MAX24 = SCALE - 1               # +满幅
MIN24 = -SCALE                  # −满幅（合法）
GAIN_Q = 12

REQUIRED = ("reference", "microphone", "prediction_pcm", "residual_pcm",
            "coefficients_q20", "metadata_json", "sample_rate_hz")


def die(msg: str, code: int = 2) -> None:
    print("FAILED: " + msg)
    raise SystemExit(code)


def clamp24(x: np.ndarray) -> np.ndarray:
    """与 RTL 一致：上界 2^23-1，下界 -2^23（合法，不裁）。"""
    return np.clip(x, MIN24, MAX24)


def over24(x: np.ndarray) -> np.ndarray:
    """越界判据：严格大于正满幅，或严格小于负满幅。−2^23 本身合法。"""
    return (x > MAX24) | (x < MIN24)


def s24_from_raw(a) -> np.ndarray:
    """板上抓包有时按无符号 24 位存（0..2^24-1）。按值域自动转成有符号。"""
    a = np.asarray(a, dtype=np.int64)
    if a.size and (a.max() > MAX24 or a.min() < MIN24):
        if a.min() >= 0 and a.max() <= (1 << 24) - 1:
            return np.where(a >= SCALE, a - (1 << 24), a)
    return a


def rtl_predict(q20: np.ndarray, u_codes: np.ndarray):
    """逐样本重现 feedback_fir：int64 累加、(|acc|+2^19)>>20、半值远离零、钳到 ±2^23。"""
    taps = len(q20)
    n = len(u_codes)
    out = np.zeros(n, dtype=np.int64)
    h = q20.astype(np.int64)
    u = u_codes.astype(np.int64)
    sat = 0
    for i in range(n):
        upto = min(taps, i)
        if upto == 0:
            continue
        acc = int(np.dot(h[:upto], u[i - 1::-1][:upto]))
        mag = (abs(acc) + (1 << (Q - 1))) >> Q
        val = -mag if acc < 0 else mag
        if val > MAX24 or val < MIN24:
            sat += 1
            val = max(MIN24, min(MAX24, val))
        out[i] = val
    return out, sat


def rtl_gain(resid: np.ndarray, gain_q12: int) -> np.ndarray:
    """与 audio_pl_replay 一致：product = resid*gain；(|p|+2048)>>12；恢复符号。"""
    prod = resid.astype(np.int64) * int(gain_q12)
    mag = np.abs(prod)
    rounded = (mag + (1 << (GAIN_Q - 1))) >> GAIN_Q
    return np.where(prod < 0, -rounded, rounded)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def resolve_model(arg):
    if not arg:
        return None
    p = Path(arg)
    if not p.is_absolute():
        p = REPO / p
    if not p.exists():
        cand = sorted((REPO / "models").rglob(Path(arg).name))
        if not cand:
            die("模型文件不存在：%s（也未在 models/ 下找到同名文件）" % arg)
        p = cand[0]
        print("注意：%s 不存在，改用实际部署位置的同名文件 %s" % (arg, _rel(p)))
    return p


def load_npz(path: Path):
    if not path.exists():
        die("抓包不存在：%s" % path)
    cap = np.load(path, allow_pickle=True)
    missing = [k for k in REQUIRED if k not in cap]
    if missing:
        die("%s 缺必需字段：%s" % (path.name, missing))
    try:
        meta = json.loads(str(cap["metadata_json"]))
    except Exception as exc:                       # noqa: BLE001
        die("%s 的 metadata_json 解析失败：%s" % (path.name, exc))
    return cap, meta


def analyze(path: Path, model_q20, model_label, gain_db):
    cap, meta = load_npz(path)
    fs = float(cap["sample_rate_hz"])
    if not np.isfinite(fs) or fs <= 0:
        die("%s 的 sample_rate_hz 非法：%s" % (path.name, fs))

    q20_npz = s24_from_raw(cap["coefficients_q20"])
    q20 = model_q20 if model_q20 is not None else q20_npz
    substituted = model_q20 is not None and not np.array_equal(q20_npz, model_q20)
    bypass = meta.get("bypass")
    gain_q12 = int(meta.get("gain_q12", 0))
    if gain_db is not None:
        gain_q12 = int(round(4096 * 10 ** (gain_db / 20)))
    first_frame = int(meta.get("first_frame", 0))

    # 浮点字段可能被四舍五入到恰好 1.0；ADC/DAC 的实际码值一定落在 24 位内，先夹回去，
    # 免得把"浮点取整"当成残差越界。
    mic = np.clip(s24_from_raw(np.rint(np.asarray(cap["microphone"], float) * SCALE).astype(np.int64)),
                  MIN24, MAX24)
    ref = np.clip(s24_from_raw(np.rint(np.asarray(cap["reference"], float) * SCALE).astype(np.int64)),
                  MIN24, MAX24)
    pred_rec = s24_from_raw(cap["prediction_pcm"])
    resid_rec = s24_from_raw(cap["residual_pcm"])
    n = len(mic)
    if n == 0:
        die("%s 没有可分析帧" % path.name)

    taps = len(q20)
    valid_start = taps + 1            # 前 taps+1 帧历史为空，RTL 从零开始填
    if n <= valid_start + 16:
        die("%s 帧数 %d 不足（需要 > %d）" % (path.name, n, valid_start + 16))

    # ---- 主路径：完全按板上记录重建宽残差（不依赖模型）
    wide = mic - pred_rec
    narrow = clamp24(wide)
    ov = over24(wide)
    rail_pos = int(np.count_nonzero(resid_rec == MAX24))
    rail_neg = int(np.count_nonzero(resid_rec == MIN24))
    recorded_res_sat = meta.get("residual_saturations")

    reasons = []
    if substituted:
        reasons.append("模型与抓包内系数不同：只能作为替代模型的算术推演，不能归因本次事件")
    if bypass is True:
        reasons.append("这一路是 bypass：prediction 不参与输出，残差＝麦克风")
    if recorded_res_sat is not None and int(recorded_res_sat) != int(ov.sum()):
        reasons.append("重建的越界个数 %d 与板上 residual_saturations=%s 不符"
                       % (int(ov.sum()), recorded_res_sat))
    if not np.array_equal(narrow, resid_rec):
        bad = int(np.count_nonzero(narrow != resid_rec))
        reasons.append("重建的窄残差与板上 residual_pcm 不符 %d/%d 个样本（钳位口径或字段语义不一致）"
                       % (bad, n))

    # ---- 辅路径：模型整数重放，与板上 prediction 比对
    pred_rep, pred_sat = rtl_predict(q20, ref)
    mism = int(np.count_nonzero(pred_rep[valid_start:] != pred_rec[valid_start:]))
    if mism and not substituted:
        reasons.append("整数重放与板上 prediction 失配 %d/%d" % (mism, n - valid_start))

    out = rtl_gain(wide, gain_q12)
    out_ov = over24(out)

    ov_valid = ov.copy()
    ov_valid[:valid_start] = False
    first = int(np.argmax(ov_valid)) if ov_valid.any() else -1
    first_out = int(np.argmax(out_ov)) if out_ov.any() else -1

    res = {
        "file": path.name,
        "fs_hz": fs,
        "frames": n,
        "valid_start_index": valid_start,
        "valid_frames": n - valid_start,
        "valid_window_ms": round(1000 * (n - valid_start) / fs, 2),
        "capture_span_ms": round(1000 * n / fs, 2),
        "first_frame_global": first_frame,
        "last_frame_global": first_frame + n - 1,
        "fixture_id": meta.get("fixture_id"),
        "bit_sha256": meta.get("bit_sha256"),
        "bypass": bypass,
        "gain_q12": gain_q12,
        "gain_db": round(20 * np.log10(gain_q12 / 4096), 3) if gain_q12 > 0 else None,
        "model": {"label": model_label, "substituted": bool(substituted), "taps": taps},
        "recorded_counts": {k: meta.get(k) for k in
                            ("prediction_saturations", "residual_saturations",
                             "gain_saturations", "mix_saturations", "stop_reason")},
        "primary_capture_only": {
            "overflow_samples": int(ov.sum()),
            "overflow_in_valid_window": int(ov_valid.sum()),
            "overflow_in_history_region": int(ov.sum() - ov_valid.sum()),
            "first_overflow_index": first,
            "first_overflow_global_frame": (first_frame + first) if first >= 0 else None,
            "max_wide": float(np.abs(wide).max() / SCALE),
            "headroom_db": float(-20 * np.log10(np.abs(wide).max() / SCALE)),
            "mic_peak_dbfs": float(20 * np.log10(np.abs(mic).max() / SCALE)),
            "pred_peak_dbfs": float(20 * np.log10(max(1, np.abs(pred_rec).max()) / SCALE)),
            "residual_rail_samples_pos": rail_pos,
            "residual_rail_samples_neg": rail_neg,
        },
        "secondary_model_replay": {
            "prediction_mismatches": mism,
            "evaluated": n - valid_start,
            "local_prediction_saturations": int(pred_sat),
        },
        "post_gain": {
            "overflow_samples": int(out_ov.sum()),
            "first_overflow_index": first_out,
            "max_abs": float(np.abs(out).max() / SCALE),
            "margin_db": float(-20 * np.log10(max(np.abs(out).max(), 1) / SCALE)),
            "residual_ceiling_x": (4096.0 / gain_q12) if gain_q12 > 0 else None,
        },
        "attribution": {"allowed": not reasons, "model_substituted": bool(substituted),
                        "reasons": reasons},
    }

    if first >= 0:
        lo, hi = max(valid_start, first - 16), min(n, first + 17)
        res["primary_capture_only"]["around_first"] = {
            "index": list(range(lo, hi)),
            "global_frame": list(range(first_frame + lo, first_frame + hi)),
            "mic": (mic[lo:hi] / SCALE).round(6).tolist(),
            "pred": pred_rec[lo:hi].tolist(),
            "wide": (wide[lo:hi] / SCALE).round(6).tolist(),
            "out_after_gain": (out[lo:hi] / SCALE).round(6).tolist(),
        }
        win = 256
        seg_lo = max(valid_start, first - 8 * win)
        covered_ms = round(1000 * (first - seg_lo) / fs, 2)
        series = []
        for s in range(seg_lo, first - win + 1, win):
            seg = wide[s:s + win].astype(float)
            series.append(round(float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) / SCALE + 1e-30)), 2))
        res["growth"] = {
            "window_ms": round(1000 * win / fs, 2),
            "covered_ms": covered_ms,
            "rms_dbfs_per_window": series,
            "note": ("覆盖 <100 ms，不能据此判“单调增长 ≥100 ms”，增长趋势记未知"
                     if covered_ms < 100 else
                     "覆盖 ≥100 ms，可看趋势；但增长本身不等于再生，还要与源起止对齐"),
        }
    return res


def ps_margin(q20: np.ndarray, label, gain_list=(-6.0, -8.0, -10.0, -12.0, -14.0),
              fs: float = 48828.125) -> None:
    """PS 拓扑的残差裕量：residual/mic = 1/(1+g·e^{-j3ω}·H_raw)。

    这是**模型层面的敏感性分析**，不是现场越界频率。
    """
    nfft = 1 << 15
    k = np.arange(nfft // 2 + 1)
    w = 2 * np.pi * k / nfft
    h = q20.astype(float) / (1 << Q)
    H = np.fft.rfft(h, nfft) * np.exp(-3j * w)   # 1 拍 FIR + 2 拍调度
    freqs = k * fs / nfft
    sel = (freqs >= 300) & (freqs <= 10250)
    print()
    print("=" * 78)
    print("PS 拓扑裕量（模型层面，不是现场越界频率）：%s" % label)
    print("residual/mic = 1/(1+g·e^-j3ω·Ĥ)")
    print("=" * 78)
    print("  增益    min|1+…|   @Hz(模型敏感点)   残差/麦克风   该点麦克风到多少残差即满幅")
    for gdb in gain_list:
        g = 10 ** (gdb / 20)
        den = np.abs(1 + g * H)
        kk = int(np.argmin(np.where(sel, den, np.inf)))
        print("  %+6.1f  %8.3f   %8.1f      %7.2fx    %.4f (%+.1f dBFS)"
              % (gdb, den[kk], freqs[kk], 1 / den[kk], den[kk], 20 * np.log10(den[kk])))
    print("  注意：这只说明模型在哪些频点会把残差放大，不说明现场越界就发生在那里；")
    print("       也不能用“频响最大增益”保证任意语音瞬态峰值都不越界。")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz", nargs="+", default=[], help="一个或多个抓包 npz")
    ap.add_argument("--model", default=None, help="模型 JSON（相对仓库根或绝对路径）")
    ap.add_argument("--gain-db", type=float, default=None,
                    help="覆盖 metadata 的 gain_q12；默认用板上记录")
    ap.add_argument("--ps-margin", action="store_true", help="只算模型裕量表，不读抓包")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    model_path = resolve_model(args.model)
    model_q20 = None
    if model_path is not None:
        raw = model_path.read_bytes()
        model_q20 = s24_from_raw(json.loads(raw.decode("utf-8"))["coefficients_q20"])
        print("模型：%s（%d 抽头，file %s…）"
              % (_rel(model_path), len(model_q20), hashlib.sha256(raw).hexdigest()[:12]))

    if args.ps_margin:
        if model_q20 is None:
            die("--ps-margin 需要 --model")
        ps_margin(model_q20, args.model)
        if not args.npz:
            return 0

    if not args.npz:
        die("没有给 --npz；只算裕量请加 --ps-margin")

    print()
    print("=" * 78)
    print("残差首次越界：主路径按板上记录重建，辅路径用模型整数重放交叉核对")
    print("越界判据 x>2^23-1 或 x<-2^23（-2^23 合法）；增益按半值远离零舍入")
    print("=" * 78)

    results, bad = [], []
    for item in args.npz:
        r = analyze(Path(item), model_q20, args.model, args.gain_db)
        results.append(r)
        p = r["primary_capture_only"]
        print()
        print("--- %s" % r["file"])
        print("  采集：%d 帧 / %.1f ms；有效窗口从第 %d 帧起（%d 帧 / %.1f ms）；全局帧 %d–%d"
              % (r["frames"], r["capture_span_ms"], r["valid_start_index"], r["valid_frames"],
                 r["valid_window_ms"], r["first_frame_global"], r["last_frame_global"]))
        gain_txt = ("%+.3f dB" % r["gain_db"]) if r["gain_db"] is not None else "无增益"
        print("  身份：fixture=%s bit=%s… bypass=%s gain_q12=%d (%s)"
              % (r["fixture_id"], str(r["bit_sha256"])[:12], r["bypass"], r["gain_q12"], gain_txt))
        print("  板上计数：%s" % r["recorded_counts"])
        print("  [主] 越界样本 %d（有效窗口 %d，历史区 %d）；残差贴轨 +%d/−%d"
              % (p["overflow_samples"], p["overflow_in_valid_window"],
                 p["overflow_in_history_region"], p["residual_rail_samples_pos"],
                 p["residual_rail_samples_neg"]))
        print("       |mic|峰值 %+.1f dBFS；|pred|峰值 %+.1f dBFS；|宽残差|max %.4f×满幅（余量 %+.2f dB）"
              % (p["mic_peak_dbfs"], p["pred_peak_dbfs"], p["max_wide"], p["headroom_db"]))
        s = r["secondary_model_replay"]
        note = "（系数被覆盖，失配属预期）" if r["attribution"]["model_substituted"] else ""
        print("  [辅] 模型整数重放：prediction 失配 %d/%d%s，本地预测饱和 %d"
              % (s["prediction_mismatches"], s["evaluated"], note, s["local_prediction_saturations"]))
        gg = r["post_gain"]
        ceil_txt = ("%.3f×满幅（=4096/gain_q12）" % gg["residual_ceiling_x"]
                    if gg["residual_ceiling_x"] else "不适用（增益为 0）")
        print("  [增益后] |out|max %.4f×满幅（余量 %+.2f dB），越界样本 %d；残差最多可到 %s"
              % (gg["max_abs"], gg["margin_db"], gg["overflow_samples"], ceil_txt))
        if p["first_overflow_index"] >= 0:
            print("  首次越界：抓包内第 %d 帧 / 全局第 %d 帧"
                  % (p["first_overflow_index"], p["first_overflow_global_frame"]))
            gr = r["growth"]
            print("  增长：窗口 %s ms，只覆盖 %s ms → %s"
                  % (gr["window_ms"], gr["covered_ms"], gr["note"]))
        a = r["attribution"]
        print("  归因：%s" % ("可以" if a["allowed"] else "停止（" + "；".join(a["reasons"]) + "）"))
        if not a["allowed"]:
            bad.append(r["file"])

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        print("\n结构化结果写入 %s" % args.json_out)

    if bad:
        print("\n结论受限：%d 个文件不能归因（%s）；不据此给“通过”或“方案成立”的结论。"
              % (len(bad), "、".join(bad)))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
