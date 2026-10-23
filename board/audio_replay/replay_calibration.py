"""Causal open-loop identification in full-scale units (interface v1)."""
from dataclasses import dataclass
# 阅读主线：load_capture → fit_path(训练) → evaluate_path(独立验证) → export_model。
# 本文件只处理数组和文件，不控制板卡，也没有实现实时闭环抵消。
import json
from pathlib import Path

import numpy as np


@dataclass
class Capture:
    # reference是实际DAC参考，microphone是同帧ADC左声道，单位均为满幅=1。
    reference: np.ndarray
    microphone: np.ndarray
    sample_rate_hz: float
    metadata: dict

    def validate(self):
        # 只能检查数据和记录字段；无法替代现场确认箱体、接线、模拟增益未变。
        for name in ("reference", "microphone"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.ndim != 1 or not len(value) or not np.isfinite(value).all():
                raise ValueError(name + " must be finite, nonempty and one-dimensional")
            if np.any(value <= -1) or np.any(value >= 1 - 2**-23):
                # 拒绝24位PCM两端满幅码；没有这些码也不能排除模拟端削顶。
                raise ValueError(name + " contains full-scale/clipped samples")
            setattr(self, name, value)
        if len(self.reference) != len(self.microphone):
            raise ValueError("reference and microphone lengths differ")
        if not np.isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0:
            raise ValueError("invalid sample rate")
        m = self.metadata
        if m.get("schema_version") != 1 or not isinstance(m.get("capture_id"), str) or not m["capture_id"]:
            raise ValueError("missing schema version / capture ID")
        if m.get("source") not in ("synthetic", "board"):
            raise ValueError("capture source must be declared")
        if m.get("forward_path_open") is not True or m.get("alignment") != "same_i2s_frame":
            raise ValueError("requires open forward path and aligned frame pairs")
        if m.get("dropped_frames") != 0:
            raise ValueError("capture has missing or unknown frame count")
        if m["source"] == "board" and (not m.get("fixture_id") or "hp_volume" not in m):
            raise ValueError("board capture needs fixture identity and Codec gain")
        return self


def load_capture(path):
    # NPZ内只读取数组和JSON字符串，禁止pickle对象反序列化。
    with np.load(path, allow_pickle=False) as data:
        capture = Capture(data["reference"], data["microphone"],
                          float(data["sample_rate_hz"].item()),
                          json.loads(str(data["metadata_json"].item())))
    return capture.validate()


def save_capture(path, capture):
    # 通用助手不防覆盖；现场采集脚本另用独占创建保护已有数据。
    capture.validate()
    np.savez_compressed(path, reference=capture.reference,
                        microphone=capture.microphone,
                        sample_rate_hz=capture.sample_rate_hz,
                        metadata_json=json.dumps(capture.metadata))


def history_matrix(reference, taps):
    """Row for n=taps onward: [u[n-1], ..., u[n-taps]]."""
    if not 1 <= taps <= 1024 or len(reference) <= taps:
        raise ValueError("taps must be 1..1024 and shorter than capture")
    # 反转每行使第0列为最近历史；去掉最后一行以匹配microphone[taps:]。
    # 例：taps=2时首行[u[1], u[0]]对应要预测的microphone[2]。
    return np.lib.stride_tricks.sliding_window_view(reference, taps)[:-1, ::-1]


def fit_path(capture, taps=256, ridge=1e-6):
    # 求解y[n] ≈ bias + Σh[k]u[n-1-k]；taps是历史长度，不是整块处理延迟。
    capture.validate()
    if not np.isfinite(ridge) or ridge < 0:
        raise ValueError("ridge must be nonnegative and finite")
    x = history_matrix(capture.reference, taps)
    y = capture.microphone[taps:]
    if len(y) < 4 * taps:
        raise ValueError("need at least four fitted rows per tap")
    # Fit an intercept separately so DC cannot masquerade as path gain.
    xm, ym = x.mean(axis=0), float(y.mean())
    # 输入每列及目标分别去均值，避免把ADC直流偏置拟合成反馈路径。
    xc, yc = x - xm, y - ym
    covariance = xc.T @ xc / len(y)
    eigenvalues = np.linalg.eigvalsh(covariance)
    # 激励必须覆盖足够多的独立方向；单个纯音无法辨识任意多抽头路径。
    largest = float(eigenvalues[-1])
    if largest <= 1e-14 or eigenvalues[0] <= largest * 1e-8:
        raise ValueError("reference lacks broadband excitation (zero/tone/ill-conditioned)")
    scale = float(np.trace(covariance) / taps)
    # 正则项随平均参考能量缩放，ridge描述相对强度；用solve求解而非显式求逆。
    coefficients = np.linalg.solve(covariance + ridge * scale * np.eye(taps),
                                   xc.T @ yc / len(y))
    return {"schema_version": 1, "sample_rate_hz": capture.sample_rate_hz,
            "lag_first": 1, "taps": taps, "coefficients": coefficients.tolist(),
            "bias": float(ym - xm @ coefficients), "ridge": ridge,
            "condition_number": float(largest / eigenvalues[0]),
            "training_capture_id": capture.metadata["capture_id"],
            "training_source": capture.metadata["source"],
            "fixture_id": capture.metadata.get("fixture_id"),
            "hp_volume": capture.metadata.get("hp_volume")}


def predict(reference, coefficients):
    # 在系数前补0，显式引入一帧因果延迟；结果截取为与参考等长。
    h = np.asarray(coefficients, dtype=np.float64)
    if h.ndim != 1 or not len(h) or not np.isfinite(h).all():
        raise ValueError("invalid coefficients")
    return np.convolve(np.asarray(reference, dtype=np.float64), np.r_[0.0, h])[:len(reference)]


def evaluate_path(model, capture, training=None):
    capture.validate()
    if model["lag_first"] != 1 or model["taps"] != len(model["coefficients"]):
        raise ValueError("unsupported model indexing")
    if capture.sample_rate_hz != model["sample_rate_hz"]:
        raise ValueError("sample rates differ")
    if capture.metadata["source"] != model["training_source"]:
        raise ValueError("training and validation sources differ")
    if model["training_source"] == "board":
        for key in ("fixture_id", "hp_volume"):
            if capture.metadata[key] != model[key]:
                raise ValueError("board capture configuration differs: " + key)
    if capture.metadata["capture_id"] == model["training_capture_id"]:
        raise ValueError("validation capture must be independent of training")
    if training is not None and np.array_equal(training.reference, capture.reference):
        raise ValueError("validation reference repeats training sequence")
    n = model["taps"]
    # 不在验证数据重新调bias；跳过起始历史不完整的区间，再计算预测误差。
    if len(capture.reference) <= n:
        raise ValueError("validation too short")
    target = capture.microphone[n:] - model["bias"]
    prediction = predict(capture.reference, model["coefficients"])[n:]
    residual = target - prediction
    # 这是离线预测残差。RMS比值不能直接作为闭环稳定增益ASG。
    target_rms = float(np.sqrt(np.mean(target**2)))
    error_rms = float(np.sqrt(np.mean(residual**2)))
    if target_rms < 1e-12:
        raise ValueError("validation target has no measurable energy")
    return {"validation_capture_id": capture.metadata["capture_id"],
            "validation_source": capture.metadata["source"],
            "evaluated_frames": len(target), "target_rms": target_rms,
            "residual_rms": error_rms,
            "prediction_reduction_db": float(20 * np.log10(target_rms / max(error_rms, 1e-15))),
            "interpretation": "open-loop prediction only; not ASG or closed-loop stability"}


def quantize_coefficients(coefficients):
    # 有符号24位、20位小数：1.0编码为2^20，系数可表示范围[-8,8)。
    h = np.asarray(coefficients, dtype=np.float64)
    if h.ndim != 1 or not 1 <= len(h) <= 1024 or not np.isfinite(h).all():
        raise ValueError("invalid coefficient vector")
    scaled = h * (1 << 20)
    rounded = np.sign(scaled) * np.floor(np.abs(scaled) + 0.5)
    # 半值远离零，区别于numpy.round的半值取偶数；越界报错，不裁剪系数。
    if np.any(rounded < -(1 << 23)) or np.any(rounded > (1 << 23) - 1):
        raise ValueError("coefficient outside signed24/20 fractional-bit range")
    return rounded.astype(np.int64)


def fixed_fir(reference_pcm, coefficients_q20):
    """Bit-exact causal reference; Python ints avoid silent int64 wraparound."""
    u, h = list(reference_pcm), list(coefficients_q20)
    if not 1 <= len(h) <= 1024:
        raise ValueError("invalid tap count")
    for values in (u, h):
        if any(not isinstance(v, (int, np.integer)) or not -(1 << 23) <= int(v) < (1 << 23) for v in values):
            raise ValueError("expected signed24 integers")
    result, saturations = [], 0
    for n in range(len(u)):
        # Python整数累加避免溢出；适合RTL对照，不追求实时运行速度。
        # h[0]乘u[n-1]；启动时不存在的历史按0处理，不使用当前u[n]。
        acc = sum(int(h[k]) * int(u[n - 1 - k]) for k in range(min(n, len(h))))
        # 乘积有20位小数：绝对值加半LSB后右移，再恢复符号。
        magnitude = (abs(acc) + (1 << 19)) >> 20
        rounded = -magnitude if acc < 0 else magnitude
        clipped = max(-(1 << 23), min((1 << 23) - 1, rounded))
        # 饱和到24位PCM，单独计数；保护动作不能当作抵消收益。
        saturations += clipped != rounded
        result.append(clipped)
    return np.asarray(result, dtype=np.int32), saturations


def export_model(path, model, validation):
    # 保存浮点/Q20系数和候选标记；不加载FPGA，调用者负责避免覆盖已有文件。
    q = quantize_coefficients(model["coefficients"])
    artifact = {**model, "validation": validation,
                "coefficient_format": "signed24_fraction20",
                "coefficients_q20": q.tolist(),
                "status": "offline_candidate_not_board_validated"}
    Path(path).write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
