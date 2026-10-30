#!/bin/bash
# Level ladder for the stationary arms, with the digital gain forced to 0 (direct_only): the board
# plays the noise through the speaker but no feedback term is added, so this measures the acoustic
# path only and cannot ring. Choose the loudest level whose microphone peak stays clear of -6 dBFS.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
DIR=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $DIR || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MODEL = DIR / 'rewired_512_20261026.json'
RATE = 48828.125


def ladder(level_db):
    n = int(2.0 * RATE)
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x = x / max(np.max(np.abs(x)), 1e-9) * (10 ** (level_db / 20))
    pcm = np.round(x * 32767).astype(np.int16)
    out = DIR / ('lvl_%d_%d.npz' % (int(-level_db), time.time_ns()))
    err = None
    try:
        replay_trial(str(out), 'room_v1_20261026b', str(MODEL), pcm, bypass=False, zero_coeff=True,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('LVL %5.1f FAILED %s' % (level_db, err), flush=True)
        return
    data = np.load(str(out))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    spec = np.abs(np.fft.rfft(mic * np.hanning(len(mic))))
    f = np.fft.rfftfreq(len(mic), 1.0 / RATE)
    band = (f >= 300) & (f <= 360)
    allb = (f >= 50) & (f <= 20000)
    share = float(np.sum(spec[band]**2) / max(float(np.sum(spec[allb]**2)), 1e-30))
    print('LVL %5.1f dBFS  mic_rms=%6.1f  mic_peak=%6.1f  clip=%d  bandshare=%.4f (%6.1f dB) %s'
          % (level_db, 20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
             20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
             int(np.count_nonzero(np.abs(mic) >= 0.999)), share, 10*np.log10(max(share, 1e-12)),
             err or 'ok'), flush=True)


for level in (-20.0, -12.0, -6.0):
    ladder(level)
PY
