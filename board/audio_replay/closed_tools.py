"""Offline closed-loop arithmetic checks; no board or audio access."""
import math
import numpy as np

RATE = 48828.125


def trial_parameters(gain_db, seconds):
    if not math.isfinite(gain_db) or not -60 <= gain_db <= 18.06179973983887:
        raise ValueError("gain_db must be finite in -60..20*log10(8)")
    if not math.isfinite(seconds) or not 0.02 <= seconds <= 10:
        raise ValueError("seconds must be finite in 0.02..10")
    return int(math.floor(4096 * 10**(gain_db / 20) + .5)), int(seconds * RATE)


def rounded_shift(value, bits):
    value = np.asarray(value, dtype=np.int64)
    magnitude = (np.abs(value) + (1 << (bits-1))) >> bits
    return np.where(value < 0, -magnitude, magnitude)


def gain_pcm(value, gain_q12):
    return np.clip(rounded_shift(np.asarray(value, dtype=np.int64)*gain_q12, 12),
                   -2**23, 2**23-1)


def verify_closed(raw, coefficients, bypass, gain_q12, first_frame=0):
    """Compare integer model to RAM and actual output reference, not audio quality.

    A truncated ring has unknown prior history: exclude its first 256 predictions.
    The two-frame output check uses recorded residuals and is independent of FIR.
    Only fixed-mode trials are supported here (driver does not switch mid-trial).
    """
    raw = np.asarray(raw)
    q = np.asarray(coefficients)
    if (raw.ndim != 2 or raw.shape[1] != 4 or len(raw) <= 256 or
            raw.dtype.kind not in "iu" or q.shape != (256,) or q.dtype.kind not in "iu" or
            np.any(raw < -2**23) or np.any(raw > 2**23-1) or
            np.any(q < -2**23) or np.any(q > 2**23-1) or
            not 0 <= gain_q12 <= 32768 or first_frame < 0):
        raise ValueError("invalid capture/coefficients/gain/index")
    raw, q = raw.astype(np.int64), q.astype(np.int64)
    acc = np.convolve(raw[:, 0], np.r_[np.int64(0), q])[:len(raw)]
    prediction = np.clip(rounded_shift(acc, 20), -2**23, 2**23-1)
    residual = raw[:, 1] if bypass else np.clip(raw[:, 1]-prediction, -2**23, 2**23-1)
    skip = 256 if first_frame else 0
    pm = int(np.count_nonzero(raw[skip:, 2] != prediction[skip:]))
    rm = int(np.count_nonzero(raw[skip:, 3] != residual[skip:]))
    tm = int(np.count_nonzero(raw[2:, 0] != gain_pcm(raw[:-2, 3], gain_q12)))
    if first_frame == 0:
        tm += int(np.count_nonzero(raw[:2, 0]))
    return dict(bit_exact=(pm == rm == tm == 0), prediction_mismatches=pm,
                residual_mismatches=rm, output_mismatches=tm,
                evaluated_frames=len(raw)-skip, history_excluded_frames=skip,
                output_schedule_frames=2, interpretation="arithmetic only; NOT MSG/ASG")
