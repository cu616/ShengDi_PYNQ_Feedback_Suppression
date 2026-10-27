#!/bin/bash
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import glob, json
import numpy as np

RATE = 48828.125
TONE = 322.0


def level(x, freqs, spec, f0, halfwidth=2.0):
    band = np.abs(freqs - f0) <= halfwidth
    return 20*np.log10(max(float(np.max(spec[band])), 1e-12))


rows = {}
for path in sorted(glob.glob('/home/xilinx/jupyter_notebooks/base/audio/audio_wide/tone_*_*.npz')):
    tag = path.split('/')[-1].split('_')[1]
    data = np.load(path)
    meta = json.loads(str(data['metadata_json']))
    n = len(data['microphone'])
    w = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1.0/RATE)
    res = {}
    for key, field in (('mic', 'microphone'), ('pred', 'prediction_pcm'), ('residual', 'residual_pcm'),
                       ('ref', 'reference')):
        x = np.asarray(data[field], dtype=np.float64)
        if x.dtype.kind == 'f' and field in ('prediction_pcm', 'residual_pcm'):
            x = x  # already in PCM units
        spec = np.abs(np.fft.rfft(x * w))
        res[key] = level(x, freqs, spec, TONE)
    st = int(meta.get('capture_status') or 0)
    rows[tag] = res
    print('TONE_%s mic@322=%.2f pred@322=%.2f res@322=%.2f ref@322=%.2f bit22=%d stop=%s'
          % (tag, res['mic'], res['pred'], res['residual'], res['ref'], (st >> 22) & 1,
             meta.get('stop_reason')), flush=True)

if {'open', 'bypass', 'cancel'} <= set(rows):
    o, b, c = rows['open'], rows['bypass'], rows['cancel']
    print('TONE_DEPTH bypass_res@322=%.2f cancel_res@322=%.2f -> cancellation_depth=%+.2f dB'
          % (b['residual'], c['residual'], b['residual'] - c['residual']), flush=True)
    print('TONE_MIC bypass_mic@322=%.2f cancel_mic@322=%.2f open_mic@322=%.2f -> cancel_vs_bypass=%+.2f dB, cancel_vs_open=%+.2f dB'
          % (b['mic'], c['mic'], o['mic'], c['mic'] - b['mic'], c['mic'] - o['mic']), flush=True)
PY
