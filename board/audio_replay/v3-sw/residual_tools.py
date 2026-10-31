"""Pure numerical checks for the open-loop overlay; no hardware access."""
import json
from pathlib import Path
import numpy as np


def load_candidate(path, fixture_id, hp_volume, sample_rate):
    model = json.loads(Path(path).read_text(encoding="utf-8"))
    taps = model.get("taps")
    if taps not in (256, 512):
        raise ValueError("candidate taps must be 256 or 512")
    expected = dict(lag_first=1, coefficient_format="signed24_fraction20",
                    training_source="board", fixture_id=fixture_id,
                    hp_volume=hp_volume, sample_rate_hz=sample_rate)
    for key, value in expected.items():
        if model.get(key) != value:
            raise ValueError("candidate mismatch: " + key)
    q = np.asarray(model["coefficients_q20"])
    h = np.asarray(model["coefficients"], dtype=np.float64)
    if (q.shape != (taps,) or q.dtype.kind not in "iu" or
            h.shape != (taps,) or not np.isfinite(h).all() or
            not np.isfinite(model["bias"])):
        raise ValueError("invalid candidate coefficients/bias")
    rounded = np.sign(h) * np.floor(np.abs(h) * 2**20 + .5)
    if np.any(q < -2**23) or np.any(q > 2**23-1) or not np.array_equal(q, rounded):
        raise ValueError("candidate Q20 mismatch/range")
    return model, q.astype(np.int64)


def verify_residual(raw, coefficients, bias):
    """Check every captured word, including startup; score after 256-frame warmup.

    int64 is safe here: 256 products of two signed24 values sum below 2^54.
    This independent convolution formulation differs from the sequential RTL MAC.
    A mismatch is recorded, not hidden by an aggregate audio metric.
    """
    raw = np.asarray(raw)
    q = np.asarray(coefficients)
    if (raw.ndim != 2 or raw.shape[1] != 4 or len(raw) <= len(q) or
            raw.dtype.kind not in "iu" or q.ndim != 1 or q.dtype.kind not in "iu" or
            np.any(raw < -2**23) or np.any(raw > 2**23-1) or
            np.any(q < -2**23) or np.any(q > 2**23-1) or not np.isfinite(bias)):
        raise ValueError("invalid PCM/coefficients/bias")
    raw = raw.astype(np.int64)
    acc = np.convolve(raw[:, 0], np.r_[np.int64(0), q.astype(np.int64)])[:len(raw)]
    magnitude = (np.abs(acc) + 2**19) >> 20
    rounded = np.where(acc < 0, -magnitude, magnitude)
    prediction = np.clip(rounded, -2**23, 2**23-1)
    difference = raw[:, 1] - prediction
    residual = np.clip(difference, -2**23, 2**23-1)
    pm = int(np.count_nonzero(raw[:, 2] != prediction))
    rm = int(np.count_nonzero(raw[:, 3] != residual))
    target = raw[256:, 1] / 2**23 - bias
    error = raw[256:, 3] / 2**23 - bias
    measurable = float(np.linalg.norm(target)) > 1e-12
    return dict(bit_exact=(pm == 0 and rm == 0), prediction_mismatches=pm,
                residual_mismatches=rm, evaluated_frames=len(target),
                prediction_saturations=int(np.count_nonzero(prediction != rounded)),
                residual_saturations=int(np.count_nonzero(residual != difference)),
                prediction_reduction_db=(float(20*np.log10(np.linalg.norm(target) /
                    max(np.linalg.norm(error), 1e-15))) if measurable and pm == 0 and rm == 0 else None),
                interpretation="open-loop residual only; not ASG")
