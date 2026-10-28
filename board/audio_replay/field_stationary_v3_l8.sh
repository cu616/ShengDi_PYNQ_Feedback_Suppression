#!/bin/bash
# SUPERSEDED by field_stationary_v3.sh (2026-10-28): that script gates the branch, requires an operator
# confirmation token and stops after a protection event. This file is kept only for the
# 2026-10-27 evidence trail and must not be used for new runs.
# SUPERSEDED by field_stationary_v3.sh (2026-10-28): that script gates the branch, requires an operator
# confirmation token and stops after a protection event. This file is kept only for the
# 2026-10-27 evidence trail and must not be used for new runs.
# Field window, stationary-source arms, on the v3 (wide-residual) package.
# Order: input gate (zero output) -> zero-coefficient arm -> candidate arm.
# Same board-generated white noise (seed 4242, -20 dBFS) for both arms, identical gain/volume.
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
GAIN_DB = -8.0


def load_meta(out):
    data = np.load(str(out))
    return data, json.loads(str(data['metadata_json']))


def report(tag, out, err):
    if not out.is_file():
        print('ARM %-5s FAILED %s' % (tag, err), flush=True)
        return None
    _, meta = load_meta(out)
    data = np.load(str(out))
    mic = np.asarray(data['microphone'], dtype=np.float64)
    spec = np.abs(np.fft.rfft(mic * np.hanning(len(mic))))
    f = np.fft.rfftfreq(len(mic), 1.0 / RATE)
    band = (f >= 300) & (f <= 360)
    allb = (f >= 50) & (f <= 20000)
    share = float(np.sum(spec[band] ** 2) / max(float(np.sum(spec[allb] ** 2)), 1e-30))
    status = int(meta.get('capture_status') or 0)
    print('ARM %-5s stop=%-9s frames=%6d mic=%6.1f peak=%6.1f clip=%d bandshare=%.4f (%6.1f dB) '
          'bit22=%d rsat=%d psat=%d gsat=%d msat=%d bit_exact=%s wide=%s'
          % (tag, meta.get('stop_reason'), int(meta.get('completed_frames') or 0),
             20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
             20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
             int(np.count_nonzero(np.abs(mic) >= 0.999)), share, 10*np.log10(max(share, 1e-12)),
             (status >> 22) & 1, meta.get('residual_saturations'), meta.get('prediction_saturations'),
             meta.get('gain_saturations'), meta.get('mix_saturations'),
             (meta.get('verification') or {}).get('bit_exact'),
             (meta.get('verification') or {}).get('wide_residual_frames')), flush=True)
    return dict(tag=tag, stop=meta.get('stop_reason'), frames=meta.get('completed_frames'),
                mic_rms_dbfs=20*np.log10(max(float(np.sqrt(np.mean(mic**2))), 1e-12)),
                mic_peak_dbfs=20*np.log10(max(float(np.max(np.abs(mic))), 1e-12)),
                mic_clip=int(np.count_nonzero(np.abs(mic) >= 0.999)),
                band_share=share, band_share_db=10*np.log10(max(share, 1e-12)),
                input_full_scale=bool((status >> 22) & 1),
                residual_saturations=meta.get('residual_saturations'),
                prediction_saturations=meta.get('prediction_saturations'),
                gain_saturations=meta.get('gain_saturations'),
                mix_saturations=meta.get('mix_saturations'),
                verification=meta.get('verification'), path=str(out),
                capture_status=status)


def run(tag, pcm, zero, bypass=False, seconds=2.2, gain_db=GAIN_DB, hp=40, direct_only=False):
    out = DIR / ('wide_%s_%d.npz' % (tag, time.time_ns()))
    err = None
    try:
        replay_trial(str(out), FIXTURE, str(MODEL), pcm, bypass=bypass, zero_coeff=zero,
                     gain_db=gain_db, seconds=seconds, hp_volume=hp,
                     speaker_confirmed=True, local_capture_confirmed=True,
                     direct_only=direct_only)
    except Exception as exc:
        err = repr(exc)[:200]
    return report(tag, out, err)


# --- input gate: direct_only sets the digital gain to 0, so the microphone is measured with
# --- no output at all (a silent source is still required; zeros are used).
gate = run('gate', np.zeros(2000, dtype=np.int16), zero=True, seconds=0.6, direct_only=True)
if gate:
    ok = -60.0 < gate['mic_peak_dbfs'] < -6.0
    print('GATE %s peak=%.1f dBFS (need -60 < peak < -6)' % ('PASS' if ok else 'FAIL',
                                                             gate['mic_peak_dbfs']), flush=True)
else:
    ok = False
    print('GATE FAIL (no capture)', flush=True)

if ok:
    n = int(2.0 * RATE)
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x = x / max(np.max(np.abs(x)), 1e-9) * (10 ** (-8.0 / 20))
    pcm = np.round(x * 32767).astype(np.int16)
    a = run('zero', pcm, zero=True)
    b = run('cand', pcm, zero=False)
    if a and b:
        print('STATIONARY_SUMMARY share_zero=%.4f share_cand=%.4f delta_db=%+.1f'
              % (a['band_share'], b['band_share'], a['band_share_db'] - b['band_share_db']),
              flush=True)
else:
    print('STATIONARY_SKIPPED gate failed', flush=True)
PY

