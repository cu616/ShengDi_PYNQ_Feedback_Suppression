"""Integer residual reference and open-loop NLMS research baseline.

NLMS is not approved for correlated closed-loop speech: caller must supply an
adaptation mask and evaluate bias/double-talk before any hardware integration.
"""
import numpy as np
from .calibration import fixed_fir


def cancel_fixed(reference_pcm, microphone_pcm, coefficients_q20, bypass=None):
    u, mic = np.asarray(reference_pcm), np.asarray(microphone_pcm)
    if u.ndim != 1 or mic.shape != u.shape or not np.issubdtype(mic.dtype, np.integer):
        raise ValueError("equal one-dimensional integer PCM arrays required")
    if np.any(mic < -2**23) or np.any(mic >= 2**23):
        raise ValueError("microphone outside signed24")
    pred, _ = fixed_fir(u, coefficients_q20)
    mask = np.zeros(len(u), dtype=bool) if bypass is None else np.asarray(bypass, dtype=bool)
    if mask.shape != u.shape:
        raise ValueError("bypass shape differs")
    delta = mic.astype(np.int64) - pred.astype(np.int64)
    clipped = (delta < -2**23) | (delta > 2**23-1)
    residual = np.where(mask, mic, np.clip(delta, -2**23, 2**23-1)).astype(np.int32)
    return pred, residual, clipped & ~mask


def nlms_open_loop(reference, microphone, initial, adapt_mask, mu=0.2,
                   power_floor=1e-8, coefficient_limit=7.0):
    """Causal NLMS with explicit update permission, low-energy freeze and bounds.

    Output uses pre-update coefficients; no current reference in prediction.
    coefficient_limit is a divergence guard, not proof of closed-loop stability.
    """
    u, d, h = (np.asarray(v, dtype=float).copy() for v in (reference, microphone, initial))
    mask = np.asarray(adapt_mask, dtype=bool)
    if u.ndim != 1 or d.shape != u.shape or mask.shape != u.shape:
        raise ValueError("one-dimensional paired signals and mask required")
    if h.ndim != 1 or not 1 <= len(h) <= 1024:
        raise ValueError("invalid filter length")
    if not all(np.isfinite(v).all() for v in (u, d, h)):
        raise ValueError("nonfinite data")
    if not (np.isfinite(mu) and 0 < mu < 2 and np.isfinite(power_floor) and power_floor > 0
            and np.isfinite(coefficient_limit) and 0 < coefficient_limit < 8):
        raise ValueError("invalid adaptation parameters")
    if np.max(np.abs(h)) > coefficient_limit:
        raise ValueError("initial coefficient outside guard")
    x = np.zeros(len(h)); prediction = np.empty(len(u)); rejected = updates = 0
    for n in range(len(u)):
        prediction[n] = h @ x
        power = float(x @ x)
        if mask[n] and power > power_floor:
            candidate = h + mu * (d[n] - prediction[n]) * x / (power + power_floor)
            if np.isfinite(candidate).all() and np.max(np.abs(candidate)) <= coefficient_limit:
                h = candidate; updates += 1
            else:
                rejected += 1
        x[1:] = x[:-1]; x[0] = u[n]
    return prediction, h, {"updates": updates, "rejected_updates": rejected}
