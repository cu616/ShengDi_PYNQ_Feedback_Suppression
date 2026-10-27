#!/bin/bash
# Steady-state two-arm with a PURE TONE at the measured |H| peak (322 Hz) instead of white noise.
# Three points, same source level, same gain/volume:
#   open   : digital gain forced to 0  -> the acoustic path alone (no loop)
#   bypass : loop closed, candidate coefficients loaded but NOT subtracted
#   cancel : loop closed, candidate subtraction active
# A tone concentrates all its energy in one bin, so the microphone band level is ~40 dB above the
# room floor even at a level that keeps the input far from clipping.
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
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
TONE_HZ = 322.0
AMP = 0.15


def run(tag, pcm, bypass, direct_only):
    out = DIR / ('tone_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), pcm, bypass=bypass, zero_coeff=False,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    if not out.is_file():
        print('TONE %-6s FAILED %s' % (tag, err), flush=True)
        return None
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    ref = np.asarray(data['reference'], dtype=np.float64)
    n = len(mic)
    w = np.hanning(n)
    spec = np.abs(np.fft.rfft(mic * w))
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    near = np.argmin(np.abs(freqs - TONE_HZ))
    tone = 20*np.log10(max(float(spec[near]), 1e-12))
    st = int(meta.get('capture_status') or 0)
    ver = meta.get('verification') or {}
    print('TONE %-6s stop=%-9s frames=%6d mic=%6.1f peak=%6.1f fs=%d 322Hz=%7.2f dB '
          'bit22=%d gsat=%d msat=%d psat=%d rsat=%d wide=%s bitexact=%s'
          % (tag, meta.get('stop_reason'), int(meta.get('completed_frames') or 0),
             20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
             20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
             int(np.count_nonzero(np.abs(mic) >= 0.999)), tone,
             (st >> 22) & 1, meta.get('gain_saturations'), meta.get('mix_saturations'),
             meta.get('prediction_saturations'), meta.get('residual_saturations'),
             ver.get('wide_residual_frames'), ver.get('bit_exact')), flush=True)
    return dict(tag=tag, tone_db=tone, mic=20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
                peak=20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
                fs=int(np.count_nonzero(np.abs(mic) >= 0.999)), stop=meta.get('stop_reason'))


n = int(2.0 * RATE)
t = np.arange(n) / RATE
x = AMP * np.sin(2*np.pi*TONE_HZ*t)
pcm = np.round(x * 32767).astype(np.int16)

o = run('open', pcm, False, True)
b = run('bypass', pcm, True, False)
c = run('cancel', pcm, False, False)
if o and b and c:
    print('TONE_SUMMARY open=%.2f bypass=%.2f cancel=%.2f dB | loop_boost=%+.2f dB | cancel_minus_bypass=%+.2f dB | cancel_minus_open=%+.2f dB'
          % (o['tone_db'], b['tone_db'], c['tone_db'], b['tone_db'] - o['tone_db'],
             c['tone_db'] - b['tone_db'], c['tone_db'] - o['tone_db']), flush=True)
PY
