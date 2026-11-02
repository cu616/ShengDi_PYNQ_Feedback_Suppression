"""一键重标定的数值决策层：把"看曲线后拍板"换成有界规则。

本模块只做判定，不采集、不碰板卡、不加载模型文件、不改 RTL。只依赖 numpy。
调用方（C 的状态机、A 的采集脚本、离线复核）传数组与字典进来，拿字典出去。

四类判定，彼此不替代：

  check_capture      这份采样能不能用来拟合          -> OK / REJECT_*
  plan_excitation    下一次要不要改激励、改成什么     -> 有界，最多 MAX_ATTEMPTS 档
  check_fit          拟合出的模型能不能装             -> DEPLOYABLE_FIT / REJECT_*
  check_three_point  三点测量支不支持启用             -> PASS / FAIL / INCONCLUSIVE + 四类原因

另有一个选点规则 select_probe_frequencies：只用开环 H 与增益，不看 cancel 的任何数据。

口径（与既有报告同源，不另立标准）：
  - 单位：PCM 满幅 ±1.0（2^23 计数）；系数 Q20 满量程 ±8.0。两个 8 不是一回事。
  - 环路提升 boost = bypass - open；过冲 over = open - cancel；声学差 acoustic = bypass - cancel。
    三者满足 acoustic = boost + over，恒等，不可能同时任意取。
  - 声源是数字注入 u = sat(source + g*residual)，闭环 played/source = 1/|1 - g(H-Hh)|。
    因此 over 的物理含义是"抵消臂相对无环路臂的电平差"，正=过抵消，负=残留正反馈。
  - CD 是离线量（残差深度），不进现场判据，只作旁证。

所有阈值集中在下面一节，改阈值必须同时改 sim/feedback/test_recal_policy.py 里的钉值。
"""
from __future__ import annotations

import hashlib

import numpy as np

SCHEMA_VERSION = 1
FULL_SCALE = 1.0
LSB24 = 2.0 ** -23

# ---------------------------------------------------------------- 阈值（有界策略的唯一定义处）

# 采集资格
MIN_VALID_FRAMES = 4096              # 512 抽头的 8 倍，低于此不做拟合
NEAR_FULL_SCALE = 0.999              # 近满幅计数门限；命中即拒收
MIN_EXCITATION_SNR_DB = 0.0          # 兜底判据：相干功率不足一半即判"激励没进来"
MIN_GATED_COHERENCE = 0.30           # 主判据：相干>=0.8 的 bin 占比下限
COHERENCE_FLOOR = 0.8
SPARSE_LINE_DB = 20.0                # 谱 p95-p50 超过它就判稀疏线（多音）激励
FLOOR_WINDOW_S = 0.010               # 短时 RMS 包络的窗长
#
# 关于 MIN_EXCITATION_SNR_DB 为什么是 0 而不是 6（2026-11-01 用历史数据反校准）：
#   这个量是"麦克风功率里能被参考解释的比例" 10log10(Σcoh·Syy / Σ(1-coh)·Syy)。
#   拿它当主判据会把**部署模型自己的训练数据判成不可用**：
#     bind4 六段（rewired_512_20261026 的来源）snr 中位 3.9 dB，但相干中位 0.90、
#     相干>=0.8 的 bin 占 73%；calib6 六段 snr 3.9、相干 0.83、门控 54%。
#   原因是 1 m 侧对布置下麦克风拾到大量不相干的环境/反射能量，它压低了这个全局比值，
#   但并没有毁掉"哪些 bin 可用"。所以主判据改成 gated ratio，SNR 退回兜底：
#   只抓真正的"激励没进来"（历史样本：mic 全零的段 snr = -326 dB，门控 0%）。
#   这条改动不是为让某个结果通过，是因为标准与已部署事实矛盾；两种数据都列在
#   report/verification/recalibration-policy-2026-11-01/ 的复核表里。

# 激励规划（有界）
EXCITATION_LADDER_DBFS = (-30.0, -24.0, -20.0)
MAX_ATTEMPTS = 2                     # 失败后最多再试 2 档，之后退出
PEAK_CAP = 0.80
MIN_LEVEL_STEP_DB = 3.0              # 相邻档位实际 RMS 差小于此值时判"没换激励"

# 模型可部署性
L1_MAX = 4.0                         # 历史：部署 2.288、10-26 新布局 2.151
L1_OVER_MAX_RANGE = (25.0, 80.0)     # 历史 49.9 / 52.3 / 51.6 / 50.1
PEAK_TAP_TOLERANCE = 4               # 与基准模型的抽头峰位差（帧）

# 三点验证
BOOST_MIN_DB = 0.5                   # 低于它该频点没有可收回的环路提升，判 INAPPLICABLE
OVER_MIN_DB = -1.5                   # 过冲下界：比无环路还响超过 1.5 dB 即拒
ACOUSTIC_MIN_DB = 0.0                # 抵消臂不得比零臂更响
OVER_PRED_TOLERANCE_DB = 1.5         # 实测 over 与离线预测 over 的允许偏差
MIN_PASSING_PROBES = 2               # 三个预选点里至少两个给出 PASS


def _db(x):
    return 20.0 * np.log10(np.asarray(x, dtype=float) + 1e-30)


def _rms_db(x):
    x = np.asarray(x, dtype=float)
    return float(20.0 * np.log10(np.sqrt(np.mean(x * x)) + 1e-30))


def _sha256_int16(pcm):
    return hashlib.sha256(np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest()


def _result(status, **extra):
    out = {"schema_version": SCHEMA_VERSION, "status": status}
    out.update(extra)
    return out


# ---------------------------------------------------------------- 激励生成（有界，不静默缩放）

def make_excitation(level_db, frames, seed=4242, peak_cap=PEAK_CAP):
    """生成一档白噪激励，返回实际达成的电平与序列身份。

    改了什么：旧实现的写法是"先归一化到目标 RMS，再按峰值上限整体缩放"。
    只要目标峰值超过上限，缩放就把所有档位压成同一个序列 —— 三个名义电平
    输出的 PCM 完全相同，板子上白跑两轮。这里把"缩放"改成"报不可达"：
    目标超过该 seed 能到的 RMS 上限时，返回 reachable=False 与实际达成值，
    由调用方决定降目标还是换 seed，绝不把两档伪装成一档。

    返回 dict: pcm(int16) / requested_rms_dbfs / achieved_rms_dbfs / peak /
               peak_dbfs / crest_db / reachable / ceiling_dbfs / sha256
    """
    n = int(frames)
    if n < 1:
        raise ValueError("frames must be positive")
    level = float(level_db)
    cap = float(peak_cap)
    if not np.isfinite(level) or not np.isfinite(cap) or not 0.0 < cap <= 1.0:
        raise ValueError("level_db must be finite and 0 < peak_cap <= 1")

    rng = np.random.default_rng(int(seed))
    x = rng.standard_normal(n)
    x -= x.mean()
    x /= np.sqrt(np.mean(x * x)) or 1.0
    crest = float(np.max(np.abs(x)))              # 该 seed 的波峰因数，≈4.0
    ceiling_dbfs = float(20.0 * np.log10(cap / crest))   # 这个 seed 在不超 cap 时能到的最大 RMS

    requested = 10.0 ** (level / 20.0)
    reachable = bool(level <= ceiling_dbfs + 1e-12)
    rms = requested if reachable else cap / crest
    x = x * rms
    pcm = np.rint(x * 32767.0).astype(np.int16)
    peak = float(np.max(np.abs(pcm)) / 32767.0)
    return {
        "schema_version": SCHEMA_VERSION,
        "pcm": pcm,
        "requested_rms_dbfs": level,
        "achieved_rms_dbfs": _rms_db(pcm.astype(float) / 32767.0),
        "peak": peak,
        "peak_dbfs": float(20.0 * np.log10(peak + 1e-30)),
        "crest_db": float(20.0 * np.log10(crest)),
        "reachable": reachable,
        "ceiling_dbfs": ceiling_dbfs,
        "seed": int(seed),
        "sha256": _sha256_int16(pcm),
    }


def assert_distinct_levels(levels):
    """同一轮里各档位的序列身份必须两两不同。

    levels: make_excitation 的返回值列表。返回 (ok, 说明)。
    这是"相同 PCM 不能当多个档位"的可执行版本：调用方在发激励之前调用一次。
    """
    seen = {}
    for item in levels:
        key = item["sha256"]
        if key in seen:
            return False, ("档位 %+.1f 与 %+.1f dBFS 生成了相同序列（sha256 %s…），"
                           "属于同一档，不能当两次试探"
                           % (seen[key], item["requested_rms_dbfs"], key[:12]))
        seen[key] = item["requested_rms_dbfs"]
    ordered = sorted(levels, key=lambda v: v["achieved_rms_dbfs"])
    for a, b in zip(ordered, ordered[1:]):
        step = b["achieved_rms_dbfs"] - a["achieved_rms_dbfs"]
        if step < MIN_LEVEL_STEP_DB:
            return False, ("相邻档位实际 RMS 只差 %.2f dB（< %.1f），激励没有实质改变"
                           % (step, MIN_LEVEL_STEP_DB))
    return True, "ok"


# ---------------------------------------------------------------- 采集资格

def _shorttime_rms_db(x, fs, window_s=FLOOR_WINDOW_S):
    x = np.asarray(x, dtype=float)
    win = max(16, int(round(window_s * fs)))
    if len(x) < win:
        return np.array([_rms_db(x)])
    hop = max(1, win // 2)
    starts = np.arange(0, len(x) - win + 1, hop)
    if starts.size == 0:
        return np.array([_rms_db(x)])
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[starts]
    return 10.0 * np.log10(np.mean(frames * frames, axis=1) + 1e-30)


def _band_coherence(reference, microphone, fs, nperseg=4096):
    """Welch 相干，返回 (freqs, coherence)，两者等长。

    用来判"这一段在需要评价的频带里有没有信息"。只做 rfft，不做归一化。
    """
    n = min(len(reference), len(microphone))
    if n < 4 * nperseg:
        nperseg = max(256, n // 4)
    if n < nperseg:
        return np.array([0.0]), np.array([0.0])
    step = max(1, nperseg // 2)
    win = np.hanning(nperseg + 1)[:nperseg]
    frames_r = np.lib.stride_tricks.sliding_window_view(reference[:n], nperseg)[::step]
    frames_m = np.lib.stride_tricks.sliding_window_view(microphone[:n], nperseg)[::step]
    if frames_r.shape[0] == 0:
        return np.array([0.0]), np.array([0.0])
    R = np.fft.rfft(frames_r * win, axis=1)
    M = np.fft.rfft(frames_m * win, axis=1)
    Sxx = np.mean(np.abs(R) ** 2, axis=0)
    Syy = np.mean(np.abs(M) ** 2, axis=0)
    Sxy = np.mean(M * np.conj(R), axis=0)
    coh = np.abs(Sxy) ** 2 / np.maximum(Sxx * Syy, 1e-30)
    freqs = np.fft.rfftfreq(nperseg, 1.0 / fs)
    return freqs, np.clip(coh, 0.0, 1.0), Syy


def check_capture(reference, microphone, sample_rate_hz, metadata=None,
                  source=None, f_lo=150.0, f_hi=10000.0, taps=512):
    """判一份开环采样能不能用于拟合。只看数据与记录，不看模型。

    拒收顺序固定：完整性 -> 削顶 -> 参考资格 -> 激励/底噪 -> 稀疏线 -> 相干。
    先命中的先返回，理由写进 reasons，后续检查仍会算出数值供诊断。

    返回 dict，字段固定，可直接进 C 的状态机。
    """
    md = dict(metadata or {})
    ref = np.asarray(reference, dtype=float)
    mic = np.asarray(microphone, dtype=float)
    fs = float(sample_rate_hz)
    reasons = []
    metrics = {"frames": int(len(ref)), "sample_rate_hz": fs, "taps": int(taps)}

    # ---- 完整性
    integrity = []
    if ref.ndim != 1 or mic.ndim != 1:
        integrity.append("数组不是一维")
    if len(ref) != len(mic):
        integrity.append("reference 与 microphone 长度不同（%d vs %d）" % (len(ref), len(mic)))
    if not np.isfinite(ref).all() or not np.isfinite(mic).all():
        integrity.append("存在非有限值")
    if md.get("dropped_frames") not in (None, 0):
        integrity.append("dropped_frames=%s" % md.get("dropped_frames"))
    valid = int(min(len(ref), len(mic)))
    if valid < MIN_VALID_FRAMES:
        integrity.append("有效帧 %d < %d" % (valid, MIN_VALID_FRAMES))
    metrics["valid_frames"] = valid
    if integrity:
        return _result("REJECT_INTEGRITY", metrics=metrics, reasons=integrity,
                       next={"kind": "redo_capture", "why": "数据不足以拟合，改参数也不会变好"})

    # ---- 削顶 / 满幅
    fs_marks = {
        "reference_fullscale": int(np.sum(np.abs(ref) >= FULL_SCALE - LSB24)),
        "microphone_fullscale": int(np.sum(np.abs(mic) >= FULL_SCALE - LSB24)),
        "reference_near": int(np.sum(np.abs(ref) >= NEAR_FULL_SCALE)),
        "microphone_near": int(np.sum(np.abs(mic) >= NEAR_FULL_SCALE)),
        "bit22": md.get("input_overflow_bit22", md.get("bit22")),
    }
    metrics["fullscale"] = fs_marks
    metrics["ref_peak"] = float(np.max(np.abs(ref)))
    metrics["mic_peak"] = float(np.max(np.abs(mic)))
    clipped = (fs_marks["reference_fullscale"] + fs_marks["microphone_fullscale"]
               + fs_marks["reference_near"] + fs_marks["microphone_near"])
    if clipped or fs_marks["bit22"] == 1:
        return _result("REJECT_CLIP", metrics=metrics,
                       reasons=["输入触及满幅：ref 近满幅 %d、mic 近满幅 %d、bit22=%s"
                                % (fs_marks["reference_near"], fs_marks["microphone_near"],
                                   fs_marks["bit22"])],
                       next={"kind": "lower_input_gain", "why": "先收回输入余量再谈激励"})

    # ---- 参考资格
    ref_rms = _rms_db(ref)
    mic_rms = _rms_db(mic)
    metrics["ref_rms_dbfs"] = ref_rms
    metrics["mic_rms_dbfs"] = mic_rms
    metrics["mic_over_ref_db"] = mic_rms - ref_rms

    ref_issues = []
    if source is not None:
        src = np.asarray(source, dtype=float)
        first = int(md.get("first_frame", 0) or 0)
        k = min(len(ref), len(src) - first)
        if k < MIN_VALID_FRAMES:
            ref_issues.append("source 与窗口重叠不足（%d 帧）" % max(0, k))
        else:
            a, b = ref[:k], src[first:first + k]
            ratio = _rms_db(a) - _rms_db(b)
            corr = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else 0.0
            metrics["ref_vs_source_db"] = float(ratio)
            metrics["ref_vs_source_corr"] = float(corr)
            if abs(ratio) > 0.01 or corr < 0.9999:
                ref_issues.append("reference 不是纯源（差 %+.3f dB，相关 %.6f），"
                                  "反馈项可能仍在环内" % (ratio, corr))
    else:
        metrics["ref_vs_source_db"] = None
        metrics["ref_vs_source_corr"] = None

    # 稀疏线检测：白噪的谱平坦，多音的谱是尖峰
    n = len(ref)
    spec_db = 20.0 * np.log10(np.abs(np.fft.rfft(ref * np.hanning(n))) + 1e-30)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    band = (f >= f_lo) & (f <= f_hi)
    if band.sum() > 32:
        p50, p95 = np.percentile(spec_db[band], [50, 95])
        metrics["spectral_p50_db"] = float(p50)
        metrics["spectral_p95_db"] = float(p95)
        metrics["spectral_spread_db"] = float(p95 - p50)
        if p95 - p50 > SPARSE_LINE_DB:
            ref_issues.append("激励不是宽带：谱 p95-p50 = %.1f dB（> %.1f），"
                              "稀疏线会让互相关出现等高峰、延迟估计不可用"
                              % (p95 - p50, SPARSE_LINE_DB))
    if ref_issues:
        return _result("REJECT_REFERENCE", metrics=metrics, reasons=ref_issues,
                       next={"kind": "redo_capture", "why": "换回宽带白噪再采，不要用多音拟合"})

    # ---- 激励 / 底噪：用"麦克风功率里能被参考解释的比例"，不用包络
    #
    # 早期写法是拿短时 RMS 包络的 p95-p5 当激励信噪比。它只在"有静默段"时成立：
    # 持续白噪的包络本来就是平的，p95-p5≈1 dB，会把一份好数据判成"激励没进麦克风"。
    # 改成频域：coh = S_signal/(S_signal+S_noise)，于是相干功率比就是有效信噪比，
    # 对"持续激励"和"有声有停"两种情况都成立；音响待机时相干崩到 0，一样会被抓到。
    env_ref = _shorttime_rms_db(ref, fs)
    env_mic = _shorttime_rms_db(mic, fs)
    metrics["mic_floor_p05_db"] = float(np.percentile(env_mic, 5))
    metrics["mic_active_p95_db"] = float(np.percentile(env_mic, 95))
    metrics["envelope_span_db"] = float(np.percentile(env_mic, 95) - np.percentile(env_mic, 5))
    metrics["ref_envelope_span_db"] = float(np.percentile(env_ref, 95) - np.percentile(env_ref, 5))

    # ---- 相干（按需评价的频带）
    freqs, coh, syy = _band_coherence(ref, mic, fs)
    sel = (freqs >= f_lo) & (freqs <= f_hi)
    if sel.sum() == 0:
        return _result("REJECT_INTEGRITY", metrics=metrics,
                       reasons=["评价频带 %g-%g Hz 内没有频点" % (f_lo, f_hi)],
                       next={"kind": "redo_capture"})
    gated_ratio = float(np.mean(coh[sel] >= COHERENCE_FLOOR))
    coh_power = float(np.sum(coh[sel] * syy[sel]))
    incoh_power = float(np.sum((1.0 - coh[sel]) * syy[sel]))
    snr_db = float(10.0 * np.log10((coh_power + 1e-30) / (incoh_power + 1e-30)))
    metrics["coherence_median"] = float(np.median(coh[sel]))
    metrics["coherence_gated_ratio"] = gated_ratio
    metrics["coherence_band_hz"] = [f_lo, f_hi]
    metrics["excitation_snr_db"] = snr_db
    metrics["mic_coherent_power_db"] = float(10 * np.log10(coh_power + 1e-30))
    metrics["mic_incoherent_power_db"] = float(10 * np.log10(incoh_power + 1e-30))

    if snr_db < MIN_EXCITATION_SNR_DB:
        return _result("REJECT_EXCITATION", metrics=metrics,
                       reasons=["麦克风功率里只有 %.1f dB 能被参考解释（< %.1f）："
                                "激励没进来，或进来的不是这一路参考"
                                % (snr_db, MIN_EXCITATION_SNR_DB)],
                       next={"kind": "raise_excitation",
                             "why": "先确认音响在响、参考与麦克风同源，再谈电平"})
    if gated_ratio < MIN_GATED_COHERENCE:
        return _result("REJECT_COHERENCE", metrics=metrics,
                       reasons=["相干>=%.1f 的 bin 只占 %.1f%%（< %.0f%%）"
                                % (COHERENCE_FLOOR, 100 * gated_ratio, 100 * MIN_GATED_COHERENCE)],
                       next={"kind": "raise_excitation",
                             "why": "相干不足可能是电平，也可能是房间/摆位"})

    return _result("OK", metrics=metrics, reasons=[],
                   next={"kind": "fit", "why": "可以进入拟合"})


# ---------------------------------------------------------------- 激励规划（有界重试）

def plan_excitation(capture_check, attempt, reference_rms_dbfs=-19.3, peak_cap=PEAK_CAP,
                    frames=16384, seed=4242):
    """给定采集判定与已试次数，决定下一次激励动作。有界，不会无限提电平。

    关键约束（本轮明确写死）：不看"环环比开环高 3 dB"。环路提升是结果，
    不是激励够不够的条件。激励够不够只看 check_capture 的 SNR 与相干，
    以及输入余量是否还允许再加。

    attempt: 已经失败的次数（0 表示还没重试过）。
    """
    status = capture_check.get("status")
    if status == "OK":
        return _result("NO_ACTION", action={"kind": "fit"}, attempt=int(attempt))

    if attempt >= MAX_ATTEMPTS:
        return _result("EXHAUSTED",
                       reasons=["已重试 %d 次仍未通过采集资格，停止提电平" % attempt],
                       action={"kind": "stop", "escalate": "HARDWARE_ERROR_OR_FIXTURE"},
                       attempt=int(attempt))

    next_hint = (capture_check.get("next") or {}).get("kind")
    if status in ("REJECT_INTEGRITY", "REJECT_REFERENCE"):
        return _result("NO_ACTION",
                       reasons=["这类失败改电平无效，必须重采或修数据"],
                       action={"kind": "stop", "escalate": "DATA_INSUFFICIENT"},
                       attempt=int(attempt))
    if status == "REJECT_CLIP":
        return _result("NO_ACTION",
                       reasons=["输入已满幅，提高激励只会更糟"],
                       action={"kind": "lower_input_gain", "why": "先收 AUX/输入增益"},
                       attempt=int(attempt))
    if next_hint != "raise_excitation":
        return _result("NO_ACTION", action={"kind": "stop", "escalate": "UNKNOWN"},
                       reasons=["未定义的动作"], attempt=int(attempt))

    # 目标：在当前基础上抬一档，但不超过可达上限
    ladder = [lv for lv in EXCITATION_LADDER_DBFS]
    current = float(capture_check["metrics"].get("ref_rms_dbfs", reference_rms_dbfs))
    targets = [lv for lv in ladder if lv > current + 1e-9]
    if not targets:
        return _result("EXCITATION_CEILING",
                       reasons=["已到阶梯顶端 %+.1f dBFS" % ladder[-1]],
                       action={"kind": "stop", "escalate": "EXCITATION_NOT_ACTIONABLE"},
                       attempt=int(attempt))
    target = targets[0]
    stim = make_excitation(target, frames, seed=seed, peak_cap=peak_cap)
    if not stim["reachable"]:
        return _result("EXCITATION_CEILING",
                       reasons=["目标 %+.1f dBFS 超过该 seed 在不削顶时的上限 %+.1f dBFS；"
                                "继续提峰值只会削顶或把档位压成同一序列"
                                % (target, stim["ceiling_dbfs"])],
                       action={"kind": "stop", "escalate": "EXCITATION_NOT_ACTIONABLE"},
                       ceiling_dbfs=stim["ceiling_dbfs"], attempt=int(attempt))
    return _result("RAISE_EXCITATION",
                   action={"kind": "raise_excitation",
                           "target_rms_dbfs": float(target),
                           "achieved_rms_dbfs": stim["achieved_rms_dbfs"],
                           "peak": stim["peak"], "sha256": stim["sha256"],
                           "frames": int(frames)},
                   reasons=["当前 ref_rms %+.1f dBFS，抬到 %+.1f dBFS（实际达成 %+.1f）"
                            % (current, target, stim["achieved_rms_dbfs"])],
                   attempt=int(attempt))


# ---------------------------------------------------------------- 选点（不用 cancel）

def select_probe_frequencies(H, freqs, coherence, gain_db, f_lo=150.0, f_hi=10000.0,
                             n_probe=3, min_sep_oct=1.0 / 3.0, coherence_floor=COHERENCE_FLOOR):
    """按开环数据固定选点，与 cancel 完全无关。

    规则：候选 = 相干达标且落在频带内的 bin；按 g|H| 降序；贪心取互相间隔
    >= 1/3 倍频程的点；最多 n_probe 个。若可用点少于 n_probe，返回能给的，
    由调用方决定是否 INCONCLUSIVE。

    为什么不按"cancel 哪个点好看"选：那是用结果挑证据。这里只用开环 H 与增益，
    它在装模型之前就已经确定，装完不能再改。
    """
    H = np.asarray(H, dtype=complex)
    freqs = np.asarray(freqs, dtype=float)
    coh = np.asarray(coherence, dtype=float)
    if H.shape != freqs.shape or coh.shape != freqs.shape:
        raise ValueError("H / freqs / coherence 形状必须一致")
    g = 10.0 ** (float(gain_db) / 20.0)
    sel = (freqs >= f_lo) & (freqs <= f_hi) & (coh >= coherence_floor) & (np.abs(H) > 0)
    idx = np.flatnonzero(sel)
    if idx.size == 0:
        return []
    loop_db = 20.0 * np.log10(g * np.abs(H[idx]) + 1e-30)
    order = idx[np.argsort(-loop_db)]
    out = []
    for i in order:
        f0 = freqs[i]
        if any(abs(np.log2(f0 / p["frequency_hz"])) < min_sep_oct for p in out):
            continue
        out.append({
            "frequency_hz": float(f0),
            "bin": int(i),
            "loop_gain_db": float(20.0 * np.log10(g * abs(H[i]) + 1e-30)),
            "magnitude_h_db": float(20.0 * np.log10(abs(H[i]) + 1e-30)),
            "coherence": float(coh[i]),
        })
        if len(out) >= n_probe:
            break
    return out


# ---------------------------------------------------------------- 模型可部署性

def q20_sha256(values):
    arr = np.asarray([int(v) for v in values], dtype=np.int64).astype("<i4")
    return hashlib.sha256(arr.tobytes()).hexdigest()


def check_fit(coefficients_q20, sample_rate_hz, lag_first=1, taps=512,
              expected_peak_tap=None, gain_db=-8.0, probe_hz=None, H_at_probe=None,
              base_peak_tap=None):
    """判拟合出的模型能不能装。不缩放、不修补，只给结论与理由。

    两类拒绝必须分开，因为处置不同：
      REJECT_SCALE  形状像、整体尺度错（L1/max 仍在历史范围）-> 查输入电平/单位
      REJECT_SHAPE  L1 与 L1/max 同时异常          -> 拟合病态，查激励与方程数

    expected_peak_tap 的口径（2026-11-01 修正）：
      它必须是**本轮开环采集实测的 ref→mic 整数延迟**（`estimate_lag` 给的值），
      不是上一个部署模型的抽头峰位。换摆位就是这个流程的正常用法，峰位本来就会变：
      50 cm 侧放实测 127/128、100 cm 侧对实测 183/184，差 56 帧全是声程。
      拿旧模型的峰位当基准，会把一次正确的重标定判成"换错了布置"。
      `base_peak_tap` 只是旧名，等价于 expected_peak_tap，保留是为了不破坏既有调用。
    """
    q = np.asarray(coefficients_q20, dtype=np.int64)
    h = q.astype(float) / (1 << 20)
    l1 = float(np.abs(h).sum())
    peak = float(np.abs(h).max())
    l1_over_max = l1 / peak if peak > 0 else float("inf")
    peak_tap = int(np.argmax(np.abs(h))) + 1        # 1-indexed，lag_first=1 时等于实际滞后

    metrics = {
        "taps": int(len(q)),
        "requested_taps": int(taps),
        "L1": l1,
        "max_abs": peak,
        "L1_over_max": float(l1_over_max),
        "peak_tap": peak_tap,
        "q20_min": int(q.min()),
        "q20_max": int(q.max()),
        "q20_in_range": bool(q.min() >= -(1 << 23) and q.max() < (1 << 23)),
        "q20_sha256": q20_sha256(q),
        "lag_first": int(lag_first),
        "sample_rate_hz": float(sample_rate_hz),
        "memory_ms": 1000.0 * len(q) / float(sample_rate_hz),
    }
    reasons = []

    if len(q) != int(taps):
        metrics["hardware_cycles"] = None
        return _result("REJECT_SHAPE", metrics=metrics,
                       reasons=["抽头数 %d 与部署位流 %d 不符" % (len(q), taps)],
                       next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED"})
    metrics["hardware_cycles"] = 3 * len(q) + 3
    if metrics["hardware_cycles"] > 2048:
        return _result("REJECT_SHAPE", metrics=metrics,
                       reasons=["3N+3 = %d 拍超过帧预算 2048" % metrics["hardware_cycles"]],
                       next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED"})
    if not metrics["q20_in_range"]:
        return _result("REJECT_SCALE", metrics=metrics,
                       reasons=["Q20 超出有符号 24 位：min=%d max=%d" % (q.min(), q.max())],
                       next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED"})

    # 物理上界：任何稳定 FIR 都有 L1 >= max|H|
    if probe_hz is not None and H_at_probe is not None:
        f = np.asarray(probe_hz, dtype=float)
        k = np.arange(len(h))
        Hm = np.array([np.sum(h * np.exp(-1j * 2 * np.pi * fi * (k + 1) / (float(sample_rate_hz))))
                       for fi in f])
        metrics["H_at_probe_db"] = [float(v) for v in _db(np.abs(Hm))]
        if np.max(np.abs(Hm)) > l1 * 1.001:
            return _result("REJECT_SHAPE", metrics=metrics,
                           reasons=["模型在探针频点的 |H| 超过 L1 上界，数值自相矛盾"],
                           next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED"})

    if base_peak_tap is not None and expected_peak_tap is None:
        expected_peak_tap = base_peak_tap          # 旧名兼容
    if expected_peak_tap is not None:
        delta = int(peak_tap - int(expected_peak_tap))
        metrics["expected_peak_tap"] = int(expected_peak_tap)
        metrics["peak_tap_delta"] = delta
        if abs(delta) > PEAK_TAP_TOLERANCE:
            reasons.append("抽头峰位 %d 与本轮实测延迟 %d 差 %+d 帧（> %d）："
                           "拟合的时间原点与本轮采集不一致，不是换摆位的问题"
                           % (peak_tap, int(expected_peak_tap), delta, PEAK_TAP_TOLERANCE))
            return _result("REJECT_SHAPE", metrics=metrics, reasons=reasons,
                           next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED",
                                 "hint": "先确认对齐用的是本轮 estimate_lag，而不是上一批的坐标"})

    if l1 > L1_MAX:
        shape_ok = L1_OVER_MAX_RANGE[0] <= l1_over_max <= L1_OVER_MAX_RANGE[1]
        reasons.append("L1 = %.3f > %.1f（部署模型 2.288、历史同类 2.15）" % (l1, L1_MAX))
        if shape_ok:
            reasons.append("L1/max = %.1f 仍在历史范围 %s，属整体尺度偏大"
                           % (l1_over_max, L1_OVER_MAX_RANGE))
            return _result("REJECT_SCALE", metrics=metrics, reasons=reasons,
                           next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED",
                                 "hint": "查 reference 的实际 RMS 与单位，不要对系数做缩放"})
        reasons.append("L1/max = %.1f 超出历史范围 %s，属拟合病态"
                       % (l1_over_max, L1_OVER_MAX_RANGE))
        return _result("REJECT_SHAPE", metrics=metrics, reasons=reasons,
                       next={"kind": "stop", "escalate": "MODEL_UNQUALIFIED",
                             "hint": "查激励是否宽带、方程数是否足够、互相关峰是否可用"})

    if l1_over_max < L1_OVER_MAX_RANGE[0]:
        # 房间更"干"时 L1/max 本来就会小（能量集中在少数抽头上），这是正常形态，
        # 不能当拒绝理由，只标出来让调用方看见。
        metrics["note"] = ("L1/max = %.1f 低于历史范围下限 %.0f：能量集中在少数抽头上，"
                           "更干的房间会有这种形态，不据此拒收" % (l1_over_max, L1_OVER_MAX_RANGE[0]))

    return _result("DEPLOYABLE_FIT", metrics=metrics, reasons=[],
                   next={"kind": "install_and_verify"})


# ---------------------------------------------------------------- 三点验证

def check_three_point(points, gain_db=None, h_complex=None, hhat_complex=None,
                      saturation_counts=None, source_sha=None):
    """三点验证。points 是每个预选频点的三臂读数（dB），由选点规则在装模型之前定好。

    points: [{"frequency_hz": f, "open_db": a, "bypass_db": b, "cancel_db": c,
              "cd_db": optional, "coherence": optional}, ...]

    判定顺序（先排除"这个测量根本不能用"，再谈"抵消有没有效"）：
      1 硬件：三臂饱和计数非零 -> HARDWARE_ERROR
      2 同源：三臂 source 序列身份不一致 -> MEASUREMENT_INAPPLICABLE
      3 该点有没有可收回的环路提升：boost < BOOST_MIN_DB -> 该点 INAPPLICABLE
      4 抵消有效性：acoustic >= 0 且 over >= OVER_MIN_DB -> 该点 PASS
      5 若给了复 H：实测 over 与预测 over 差 > 1.5 dB -> MEASUREMENT_INCONSISTENT

    "322 Hz 负环路提升"落在第 3 条：那里没有可收回的东西，判 INAPPLICABLE，
    既不算成功也不算失败。这也是"不能看到 cancel 哪个点好看才选它"的另一半。
    """
    counts = dict(saturation_counts or {})
    bad_sat = {k: v for k, v in counts.items() if isinstance(v, (int, float)) and v}
    if bad_sat:
        return _result("FAIL", cause="HARDWARE_ERROR",
                       reasons=["饱和计数非零：%s" % bad_sat], points=[])

    shas = None
    if source_sha is not None:
        shas = {source_sha} if isinstance(source_sha, str) else set(source_sha)
        if len(shas) > 1:
            return _result("INCONCLUSIVE", cause="MEASUREMENT_INAPPLICABLE",
                           reasons=["三臂 source 序列身份不一致（%d 个不同 sha256），"
                                    "电平不同就不能相减" % len(shas)], points=[])

    g = None if gain_db is None else 10.0 ** (float(gain_db) / 20.0)
    rows = []
    for p in points:
        f0 = float(p["frequency_hz"])
        o, b, c = float(p["open_db"]), float(p["bypass_db"]), float(p["cancel_db"])
        boost = b - o
        over = o - c
        acoustic = b - c
        row = {"frequency_hz": f0, "open_db": o, "bypass_db": b, "cancel_db": c,
               "boost_db": boost, "overshoot_db": over, "acoustic_db": acoustic,
               "cd_db": p.get("cd_db"), "coherence": p.get("coherence"),
               "status": None, "why": None}
        if boost < BOOST_MIN_DB:
            row["status"] = "INAPPLICABLE"
            row["why"] = ("环路提升 %+.2f dB < %.2f：这个频点本来就没有可收回的增益，"
                          "不能拿它判成败" % (boost, BOOST_MIN_DB))
        elif acoustic < ACOUSTIC_MIN_DB:
            row["status"] = "FAIL"
            row["why"] = ("抵消臂比零臂还响 %.2f dB：残留误差仍在正反馈方向上"
                          % (-acoustic))
        elif over < OVER_MIN_DB:
            row["status"] = "FAIL"
            row["why"] = ("抵消臂比无环路臂响 %.2f dB（过冲下界 %.1f），"
                          "属于欠抵消引入的正反馈" % (-over, OVER_MIN_DB))
        else:
            row["status"] = "PASS"
            row["why"] = ("收回 %+.2f dB，过冲 %+.2f dB" % (acoustic, over))
        rows.append(row)

    # 复 H 存在时，把"模型装错了"与"测量不可比"分开
    if g is not None and h_complex is not None and hhat_complex is not None:
        for row in rows:
            if row["status"] == "INAPPLICABLE":
                continue
            f0 = row["frequency_hz"]
            H = complex(h_complex(f0) if callable(h_complex) else h_complex)
            Hh = complex(hhat_complex(f0) if callable(hhat_complex) else hhat_complex)
            pred = float(-20.0 * np.log10(abs(1.0 - g * (H - Hh)) + 1e-30))
            row["over_pred_db"] = pred
            row["over_pred_gap_db"] = row["overshoot_db"] - pred
            if abs(row["over_pred_gap_db"]) > OVER_PRED_TOLERANCE_DB:
                row["status"] = "INCONCLUSIVE"
                row["why"] = ("实测过冲 %+.2f dB 与离线预测 %+.2f dB 差 %+.2f dB（> %.1f），"
                              "三臂不是同一组条件或模型与数据不同源"
                              % (row["overshoot_db"], pred, row["over_pred_gap_db"],
                                 OVER_PRED_TOLERANCE_DB))

    passing = [r for r in rows if r["status"] == "PASS"]
    failing = [r for r in rows if r["status"] == "FAIL"]
    unknown = [r for r in rows if r["status"] == "INCONCLUSIVE"]

    if failing:
        return _result("FAIL", cause="MODEL_UNQUALIFIED", points=rows,
                       reasons=[r["why"] for r in failing])
    if unknown:
        return _result("INCONCLUSIVE", cause="MEASUREMENT_INAPPLICABLE", points=rows,
                       reasons=[r["why"] for r in unknown] + 
                               ["无法区分是模型不合格还是测量不适用，不据此宣布抵消失败"])
    if len(passing) < MIN_PASSING_PROBES:
        inapl = [r for r in rows if r["status"] == "INAPPLICABLE"]
        if inapl and not passing:
            return _result("INCONCLUSIVE", cause="MEASUREMENT_INAPPLICABLE", points=rows,
                           reasons=["%d 个预选频点全部没有可收回的环路提升（boost < %.1f dB）："
                                    "这套布置在该频段本来就没有可抑制的反馈，"
                                    "既不能宣布抵消失败，也不能宣布成功"
                                    % (len(inapl), BOOST_MIN_DB)])
        return _result("INCONCLUSIVE", cause="DATA_INSUFFICIENT", points=rows,
                       reasons=["可判的频点只有 %d 个（< %d）" % (len(passing), MIN_PASSING_PROBES)])
    return _result("PASS", cause=None, points=rows,
                   reasons=["%d/%d 个预选频点收回环路提升且未引入正反馈"
                            % (len(passing), len(rows))])


def _already_computed(value):
    """判定结果本身也带 status，不能再当参数喂回判定函数。

    结果里有 metrics（采集/拟合）或 points（三点），原始输入没有。
    """
    return (isinstance(value, dict) and "status" in value
            and ("metrics" in value or "points" in value))


def decide(capture=None, attempt=0, fit=None, three_point=None,
           require_three_point=True, **kw):
    """一次调用的汇总入口：按 采集 -> 拟合 -> 验证 的顺序给出第一个阻断项。

    每个子判定都可以只给一部分；缺的那步标 NOT_RUN，不会被当成通过。

    require_three_point（默认 True）：没有三点验证就不返回 READY_TO_INSTALL。
    采集合格 + 模型可部署只说明"这份数据能拟合、这个模型装得进去"，
    不说明"抵消有效"；缺验证时必须是 INCONCLUSIVE，不能自动装。
    只有调用方明确传 False（例如只做离线检查）才允许在这种情况下返回可安装。
    """
    out = {"schema_version": SCHEMA_VERSION, "steps": {}}
    if capture is not None:
        c = capture if _already_computed(capture) else check_capture(**capture)
        out["steps"]["capture"] = c
        if c["status"] != "OK":
            out["decision"] = plan_excitation(c, attempt, **(kw.get("plan") or {}))
            out["blocked_at"] = "capture"
            return out
    else:
        out["steps"]["capture"] = {"status": "NOT_RUN"}
    if fit is not None:
        f = fit if _already_computed(fit) else check_fit(**fit)
        out["steps"]["fit"] = f
        if f["status"] != "DEPLOYABLE_FIT":
            out["decision"] = f
            out["blocked_at"] = "fit"
            return out
    else:
        out["steps"]["fit"] = {"status": "NOT_RUN"}
    if three_point is not None:
        v = (three_point if _already_computed(three_point)
             else check_three_point(**three_point))
        out["steps"]["three_point"] = v
        if v["status"] != "PASS":
            out["decision"] = v
            out["blocked_at"] = "three_point"
            return out
    else:
        out["steps"]["three_point"] = {"status": "NOT_RUN"}
        if require_three_point:
            out["blocked_at"] = "three_point"
            out["decision"] = _result(
                "INCONCLUSIVE", cause="DATA_INSUFFICIENT",
                reasons=["采集合格、模型可部署都不等于抵消有效；"
                         "没有三点验证数据就不自动安装"])
            return out
    out["blocked_at"] = None
    out["decision"] = {"status": "READY_TO_INSTALL",
                       "reasons": ["采集、拟合、验证三步都给了可用结论"]}
    return out
