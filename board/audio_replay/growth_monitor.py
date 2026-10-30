"""Offline narrowband-growth monitor. No PYNQ imports or hardware actions.

An alarm means suspected growth, not proof that acoustic feedback caused it.
Frame intervals are half-open; PCM is signed24 integer code, not normalized audio.
"""
from collections import deque
from dataclasses import asdict, dataclass
import math

import numpy as np


@dataclass(frozen=True)
class MonitorConfig:
    window_seconds: float = 0.064
    hop_seconds: float = 0.016
    growth_seconds: float = 0.5
    confirm_seconds: float = 0.08
    minimum_rise_db: float = 3.0
    minimum_slope_db_per_second: float = 6.0
    minimum_fit_r2: float = 0.85
    minimum_tonal_fraction: float = 0.55
    minimum_tonal_dbfs: float = -70.0
    low_hz: float = 20.0
    high_hz: float = 20000.0
    frequency_tolerance_bins: int = 2

    def validate(self, sample_rate):
        values = asdict(self)
        if not all(math.isfinite(float(v)) for v in values.values()):
            raise ValueError('finite monitor parameters required')
        if not math.isfinite(sample_rate) or sample_rate < 1000:
            raise ValueError('sample rate must be finite and at least 1000 Hz')
        if not 0 < self.hop_seconds <= self.window_seconds:
            raise ValueError('require 0 < hop <= window')
        if self.growth_seconds <= 0 or self.confirm_seconds < 0:
            raise ValueError('invalid growth/confirmation duration')
        if self.minimum_rise_db <= 0 or self.minimum_slope_db_per_second <= 0:
            raise ValueError('positive growth thresholds required')
        if not 0 < self.minimum_fit_r2 <= 1 or not 0 < self.minimum_tonal_fraction <= 1:
            raise ValueError('fit and tonality thresholds must be in (0, 1]')
        if not 0 <= self.low_hz < min(self.high_hz, sample_rate / 2):
            raise ValueError('empty monitoring band')
        if type(self.frequency_tolerance_bins) is not int or self.frequency_tolerance_bins < 0:
            raise ValueError('frequency tolerance must be a nonnegative integer')


class GrowthMonitor:
    """Chunk-invariant analysis of explicitly indexed, nonoverlapping PCM blocks."""

    def __init__(self, sample_rate, config=None):
        self.sample_rate = float(sample_rate)
        self.config = config or MonitorConfig()
        self.config.validate(self.sample_rate)
        self.window_size = round(self.sample_rate * self.config.window_seconds)
        self.hop_size = round(self.sample_rate * self.config.hop_seconds)
        if self.window_size < 16 or self.hop_size < 1:
            raise ValueError('window/hop too short')
        self.history_size = max(3, math.ceil(
            self.config.growth_seconds * self.sample_rate / self.hop_size) + 1)
        self.confirm_frames = math.ceil(self.config.confirm_seconds * self.sample_rate)
        self.minimum_frames = (self.window_size + (self.history_size - 1) * self.hop_size
                               + math.ceil(self.confirm_frames / self.hop_size) * self.hop_size)
        self.window = np.hanning(self.window_size)
        self.power_scale = 2.0 / (self.window_size * np.sum(self.window ** 2))
        self.frequencies = np.fft.rfftfreq(self.window_size, 1 / self.sample_rate)
        self.band = np.flatnonzero((self.frequencies >= self.config.low_hz) &
                                  (self.frequencies <= self.config.high_hz) &
                                  (self.frequencies > 0))
        if not len(self.band):
            raise ValueError('no FFT bins in monitoring band')
        self.history = deque(maxlen=self.history_size)
        self.buffer = np.empty(0, dtype=np.int32)
        self.buffer_start = 0
        self.intervals = []
        self.trace = []
        self.events = []
        self.full_scale_samples = 0
        self.candidate_start = None
        self.growth_reported = False
        self.finalized = False

    def push(self, pcm, first_frame):
        if self.finalized:
            raise ValueError('monitor already finalized')
        pcm = np.asarray(pcm)
        if (type(first_frame) is not int or first_frame < 0 or pcm.ndim != 1 or
                not len(pcm) or pcm.dtype.kind not in 'iu'):
            raise ValueError('nonempty integer PCM and nonnegative integer first_frame required')
        if np.any(pcm < -2**23) or np.any(pcm > 2**23 - 1):
            raise ValueError('PCM outside signed24 range')
        end = first_frame + len(pcm)
        if self.intervals and first_frame < self.intervals[-1][1]:
            raise ValueError('overlapping or out-of-order PCM')
        contiguous = bool(self.intervals and first_frame == self.intervals[-1][1])
        if not contiguous:
            self.buffer = np.empty(0, dtype=np.int32)
            self.buffer_start = first_frame
            self.history.clear()
            self.candidate_start = None
            self.intervals.append([first_frame, end])
        else:
            self.intervals[-1][1] = end
        clipped = np.flatnonzero((pcm == -2**23) | (pcm == 2**23 - 1))
        if len(clipped) and self.full_scale_samples == 0:
            frame = first_frame + int(clipped[0])
            self.events.append(dict(kind='full_scale', frame=frame,
                                    time_seconds=frame / self.sample_rate))
        self.full_scale_samples += len(clipped)
        self.buffer = np.concatenate((self.buffer, pcm.astype(np.int32)))
        while len(self.buffer) >= self.window_size:
            self._analyze_window(self.buffer[:self.window_size], self.buffer_start)
            self.buffer = self.buffer[self.hop_size:]
            self.buffer_start += self.hop_size

    def _analyze_window(self, pcm, start):
        signal = pcm.astype(np.float64) / 2**23
        dc = float(signal.mean())
        signal -= dc
        power = np.abs(np.fft.rfft(signal * self.window)) ** 2
        peak = int(self.band[np.argmax(power[self.band])])
        left = max(int(self.band[0]), peak - 1)
        right = min(int(self.band[-1]) + 1, peak + 2)
        tonal_power = float(power[left:right].sum())
        total_power = float(power[1:].sum())
        feature = dict(
            first_frame=start, end_frame=start + self.window_size,
            time_seconds=(start + self.window_size) / self.sample_rate,
            peak_hz=float(self.frequencies[peak]), peak_bin=peak,
            rms_dbfs=float(20 * np.log10(max(float(np.sqrt(np.mean(signal ** 2))), 1e-12))),
            dc_fs=dc,
            tonal_dbfs=float(10 * np.log10(max(tonal_power * self.power_scale, 1e-24))),
            tonal_fraction=tonal_power / max(total_power, 1e-24))
        self.history.append(feature)
        ready = len(self.history) == self.history_size
        candidate, rise, slope, fit = False, 0.0, 0.0, 0.0
        if ready:
            levels = np.array([row['tonal_dbfs'] for row in self.history])
            times = np.arange(len(levels)) * self.hop_size / self.sample_rate
            centered = levels - levels.mean()
            slope = float(np.dot(times - times.mean(), centered) /
                          np.sum((times - times.mean()) ** 2))
            fitted = levels.mean() + slope * (times - times.mean())
            variance = float(np.sum(centered ** 2))
            fit = max(0.0, 1 - float(np.sum((levels - fitted) ** 2)) / max(variance, 1e-24))
            rise = float(levels[-1] - levels[0])
            bins = [row['peak_bin'] for row in self.history]
            candidate = bool(
                min(row['tonal_fraction'] for row in self.history) >= self.config.minimum_tonal_fraction
                and min(levels) >= self.config.minimum_tonal_dbfs
                and max(bins) - min(bins) <= self.config.frequency_tolerance_bins
                and rise >= self.config.minimum_rise_db
                and slope >= self.config.minimum_slope_db_per_second
                and fit >= self.config.minimum_fit_r2)
        feature.update(history_ready=ready, growth_candidate=candidate,
                       rise_db=rise, slope_db_per_second=slope, fit_r2=fit)
        self.trace.append(feature)
        if candidate:
            if self.candidate_start is None:
                self.candidate_start = feature['end_frame']
            if (not self.growth_reported and
                    feature['end_frame'] - self.candidate_start >= self.confirm_frames):
                self.events.append(dict(
                    kind='suspected_howl', frame=feature['end_frame'],
                    time_seconds=feature['time_seconds'], peak_hz=feature['peak_hz'],
                    candidate_since_frame=self.candidate_start,
                    evidence_first_frame=self.history[0]['first_frame'],
                    rise_db=rise, slope_db_per_second=slope, fit_r2=fit))
                self.growth_reported = True
        else:
            self.candidate_start = None

    def finish(self, total_frames):
        if type(total_frames) is not int or total_frames < 1:
            raise ValueError('positive integer total_frames required')
        if self.intervals and self.intervals[-1][1] > total_frames:
            raise ValueError('PCM exceeds declared recording extent')
        self.finalized = True
        missing, cursor = [], 0
        for start, end in self.intervals:
            if start > cursor:
                missing.append([cursor, start])
            cursor = end
        if cursor < total_frames:
            missing.append([cursor, total_frames])
        observed = sum(end - start for start, end in self.intervals)
        longest = max((end - start for start, end in self.intervals), default=0)
        spectral = []
        for row in self.trace:
            start, end = row['first_frame'], row['end_frame']
            if spectral and start <= spectral[-1][1]:
                spectral[-1][1] = end
            else:
                spectral.append([start, end])
        spectral_missing, cursor = [], 0
        for start, end in spectral:
            if start > cursor:
                spectral_missing.append([cursor, start])
            cursor = end
        if cursor < total_frames:
            spectral_missing.append([cursor, total_frames])
        events = sorted(self.events, key=lambda item: item['frame'])
        growth = next((e for e in events if e['kind'] == 'suspected_howl'), None)
        enough_history = longest >= self.minimum_frames
        verdict = ('suspected_howl' if growth else 'full_scale' if self.full_scale_samples
                   else 'insufficient_data' if missing or not enough_history
                   else 'no_growth_detected')
        return dict(
            schema_version=1, detector_version='narrowband-growth-v1', offline_only=True,
            sample_rate_hz=self.sample_rate, config=asdict(self.config), verdict=verdict,
            analysis=dict(window_frames=self.window_size, hop_frames=self.hop_size,
                          history_windows=self.history_size,
                          fft_bin_hz=self.sample_rate / self.window_size,
                          monitored_first_bin_hz=float(self.frequencies[self.band[0]]),
                          monitored_last_bin_hz=float(self.frequencies[self.band[-1]])),
            events=events, first_suspected_howl=growth,
            full_scale_samples=int(self.full_scale_samples),
            coverage=dict(total_frames=total_frames, observed_frames=observed,
                          fraction=observed / total_frames, complete=not missing,
                          observed_intervals=self.intervals, missing_intervals=missing,
                          sufficient_contiguous_history=enough_history,
                          minimum_contiguous_frames=self.minimum_frames,
                          minimum_contiguous_seconds=self.minimum_frames / self.sample_rate,
                          analyzed_windows=len(self.trace),
                          history_ready_windows=sum(row['history_ready'] for row in self.trace),
                          spectral_intervals=spectral,
                          spectral_unanalyzed_intervals=spectral_missing),
            interpretation='Offline suspected-growth screening; not feedback causality, measured stability or MSG/ASG',
            trace=self.trace)


def replay(pcm, sample_rate, first_frame=0, total_frames=None, frame_indices=None,
           config=None, chunk_frames=4096):
    """Replay PCM in bounded chunks. Optional explicit frame indices expose gaps."""
    pcm = np.asarray(pcm)
    if pcm.ndim != 1 or pcm.dtype.kind not in 'iu' or not len(pcm):
        raise ValueError('nonempty one-dimensional integer PCM required')
    if type(chunk_frames) is not int or chunk_frames < 1:
        raise ValueError('positive integer chunk_frames required')
    if type(first_frame) is not int or first_frame < 0:
        raise ValueError('invalid first_frame')
    monitor = GrowthMonitor(sample_rate, config)
    if frame_indices is None:
        indices = np.arange(first_frame, first_frame + len(pcm), dtype=np.int64)
    else:
        indices = np.asarray(frame_indices)
        if (indices.shape != pcm.shape or indices.dtype.kind not in 'iu' or
                np.any(indices < 0) or np.any(np.diff(indices.astype(np.int64)) <= 0)):
            raise ValueError('frame_indices must be aligned and strictly increasing')
    if total_frames is None:
        total_frames = int(indices[-1]) + 1
    boundaries = np.r_[0, np.flatnonzero(np.diff(indices.astype(np.int64)) != 1) + 1, len(pcm)]
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        for offset in range(int(start), int(end), chunk_frames):
            stop = min(offset + chunk_frames, int(end))
            monitor.push(pcm[offset:stop], int(indices[offset]))
    return monitor.finish(total_frames)


def load_capture(path, channel='residual'):
    """Read existing project NPZ; tail extents come from driver metadata.

    Frame numbering is declared by the file, not independently verified here.
    No pickle, playback, overlay loading, or raw-audio export.
    """
    keys = dict(residual='residual_pcm', prediction='prediction_pcm',
                microphone='microphone', reference='reference')
    if channel not in keys:
        raise ValueError('unsupported channel')
    with np.load(path, allow_pickle=False) as capture:
        signal = np.asarray(capture[keys[channel]])
        rate = float(capture['sample_rate_hz'].item())
        metadata = (json_metadata(capture['metadata_json'])
                    if 'metadata_json' in capture else {})
        if signal.dtype.kind == 'f' and channel in ('reference', 'microphone'):
            if not np.isfinite(signal).all() or np.any(signal < -1) or np.any(signal >= 1):
                raise ValueError('invalid normalized PCM')
            signal = np.rint(signal * 2**23).astype(np.int64)
        indices = np.array(capture['frame_indices']) if 'frame_indices' in capture else None
        first = metadata.get('first_frame', 0)
        total = metadata.get('completed_frames', len(signal))
        if 'frames' in metadata and metadata['frames'] != len(signal):
            raise ValueError('metadata frames differs from PCM length')
        if metadata.get('dropped_frames', 0) != 0 and indices is None:
            raise ValueError('dropped/unknown frames require explicit frame_indices')
        # A tail with no extent cannot be safely treated as a whole recording.
        if first and 'completed_frames' not in metadata:
            raise ValueError('tail capture requires completed_frames')
    return signal, rate, dict(first_frame=first, total_frames=total,
                              frame_indices=indices), metadata


def json_metadata(value):
    import json
    metadata = json.loads(str(value.item()))
    if not isinstance(metadata, dict):
        raise ValueError('metadata must be a JSON object')
    return metadata
