#!/bin/bash
# Can the ADC-side analog gain be changed on this board at all?
# The driver exposes only hp_volume (output). The codec is an ADAU1761 on PYNQ-Z2; its input PGA is
# programmed over I2C. This probe only inspects what is reachable - it changes nothing.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import inspect

print('=== pynq audio class surface ===')
try:
    from pynq.lib import audio as A
    src = inspect.getsource(A)
    for kw in ('pga', 'PGA', 'adc', 'ADC', 'input_gain', 'mic'):
        hits = [ln.strip() for ln in src.splitlines() if kw in ln]
        print('%-12s %d hits' % (kw, len(hits)))
        for h in hits[:3]:
            print('    ', h[:110])
except Exception as exc:
    print('pynq.lib.audio unavailable:', exc)

print('=== is an I2C bus exposed? ===')
try:
    from pynq import I2C
    print('pynq.I2C available')
except Exception as exc:
    print('pynq.I2C unavailable:', exc)

import subprocess
for cmd in ('ls /dev/i2c-* 2>/dev/null', 'i2cdetect -l 2>/dev/null | head -5'):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print('$', cmd)
    print((r.stdout or r.stderr).strip()[:300] or '(no output)')
PY
