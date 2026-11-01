#!/bin/bash
# Is the status-word path itself alive? Flip SW0 and watch bit 24/25. If those move while the button bits
# do not, the sync+status path is fine and only the btn port is disconnected.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time

from pynq import MMIO, Overlay

D = '/home/xilinx/jupyter_notebooks/base/audio/audio_io'
ov = Overlay(D + '/audio_replay.bit')
status = MMIO(ov.ip_dict['audio_calibrate_cmd']['phys_addr'], 0x1000)
print('SW_PATH start=0x%08X  (flip SW0 now)' % (status.read(8) & 0xFFFFFFFF))
last = None
t0 = time.time()
while time.time() - t0 < 15:
    w = status.read(8) & 0xFFFFFFFF
    if w != last:
        print('SW_PATH %5.1fs 0x%08X  sw0_raw=%d sw0_sync=%d sw1=%d btn=%s'
              % (time.time() - t0, w, (w >> 25) & 1, (w >> 24) & 1, (w >> 23) & 1,
                 [(w >> (27 + i)) & 1 for i in range(4)]))
        last = w
    time.sleep(0.02)
print('SW_PATH done')
PY
