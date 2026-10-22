"""Frequency attribution for the howl: which frequency dominates in each capture?

Compares microphone and residual spectra, so a digital self-oscillation (residual only)
is never mistaken for an acoustic howl (both).
"""
import json
import sys

import numpy as np

RATE = 48828.125


def peaks(signal, nfft=8192, top=5):
    segment = signal[-nfft:] * np.hanning(nfft)
    spectrum = np.abs(np.fft.rfft(segment))
    freqs = np.fft.rfftfreq(nfft, 1 / RATE)
    total = float(np.sum(spectrum)) or 1.0
    order = np.argsort(spectrum)[::-1]
    out = []
    for index in order[:top]:
        if 20 < freqs[index] < 20000:
            out.append([round(float(freqs[index]), 1), round(float(spectrum[index] / total), 3)])
    band = spectrum[(freqs > 200) & (freqs < 4000)]
    median = float(np.median(spectrum[freqs > 20])) or 1e-12
    return out, round(float(np.max(spectrum) / median), 1), round(float(np.max(band) / median), 1)


for path in sys.argv[1:]:
    try:
        with np.load(path) as data:
            mic = np.asarray(data['microphone'], dtype=float)
            residual = np.asarray(data['residual_pcm'], dtype=float) / 2**23
            reference = np.asarray(data['reference'], dtype=float)
            meta = json.loads(str(data['metadata_json']))
    except Exception as exc:                                   # noqa: BLE001
        print('FAILED', path, exc)
        continue
    mic_peaks, mic_ratio, mic_band = peaks(mic)
    res_peaks, res_ratio, res_band = peaks(residual)
    print(json.dumps(dict(
        file=path.split('/')[-1], mode='bypass' if meta['bypass'] else 'cancel',
        gain_db=round(float(meta.get('gain_db_actual') or 0), 2),
        mic_rms=round(float(20 * np.log10(max(np.std(mic), 1e-12))), 1),
        mic_peaks=mic_peaks, mic_peak_to_median=mic_ratio, mic_band_peak=mic_band,
        residual_peaks=res_peaks, residual_peak_to_median=res_ratio,
        residual_band_peak=res_band), ensure_ascii=False))
