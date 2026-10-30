"""PCM preparation and integer verification. No hardware access."""
import hashlib
import math
import wave
from pathlib import Path

import numpy as np
from closed_tools import gain_pcm, rounded_shift

RATE = 48828.125
MAX_SOURCE_FRAMES = 131072


def prepare_source(path, coefficients, gain_q12):
    """Use left input channel, resample upwards, fade ends, then peak-normalize.

    Source level is separate from loop gain. Model-based worst-case mic bound:
    ||mic|| <= L1*||source||/(1-g*L1). Allow at most 0.5 FS by that estimate.
    This is not an acoustic guarantee; the current fixture must match calibration.
    """
    with wave.open(str(path), "rb") as stream:
        channels, width, rate, n = (stream.getnchannels(), stream.getsampwidth(),
                                     stream.getframerate(), stream.getnframes())
        if (channels not in (1, 2) or width not in (2, 3, 4) or
                not 8000 <= rate <= 48000 or not 0.5 <= n / rate <= 2.5 or
                stream.getcomptype() != "NONE"):
            raise ValueError("source.wav must be PCM16/24/32, mono/stereo, 8..48 kHz, 0.5..2.5 seconds")
        data = stream.readframes(n)
    if len(data) != n * channels * width:
        raise ValueError("truncated source.wav")
    if width == 3:
        b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int64)
        pcm = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        pcm = np.where(pcm >= 2**23, pcm - 2**24, pcm)
    else:
        pcm = np.frombuffer(data, dtype="<i%d" % width).astype(np.int64)
    x = pcm.reshape(-1, channels)[:, 0] / float(2**(8*width-1))
    if np.max(np.abs(x)) >= 0.999:
        raise ValueError("recording clipped: lower phone recording volume; do not replay this clip")
    x -= np.mean(x)
    if np.std(x) < 1e-5:
        raise ValueError("recording is silent/too weak; no playback")
    count = int(math.floor(n * RATE / rate))
    if count > MAX_SOURCE_FRAMES:
        raise ValueError("source exceeds hardware memory")
    x = np.interp(np.arange(count) * rate / RATE, np.arange(n), x)
    fade = min(int(.01 * RATE), count // 4)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    q = np.asarray(coefficients, dtype=np.int64)
    l1 = float(np.sum(np.abs(q))) / 2**20
    loop_bound = gain_q12 / 4096.0 * l1
    if l1 <= 0 or not math.isfinite(l1) or loop_bound > 10**(-6/20):
        raise ValueError("requested loop gain exceeds model bound with 6 dB margin")
    max_peak = min(10**(-30/20), .5 * (1 - loop_bound) / l1)
    # Integer peak limit is rounded down, so quantization cannot exceed the bound.
    peak16 = int(math.floor(max_peak * 32768))
    if peak16 < 8:
        raise ValueError("model leaves insufficient source headroom")
    scaled = x * peak16 / np.max(np.abs(x))
    source = (np.sign(scaled) * np.floor(np.abs(scaled) + .5)).astype("<i2")
    return source, dict(wav_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                        pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest(),
                        input_rate_hz=rate, input_channels=channels, selected_channel="left",
                        source_frames=count, source_seconds=count/RATE,
                        source_peak_dbfs=20*math.log10(peak16/32768),
                        model_l1_q20=l1, loop_bound=loop_bound,
                        interpretation="model-based level estimate; not measured stability or loudness")


def verify_replay(raw, coefficients, bypass, gain_q12, source_pcm16, first_frame=0):
    raw = np.asarray(raw, dtype=np.int64)
    q = np.asarray(coefficients, dtype=np.int64)
    if raw.ndim != 2 or raw.shape[1] != 4 or q.ndim != 1 or q.size < 2 or \
            len(raw) <= q.size:
        raise ValueError("invalid capture shape")
    acc = np.convolve(raw[:, 0], np.r_[np.int64(0), q])[:len(raw)]
    prediction = np.clip(rounded_shift(acc, 20), -2**23, 2**23-1)
    residual = raw[:, 1] if bypass else np.clip(raw[:, 1]-prediction, -2**23, 2**23-1)
    # audio-replay v3 (docs/contracts/audio-replay-v3.md): the gain multiplies the UNCLAMPED
    # 25-bit difference and the only clamp is after the gain. The captured residual is still the
    # clamped 24-bit diagnostic value, so the output oracle must be rebuilt from mic - prediction
    # instead of from the captured residual; otherwise every clipped transient looks like a
    # datapath mismatch. In bypass the hardware multiplies the sign-extended microphone.
    #
    # The prediction used here is the RECORDED one (raw[:,2]), not the recomputed convolution.
    # C 2026-10-27: with a truncated ring the recomputed prediction has no history for the first
    # `skip` frames, so an overflow that already happened there was reported as 0. The recorded
    # prediction is exactly what the hardware subtracts, so the wide residual is exact for every
    # frame, including the prefix. The model itself is still cross-checked separately by `pm`/`rm`
    # against the recomputed prediction.
    wide = raw[:, 1] if bypass else raw[:, 1] - raw[:, 2]
    skip = q.size if first_frame else 0
    indices = np.arange(first_frame, first_frame+len(raw))
    injected = np.zeros(len(raw), dtype=np.int64)
    valid = indices < len(source_pcm16)
    injected[valid] = np.asarray(source_pcm16, dtype=np.int64)[indices[valid]] * 256
    pm = int(np.count_nonzero(raw[skip:, 2] != prediction[skip:]))
    rm = int(np.count_nonzero(raw[skip:, 3] != residual[skip:]))
    # The played word at ring frame n is gain(wide[n-2]). With the recorded prediction the wide
    # value is exact for every frame, so only the two-frame schedule needs to be respected.
    out_start = 2
    frames = np.arange(out_start, len(raw))
    expected = np.clip(injected[frames] + gain_pcm(wide[frames-2], gain_q12), -2**23, 2**23-1)
    tm = int(np.count_nonzero(raw[frames, 0] != expected))
    if first_frame == 0:
        tm += int(np.count_nonzero(raw[:2, 0] != injected[:2]))
    # Wide-residual counting:
    #  (a) the 24-bit rail is ASYMMETRIC: +8388607 and -8388608 are both legal values, so an
    #      overflow needs `> 8388607` or `< -8388608`;
    #  (b) the prefix of a truncated ring is counted, not dropped, because the recorded prediction
    #      makes it exact;
    #  (c) a capture with no checkable output frame must not read as a pass (defensive: the shape
    #      guard above already requires len(raw) > q.size).
    rail_pos, rail_neg = 2**23 - 1, -2**23
    over = (wide > rail_pos) | (wide < rail_neg)
    wide_count = int(np.count_nonzero(over))
    prefix_count = int(np.count_nonzero(over[:skip])) if skip else 0
    no_output_frames = len(frames) == 0
    bit_exact = (pm == rm == tm == 0) and not no_output_frames
    return dict(bit_exact=bit_exact,
                verified=not no_output_frames,
                verification_note=(None if not no_output_frames else
                                   "no verifiable output frames in this capture; not a pass"),
                prediction_mismatches=pm, residual_mismatches=rm, output_mismatches=tm,
                wide_residual_frames=wide_count,
                wide_residual_frames_prefix=prefix_count,
                wide_residual_count_partial=False,
                wide_prediction_source="recorded prediction column (exact for the prefix too)",
                wide_rail_definition="overflow iff wide > 8388607 or wide < -8388608",
                history_excluded_frames=skip, evaluated_frames=len(raw)-skip,
                output_checked_frames=len(frames),
                interpretation="played[n]=source[n]+gain(wide residual[n-2]), one clamp after "
                               "gain; arithmetic only")
