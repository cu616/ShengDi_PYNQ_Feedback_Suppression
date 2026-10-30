#!/bin/bash
# Where is the |H| peak on the fixture that is connected RIGHT NOW?
# Digital gain forced to 0 (open path), one pure tone per run at a fixed amplitude, so the
# microphone level at each frequency is the open-loop path gain at that frequency.
# This answers B's condition 1: the 322 Hz used earlier came from an older calibration, and must
# not be carried over to a fixture that has not been re-bound.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
DIR=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $DIR || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MODEL = DIR / 'rewired_512_20261026.json'
RATE = 48828.125
AMP = 0.15
TONES = (280.0, 300.0, 320.0, 340.0, 360.0, 380.0, 400.0, 420.0)


def probe(f0):
    n = int(2.0 * RATE)
    t = np.arange(n) / RATE
    pcm = np.round(AMP * np.sin(2*np.pi*f0*t) * 32767).astype(np.int16)
    out = DIR / ('peak_%d_%d.npz' % (int(f0), time.time_ns()))
    err = None
    try:
        replay_trial(str(out), 'room_v1_20261026b', str(MODEL), pcm, bypass=False, zero_coeff=True,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        err = repr(exc)[:160]
    if not out.is_file():
        print('PEAK %5.0f Hz FAILED %s' % (f0, err), flush=True)
        return None
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    w = np.hanning(len(mic))
    spec = np.abs(np.fft.rfft(mic * w))
    freqs = np.fft.rfftfreq(len(mic), 1.0 / RATE)
    band = np.abs(freqs - f0) <= 3.0
    level = 20*np.log10(max(float(np.max(spec[band])), 1e-12))
    st = int(meta.get('capture_status') or 0)
    print('PEAK %5.0f Hz  mic@f=%7.2f dB  peak=%6.1f dBFS  fs=%d bit22=%d'
          % (f0, level, 20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
             int(np.count_nonzero(np.abs(mic) >= 0.999)), (st >> 22) & 1), flush=True)
    return f0, level


rows = [r for r in (probe(f) for f in TONES) if r]
if rows:
    best = max(rows, key=lambda r: r[1])
    ref = [r for r in rows if r[0] == 320.0]
    gain_ref = (best[1] - ref[0][1]) if ref else float('nan')
    print('PEAK_SUMMARY max at %.0f Hz (%.2f dB); vs 320 Hz %+.2f dB'
          % (best[0], best[1], gain_ref), flush=True)
    print('PEAK_TABLE ' + ' '.join('%.0f:%.1f' % (f, v) for f, v in rows), flush=True)
PY
