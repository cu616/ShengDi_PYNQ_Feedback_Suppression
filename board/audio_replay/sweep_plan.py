"""A's field range selection. File-only analysis; no board/audio imports."""
import hashlib
import math
from pathlib import Path
import numpy as np
from replay_calibration import load_capture, fit_path, evaluate_path
from residual_tools import load_candidate
from replay_tools import RATE
from closed_tools import trial_parameters


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frequency_upper(h):
    # FIR frequency derivative bound covers the intervals between FFT bins.
    h = np.asarray(h, dtype=float)
    nfft = 65536
    return float(np.max(np.abs(np.fft.rfft(h, nfft))) +
                 math.pi/nfft * np.dot(np.arange(len(h)), np.abs(h)))


def response_bound(h, loop, gain):
    """Induced peak bound of H/(1-g*z^-2*loop) for this fitted linear model.

    Group the Neumann series in blocks: S_m / (1-L**m).
    ||H*S_m||1/(1-||L**m||1) bounds all times, not a truncated decay tail.
    Physical model error is NOT certified by this numerical calculation.
    """
    kernel = np.r_[0., 0., gain*np.asarray(loop)]
    power = np.ones(1)
    partial = np.zeros(1)
    for _ in range(32):
        if len(partial) < len(power):
            partial = np.pad(partial, (0, len(power)-len(partial)))
        partial[:len(power)] += power
        power = np.convolve(power, kernel)
        norm = float(np.sum(np.abs(power)))
        if norm < .5:
            return float(np.sum(np.abs(np.convolve(h, partial))) / (1-norm))
        if not np.isfinite(norm) or norm > 1e8:
            break
    raise ValueError('cannot bound model response; no playback at this gain')


def make_plan(data_dir):
    root = Path(data_dir)
    paths = [root/n for n in ('training_box_v1.npz', 'validation_box_v1.npz',
                              'candidate_box_v1_256.json')]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError('缺少已有标定文件（不需重新录音）：' + ', '.join(missing))
    train, valid = [load_capture(p) for p in paths[:2]]
    model, q = load_candidate(paths[2], 'box_v1_20261016', 40, RATE)
    for capture in (train, valid):
        if (capture.metadata['source'] != 'board' or capture.sample_rate_hz != RATE or
                capture.metadata.get('fixture_id') != model['fixture_id'] or
                capture.metadata.get('hp_volume') != 40):
            raise ValueError('标定数据的夹具/音量/采样率不匹配')
    if model['training_capture_id'] != train.metadata['capture_id']:
        raise ValueError('candidate training ID does not match training NPZ')
    score = evaluate_path({**model, 'coefficients': (q/2**20).tolist()}, valid, train)
    if score['prediction_reduction_db'] <= 0:
        raise ValueError('Q20模型在已有验证数据中没有改善，停止升档，需B处理模型')
    print('静默分析已有数据：拟合训练/验证路径；不加载overlay、不发声。', flush=True)
    fits = [fit_path(c) for c in (train, valid)]
    if max(abs(f['bias']) for f in fits) > .1 or abs(model['bias']) > .1:
        raise ValueError('标定直流偏置过大，不能授权播放')
    plants = [np.r_[0., q/2**20]] + [np.r_[0., f['coefficients']] for f in fits]
    deployed = plants[0]
    # Reserve observed train/validation disagreement in addition to 6 dB margin.
    disagreement = frequency_upper(plants[1]-plants[2])
    bound = max(frequency_upper(p) for p in plants)
    residual_bound = max(frequency_upper(p-deployed) for p in plants)
    robust_bound = max(bound, residual_bound) + disagreement
    if not np.isfinite(robust_bound) or robust_bound <= 0:
        raise ValueError('no usable frequency envelope')
    ceiling = min(0., -20*math.log10(robust_bound)-6.)
    points = []
    peak = min(10**(-30/20), .25/max(float(np.sum(np.abs(p))) for p in plants))
    grid = list(range(-35, -13, 3))
    # Use a final half-dB point below the ceiling when the 3 dB grid skips it.
    # Keep at least 1 dB separation; actual Q12 gain must still pass the bound.
    endpoint = min(-14., math.floor(ceiling*2)/2)
    accepted = [db for db in grid if db <= ceiling]
    if accepted and endpoint-accepted[-1] >= 1.:
        grid = sorted(set(accepted+[endpoint]))[:8]
    for db in grid:
        gain, _ = trial_parameters(db, 2.4)
        actual = 20*math.log10(gain/4096)
        if actual > ceiling:
            break
        response = max(response_bound(p, loop, gain/4096) for p in plants
                       for loop in (p, p-deployed))
        peak = min(peak, .25/max(response, 1e-12))
        points.append(dict(gain_db=db, gain_q12=gain, gain_db_actual=actual,
                           model_response_peak_bound=response))
    if len(points) < 2:
        raise ValueError('已有数据只支持不足两档；不重复单档低增益测试。估算上限 %.2f dB；需审核真实路径/观测保护后再扩大范围' % ceiling)
    if peak*32768 < 8:
        raise ValueError('全批固定声源幅度过低，不能进行有用的听感对照')
    return dict(schema_version=1, artifact_kind='replay_gain_plan',
                files={p.name: dict(sha256=sha(p), bytes=p.stat().st_size) for p in paths},
                points=points, operating_ceiling_db=ceiling, margin_db=6.,
                frequency_envelope=robust_bound, train_validation_disagreement=disagreement,
                q20_validation=score, source_peak_limit=peak,
                interpretation='empirical fitted-model envelope; not certified acoustic stability or measured ASG')
