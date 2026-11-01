#!/bin/bash
# Is the overlay actually configured? The codec PLL needs MCLK from the PL, so an unconfigured PL
# produces exactly the "unexpected 50 MHz PLL readback" symptom.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
from pathlib import Path

from pynq import Overlay, PL

print('PL bitfile before load:', getattr(PL, 'bitfile_name', None))
bit = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch/audio_replay.bit')
try:
    ov = Overlay(str(bit))
    print('OVERLAY loaded, bitfile now:', getattr(PL, 'bitfile_name', None))
    ips = sorted(ov.ip_dict.keys())
    print('OVERLAY ips (%d): %s' % (len(ips), ips))
    for want in ('audio_control', 'audio_samples', 'audio_coefficients', 'audio_runtime'):
        print('  has %-18s %s' % (want, want in ov.ip_dict))
except Exception as exc:
    print('OVERLAY_FAIL %r' % (exc,))
PY
