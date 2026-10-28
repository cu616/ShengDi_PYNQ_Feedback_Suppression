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
  * 抓包只留运行末尾一圈，所以**本地模型重放缺前史**（需要前 taps 帧）；板上 prediction 本身没有缺，
    因此"主路径"不受影响，只有辅路径的前 taps+1 帧不能用来判"余量"或"首次越界"。

退出码：0 正常；2 输入不合格 / 身份不符 / 无可分析帧（此时不给"通过"结论）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

try:                       # Windows GBK 控制台遇到 U+2212 会崩在输出阶段
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:          # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent
Q = 20
SCALE = 1 << 23                 # PCM 满幅（计数）
MAX24 = SCALE - 1               # +满幅
MIN24 = -SCALE                  # −满幅（合法）
GAIN_Q = 12
# 归一化浮点的容差：只吸收浮点表示误差，不吸收量级越界。
# 1+2^-23 = 1.00000012 远超此值 → 直接拒绝（C 的边界用例）。
FLOAT_TOL = 4.0 * float(np.finfo(np.float64).eps)   # ≈ 8.9e-16

REQUIRED = ("reference", "microphone", "prediction_pcm", "residual_pcm",
            "coefficients_q20", "metadata_json", "sample_rate_hz")


def die(msg: str, code: int = 2) -> None:
    print("FAILED: " + msg)
    raise SystemExit(code)


def as_frame_index(v, name: str) -> int:
    """帧号必须是整数：0.5 / 1024.5 这类小数先拒绝，**不截断**。

    截断会静默把一个"字段写错了的抓包"当成合法帧域，后面所有全局帧号都跟着错。
    """
    if isinstance(v, bool):
        die("%s 是布尔值：%r（帧号必须是整数）" % (name, v))
    if isinstance(v, (int, np.integer)):
        return int(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        die("%s 不是数值：%r" % (name, v))
    if not np.isfinite(f):
        die("%s 非有限：%r" % (name, v))
    if f != int(f):
        die("%s 不是整数：%r（帧号必须是整数，不能截断）" % (name, v))
    return int(f)


def optional_frame_index(v, name: str, fname: str):
    """缺字段返回 None（后续按"未知"处理），有值则必须是整数。"""
    if v is None:
        return None
    try:
        return as_frame_index(v, "%s（%s）" % (name, fname))
    except SystemExit:
        raise


def clamp24(x: np.ndarray) -> np.ndarray:
    """与 RTL 一致：上界 2^23-1，下界 -2^23（合法，不裁）。"""
    return np.clip(x, MIN24, MAX24)


def over24(x: np.ndarray) -> np.ndarray:
    """越界判据：严格大于正满幅，或严格小于负满幅。−2^23 本身合法。"""
    return (x > MAX24) | (x < MIN24)


def codes_from_float(x, name: str):
    """归一化浮点字段（reference / microphone）→ 24 位码值。

    只接受 |x| <= 1.0。超范围就拒绝，**不静默夹**：抓到 2.0 说明字段不是归一化浮点，
    继续算下去会用错的量归因。

    容差只吸收**浮点表示误差**（4·eps ≈ 8.9e-16），不吸收量级上的越界：
    ±(1+2^-23) 属于"超出归一化范围"，直接拒绝，不再夹回后让整轮分析继续跑。
    恰好 ±1.0 允许；÷2^23 的舍入可能让码值取整到 2^23，那种单个计数的夹回会计数上报。
    """
    a = np.asarray(x, dtype=np.float64)
    if a.size == 0:
        die("%s 为空" % name)
    peak = float(np.max(np.abs(a)))
    if not np.isfinite(peak):
        die("%s 含 NaN/Inf" % name)
    if peak > 1.0 + FLOAT_TOL:
        die("%s 超出归一化范围：|max|=%.12f（容差只有 %.1e；该字段应为归一化到 ±1.0 的浮点，"
            "不接受超范围后夹回）" % (name, peak, FLOAT_TOL))
    c = np.rint(a * SCALE).astype(np.int64)
    clamped = int(np.count_nonzero((c > MAX24) | (c < MIN24)))
    return np.clip(c, MIN24, MAX24), clamped


def codes_from_int(x, name: str) -> np.ndarray:
    """整数 PCM / Q20 字段 → 有符号 24 位。

    必须是整数 dtype；允许"全非负且超过正满幅"的无符号 24 位打包（板上确实这么存过），
    但**混合符号又超正满幅**一律拒绝。-2^23 合法。
    """
    a = np.asarray(x)
    if not np.issubdtype(a.dtype, np.integer):
        die("%s 不是整数 dtype（%s）；PCM/Q20 字段不接受浮点" % (name, a.dtype))
    v = a.astype(np.int64)
    if v.size == 0:
        die("%s 为空" % name)
    if v.min() < MIN24:
        die("%s 低于 −2^23（min=%d）" % (name, int(v.min())))
    if v.max() <= MAX24:
        return v
    if v.min() >= 0 and v.max() <= (1 << 24) - 1:
        return np.where(v >= SCALE, v - (1 << 24), v)     # 无符号 24 位打包
    die("%s 混合符号且超过正满幅（min=%d max=%d）" % (name, int(v.min()), int(v.max())))


def q20_sha256(q: np.ndarray) -> str:
    """与 models/manifest.json 一致的 Q20 打包哈希（int32 小端）。"""
    return hashlib.sha256(np.asarray(q, dtype=np.int64).astype("<i4").tobytes()).hexdigest()


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

    # ---- 字段编码：浮点/整数分开处理，非法值拒绝而不是夹
    q20_npz = codes_from_int(cap["coefficients_q20"], "coefficients_q20")
    mic, mic_clamped = codes_from_float(cap["microphone"], "microphone")
    ref, ref_clamped = codes_from_float(cap["reference"], "reference")
    pred_rec = codes_from_int(cap["prediction_pcm"], "prediction_pcm")
    resid_rec = codes_from_int(cap["residual_pcm"], "residual_pcm")

    q20 = model_q20 if model_q20 is not None else q20_npz
    substituted = model_q20 is not None and not np.array_equal(q20_npz, model_q20)
    bypass = meta.get("bypass")
    gain_q12 = int(meta.get("gain_q12", 0))
    if gain_db is not None:
        gain_q12 = int(round(4096 * 10 ** (gain_db / 20)))
    first_frame = optional_frame_index(meta.get("first_frame"), "first_frame", path.name)
    n = len(mic)
    if n == 0:
        die("%s 没有可分析帧" % path.name)
    if not (len(ref) == len(pred_rec) == len(resid_rec) == n):
        die("%s 各字段帧数不一致：mic %d / ref %d / pred %d / resid %d"
            % (path.name, n, len(ref), len(pred_rec), len(resid_rec)))

    # ---- 帧域核对：抓包是"最后一圈"，first + frames 必须等于 completed。
    # 缺字段时**不默认成 0 或闭合**：局部分析照做，但全局位置与闭合规核标记为未知。
    if first_frame is not None and first_frame < 0:
        die("%s 的 first_frame 为负：%d" % (path.name, first_frame))
    completed = optional_frame_index(meta.get("completed_frames"), "completed_frames", path.name)
    if first_frame is not None and completed is not None:
        if first_frame + n != completed:
            die("%s 帧域不一致：first_frame %d + frames %d = %d ≠ completed_frames %d"
                "（抓包应为运行末尾那一圈）"
                % (path.name, first_frame, n, first_frame + n, completed))
        frame_domain = "ok"
    else:
        frame_domain = "unknown"      # 缺 first_frame 或 completed_frames，闭合核不了

    taps = len(q20)
    valid_start = taps + 1            # 本地重放缺前史，前 taps+1 帧不可信
    if n <= valid_start + 16:
        die("%s 帧数 %d 不足（需要 > %d）" % (path.name, valid_start + 16))

    # ---- 主路径：完全按板上记录重建宽残差（不依赖模型、不依赖历史）
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
    if mic_clamped or ref_clamped:
        reasons.append("归一化字段有 %d/%d 个样本落到 ±满幅后需夹回（可能是 ÷2^23 的浮点取整，"
                       "也可能是真的到轨）；已计数，不当作越界" % (mic_clamped, ref_clamped))
    declared = meta.get("coefficients_sha256")
    actual_hash = q20_sha256(q20_npz)
    if declared and str(declared).lower() != actual_hash:
        reasons.append("metadata 声明的 coefficients_sha256=%s… 与实际数组哈希 %s… 不符"
                       % (str(declared)[:12], actual_hash[:12]))
    if recorded_res_sat is not None and int(recorded_res_sat) != int(ov.sum()):
        reasons.append("重建的越界个数 %d 与板上 residual_saturations=%s 不符"
                       % (int(ov.sum()), recorded_res_sat))
    if not np.array_equal(narrow, resid_rec):
        bad = int(np.count_nonzero(narrow != resid_rec))
        reasons.append("重建的窄残差与板上 residual_pcm 不符 %d/%d 个样本（钳位口径或字段语义不一致）"
                       % (bad, n))

    # ---- 辅路径：模型整数重放（依赖历史，只判有效区）
    pred_rep, pred_sat = rtl_predict(q20, ref)
    mism = int(np.count_nonzero(pred_rep[valid_start:] != pred_rec[valid_start:]))
    if mism and not substituted:
        reasons.append("整数重放与板上 prediction 失配 %d/%d" % (mism, n - valid_start))

    out = rtl_gain(wide, gain_q12)
    out_ov = over24(out)

    v = slice(valid_start, n)
    ov_valid = ov.copy()
    ov_valid[:valid_start] = False
    first = int(np.argmax(ov_valid)) if ov_valid.any() else -1
    out_ov_valid = out_ov.copy()
    out_ov_valid[:valid_start] = False
    first_out = int(np.argmax(out_ov_valid)) if out_ov_valid.any() else -1

    def lvl(x):
        return float(20 * np.log10(max(np.abs(x).max(), 1) / SCALE))

    res = {
        "file": path.name,
        "fs_hz": fs,
        "frames": n,
        "valid_start_index": valid_start,
        "valid_frames": n - valid_start,
        "valid_window_ms": round(1000 * (n - valid_start) / fs, 2),
        "capture_span_ms": round(1000 * n / fs, 2),
        "first_frame_global": first_frame,
        "last_frame_global": (first_frame + n - 1) if first_frame is not None else None,
        "completed_frames": completed,
        "frame_domain": frame_domain,          # "ok" / "unknown"
        "frame_domain_note": ("first_frame + frames == completed_frames，全局帧号可用"
                              if frame_domain == "ok" else
                              "缺 first_frame 或 completed_frames：只做局部分析，全局帧号与闭合核对为未知"),
        "fixture_id": meta.get("fixture_id"),
        "bit_sha256": meta.get("bit_sha256"),
        "bypass": bypass,
        "gain_q12": gain_q12,
        "gain_db": round(20 * np.log10(gain_q12 / 4096), 3) if gain_q12 > 0 else None,
        "encoding": {"mic_clamped": mic_clamped, "ref_clamped": ref_clamped,
                     "coefficients_sha256_declared": declared,
                     "coefficients_sha256_actual": actual_hash},
        "model": {"label": model_label, "substituted": bool(substituted), "taps": taps},
        "recorded_counts": {k: meta.get(k) for k in
                            ("prediction_saturations", "residual_saturations",
                             "gain_saturations", "mix_saturations", "stop_reason")},
        "primary_capture_only": {
            "note": "mic 与板上 prediction 相减，不依赖模型、不依赖历史；"
                    "但抓包只留末尾一圈、本地重放缺前史，前 taps+1 帧的 prediction 不可信，"
                    "所以归因与余量以有效区为准",
            "mic_peak_dbfs": {"whole": lvl(mic), "valid": lvl(mic[v])},
            "pred_peak_dbfs": {"whole": lvl(pred_rec), "valid": lvl(pred_rec[v])},
            "wide_max_x": {"whole": float(np.abs(wide).max() / SCALE),
                           "valid": float(np.abs(wide[v]).max() / SCALE)},
            "wide_headroom_db": {"whole": float(-20 * np.log10(np.abs(wide).max() / SCALE)),
                                 "valid": float(-20 * np.log10(np.abs(wide[v]).max() / SCALE))},
            "overflow_samples": {"whole": int(ov.sum()), "valid": int(ov_valid.sum()),
                                 "history": int(ov.sum() - ov_valid.sum())},
            "first_overflow_index": first,
            "first_overflow_global_frame": ((first_frame + first)
                                            if (first >= 0 and first_frame is not None) else None),
            "residual_rail_samples_pos": rail_pos,
            "residual_rail_samples_neg": rail_neg,
        },
        "secondary_model_replay": {
            "note": "本地模型重放缺前史（需前 taps 帧），只判有效区；前缀失配单独计数",
            "prediction_mismatches": mism,
            "mismatches_in_prefix": int(np.count_nonzero(pred_rep[:valid_start] != pred_rec[:valid_start])),
            "evaluated": n - valid_start,
            "local_prediction_saturations": int(pred_sat),
        },
        "post_gain": {
            "overflow_samples": {"whole": int(out_ov.sum()), "valid": int(out_ov_valid.sum())},
            "first_overflow_index": first_out,
            "max_abs": {"whole": float(np.abs(out).max() / SCALE),
                        "valid": float(np.abs(out[v]).max() / SCALE)},
            "margin_db": {"whole": float(-20 * np.log10(max(np.abs(out).max(), 1) / SCALE)),
                          "valid": float(-20 * np.log10(max(np.abs(out[v]).max(), 1) / SCALE))},
            "residual_ceiling_x": (4096.0 / gain_q12) if gain_q12 > 0 else None,
        },
        "attribution": {"allowed": not reasons, "model_substituted": bool(substituted),
                        "reasons": reasons},
    }

    if first >= 0:
        lo, hi = max(valid_start, first - 16), min(n, first + 17)
        res["primary_capture_only"]["around_first"] = {
            "index": list(range(lo, hi)),
            "global_frame": (list(range(first_frame + lo, first_frame + hi))
                             if first_frame is not None else None),
            "mic": (mic[lo:hi] / SCALE).round(6).tolist(),
            "pred": pred_rec[lo:hi].tolist(),
            "wide": (wide[lo:hi] / SCALE).round(6).tolist(),
            "out_after_gain": (out[lo:hi] / SCALE).round(6).tolist(),
        }
        win = 256
        seg_lo = max(valid_start, first - 8 * win)
        covered_ms = round(1000 * (first - seg_lo) / fs, 2)
        series = []
        for st in range(seg_lo, first - win + 1, win):
            seg = wide[st:st + win].astype(float)
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


def envelope(mic: np.ndarray, fs: float, block: int, taps: int):
    """分块包络：RMS、峰值、贴轨样本数、主频与窄带占比。

    主频/占比只用来分"讲话的共振峰"还是"环路在某个模态上起振"，
    不当作再生判据本身。
    """
    n = len(mic)
    rows = []
    win = np.hanning(block)
    freqs = np.fft.rfftfreq(block, 1.0 / fs)
    sel = (freqs >= 100) & (freqs <= 1500)
    for start in range(0, n - block + 1, block):
        seg = mic[start:start + block].astype(float) / SCALE
        rms = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-30)
        peak = 20 * np.log10(np.abs(seg).max() + 1e-30)
        seg_raw = mic[start:start + block]
        rails = int(np.count_nonzero((seg_raw >= MAX24) | (seg_raw <= MIN24)))
        spec = np.abs(np.fft.rfft(seg * win)) ** 2
        k = int(np.argmax(np.where(sel, spec, 0)))
        share = float(spec[max(0, k - 1):k + 2].sum() / (spec.sum() + 1e-30))
        rows.append({"start": start, "end": start + block - 1,
                     "rms_dbfs": round(float(rms), 1), "peak_dbfs": round(float(peak), 1),
                     "rail_samples": rails, "dominant_hz": round(float(freqs[k]), 1),
                     "narrow_share": round(share, 3)})
    return rows


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
    ap.add_argument("--envelope", action="store_true",
                    help="额外打印分块包络（RMS/峰值/贴轨/主频/窄带占比）")
    ap.add_argument("--block", type=int, default=2048, help="包络块长（帧），默认 2048")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    model_path = resolve_model(args.model)
    model_q20 = None
    if model_path is not None:
        raw = model_path.read_bytes()
        model_q20 = codes_from_int(json.loads(raw.decode("utf-8"))["coefficients_q20"], "model.coefficients_q20")
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
        if args.envelope:
            cap, _meta = load_npz(Path(item))
            mic_codes = np.clip(np.rint(np.asarray(cap["microphone"], float) * SCALE).astype(np.int64),
                                MIN24, MAX24)
            r["envelope"] = envelope(mic_codes, r["fs_hz"], args.block, r["model"]["taps"])
        results.append(r)
        p = r["primary_capture_only"]
        print()
        print("--- %s" % r["file"])
        if r["frame_domain"] == "ok":
            where = ("全局帧 %d–%d（completed %s，闭合核对通过）"
                     % (r["first_frame_global"], r["last_frame_global"], r["completed_frames"]))
        else:
            where = "全局帧未知（缺 first_frame / completed_frames，只做局部分析）"
        print("  采集：%d 帧 / %.1f ms；有效窗口从第 %d 帧起（%d 帧 / %.1f ms）；%s"
              % (r["frames"], r["capture_span_ms"], r["valid_start_index"], r["valid_frames"],
                 r["valid_window_ms"], where))
        gain_txt = ("%+.3f dB" % r["gain_db"]) if r["gain_db"] is not None else "无增益"
        print("  身份：fixture=%s bit=%s… bypass=%s gain_q12=%d (%s)"
              % (r["fixture_id"], str(r["bit_sha256"])[:12], r["bypass"], r["gain_q12"], gain_txt))
        print("  编码：mic 夹回 %d 个、ref 夹回 %d 个；Q20 实算 %s… / 声明 %s…"
              % (r["encoding"]["mic_clamped"], r["encoding"]["ref_clamped"],
                 str(r["encoding"]["coefficients_sha256_actual"])[:12],
                 str(r["encoding"]["coefficients_sha256_declared"])[:12]))
        print("  板上计数：%s" % r["recorded_counts"])
        print("  [主] 越界样本 %d（有效区 %d / 历史区 %d）；残差贴轨 +%d/−%d"
              % (p["overflow_samples"]["whole"], p["overflow_samples"]["valid"],
                 p["overflow_samples"]["history"],
                 p["residual_rail_samples_pos"], p["residual_rail_samples_neg"]))
        print("       |mic|峰值  整窗 %+.1f / 有效区 %+.1f dBFS"
              % (p["mic_peak_dbfs"]["whole"], p["mic_peak_dbfs"]["valid"]))
        print("       |pred|峰值 整窗 %+.1f / 有效区 %+.1f dBFS"
              % (p["pred_peak_dbfs"]["whole"], p["pred_peak_dbfs"]["valid"]))
        print("       宽残差max  整窗 %.4f / 有效区 %.4f ×满幅（余量 %+.2f / %+.2f dB）"
              % (p["wide_max_x"]["whole"], p["wide_max_x"]["valid"],
                 p["wide_headroom_db"]["whole"], p["wide_headroom_db"]["valid"]))
        s2 = r["secondary_model_replay"]
        note = "（系数被覆盖，失配属预期）" if r["attribution"]["model_substituted"] else ""
        print("  [辅] 模型整数重放：有效区失配 %d/%d%s，前缀失配 %d，本地预测饱和 %d"
              % (s2["prediction_mismatches"], s2["evaluated"], note,
                 s2["mismatches_in_prefix"], s2["local_prediction_saturations"]))
        gg = r["post_gain"]
        ceil_txt = ("%.3f×满幅（=4096/gain_q12）" % gg["residual_ceiling_x"]
                    if gg["residual_ceiling_x"] else "不适用（增益为 0）")
        print("  [增益后] |out|max 整窗 %.4f / 有效区 %.4f ×满幅（余量 %+.2f / %+.2f dB），"
              "越界样本 整窗 %d / 有效区 %d；残差最多可到 %s"
              % (gg["max_abs"]["whole"], gg["max_abs"]["valid"],
                 gg["margin_db"]["whole"], gg["margin_db"]["valid"],
                 gg["overflow_samples"]["whole"], gg["overflow_samples"]["valid"], ceil_txt))
        if p["first_overflow_index"] >= 0:
            g = p["first_overflow_global_frame"]
            print("  首次越界（有效区）：抓包内第 %d 帧 / %s"
                  % (p["first_overflow_index"],
                     ("全局第 %d 帧" % g) if g is not None else "全局帧未知"))
            gr = r["growth"]
            print("  增长：窗口 %s ms，只覆盖 %s ms → %s"
                  % (gr["window_ms"], gr["covered_ms"], gr["note"]))
        if args.envelope and "envelope" in r:
            print("  [包络] 每 %d 帧（%.2f ms）一块：块起点 RMS 峰值 贴轨 主频 窄带占比"
                  % (args.block, 1000 * args.block / r["fs_hz"]))
            for row in r["envelope"]:
                print("         %6d–%6d  %+7.1f  %+7.1f  %4d  %7.1f Hz  %.3f"
                      % (row["start"], row["end"], row["rms_dbfs"], row["peak_dbfs"],
                         row["rail_samples"], row["dominant_hz"], row["narrow_share"]))
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
