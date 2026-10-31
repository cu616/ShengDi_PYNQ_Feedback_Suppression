#!/bin/bash
# Three silent captures back to back, so a bad seal on one of them does not decide the question.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
silent = np.zeros(16000, dtype=np.int16)
for i in range(3):
    out = D / ('noise_floor_probe_%d.npz' % i)
    out.unlink(missing_ok=True)
    try:
        replay_trial(str(out), 'room_v1_20261026b', str(D / 'rewired_512_20261026.json'), silent,
                     bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        print('probe %d raised %r' % (i, exc))
        continue
    mic = np.asarray(np.load(str(out))['microphone'], float)
    rms = 20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12))
    peak = 20 * np.log10(max(np.max(np.abs(mic)), 1e-12))
    # mid-band share, to tell 'room rumble' from 'broadband input noise'
    S = np.abs(np.fft.rfft(mic - mic.mean())) ** 2
    f = np.fft.rfftfreq(len(mic), 1 / 48828.125)
    mid = S[(f >= 300) & (f < 5000)].sum() / max(S.sum(), 1e-30)
    print('probe %d  rms=%+7.2f dBFS  peak=%+7.2f dBFS  mid-band-share=%.0f%%' % (i, rms, peak, 100 * mid))
PY
