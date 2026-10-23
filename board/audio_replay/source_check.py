"""Silent on-board check: is source.wav speech-like or just amplified noise?

Only statistics leave the board; the PCM itself never does.
"""
import json
import sys
import wave

import numpy as np

PATH = '/home/xilinx/bcheck_pkg/source.wav'


def main():
    with wave.open(PATH, 'rb') as stream:
        channels, width, rate, n = (stream.getnchannels(), stream.getsampwidth(),
                                    stream.getframerate(), stream.getnframes())
        data = stream.readframes(n)
    if width == 3:
        b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int64)
        pcm = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        pcm = np.where(pcm >= 2**23, pcm - 2**24, pcm)
    else:
        pcm = np.frombuffer(data, dtype='<i%d' % width).astype(np.int64)
    x = pcm.reshape(-1, channels)[:, 0] / float(2 ** (8 * width - 1))
    report = dict(channels=channels, width_bits=8 * width, rate_hz=rate, frames=n)

    peak = float(np.max(np.abs(x)))
    rms = float(np.std(x))
    report['peak_dbfs'] = 20 * np.log10(max(peak, 1e-12))
    report['rms_dbfs'] = 20 * np.log10(max(rms, 1e-12))
    report['crest_db'] = 20 * np.log10(max(peak, 1e-12) / max(rms, 1e-12))

    frame = int(0.05 * rate)
    usable = len(x) // frame * frame
    frames = x[:usable].reshape(-1, frame)
    frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
    loud = frame_rms > max(np.max(frame_rms) * 10 ** (-30 / 20), 1e-9)
    report['active_frame_fraction'] = float(np.mean(loud))
    report['frame_rms_db_range'] = [float(20 * np.log10(max(np.min(frame_rms), 1e-12))),
                                    float(20 * np.log10(max(np.max(frame_rms), 1e-12)))]

    # Spectral flatness: near 1 = noise-like, near 0 = tonal/speech-like.
    window = np.hanning(8192)
    flats = []
    for start in range(0, max(1, usable - 8192), 4096):
        segment = x[start:start + 8192] * window
        power = np.abs(np.fft.rfft(segment)) ** 2 + 1e-20
        band = power[(np.fft.rfftfreq(8192, 1 / rate) > 100) &
                     (np.fft.rfftfreq(8192, 1 / rate) < 6000)]
        if len(band) > 16 and np.mean(band) > 0:
            flats.append(float(np.exp(np.mean(np.log(band))) / np.mean(band)))
    report['spectral_flatness_median'] = float(np.median(flats)) if flats else None

    # Autocorrelation periodicity on the loudest 40 ms frame: speech is periodic.
    loudest = int(np.argmax(frame_rms)) * frame
    segment = x[loudest:loudest + int(0.04 * rate)]
    if len(segment) > 200:
        segment = segment - np.mean(segment)
        energy = float(np.dot(segment, segment))
        if energy > 0:
            ac = np.correlate(segment, segment, 'full')[len(segment) - 1:]
            ac = ac / energy
            lag_min, lag_max = int(rate / 500), int(rate / 60)
            if lag_max < len(ac):
                window_ac = ac[lag_min:lag_max]
                best = int(np.argmax(window_ac)) + lag_min
                report['pitch_hz'] = float(rate / best)
                report['pitch_periodicity'] = float(ac[best])
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    sys.exit(main())
