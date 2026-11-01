"""B 侧数值判定：recal_algorithm.evaluate(request) 的真实实现。

契约：`docs/contracts/recal-product-v1.md`（C 定义，版本 recal-product-v1）。
纯数值：不 import PYNQ、不开音频设备、不写硬件、不读人声 PCM 以外的任何外部状态。
只依赖 numpy 与标准库——板上没有 `src/`，所以判据在本文件里**自包含**实现，
与 `src/feedback/recal_policy.py` 同源；两边由 `sim/feedback/test_recal_algorithm.py`
对拍（同一输入、同一结论），防止一份改了另一份忘改。

三个 phase：

  input     这份讲话输入检查的采集能不能用            -> valid_pass / data_insufficient / retry
  fit       用 training 捕获拟合 512 抽头，判能不能装  -> valid_pass（附 model_path/hash）/ retry / data_insufficient
  validate  用独立 validation 捕获判"够不够格做抵消"   -> valid_pass（附 evidence）/ data_insufficient

decision 只取契约允许的四个值：valid_pass / data_insufficient / model_rejected / retry。
`retry` 只在还有下一个 attempt 时给（由请求的 attempt 与 plan 里声明的 attempts 总数决定）。

明确不做：
  - 不把离线预测抑制输出成 MSG/ASG。evidence 里只有"残差深度/界差/预测抑制"，
    并显式写明 `not_asg`。
  - 不在 validate 里当"没有保护"就是通过：protected/削顶一律不算通过。
  - 不重用 training 的 capture_id 或 source_sha256 做 validation。

阈值出处与依据见 `docs/contracts/recalibration-algorithm-v1.md` §3。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

CONTRACT = 'recal-product-v1'
TAPS = 512
LAG_FIRST = 1
FS_DEFAULT = 48828.125

# ---------------------------------------------------------------- 阈值（与 src/feedback/recal_policy.py 同源）

MIN_VALID_FRAMES = 4096
NEAR_FULL_SCALE = 0.999
MIN_EXCITATION_SNR_DB = 0.0
MIN_GATED_COHERENCE = 0.30
COHERENCE_FLOOR = 0.8
SPARSE_LINE_DB = 20.0
BAND_HZ = (150.0, 10000.0)

L1_MAX = 4.0
L1_OVER_MAX_RANGE = (25.0, 80.0)
PEAK_TAP_TOLERANCE = 4

# 独立验证判据：**只用逐段时间域残差**，不用 Welch/CD/界差。
#
# 2026-11-01 校准（同一份数据，好模型=部署模型、坏模型=旧夹具模型、零模型=全零系数）：
#
#   指标          nperseg=2048   4096    8192   整段    结论
#   好模型 CD 中位    1.61       2.80    3.06   2.63   随口径漂 1.5 dB
#   好模型 界差       4.36       9.24    3.42   2.76   随口径漂 6.5 dB ← 不能当判据
#   好模型 时域抑制   1.02       1.02    1.02   1.02   与口径无关
#
# 换成带内（300–460 Hz）时间域抑制后梯度更大：
#   好模型 4.21 dB、旧夹具 −4.40 dB、零模型 0.00 dB。
# 所以判定用带内抑制，全带抑制只作"没有把别的频段搞坏"的附加条件。
BAND_LOW_HZ = (300.0, 460.0)
BAND_FULL_HZ = (150.0, 10000.0)
BAND_REDUCTION_MIN_DB = 0.5     # 好模型 3.5–4.9，旧夹具 −4.4，零模型 0
FULL_REDUCTION_MIN_DB = 0.0     # 好模型 2.2，旧夹具 −11.4
MIN_VALIDATION_CAPTURES = 2     # 单段不足以判"独立验证"

NFFT_VALIDATE = 8192            # 只用于 evidence 里的 CD/界差，不参与判定


def _db(x):
    return 20.0 * np.log10(np.asarray(x, dtype=float) + 1e-30)


def _rms_db(x):
    x = np.asarray(x, dtype=float)
    return float(20.0 * np.log10(np.sqrt(np.mean(x * x)) + 1e-30))


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _envelope(req):
    return {k: req.get(k) for k in ('contract', 'request_id', 'scene_id')}


def _reply(req, decision, reason, **extra):
    out = _envelope(req)
    out['decision'] = decision
    out['reason'] = reason
    out.update(extra)
    return out


# ---------------------------------------------------------------- 读捕获

def _as_float(x):
    a = np.asarray(x)
    if a.dtype.kind in 'iu':
        return a.astype(float) / 32768.0
    return a.astype(float)


def load_capture(entry):
    """读一份捕获，返回 dict(ref, mic, source, fs, metadata, capture_id, source_sha256)。

    支持两种落盘：npz（A 现有驱动的格式）与 json（hw_api 按本契约写的格式）。
    json 里 `reference`/`microphone` 必须是归一化到 ±1 的浮点数组；
    `source_pcm16` 可以是 int16 计数，也可以已经是 ±1。
    文件缺失或字段不全时抛 ValueError，由 evaluate 转成 data_insufficient。
    """
    path = Path(str(entry.get('path', '')))
    if not path.exists():
        raise ValueError('捕获文件不存在：%s' % path.name)
    if path.suffix.lower() == '.npz':
        cap = np.load(path, allow_pickle=True)
        if 'reference' not in cap.files or 'microphone' not in cap.files:
            raise ValueError('npz 缺 reference/microphone：%s' % path.name)
        ref = _as_float(cap['reference'])
        mic = _as_float(cap['microphone'])
        src = _as_float(cap['source_pcm16']) if 'source_pcm16' in cap.files else None
        fs = float(cap['sample_rate_hz']) if 'sample_rate_hz' in cap.files else FS_DEFAULT
        md = {}
        if 'metadata_json' in cap.files:
            try:
                md = json.loads(str(cap['metadata_json']))
            except Exception:
                md = {}
    else:
        raw = path.read_bytes()
        payload = json.loads(raw.decode('utf-8'))
        if 'reference' not in payload or 'microphone' not in payload:
            raise ValueError('json 缺 reference/microphone：%s（模拟夹具不是真实采集）' % path.name)
        ref = _as_float(payload['reference'])
        mic = _as_float(payload['microphone'])
        src = _as_float(payload['source_pcm16']) if 'source_pcm16' in payload else None
        fs = float(payload.get('sample_rate_hz', FS_DEFAULT))
        md = payload.get('metadata') or payload.get('metadata_json') or {}
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except Exception:
                md = {}
    return {
        'ref': ref, 'mic': mic, 'source': src, 'fs': fs, 'metadata': md,
        'capture_id': entry.get('capture_id'),
        'source_sha256': entry.get('source_sha256'),
        'first_frame': entry.get('first_frame'),
        'content_kind': entry.get('content_kind'),
    }


# ---------------------------------------------------------------- 复用的数值内核

def _band_coherence(ref, mic, fs, nperseg=4096):
    n = min(len(ref), len(mic))
    if n < 4 * nperseg:
        nperseg = max(256, n // 4)
    if n < nperseg or nperseg < 64:
        return np.array([0.0]), np.array([0.0]), np.array([0.0])
    step = max(1, nperseg // 2)
    win = np.hanning(nperseg + 1)[:nperseg]
    fr = np.lib.stride_tricks.sliding_window_view(ref[:n], nperseg)[::step]
    fm = np.lib.stride_tricks.sliding_window_view(mic[:n], nperseg)[::step]
    if fr.shape[0] == 0:
        return np.array([0.0]), np.array([0.0]), np.array([0.0])
    R = np.fft.rfft(fr * win, axis=1)
    M = np.fft.rfft(fm * win, axis=1)
    Sxx = np.mean(np.abs(R) ** 2, axis=0)
    Syy = np.mean(np.abs(M) ** 2, axis=0)
    Sxy = np.mean(M * np.conj(R), axis=0)
    coh = np.abs(Sxy) ** 2 / np.maximum(Sxx * Syy, 1e-30)
    return np.fft.rfftfreq(nperseg, 1.0 / fs), np.clip(coh, 0.0, 1.0), Syy


def _estimate_lag(u, m):
    n = len(u)
    R = np.fft.rfft(u, 2 * n)
    M = np.fft.rfft(m, 2 * n)
    cc = np.abs(np.fft.irfft(M * np.conj(R)))
    k = int(np.argmax(cc))
    return k - 2 * n if k > n else k


def _align_to(pairs, target):
    out = []
    for u, m, lag in pairs:
        shift = target - lag
        mm = np.concatenate([np.zeros(shift), m[:len(m) - shift]]) if shift else m
        out.append((u, mm))
    return out


def predict_stream(h, u):
    """y[n] = Σ h[k]·u[n−1−k]；前 taps 个样本无效（返回 nan）。"""
    conv = np.convolve(np.asarray(u, dtype=float), np.asarray(h, dtype=float))
    y = np.full(len(u), np.nan)
    y[1:] = conv[:len(u) - 1]
    return y


def _band_ratio(signal, residual, fs, lo, hi):
    """带内功率比 10log10(Σ|bp(signal)|² / Σ|bp(residual)|²)。

    带通用 rfft 掩码置零实现，不加窗——加了窗会改 RMS，让"抑制 dB"变成窗的函数。
    """
    n = len(signal)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    mask = (f >= lo) & (f < hi)

    def bp(x):
        X = np.fft.rfft(np.asarray(x, dtype=float))
        X[~mask] = 0.0
        return np.fft.irfft(X, n)

    return float(10.0 * np.log10(np.sum(bp(signal) ** 2) / (np.sum(bp(residual) ** 2) + 1e-30)))


def model_response(h, nfft=NFFT_VALIDATE, lag_first=LAG_FIRST):
    k = np.arange(len(h))
    f = np.fft.rfftfreq(nfft, 1.0 / FS_DEFAULT)
    return np.array([np.sum(h * np.exp(-1j * 2 * np.pi * fi * (k + lag_first) / FS_DEFAULT))
                     for fi in f])


def segment_gram(pairs, taps=TAPS, chunk=4096):
    G = np.zeros((taps, taps))
    b = np.zeros(taps)
    rows = 0
    for u, m in pairs:
        starts = np.arange(taps, len(u))
        for s in range(0, len(starts), chunk):
            blk = starts[s:s + chunk]
            X = u[blk[:, None] - 1 - np.arange(taps)[None, :]]
            G += X.T @ X
            b += X.T @ m[blk]
            rows += len(blk)
    return G, b, rows


def solve_ridge(G, b, ridge=1e-9):
    return np.linalg.solve(G + np.eye(len(b)) * np.trace(G) * ridge, b)


def quantize_q20(h):
    """有符号 24 位 / 20 位小数，半值远离零。"""
    q = np.where(h >= 0, np.floor(np.asarray(h, dtype=float) * (1 << 20) + 0.5),
                 np.ceil(np.asarray(h, dtype=float) * (1 << 20) - 0.5))
    return np.clip(q, -(1 << 23), (1 << 23) - 1).astype(np.int64)


# ---------------------------------------------------------------- input

def _check_capture(cap, source_expected=True):
    """返回 (ok, status, reasons, metrics)。与 src/feedback/recal_policy.check_capture 同口径。"""
    ref, mic, fs = cap['ref'], cap['mic'], cap['fs']
    md = cap['metadata'] or {}
    reasons, metrics = [], {'frames': int(len(ref)), 'sample_rate_hz': float(fs), 'taps': TAPS}

    if ref.ndim != 1 or mic.ndim != 1 or len(ref) != len(mic):
        reasons.append('reference/microphone 形状不一致')
    if not np.isfinite(ref).all() or not np.isfinite(mic).all():
        reasons.append('存在非有限值')
    if md.get('dropped_frames') not in (None, 0):
        reasons.append('dropped_frames=%s' % md.get('dropped_frames'))
    valid = int(min(len(ref), len(mic)))
    metrics['valid_frames'] = valid
    if valid < MIN_VALID_FRAMES:
        reasons.append('有效帧 %d < %d' % (valid, MIN_VALID_FRAMES))
    if reasons:
        return False, 'REJECT_INTEGRITY', reasons, metrics

    fs_marks = {
        'reference_near': int(np.sum(np.abs(ref) >= NEAR_FULL_SCALE)),
        'microphone_near': int(np.sum(np.abs(mic) >= NEAR_FULL_SCALE)),
        'bit22': md.get('input_overflow_bit22', md.get('bit22')),
    }
    metrics['fullscale'] = fs_marks
    metrics['ref_rms_dbfs'] = _rms_db(ref)
    metrics['mic_rms_dbfs'] = _rms_db(mic)
    metrics['mic_over_ref_db'] = metrics['mic_rms_dbfs'] - metrics['ref_rms_dbfs']
    if any(v for k, v in fs_marks.items() if k != 'bit22') or fs_marks['bit22'] == 1:
        return False, 'REJECT_CLIP', ['输入触及满幅：ref 近满幅 %d、mic 近满幅 %d、bit22=%s'
                                      % (fs_marks['reference_near'], fs_marks['microphone_near'],
                                         fs_marks['bit22'])], metrics

    if source_expected and cap['source'] is not None:
        src = cap['source']
        first = int(md.get('first_frame', cap['first_frame'] or 0) or 0)
        k = min(len(ref), len(src) - first)
        if k < MIN_VALID_FRAMES:
            return False, 'REJECT_REFERENCE', ['source 与窗口重叠不足（%d 帧）' % max(0, k)], metrics
        a, b = ref[:k], src[first:first + k]
        ratio = _rms_db(a) - _rms_db(b)
        corr = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else 0.0
        metrics['ref_vs_source_db'] = float(ratio)
        metrics['ref_vs_source_corr'] = float(corr)
        if abs(ratio) > 0.01 or corr < 0.9999:
            return False, 'REJECT_REFERENCE', [
                'reference 不是纯源（差 %+.3f dB，相关 %.6f）：反馈项可能仍在环内' % (ratio, corr)], metrics

    n = len(ref)
    spec = 20.0 * np.log10(np.abs(np.fft.rfft(ref * np.hanning(n))) + 1e-30)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    band = (f >= BAND_HZ[0]) & (f <= BAND_HZ[1])
    if band.sum() > 32:
        p50, p95 = np.percentile(spec[band], [50, 95])
        metrics['spectral_spread_db'] = float(p95 - p50)
        if p95 - p50 > SPARSE_LINE_DB:
            return False, 'REJECT_REFERENCE', [
                '激励不是宽带：谱 p95-p50 = %.1f dB（> %.1f），稀疏线会让延迟估计不可用'
                % (p95 - p50, SPARSE_LINE_DB)], metrics

    freqs, coh, syy = _band_coherence(ref, mic, fs)
    sel = (freqs >= BAND_HZ[0]) & (freqs <= BAND_HZ[1])
    if sel.sum() == 0:
        return False, 'REJECT_INTEGRITY', ['评价频带内没有频点'], metrics
    gated = float(np.mean(coh[sel] >= COHERENCE_FLOOR))
    coh_power = float(np.sum(coh[sel] * syy[sel]))
    incoh = float(np.sum((1.0 - coh[sel]) * syy[sel]))
    snr = float(10.0 * np.log10((coh_power + 1e-30) / (incoh + 1e-30)))
    metrics.update(coherence_median=float(np.median(coh[sel])),
                   coherence_gated_ratio=gated, excitation_snr_db=snr)
    if snr < MIN_EXCITATION_SNR_DB:
        return False, 'REJECT_EXCITATION', [
            '麦克风功率里只有 %.1f dB 能被参考解释（< %.1f）：激励没进来，或不是这一路参考'
            % (snr, MIN_EXCITATION_SNR_DB)], metrics
    if gated < MIN_GATED_COHERENCE:
        return False, 'REJECT_COHERENCE', [
            '相干>=%.1f 的 bin 只占 %.1f%%（< %.0f%%）'
            % (COHERENCE_FLOOR, 100 * gated, 100 * MIN_GATED_COHERENCE)], metrics
    return True, 'OK', [], metrics


# 能在"加一档激励或重采一次"后变得更好的失败；其余必须回硬件/数据
_RETRYABLE = {'REJECT_EXCITATION', 'REJECT_COHERENCE'}


def _phase_input(req):
    caps = [e for e in (req.get('input') or [])]
    if not caps:
        return _reply(req, 'data_insufficient', '请求里没有 input 捕获，无法判讲话输入')
    worst = None
    metrics = {}
    for entry in caps:
        try:
            cap = load_capture(entry)
        except ValueError as exc:
            return _reply(req, 'data_insufficient', str(exc))
        ok, status, reasons, m = _check_capture(cap, source_expected=False)
        metrics[entry.get('capture_id')] = m
        if not ok and worst is None:
            worst = (status, reasons)
    attempts_total = int(req.get('attempts_total') or 1)
    if worst is None:
        return _reply(req, 'valid_pass', '讲话输入检查：采样完整、未触满幅、参考合格',
                      evidence={'metrics': metrics})
    status, reasons = worst
    if status in _RETRYABLE and int(req.get('attempt') or 0) + 1 < attempts_total:
        return _reply(req, 'retry', reasons[0], evidence={'metrics': metrics})
    return _reply(req, 'data_insufficient', reasons[0], evidence={'metrics': metrics})


# ---------------------------------------------------------------- fit

def _check_fit(q, fs, expected_peak_tap=None):
    h = np.asarray(q, dtype=float) / (1 << 20)
    l1 = float(np.abs(h).sum())
    peak = float(np.abs(h).max())
    l1_over_max = l1 / peak if peak > 0 else float('inf')
    peak_tap = int(np.argmax(np.abs(h))) + LAG_FIRST
    metrics = {'taps': int(len(h)), 'L1': l1, 'max_abs': peak, 'L1_over_max': l1_over_max,
               'peak_tap': peak_tap, 'q20_sha256': _sha256_bytes(
                   np.asarray(q, dtype='<i4').tobytes()),
               'hardware_cycles': 3 * len(h) + 3,
               'memory_ms': 1000.0 * len(h) / float(fs)}
    if len(h) != TAPS:
        return False, 'REJECT_SHAPE', ['抽头数 %d 与部署位流 %d 不符' % (len(h), TAPS)], metrics
    if metrics['hardware_cycles'] > 2048:
        return False, 'REJECT_SHAPE', ['3N+3 超过帧预算 2048'], metrics
    if np.asarray(q).min() < -(1 << 23) or np.asarray(q).max() > (1 << 23) - 1:
        return False, 'REJECT_SCALE', ['Q20 超出有符号 24 位'], metrics
    if expected_peak_tap is not None:
        delta = int(peak_tap - int(expected_peak_tap))
        metrics['expected_peak_tap'] = int(expected_peak_tap)
        metrics['peak_tap_delta'] = delta
        if abs(delta) > PEAK_TAP_TOLERANCE:
            return False, 'REJECT_SHAPE', [
                '抽头峰位 %d 与本轮实测延迟 %d 差 %+d 帧（> %d）：拟合的时间原点与本轮采集不一致'
                % (peak_tap, int(expected_peak_tap), delta, PEAK_TAP_TOLERANCE)], metrics
    if l1 > L1_MAX:
        shape_ok = L1_OVER_MAX_RANGE[0] <= l1_over_max <= L1_OVER_MAX_RANGE[1]
        msg = 'L1 = %.3f > %.1f' % (l1, L1_MAX)
        if shape_ok:
            return False, 'REJECT_SCALE', [msg + '；L1/max = %.1f 在历史范围内，属整体尺度偏大'
                                           % l1_over_max], metrics
        return False, 'REJECT_SHAPE', [msg + '；L1/max = %.1f 超出历史范围，属拟合病态'
                                       % l1_over_max], metrics
    return True, 'DEPLOYABLE_FIT', [], metrics


def _common_valid_length(caps):
    """多份捕获的公共有效帧数：取 reference 长度与"源在窗口内的长度"的最小值。

    捕获尾部往往还有几百帧源已停、只剩底噪；把它们算进 H 会把残差拖向噪声底，
    CD 会凭空掉十几 dB（实测：不截断 2.93 dB，截断 11.81 dB）。这是已知口径错误。
    """
    n = min(len(c['ref']) for c in caps)
    for c in caps:
        if c['source'] is None:
            continue
        first = int((c['metadata'] or {}).get('first_frame', c['first_frame'] or 0) or 0)
        n = min(n, len(c['source']) - first)
    return int(n)


def _phase_fit(req):
    entries = req.get('training') or []
    if len(entries) < 2:
        return _reply(req, 'data_insufficient',
                      'training 捕获只有 %d 份，少于 2 份无法区分拟合与验证' % len(entries))
    caps = []
    for entry in entries:
        try:
            cap = load_capture(entry)
        except ValueError as exc:
            return _reply(req, 'data_insufficient', str(exc))
        ok, status, reasons, m = _check_capture(cap)
        if not ok:
            return _reply(req, 'data_insufficient', 'training 捕获不合格：' + reasons[0],
                          evidence={'capture_id': entry.get('capture_id'), 'status': status,
                                    'metrics': m})
        caps.append(cap)

    n = _common_valid_length(caps)
    if n < MIN_VALID_FRAMES:
        return _reply(req, 'data_insufficient', '六段共同有效帧只有 %d（< %d）' % (n, MIN_VALID_FRAMES))

    lags = [_estimate_lag(c['ref'][:n], c['mic'][:n]) for c in caps]
    expected = int(np.median(lags))
    aligned = []
    for c, lag in zip(caps, lags):
        shift = expected - lag
        mic = c['mic'][:n]
        if shift:
            mic = np.concatenate([np.zeros(shift), mic[:len(mic) - shift]])
        aligned.append((c['ref'][:n], mic))

    G, b, rows = segment_gram(aligned)
    if rows < TAPS:
        return _reply(req, 'data_insufficient', '拟合方程数 %d 少于抽头数 %d' % (rows, TAPS))
    h = solve_ridge(G, b)
    q = quantize_q20(h)
    ok, status, reasons, metrics = _check_fit(q, caps[0]['fs'], expected_peak_tap=expected)
    metrics.update(equation_rows=int(rows), integer_lags=[int(v) for v in lags],
                   expected_peak_tap=expected)
    if not ok:
        attempts_total = int(req.get('attempts_total') or 1)
        if status == 'REJECT_SCALE' and int(req.get('attempt') or 0) + 1 < attempts_total:
            return _reply(req, 'retry', reasons[0], evidence=metrics)
        return _reply(req, 'model_rejected', reasons[0], evidence=metrics)

    fs = float(caps[0]['fs'])
    hq = q.astype(float) / (1 << 20)
    model = {
        'schema_version': 1, 'sample_rate_hz': fs, 'lag_first': LAG_FIRST, 'taps': int(len(q)),
        'coefficient_format': 'signed24_fraction20',
        'coefficients_q20': [int(v) for v in q],
        'coefficients': [float(v) for v in hq],
        'bias': 0.0, 'ridge': 1e-9,
        'fixture_id': req.get('scene_id'),
        'training_source': 'board',
        'hp_volume': (req.get('identity') or {}).get('hp_volume'),
        'training_capture_id': [e.get('capture_id') for e in entries],
        'status': 'offline_candidate_not_board_validated',
    }
    out = Path(req['run_dir']) / 'candidate_model.json'
    text = json.dumps(model, indent=1, ensure_ascii=False) + '\n'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(text.encode('utf-8'))
    digest = _sha256_file(out)
    return _reply(req, 'valid_pass', '拟合后判据：L1 %.3f、峰位 %d 与实测延迟 %d 一致'
                  % (metrics['L1'], metrics['peak_tap'], expected),
                  model_path=str(out), model_sha256=digest,
                  evidence={'not_asg': True, 'metrics': metrics})


# ---------------------------------------------------------------- validate

def _identity_disjoint(training, validation):
    """独立验证：capture_id 与 source_sha256 都不能与 training 重叠。"""
    t_ids = {e.get('capture_id') for e in training if e.get('capture_id')}
    t_src = {e.get('source_sha256') for e in training if e.get('source_sha256')}
    dup_id = [e.get('capture_id') for e in validation if e.get('capture_id') in t_ids]
    dup_src = [e.get('capture_id') for e in validation if e.get('source_sha256') in t_src]
    return dup_id, dup_src


def _welch_complex(pairs, fs, nperseg=NFFT_VALIDATE):
    """把多段的交叉谱按段累加，得到一条 H 与相干。不跨段拼接。"""
    f = None
    num = den = syy = None
    for u, m in pairs:
        n = len(u)
        seg = min(nperseg, n)
        step = max(1, seg // 2)
        win = np.hanning(seg + 1)[:seg]
        fr = np.lib.stride_tricks.sliding_window_view(u, seg)[::step]
        fm = np.lib.stride_tricks.sliding_window_view(m, seg)[::step]
        R = np.fft.rfft(fr * win, axis=1)
        M = np.fft.rfft(fm * win, axis=1)
        a = np.mean(np.abs(R) ** 2, axis=0)
        c = np.mean(np.abs(M) ** 2, axis=0)
        x = np.mean(M * np.conj(R), axis=0)
        if num is None:
            num, den, syy = x, a, c
        else:
            num, den, syy = num + x, den + a, syy + c
        f = np.fft.rfftfreq(seg, 1.0 / fs)
    H = num / np.maximum(den, 1e-30)
    coh = np.abs(num) ** 2 / np.maximum(den * syy, 1e-30)
    return f, H, np.clip(coh, 0.0, 1.0)


def _phase_validate(req):
    entries = req.get('validation') or []
    training = req.get('training') or []
    model_path = req.get('model_path')
    model_sha = req.get('model_sha256')
    if not entries:
        return _reply(req, 'data_insufficient', '请求里没有 validation 捕获')
    if not model_path or not model_sha:
        return _reply(req, 'data_insufficient', '请求缺 model_path/model_sha256，无法判同一模型')
    p = Path(str(model_path))
    if not p.exists():
        return _reply(req, 'data_insufficient', '候选模型文件不存在：%s' % p.name)
    actual = _sha256_file(p)
    if actual != model_sha:
        return _reply(req, 'model_rejected', '候选模型哈希与请求不一致（%s… vs %s…）'
                      % (actual[:12], str(model_sha)[:12]))

    dup_id, dup_src = _identity_disjoint(training, entries)
    if dup_id or dup_src:
        return _reply(req, 'data_insufficient',
                      '验证集与训练集重叠（capture_id %s，source_sha256 %s）：不是独立验证'
                      % (dup_id[:1], dup_src[:1]))

    model = json.loads(p.read_text(encoding='utf-8'))
    q = model.get('coefficients_q20')
    if q is None:
        return _reply(req, 'model_rejected', '候选模型缺 coefficients_q20')
    h = np.asarray(q, dtype=float) / (1 << 20)

    caps, lags = [], []
    for entry in entries:
        try:
            cap = load_capture(entry)
        except ValueError as exc:
            return _reply(req, 'data_insufficient', str(exc))
        if (cap['metadata'] or {}).get('input_overflow_bit22') == 1 or (cap['metadata'] or {}).get('bit22') == 1:
            return _reply(req, 'data_insufficient', '验证捕获触发了输入满幅：不是"无保护"，但也不能当通过')
        caps.append(cap)
    n = _common_valid_length(caps)
    if n < MIN_VALID_FRAMES:
        return _reply(req, 'data_insufficient',
                      '验证集共同有效帧只有 %d（< %d）' % (n, MIN_VALID_FRAMES))
    for cap in caps:
        lags.append(_estimate_lag(cap['ref'][:n], cap['mic'][:n]))
    target = int(np.median(lags))
    pairs = []
    for cap, lag in zip(caps, lags):
        shift = target - lag
        mic = cap['mic'][:n]
        if shift:
            mic = np.concatenate([np.zeros(shift), mic[:len(mic) - shift]])
        pairs.append((cap['ref'][:n], mic))

    fs = float(caps[0]['fs'])
    bands = []
    for u, m in pairs:
        y = predict_stream(h, u)
        s = m[TAPS:]
        e = s - y[TAPS:]
        rec = {'reduction_db': _band_ratio(s, e, fs, *BAND_FULL_HZ),
               'band_reduction_db': _band_ratio(s, e, fs, *BAND_LOW_HZ)}
        bands.append(rec)
    band_med = float(np.median([b['band_reduction_db'] for b in bands]))
    full_med = float(np.median([b['reduction_db'] for b in bands]))
    band_min = float(min(b['band_reduction_db'] for b in bands))

    # CD / 界差：只写进 evidence 作旁证，不参与判定（口径相关，见顶部注释）
    cd_med = cd_p10 = bound_gain = None
    try:
        freqs, H, coh = _welch_complex(pairs, fs, NFFT_VALIDATE)
        Hh = np.array([np.sum(h * np.exp(-1j * 2 * np.pi * fi * (np.arange(len(h)) + LAG_FIRST) / fs))
                       for fi in freqs])
        gate = (coh >= COHERENCE_FLOOR) & (freqs >= BAND_FULL_HZ[0]) & (freqs <= BAND_FULL_HZ[1])
        if gate.sum() >= 32:
            E = np.abs(H - Hh)
            ratio = _db(np.abs(H[gate]) / np.maximum(E[gate], 1e-30))
            cd_med = float(np.median(ratio))
            cd_p10 = float(np.percentile(ratio, 10))
            bound_gain = float(-20 * np.log10(E[gate].max()) + 20 * np.log10(np.abs(H[gate]).max()))
    except Exception:                                     # noqa: BLE001
        pass

    evidence = {
        'not_asg': True,
        'policy': 'recalibration-algorithm-v1',
        'thresholds': {'band_reduction_min_db': BAND_REDUCTION_MIN_DB,
                       'full_reduction_min_db': FULL_REDUCTION_MIN_DB,
                       'band_hz': list(BAND_LOW_HZ)},
        'metrics': {'band_reduction_median_db': band_med,
                    'band_reduction_min_db': band_min,
                    'full_reduction_median_db': full_med,
                    'per_capture': [{'reduction_db': round(float(b['reduction_db']), 3),
                                     'band_reduction_db': round(float(b['band_reduction_db']), 3)}
                                    for b in bands],
                    'validation_lags': [int(v) for v in lags],
                    'cd_median_db_context_only': cd_med,
                    'cd_p10_db_context_only': cd_p10,
                    'bound_gain_db_context_only': bound_gain},
        'meaning': ('measured as held-out prediction residuals on independent captures; '
                    'these are prediction-suppression figures, NOT a gain-before-feedback '
                    '(MSG/ASG) and NOT a listening result'),
    }
    fails = []
    if band_min < 0.0:
        fails.append('至少一段在 %g–%g Hz 带内变差（最低 %+.2f dB）'
                     % (BAND_LOW_HZ[0], BAND_LOW_HZ[1], band_min))
    if band_med < BAND_REDUCTION_MIN_DB:
        fails.append('带内抑制中位 %+.2f dB < %.1f' % (band_med, BAND_REDUCTION_MIN_DB))
    if full_med < FULL_REDUCTION_MIN_DB:
        fails.append('全带抑制中位 %+.2f dB < %.1f（把别的频段搞差了）'
                     % (full_med, FULL_REDUCTION_MIN_DB))
    if fails:
        return _reply(req, 'model_rejected', '；'.join(fails), evidence=evidence,
                      model_sha256=model_sha,
                      validation_ids=[e.get('capture_id') for e in entries],
                      qualifies_cancellation=False)
    return _reply(req, 'valid_pass', '独立验证通过：%g–%g Hz 带内抑制中位 %+.2f dB（最低 %+.2f）'
                  % (BAND_LOW_HZ[0], BAND_LOW_HZ[1], band_med, band_min),
                  model_sha256=model_sha,
                  validation_ids=[e.get('capture_id') for e in entries],
                  qualifies_cancellation=True, evidence=evidence)


# ---------------------------------------------------------------- 入口

def evaluate(request):
    """契约入口。任何异常都转成带 reason 的 data_insufficient，不往上抛。"""
    if not isinstance(request, dict):
        return {'contract': CONTRACT, 'decision': 'data_insufficient',
                'reason': '请求不是 dict'}
    if request.get('contract') != CONTRACT:
        return _reply(request, 'data_insufficient',
                      '契约版本不符：%r' % request.get('contract'))
    phase = request.get('phase')
    try:
        if phase == 'input':
            return _phase_input(request)
        if phase == 'fit':
            return _phase_fit(request)
        if phase == 'validate':
            return _phase_validate(request)
        return _reply(request, 'data_insufficient', '未知 phase：%r' % (phase,))
    except Exception as exc:                                   # noqa: BLE001
        return _reply(request, 'data_insufficient',
                      '数值计算失败（%s: %s），按数据不足处理，不宣布失败'
                      % (type(exc).__name__, exc))
