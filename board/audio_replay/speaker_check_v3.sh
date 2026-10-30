#!/bin/bash
# Speaker-path check with NO feedback: direct_only sets the digital gain to 0, so the only thing
# reaching the DAC is the injected 1 kHz tone. If the microphone rises well above the silent gate,
# board -> codec -> speaker -> air -> microphone is live; if it does not, the chain is open.
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


def measure(tag, pcm, seconds, gain_db, direct_only):
    out = DIR / ('spk_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), 'room_v1_20261026b', str(MODEL), pcm, bypass=False, zero_coeff=True,
                     gain_db=gain_db, seconds=seconds, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('SPK %-6s FAILED %s' % (tag, err), flush=True)
        return None
    data = np.load(str(out))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    spec = np.abs(np.fft.rfft(mic * np.hanning(len(mic))))
    f = np.fft.rfftfreq(len(mic), 1.0 / RATE)
    near = (f >= 950) & (f <= 1050)
    other = (f >= 50) & (f <= 20000) & ~near
    rms = 20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12))
    tone = 10*np.log10(max(float(np.mean(spec[near]**2)), 1e-30))
    rest = 10*np.log10(max(float(np.mean(spec[other]**2)), 1e-30))
    print('SPK %-6s mic_rms=%6.1f dBFS  peak=%6.1f  1kHz=%7.1f dB  rest=%7.1f dB  1kHz-over-rest=%+5.1f dB  %s'
          % (tag, rms, 20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)), tone, rest, tone-rest,
             err or 'ok'), flush=True)
    return rms, tone, rest


n = int(1.5 * RATE)
t = np.arange(n) / RATE
tone = 0.3 * np.sin(2*np.pi*1000.0*t)
pcm_tone = np.round(tone * 32767).astype(np.int16)
silent = np.zeros(n, dtype=np.int16)

a = measure('silent', silent, 1.6, -8.0, True)
b = measure('tone', pcm_tone, 1.6, -8.0, True)
if a and b:
    print('SPEAKER_PATH %s: microphone rose %.1f dB with the tone'
          % ('LIVE' if b[0] - a[0] > 6.0 else 'OPEN', b[0] - a[0]), flush=True)
PY
