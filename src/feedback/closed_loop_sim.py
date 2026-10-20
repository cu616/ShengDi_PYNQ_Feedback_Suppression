"""闭环参考模拟：逐帧复刻 audio_pl_closed 的调度与定点行为。

为什么必须逐帧写：
- 顶层是 played[n+2] = gain(residual[n])，这 2 帧延迟直接决定起振频率与相位，
  换成"整体卷积"就会把环路延迟算错，得出的起振增益不可信。
- 增益是 Q4.12、半值远离零舍入、再饱和到 24 位；残差相减也饱和到 24 位。
  这些非线性会改变大信号下的行为，不能用浮点乘加代替。

用法：
- simulate(...) 跑一段，给出会不会发散、增长多快、饱和多少次；
- find_msg(...) 用二分法找数字增益的起振阈值，可与
  path_analysis.stability_summary 的理论值 max|H_eff| 对照。

边界：这是数值模拟，不是实测 MSG。声学路径用实数冲激响应近似，
不包含模拟电路的失真、温漂和箱体移动。
"""
import numpy as np

FULL_SCALE = 1 << 23
MAX_CODE = (1 << 23) - 1
MIN_CODE = -(1 << 23)
SCHEDULE_DELAY_FRAMES = 2
DEFAULT_TAPS = 256


def _round_half_away(values):
    """半值远离零，与 RTL 的 (|acc| + 2^19) >> 20 口径一致。"""
    values = np.asarray(values, dtype=np.float64)
    return np.where(values >= 0, np.floor(values + 0.5), -np.floor(-values + 0.5))


def _clip_signed(values, bits=FULL_SCALE):
    """饱和到 24 位补码区间，返回 (裁剪后, 是否发生饱和)。"""
    high = bits - 1
    low = -bits
    clipped = np.clip(values, low, high)
    return clipped, np.any(clipped != values)


def _gain_q12(residual, gain_q12):
    """Q4.12 增益：整数乘法、半值远离零、24 位饱和。"""
    product = np.asarray(residual, dtype=np.int64) * np.int64(gain_q12)
    magnitude = np.abs(product)
    rounded = (magnitude + (1 << 11)) >> 12
    signed = np.where(product < 0, -rounded, rounded)
    return _clip_signed(signed)


def simulate(room, source, coefficients_q20, gain_q12, bypass=False,
             frames=None, dither_q=1, taps=None, block=512, keep_signal=False):
    """跑一段闭环，返回统计量。room 是"已播放数据→麦克风"的实数冲激响应。

    参数
    ----
    room : 声学路径冲激响应（满幅为 1），长度即路径覆盖的帧数。
    source : 外部声源/底噪，长度为 frames。这是闭环能够"被激发起来"的原因，
             没有它，零初值加零舍入的环路会永远保持 0，测不出任何东西。
    coefficients_q20 : 24 位、20 位小数的系数，语义同 RTL。
    gain_q12 : 数字增益，4096 = 1.0。
    """
    room = np.asarray(room, dtype=np.float64)
    source = np.asarray(source, dtype=np.float64)
    h = np.asarray(coefficients_q20, dtype=np.int64)
    if room.ndim != 1 or not len(room):
        raise ValueError("room must be a non-empty 1-D impulse response")
    if h.ndim != 1 or not len(h):
        raise ValueError("invalid coefficient vector")
    if frames is None:
        frames = len(source)
    if len(source) < frames:
        raise ValueError("source shorter than frames")
    taps = int(taps if taps is not None else len(h))
    if taps > len(h):
        raise ValueError("taps exceeds coefficient count")
    if gain_q12 <= 0 or gain_q12 > 32768:
        raise ValueError("gain_q12 out of the RTL allowed range 1..32768")

    played = np.zeros(frames + SCHEDULE_DELAY_FRAMES + 1, dtype=np.int64)
    residual_hist = np.zeros(frames, dtype=np.int64)
    mic_hist = np.zeros(frames, dtype=np.int64)
    prediction_saturations = 0
    residual_saturations = 0
    gain_saturations = 0
    room_len = len(room)

    for n in range(frames):
        # --- 麦克风：已播放数据经过声学路径，叠加外部声源
        # room 作用在 24 位码值上（增益无量纲），source 是满幅=1 的实际声压信号。
        down = min(room_len, n + 1)
        window = played[n - down + 1:n + 1][::-1]
        mic_code = int(_round_half_away(float(np.dot(room[:down], window))))
        mic_code += int(_round_half_away(float(source[n]) * FULL_SCALE)) + int(dither_q)
        mic_code = max(MIN_CODE, min(MAX_CODE, mic_code))

        # --- 预测：只用到 n-1 及更早的已播放数据，与 RTL 的前一帧因果一致
        upto = min(taps, n)
        if upto:
            history = played[n - upto:n][::-1]
            acc = int(np.dot(h[:upto], history))
        else:
            acc = 0
        magnitude = (abs(acc) + (1 << 19)) >> 20
        pred = -magnitude if acc < 0 else magnitude
        if pred > MAX_CODE or pred < MIN_CODE:
            prediction_saturations += 1
        pred = max(MIN_CODE, min(MAX_CODE, pred))

        # --- 残差：旁路时原样输出麦克风
        if bypass:
            residual = mic_code
        else:
            delta = mic_code - pred
            if delta > MAX_CODE or delta < MIN_CODE:
                residual_saturations += 1
            residual = max(MIN_CODE, min(MAX_CODE, delta))

        # --- 增益并调度到 2 帧之后
        gained, clipped = _gain_q12(residual, gain_q12)
        if clipped:
            gain_saturations += 1
        played[n + SCHEDULE_DELAY_FRAMES] = int(gained)
        residual_hist[n] = residual
        mic_hist[n] = mic_code

    # 只看后半段的增长趋势：前半段还在建立滤波历史。
    level = np.abs(residual_hist.astype(np.float64)) / FULL_SCALE
    usable = level[frames // 4:]
    blocks = len(usable) // block
    block_db = []
    for index in range(blocks):
        chunk = usable[index * block:(index + 1) * block]
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        block_db.append(20.0 * np.log10(max(rms, 1e-12)))
    block_db = np.asarray(block_db)
    slope = 0.0
    if len(block_db) >= 2:
        fit = np.polyfit(np.arange(len(block_db)) * block / frames, block_db, 1)
        slope = float(fit[0])  # dB 每 1 倍总时长
    final_rms_db = float(block_db[-1]) if len(block_db) else -999.0
    peak_code = int(np.max(np.abs(played)))
    saturated_frames = int(prediction_saturations + residual_saturations + gain_saturations)

    # 判据：饱和已经发生，或电平在明显指数增长（>6 dB 每整段）。
    diverged = bool(saturated_frames > 0 or slope > 6.0)
    result = {
        "frames": int(frames),
        "bypass": bool(bypass),
        "gain_q12": int(gain_q12),
        "gain_db": float(20.0 * np.log10(gain_q12 / 4096.0)),
        "final_residual_dbfs": final_rms_db,
        "growth_db_per_run": slope,
        "peak_code": peak_code,
        "prediction_saturations": int(prediction_saturations),
        "residual_saturations": int(residual_saturations),
        "gain_saturations": int(gain_saturations),
        "saturated_frames": saturated_frames,
        "diverged": diverged,
    }
    if keep_signal:
        result["residual"] = residual_hist
        result["played"] = played[:frames]
        result["block_db"] = block_db.tolist()
    return result


def find_msg(room, coefficients_q20, bypass=False, low_db=-40.0, high_db=30.0,
             tolerance_db=0.5, frames=8192, seed=1, dither_q=1, source_db=-60.0):
    """二分找起振增益阈值（dB，相对 1.0 倍）。

    激励用一段低电平噪声；电平取得足够低，保证在阈值以下不会因源信号太大
    而误判为发散。返回的阈值应与 1/max|H_eff| 同量级，两者不一致就说明
    模型或模拟有一处错了，先查清楚再用于现场建议。
    """
    rng = np.random.default_rng(seed)
    amplitude = 10.0 ** (source_db / 20.0)
    source = rng.standard_normal(frames) * amplitude
    coeffs = np.asarray(coefficients_q20, dtype=np.int64)

    def verdict(gain_db):
        gain_q12 = int(round(4096.0 * 10.0 ** (gain_db / 20.0)))
        gain_q12 = max(1, min(32768, gain_q12))
        stats = simulate(room, source, coeffs, gain_q12, bypass=bypass,
                         frames=frames, dither_q=dither_q)
        return stats["diverged"], stats

    low_stats = verdict(low_db)[1]
    if low_stats["diverged"]:
        raise ValueError("loop already diverges at the lowest probe gain; check room scale")
    if not verdict(high_db)[0]:
        raise ValueError("loop stable even at the highest probe gain; widen the search")
    low, high = low_db, high_db
    while high - low > tolerance_db:
        mid = 0.5 * (low + high)
        if verdict(mid)[0]:
            high = mid
        else:
            low = mid
    threshold_stats = verdict(high)[1]
    return {
        "msg_db": float(low),
        "diverges_at_db": float(high),
        "bypass": bool(bypass),
        "frames": int(frames),
        "source_dbfs": float(source_db),
        "tolerance_db": float(tolerance_db),
        "growth_at_threshold_db_per_run": threshold_stats["growth_db_per_run"],
        "saturations_at_threshold": threshold_stats["saturated_frames"],
        "interpretation": "numerical closed-loop simulation; not a measured MSG",
    }
