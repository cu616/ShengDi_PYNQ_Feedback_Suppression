#!/bin/bash
# Decisive check: does the codec work at all through PYNQ's own audio path?
# If stock audio records/plays fine, our driver's init sequence is at fault. If stock audio also fails,
# the codec or the overlay is at fault and no register work will help.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import numpy as np

print('=== stock PYNQ audio path ===')
try:
    from pynq.lib.audio import Audio
    a = Audio('/home/xilinx/jupyter_notebooks/base/audio/audio_switch/audio_replay.bit')
    info = a.info()
    print('STOCK_INFO', {k: info[k] for k in list(info)[:8]})
    print('STOCK dir', [n for n in dir(a) if not n.startswith('_')])
    # try a short record through the stock path
    try:
        a.record(0.5).wait()
        buf = a.buffer
        print('STOCK_RECORD ok frames=%s peak=%.4f' % (len(buf), float(np.max(np.abs(buf)))))
    except Exception as exc:
        print('STOCK_RECORD_FAIL %r' % (exc,))
except Exception as exc:
    print('STOCK_UNAVAILABLE %r' % (exc,))
PY
