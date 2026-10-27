"""Per-block envelope of a replay capture (blind2 candidate), for the speech/loop question.

usage: python -X utf8 a-envelope-blind2-2026-10-27.py [capture.npz]

Prints, for each 2048-frame block (41.9 ms at 48.828 kHz): microphone RMS and peak, rail-contact
counts for microphone and residual, dominant frequency, narrowband share (+-10 Hz around the
dominant peak) and the 300-360 Hz share. Read the numbers together with
a-envelope-blind2-2026-10-27.json, which records what they were taken to mean.

This is A's own measurement, written because B asked for --envelope on a capture that is local
here while B's script version was not available.
"""
import json
import sys
from pathlib import Path

import numpy as np

DEFAULT = Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\failevid'
               r'\blind2_cand_1746867731709459239.npz')
BLOCK = 2048
RAIL_POS = 2**23 - 1
RAIL_NEG = -2**23


def longest_run(mask):
    best = cur = 0
    for flag in mask:
        cur = cur + 1 if flag else 0
        best = max(best, cur)
    return best


def main(argv):
    path = Path(argv[0]) if argv else DEFAULT
    data = np.load(str(path))
    meta = json.loads(str(data['metadata_json']))
    mic_i = np.rint(np.asarray(data['microphone'], dtype=np.float64) * 2**23).astype(np.int64)
    res_i = np.rint(np.asarray(data['residual_pcm'], dtype=np.float64)).astype(np.int64)
    rate = float(meta.get('sample_rate_hz') or 48828.125)
    n = len(mic_i)
    rail_mic = (mic_i >= RAIL_POS) | (mic_i <= RAIL_NEG)
    rail_res = (res_i >= RAIL_POS) | (res_i <= RAIL_NEG)
    print('capture', path.name, 'frames', n, 'rate', rate)
    print('meta stop=%s completed=%s psat=%s rsat=%s gain_q12=%s'
          % (meta.get('stop_reason'), meta.get('completed_frames'),
             meta.get('prediction_saturations'), meta.get('residual_saturations'),
             meta.get('gain_q12')))
    print('whole capture: mic rail %d (longest %d), residual rail %d (longest %d)'
          % (int(np.count_nonzero(rail_mic)), longest_run(rail_mic),
             int(np.count_nonzero(rail_res)), longest_run(rail_res)))
    freqs = np.fft.rfftfreq(BLOCK, 1.0 / rate)
    band_hi = (freqs >= 50) & (freqs <= 8000)
    band_300 = (freqs >= 300) & (freqs <= 360)
    print()
    print('blk   mic_rms  mic_pk  mic_rail  res_rail   mic_f0   mic_nb   res_f0   res_nb  share300')
    for b in range(n // BLOCK):
        s = slice(b * BLOCK, (b + 1) * BLOCK)
        w = np.hanning(BLOCK)
        sm = np.abs(np.fft.rfft(mic_i[s].astype(np.float64) * w))
        sr = np.abs(np.fft.rfft(res_i[s].astype(np.float64) * w))
        i_m = int(np.argmax(np.where(band_hi, sm, 0)))
        i_r = int(np.argmax(np.where(band_hi, sr, 0)))
        nb_m = float(np.sum(sm[np.abs(freqs - freqs[i_m]) <= 10] ** 2)
                     / max(float(np.sum(sm[band_hi] ** 2)), 1e-30))
        nb_r = float(np.sum(sr[np.abs(freqs - freqs[i_r]) <= 10] ** 2)
                     / max(float(np.sum(sr[band_hi] ** 2)), 1e-30))
        share300 = float(np.sum(sm[band_300] ** 2) / max(float(np.sum(sm[band_hi] ** 2)), 1e-30))
        print('%3d  %7.1f %7.1f  %8d  %8d  %7.1f %8.3f  %7.1f %8.3f  %.3f'
              % (b,
                 20 * np.log10(max(float(np.sqrt(np.mean((mic_i[s] / 2**23) ** 2))), 1e-12)),
                 20 * np.log10(max(float(np.max(np.abs(mic_i[s]))), 1e-12) / 2**23),
                 int(np.count_nonzero(rail_mic[s])), int(np.count_nonzero(rail_res[s])),
                 freqs[i_m], nb_m, freqs[i_r], nb_r, share300))


if __name__ == '__main__':
    main(sys.argv[1:])
