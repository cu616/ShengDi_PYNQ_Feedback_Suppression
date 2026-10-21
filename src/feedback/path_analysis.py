"""频域抵消深度与稳定增益估算（分析 v1）。

本模块只回答三个问题，全部基于已有标定数据，不需要重新录音、不需要发声：

1. 每个频点上"抵消之后还剩多少"：CD(f) = |H(f)-Ĥ(f)| / |H(f)|。
   宽带 RMS 降低 9.8 dB 是整段平均，啸叫却只发生在一个频点上，
   所以必须逐频点看，不能拿平均数当结论。
2. 这点余量被什么限制：用相干函数估出噪声地板，
   区分"算法不够好"和"数据里本来就没有那么多信息"。
3. 旁路和抵消各自的起振增益与 ASG：

       u = G·z^-2·(H - Ĥ)·u + 源   ⇒   稳定条件 |G·(H-Ĥ)| < 1
       MSG_bypass = 1 / max|H|,     MSG_cancel = 1 / max|H-Ĥ|
       ASG        = MSG_cancel / MSG_bypass = max|H| / max|H-Ĥ|

   z^-2 是顶层的播放调度延迟（played[n+2] = gain(residual[n])），
   它参与相位判据，但旁路和抵消都一样，所以不影响 ASG 比值。

结论边界：
- 本模块输出的是"模型预测的稳定性估算"，不是实测 MSG/ASG。
- H 的估计只在相干函数高的频点可信；低于地板的频点单独标记。
- 所有结果都绑定当次 fixture 与 Codec 音量：H 随 hp_volume 线性缩放，
  换音量后 MSG 要按 dB 平移，不能直接沿用。
"""
import numpy as np

try:  # 包内使用（本地测试、脚本）；板上是扁平目录，走下面的回退。
    from .calibration import evaluate_path, fit_path
except ImportError:  # pragma: no cover - 板上 Jupyter 的扁平导入路径
    from calibration import evaluate_path, fit_path

FRAME_BUDGET_CYCLES = 2048

FULL_SCALE = 1 << 23
# 播放调度延迟：顶层在 divider==2047 才装载 u_hold，串行器下一帧才送出，
# 接口文档记录为 played[n+2] = gain(residual[n])。
SCHEDULE_DELAY_FRAMES = 2


# ---------------------------------------------------------------- 频谱估计

def welch_cross(reference, microphone, fs, nperseg=4096, overlap=0.5):
    """分段平均的互谱估计，返回 (freqs, S_uu, S_um, S_mm)。

    用 Hann 窗 + 50% 重叠。S_um = E[conj(U)·M]，因此 H1 估计为 S_um/S_uu。
    只做算术，不假设激励是白噪声；激励谱形由 S_uu 自己带着。
    """
    u = np.asarray(reference, dtype=np.float64)
    m = np.asarray(microphone, dtype=np.float64)
    if u.ndim != 1 or u.shape != m.shape:
        raise ValueError("reference and microphone must be equal 1-D arrays")
    if not (np.isfinite(u).all() and np.isfinite(m).all()):
        raise ValueError("non-finite capture")
    if not 0 < overlap < 1:
        raise ValueError("overlap must be in (0,1)")
    if nperseg < 64 or nperseg > len(u):
        raise ValueError("nperseg must be 64..len(capture)")
    hop = max(1, int(round(nperseg * (1.0 - overlap))))
    window = np.hanning(nperseg)
    scale = 1.0 / float(window @ window)
    count = 1 + (len(u) - nperseg) // hop
    if count < 2:
        raise ValueError("capture too short for the requested segment count")
    nfreq = nperseg // 2 + 1
    acc_uu = np.zeros(nfreq, dtype=np.complex128)
    acc_um = np.zeros(nfreq, dtype=np.complex128)
    acc_mm = np.zeros(nfreq, dtype=np.complex128)
    for index in range(count):
        start = index * hop
        seg_u = u[start:start + nperseg] * window
        seg_m = m[start:start + nperseg] * window
        spec_u = np.fft.rfft(seg_u)
        spec_m = np.fft.rfft(seg_m)
        acc_uu += np.conj(spec_u) * spec_u
        acc_um += np.conj(spec_u) * spec_m
        acc_mm += np.conj(spec_m) * spec_m
    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    factor = scale / count
    return freqs, acc_uu.real * factor, acc_um * factor, acc_mm.real * factor


def coherence_from_spectra(S_uu, S_um, S_mm):
    """γ²(f) = |S_um|² / (S_uu·S_mm)，0..1。接近 1 表示 H 估得住。"""
    denom = S_uu * S_mm
    out = np.zeros_like(denom, dtype=np.float64)
    good = denom > 0
    out[good] = np.abs(S_um[good]) ** 2 / denom[good]
    return np.clip(out, 0.0, 1.0)


def noise_ceiling_db(coh):
    """相干函数给出的逐频点误差地板（dB，正值代表最多能降多少）。

    把麦克风信号看成"可被参考解释的部分 + 与参考无关的部分"，
    两者功率比就是 γ²/(1-γ²)。任何线性模型都无法消除与参考无关的成分，
    所以这是"完美模型"在该频点上能达到的抵消上限。
    """
    c = np.clip(np.asarray(coh, dtype=np.float64), 0.0, 1.0 - 1e-12)
    ratio = c / np.maximum(1.0 - c, 1e-12)
    return 10.0 * np.log10(np.maximum(ratio, 1e-12))


def estimate_path(reference, microphone, fs, nperseg=4096, overlap=0.5):
    """估计真实反馈路径 H(f)，返回 dict（无板卡、无 IO）。"""
    freqs, S_uu, S_um, S_mm = welch_cross(reference, microphone, fs, nperseg, overlap)
    H = np.zeros_like(S_um)
    good = S_uu > 0
    H[good] = S_um[good] / S_uu[good]
    coh = coherence_from_spectra(S_uu, S_um, S_mm)
    return {
        "freqs": freqs,
        "H": H,
        "S_uu": S_uu,
        "coherence": coh,
        "noise_ceiling_db": noise_ceiling_db(coh),
    }


# ---------------------------------------------------------------- 模型响应

def fir_response(coefficients, fs, freqs):
    """模型 Ĥ(f) = e^{-jω}·Σ_k h[k]·e^{-jωk}，ω = 2πf/fs。

    与 RTL 的 pred[n] = Σ h[k]·u[n-1-k] 逐项对应，因此多一个 z^-1。
    """
    h = np.asarray(coefficients, dtype=np.float64)
    if h.ndim != 1 or not len(h):
        raise ValueError("invalid coefficients")
    freqs = np.asarray(freqs, dtype=np.float64)
    omega = 2.0 * np.pi * freqs / fs
    taps = np.arange(len(h))
    # (nfreq, taps) 的复指数矩阵；256 抽头 × 数千频点仍在内存内。
    phase = np.exp(-1j * np.outer(omega, taps + 1.0))
    return phase @ h


def band_slice(freqs, low_hz=20.0, high_hz=None, fs=None):
    """取分析频带。下界默认 20 Hz：再往下 Codec 交流耦合，且标定数据分辨不出。

    注意：不要为了"看起来干净"把下界抬到 60 Hz 以上。
    合成验证里出现过 DC 环路增益 > 1 直接把低频推起来的例子；
    真实系统里对应的是残余直流偏置被环路反复放大（RTL 不减 bias），
    所以低频段必须单列出来看，不能直接排除。
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    high = high_hz
    if high is None:
        high = 0.45 * (fs if fs else 2.0 * freqs[-1])
    return (freqs >= low_hz) & (freqs <= min(high, freqs[-1]))


def dc_diagnostics(microphone, H, freqs, coherence=None, gate=0.5):
    """直流/低频诊断：环路里最容易先失控、也最容易被忽略的一段。

    - bias_dbfs：麦克风信号的直流分量。RTL 不减 bias，残差会带着它进环路。
    - dc_gain：|H| 在 20 Hz 以下的峰值。若它乘上数字增益 ≥ 1，
      低频会先漂起来（表现为逐渐变响的闷响或彻底跑偏，不是尖锐啸叫）。
    """
    mic = np.asarray(microphone, dtype=np.float64)
    freqs = np.asarray(freqs, dtype=np.float64)
    mag = np.abs(np.asarray(H, dtype=np.complex128))
    low = freqs < 20.0
    dc_gain = float(mag[low].max()) if low.any() else float(mag[0])
    peak_freq = float(freqs[low][np.argmax(mag[low])]) if low.any() else float(freqs[0])
    bias = float(np.mean(mic))
    # 低频段相干往往极低（真实箱体 50 Hz 只有 0.07），那里的 |H| 是噪声，
    # 不能拿去报"多少 dB 起振"。相干不够就明确标未知，不给假数字。
    usable = True
    trust = ''
    if coherence is not None:
        low_coh = float(np.median(np.asarray(coherence)[low])) if low.any() else 0.0
        if low_coh < gate:
            usable = False
            trust = ("20 Hz 以下相干仅 %.2f，H 估不出来，这一段的增益与起振点不予给出；"
                     "真实系统该频段由 Codec 交流耦合阻挡" % low_coh)
    return {
        "bias_dbfs": float(20.0 * np.log10(max(abs(bias), 1e-12))),
        "dc_gain_below_20hz": dc_gain if usable else None,
        "dc_gain_at_hz": peak_freq if usable else None,
        "dc_gain_to_howl_db": (float(-20.0 * np.log10(max(dc_gain, 1e-12)))
                               if usable else None),
        "dc_gain_note": trust or "低频相干足够，数值可用",
    }


# ---------------------------------------------------------------- 抵消深度

def cancellation_depth_db(H, H_hat, floor=1e-12):
    """20·log10(|H| / |H-Ĥ|)：正值表示该频点被压下去的 dB 数。"""
    H = np.asarray(H, dtype=np.complex128)
    H_hat = np.asarray(H_hat, dtype=np.complex128)
    if H.shape != H_hat.shape:
        raise ValueError("H and H_hat must have the same shape")
    residual = np.abs(H - H_hat)
    return 20.0 * np.log10(np.maximum(np.abs(H), floor) / np.maximum(residual, floor))


# ---------------------------------------------------------------- 起振判据

def phase_zero_points(freqs, loop_response):
    """找 loop_response 相位穿过 0（模 2π）的频点。

    闭环起振要求 ∠[G·z^-2·(H-Ĥ)] = 0 (mod 2π)；G 是正实数，
    所以只需看 ∠[z^-2·(H-Ĥ)]。这里只做离散栅格上的线性插值，
    栅格分辨不了的更窄共振需要在真实数据上再确认。
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    phi = np.angle(loop_response)
    # 还原到主值区间后检查相邻两点符号变化；跨越 ±π 的跳变不算过零。
    crossings = []
    for index in range(len(phi) - 1):
        a, b = phi[index], phi[index + 1]
        if a == 0.0:
            crossings.append((index, freqs[index]))
            continue
        if np.sign(a) == np.sign(b):
            continue
        if abs(a - b) > np.pi:  # 这是 ±π 的环绕，不是零点
            continue
        frac = abs(a) / (abs(a) + abs(b))
        crossings.append((index, freqs[index] + frac * (freqs[index + 1] - freqs[index])))
    return crossings


def howl_candidates(freqs, H, H_hat, fs, schedule_delay=SCHEDULE_DELAY_FRAMES,
                    band=None, top=5):
    """按"最容易先啸叫"排序的频点表。

    判据是两条同时满足：相位过零（能自持），且 |H-Ĥ| 最大（增益最先撞线）。
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    loop = np.exp(-1j * 2.0 * np.pi * freqs * schedule_delay / fs) * (H - H_hat)
    crossings = phase_zero_points(freqs, loop)
    rows = []
    for index, f_zero in crossings:
        if band is not None and not band[index]:
            continue
        rows.append({
            "frequency_hz": float(f_zero),
            "abs_H_eff": float(np.abs(loop[index])),
            "gain_to_howl_db": float(-20.0 * np.log10(max(np.abs(loop[index]), 1e-12))),
        })
    rows.sort(key=lambda row: row["abs_H_eff"], reverse=True)
    return rows[:top]


def resonances(freqs, H, band=None, top=5):
    """|H| 的局部极大值（共振峰）：这里才是最先起振的地方。"""
    mag = np.abs(np.asarray(H, dtype=np.complex128))
    freqs = np.asarray(freqs, dtype=np.float64)
    rows = []
    for index in range(1, len(mag) - 1):
        if band is not None and not band[index]:
            continue
        if mag[index] >= mag[index - 1] and mag[index] > mag[index + 1]:
            rows.append({"frequency_hz": float(freqs[index]), "abs_H": float(mag[index]),
                         "gain_to_howl_db": float(-20.0 * np.log10(max(mag[index], 1e-12)))})
    rows.sort(key=lambda row: row["abs_H"], reverse=True)
    return rows[:top]


def stability_summary(freqs, H, H_hat, band, fs, schedule_delay=SCHEDULE_DELAY_FRAMES, floor=1e-12):
    """旁路/抵消的起振增益与 ASG，保守口径和相位口径都给。

    - conservative：整个频带上取 max|L|，再取倒数。这是充分条件，
      一定不会高估能用的增益，但可能低估得比较多（最坏的 |L| 未必满足相位）。
    - phase_gated：只在相位过零的频点上取 max|L|。这是线性系统真正的起振点，
      也是现场实际会先叫的频率；但它依赖 H 的估计精度，不能当作实测结论。

    两个数差很多时，说明最坏的 |H_eff| 落在相位不允许的频点上；
    现场必须用保守口径当上限，否则要么推不响、要么直接炸。
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    mag_H = np.abs(H)
    mag_eff = np.abs(H - H_hat)
    idx = np.where(band)[0]
    if not len(idx):
        raise ValueError("empty analysis band")
    peak_H = float(np.max(mag_H[idx]))
    peak_eff = float(np.max(mag_eff[idx]))
    worst_eff = int(idx[np.argmax(mag_eff[idx])])
    worst_H = int(idx[np.argmax(mag_H[idx])])

    loop = np.exp(-1j * 2.0 * np.pi * freqs * schedule_delay / fs) * (H - H_hat)
    loop_bypass = np.exp(-1j * 2.0 * np.pi * freqs * schedule_delay / fs) * H
    crossings = [(index, value) for index, value in phase_zero_points(freqs, loop)
                 if band[index]]
    crossings_bypass = [(index, value) for index, value in phase_zero_points(freqs, loop_bypass)
                        if band[index]]
    gated_eff = max((float(np.abs(loop[index])) for index, _ in crossings), default=float("inf"))
    gated_H = max((float(np.abs(loop_bypass[index])) for index, _ in crossings_bypass),
                  default=float("inf"))

    msg_bypass = 1.0 / max(peak_H, floor)
    msg_cancel = 1.0 / max(peak_eff, floor)
    return {
        "peak_abs_H": peak_H,
        "peak_abs_H_at_hz": float(freqs[worst_H]),
        "peak_abs_H_eff": peak_eff,
        "peak_abs_H_eff_at_hz": float(freqs[worst_eff]),
        "msg_bypass_conservative_db": float(20.0 * np.log10(msg_bypass)),
        "msg_cancel_conservative_db": float(20.0 * np.log10(msg_cancel)),
        "asg_conservative_db": float(20.0 * np.log10(msg_cancel / msg_bypass)),
        "msg_bypass_phase_gated_db": float(-20.0 * np.log10(max(gated_H, floor))),
        "msg_cancel_phase_gated_db": float(-20.0 * np.log10(max(gated_eff, floor))),
        "asg_phase_gated_db": float(20.0 * np.log10(max(gated_H, floor) / max(gated_eff, floor))),
        "phase_crossings_bypass": len(crossings_bypass),
        "phase_crossings_cancel": len(crossings),
        "interpretation": "predicted from model; not a measured MSG/ASG",
    }


def recommend_field_range(summary, margin_db=6.0, step_db=3.0):
    """把估算换成现场可执行的数字增益区间（dB，相对 PL 的 Q4.12 增益 1.0）。

    - 起点：旁路保守起振增益再退 margin_db，保证开机不会一上来就啸叫。
    - 终点：抵消相位口径的起振增益再退 2 dB（估算不含 H 的估计误差与箱体漂移）。
    - 硬件上限：Q4.12 增益最大 8 倍 = +18.06 dB，超过就没有意义。
    """
    start = summary["msg_bypass_conservative_db"] - margin_db
    stop = min(summary["msg_cancel_phase_gated_db"] - 2.0,
               summary["msg_cancel_conservative_db"], 18.06)
    if stop <= start:
        stop = start
    count = int(np.floor((stop - start) / step_db)) + 1
    # 对照点：刚好越过旁路起振阈值的位置。这一点上旁路应该叫、抵消应该安静，
    # 是同一增益下唯一能一眼看出差别的增益，比在 -36 dB 听一万次都值。
    contrast = min(summary["msg_bypass_conservative_db"] + 2.0, 18.06)
    return {
        "gain_db_start": float(start),
        "gain_db_stop": float(stop),
        "step_db": float(step_db),
        "suggested_points": [float(round(start + index * step_db, 2)) for index in range(max(count, 1))],
        "contrast_gain_db": float(contrast),
        "margin_db": float(margin_db),
        "hardware_gain_ceiling_db": 18.06,
        "assumes": "same fixture and same hp_volume as the fitted capture",
    }


# ---------------------------------------------------------------- 加权拟合

def emphasis_fir(magnitude, nfft=2048, length=65):
    """按给定幅频做线性相位预加重 FIR。

    做法：把目标幅频放到真实频率栅格上，irfft 得到零相位冲激响应，
    再搬移 (length-1)/2 拍变成因果，加 Hamming 窗截断。
    两端都乘同一个滤波器时，H = M/U 不变，所以拟合出的系数对原始数据依然成立——
    改的只是"误差在哪些频点上算数"，这正是我们要改的东西。
    """
    target = np.asarray(magnitude, dtype=np.float64)
    if target.ndim != 1 or not len(target) or not np.isfinite(target).all():
        raise ValueError("magnitude must be finite and 1-D")
    if length % 2 == 0 or length < 3:
        raise ValueError("length must be odd and >= 3")
    grid = min(nfft, 2 * (len(target) - 1))
    source = np.linspace(0.0, 1.0, len(target))
    dest = np.linspace(0.0, 1.0, grid // 2 + 1)
    resampled = np.interp(dest, source, target)
    resampled = np.maximum(resampled, 1e-6)
    full = np.concatenate([resampled, resampled[-2:0:-1]])
    impulse = np.fft.ifft(full).real
    half = (length - 1) // 2
    # 零相位响应中心在 0，取循环前后各 half 段拼成因果核。
    kernel = np.concatenate([impulse[-half:], impulse[:half + 1]])
    kernel *= np.hamming(length)
    norm = np.sqrt(np.sum(kernel ** 2))
    if norm <= 0:
        raise ValueError("degenerate emphasis filter")
    return kernel / norm


def fit_path_emphasized(capture, taps=256, gamma=1.0, nperseg=4096, ridge=1e-6, length=65):
    """按 |H|^gamma 加权的拟合：在容易啸叫的频段更准。

    与 fit_path 的唯一区别是拟合误差按频点加权。先估一次 H，
    用它构造预加重滤波器，再对参考/麦克风同时滤波后做普通最小二乘。
    输出的模型格式与 fit_path 完全一致，可直接交给现有 RTL 加载。
    """
    try:
        from .calibration import Capture
    except ImportError:  # pragma: no cover - 板上扁平导入
        from calibration import Capture

    capture.validate()
    probe = estimate_path(capture.reference, capture.microphone,
                          capture.sample_rate_hz, nperseg=nperseg)
    mag = np.abs(probe["H"])
    weight = np.maximum(mag, 1e-9) ** float(gamma)
    # 去掉整体尺度，避免预加重把信号推到数值上不好处理的范围。
    weight = weight / max(float(np.mean(weight)), 1e-15)
    kernel = emphasis_fir(weight, nfft=2048, length=length)
    filtered_reference = np.convolve(capture.reference, kernel, mode="same")
    filtered_microphone = np.convolve(capture.microphone, kernel, mode="same")
    # 预加重会把峰值推过满幅，触发 Capture 的削顶拒绝。两边同比例缩小，
    # H = M/U 不变，拟合结果不变，只是数值回到可表示的范围内。
    peak = max(float(np.max(np.abs(filtered_reference))),
               float(np.max(np.abs(filtered_microphone))), 1e-12)
    limit = 1.0 - 2.0 ** -23
    if peak > limit:
        scale = limit / peak
        filtered_reference = filtered_reference * scale
        filtered_microphone = filtered_microphone * scale
    shaped = Capture(filtered_reference, filtered_microphone,
                     capture.sample_rate_hz, dict(capture.metadata))
    model = fit_path(shaped, taps=taps, ridge=ridge)
    # 记录来源，便于报告区分"加权拟合"和基线。
    model["estimator"] = "frequency_emphasized"
    model["emphasis_gamma"] = float(gamma)
    model["training_capture_id"] = capture.metadata["capture_id"]
    return model


# ---------------------------------------------------------------- 汇总分析

def core_cycles(taps):
    """RTL 每抽头 3 拍 + 3 拍收尾，见 docs/interfaces/feedback-fir-v1.md。"""
    return 3 * int(taps) + 3


def load_model_artifact(path, q20_scale=1 << 20):
    """读候选系数 JSON，统一成 fit_path 的格式。

    兼容 `coefficients`（浮点）和 `coefficients_q20`（整数）两种写法；
    只补 taps，不改系数，不改任何既有字段。
    """
    import json
    from pathlib import Path

    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    coefficients = artifact.get("coefficients")
    if coefficients is None:
        if "coefficients_q20" not in artifact:
            raise ValueError("model file has neither coefficients nor coefficients_q20")
        coefficients = [float(v) / q20_scale for v in artifact["coefficients_q20"]]
    artifact["coefficients"] = [float(v) for v in coefficients]
    if not 1 <= len(artifact["coefficients"]) <= 1024:
        raise ValueError("invalid coefficient count")
    artifact.setdefault("taps", len(artifact["coefficients"]))
    if int(artifact["taps"]) != len(artifact["coefficients"]):
        raise ValueError("taps does not match coefficient count")
    return artifact


def score_model(estimate, model, band, fs, validation, training):
    """同一个模型在验证数据上的两套口径：宽带 RMS 和逐频点。"""
    H_hat = fir_response(model["coefficients"], fs, estimate["freqs"])
    cd = cancellation_depth_db(estimate["H"], H_hat)
    band_cd = cd[band]
    summary = stability_summary(estimate["freqs"], estimate["H"], H_hat, band, fs)
    worst = int(np.where(band)[0][np.argmin(band_cd)])
    block = {
        "broadband_reduction_db": float(evaluate_path(model, validation,
                                                      training)["prediction_reduction_db"]),
        "cd_median_db": float(np.median(band_cd)),
        "cd_min_db": float(np.min(band_cd)),
        "cd_min_at_hz": float(estimate["freqs"][worst]),
        "cd_p10_db": float(np.percentile(band_cd, 10)),
        "max_abs_coefficient": float(np.max(np.abs(model["coefficients"]))),
    }
    block.update(summary)
    return block, H_hat, cd


def _decimate(freqs, values, band, points):
    idx = np.where(band)[0]
    if len(idx) > points:
        idx = idx[np.linspace(0, len(idx) - 1, points).astype(int)]
    return [float(freqs[i]) for i in idx], [float(np.asarray(values)[i]) for i in idx]


def analyze_captures(training, validation, model, band_low=20.0, band_high=20000.0,
                     gamma=1.0, tap_list=(128, 256, 512), curve_points=160,
                     coherence_gate=0.8):
    """现有模型诊断 + 抽头扫描 + 加权候选，同训练/验证划分、同评价口径。

    全程只读数组：不加载 overlay、不播放、不写原始录音。
    训练集只用于拟合，验证集只用于评价；加权候选的 gamma 固定，不在验证集上调。

    coherence_gate 是必须的，不是可选项：相干低的地方 H 根本估不出来，
    把那些频点算进 max|H-Ĥ| 会得出"抵消深度为负"的假结论
    （2026-10-21 在真实箱体上就踩过：12 kHz 以上相干 0.05，把中位数拉到 0）。
    """
    if model["sample_rate_hz"] != validation.sample_rate_hz:
        raise ValueError("model and validation sample rates differ")
    if not 1 <= len(model["coefficients"]) <= 1024:
        raise ValueError("invalid coefficient vector")
    fs = validation.sample_rate_hz
    estimate = estimate_path(validation.reference, validation.microphone, fs)
    freqs = estimate["freqs"]
    band = band_slice(freqs, band_low, band_high, fs) & (estimate["coherence"] >= coherence_gate)
    if not band.any():
        raise ValueError("no frequency bin passes the coherence gate; lower it or "
                         "the capture has no usable band")

    shipped, shipped_hat, shipped_cd = score_model(estimate, model, band, fs,
                                                   validation, training)

    sweep = []
    for taps in tap_list:
        try:
            fitted = fit_path(training, taps=int(taps))
        except (ValueError, np.linalg.LinAlgError) as error:
            sweep.append({"taps": int(taps), "error": type(error).__name__ + ": " + str(error)})
            continue
        block, _, _ = score_model(estimate, fitted, band, fs, validation, training)
        block["taps"] = int(taps)
        block["core_cycles"] = core_cycles(taps)
        block["fits_frame_budget"] = core_cycles(taps) <= FRAME_BUDGET_CYCLES
        sweep.append(block)

    emphasis = None
    try:
        weighted = fit_path_emphasized(training, taps=int(model["taps"]), gamma=gamma)
        block, _, _ = score_model(estimate, weighted, band, fs, validation, training)
        block["estimator"] = "frequency_emphasized"
        block["gamma"] = float(gamma)
        try:
            from .calibration import quantize_coefficients
        except ImportError:  # pragma: no cover
            from calibration import quantize_coefficients
        block["coefficients_q20"] = [int(v) for v in
                                     quantize_coefficients(weighted["coefficients"])]
        emphasis = block
    except (ValueError, np.linalg.LinAlgError) as error:
        emphasis = {"error": type(error).__name__ + ": " + str(error)}

    curve_freqs, curve_cd = _decimate(freqs, shipped_cd, band, curve_points)
    return {
        "schema_version": 1,
        "fixture_id": validation.metadata.get("fixture_id"),
        "hp_volume": validation.metadata.get("hp_volume"),
        "sample_rate_hz": fs,
        "band_hz": [float(freqs[band][0]), float(freqs[band][-1])],
        "coherence_gate": float(coherence_gate),
        "bins_used": int(np.count_nonzero(band)),
        "band_note": "band_hz 是实际参与评价的频段：已按相干门控裁剪，"
                     "门控外的频点估不出 H，其结果无意义", 
        "training_capture_id": training.metadata["capture_id"],
        "validation_capture_id": validation.metadata["capture_id"],
        "shipped_model": {
            "taps": int(model["taps"]),
            "training_capture_id": model.get("training_capture_id"),
            "ridge": model.get("ridge"),
        },
        "estimator": {
            "method": "H1 (S_um/S_uu), Hann, 50% overlap",
            "nperseg": 4096,
            "median_coherence_in_band": float(np.median(estimate["coherence"][band])),
        },
        "dc": dc_diagnostics(validation.microphone, estimate["H"], freqs,
                             estimate["coherence"]),
        "shipped": shipped,
        "tap_sweep": sweep,
        "emphasis": emphasis,
        "resonances": resonances(freqs, estimate["H"], band, top=5),
        "howl_bypass": howl_candidates(freqs, estimate["H"],
                                       np.zeros_like(estimate["H"]), fs, band=band, top=5),
        "howl_cancel": howl_candidates(freqs, estimate["H"], shipped_hat, fs,
                                       band=band, top=5),
        "noise_ceiling": {
            "ceiling_median_db": float(np.median(estimate["noise_ceiling_db"][band])),
            "ceiling_p90_db": float(np.percentile(estimate["noise_ceiling_db"][band], 90)),
            "note": ("a perfect model cannot beat this: it is set by the part of the "
                     "mic signal that is not predictable from the reference"),
        },
        "curve": {"freqs": curve_freqs, "cd_shipped_db": curve_cd,
                  "coherence": _decimate(freqs, estimate["coherence"], band,
                                         curve_points)[1]},
        "recommendation": recommend_field_range(shipped),
        "interpretation": ("MODEL-BASED PREDICTION from the existing captures. "
                           "Not a measured MSG/ASG. H is estimated on the validation "
                           "capture; models are fitted on the training capture only."),
    }


def _line(block):
    return ("宽带 %6.2f dB | CD中位 %5.2f | CD最差 %6.2f @%6.0f Hz | "
            "MSG旁路 %6.2f..%6.2f | MSG抵消 %6.2f..%6.2f | ASG %6.2f/%6.2f dB"
            % (block["broadband_reduction_db"], block["cd_median_db"],
               block["cd_min_db"], block["cd_min_at_hz"],
               block["msg_bypass_conservative_db"], block["msg_bypass_phase_gated_db"],
               block["msg_cancel_conservative_db"], block["msg_cancel_phase_gated_db"],
               block["asg_conservative_db"], block["asg_phase_gated_db"]))


def report_lines(result):
    """统一的打印口径，本地和板上共用，避免两份表慢慢对不上。"""
    out = ["相干中位 %.3f  夹具 %s  音量 %s"
           % (result["estimator"]["median_coherence_in_band"], result["fixture_id"],
              result["hp_volume"]),
           "现有模型 %d 抽头: %s" % (result["shipped_model"]["taps"],
                                    _line(result["shipped"])),
           "抽头扫描（重新拟合，同一验证区间）:"]
    for row in result["tap_sweep"]:
        if "error" in row:
            out.append("  %4d 抽头 失败 %s" % (row["taps"], row["error"]))
            continue
        out.append("  %4d 抽头 周期%5d%s %s"
                   % (row["taps"], row["core_cycles"],
                      "" if row["fits_frame_budget"] else " 超出帧预算!",
                      _line(row)))
    emphasis = result.get("emphasis")
    if emphasis and "error" not in emphasis:
        out.append("加权候选 g=%.1f: %s" % (emphasis["gamma"], _line(emphasis)))
    elif emphasis:
        out.append("加权候选失败: %s" % emphasis["error"])
    dc = result["dc"]
    if dc.get("dc_gain_below_20hz") is None:
        out.append("直流: bias %.2f dBFS；20Hz 以下 %s"
                   % (dc["bias_dbfs"], dc.get("dc_gain_note", "不可用")))
    else:
        out.append("直流: bias %.2f dBFS, 20Hz以下 |H| %.3f -> %.1f dB 起振"
                   "（RTL 不减 bias）"
                   % (dc["bias_dbfs"], dc["dc_gain_below_20hz"],
                      dc["dc_gain_to_howl_db"]))
    rec = result["recommendation"]
    out.append("现场建议: 起点 %.1f dB, 终点 %.1f dB, 步进 %.1f, 点位 %s"
               % (rec["gain_db_start"], rec["gain_db_stop"], rec["step_db"],
                  rec["suggested_points"]))
    out.append("对照点: %.1f dB（旁路应有明显啸叫，抵消应保持安静）"
               % rec["contrast_gain_db"])
    return out
