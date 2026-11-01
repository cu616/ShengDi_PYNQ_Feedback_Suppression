#!/bin/bash
# Cross-check the physical buttons with the vendor base overlay.
# If the base overlay's button GPIO also sees nothing while pressing, the problem is physical (polarity or
# the board), not our block design.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import time

from pynq import Overlay

base = Overlay('/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit')
names = sorted(base.ip_dict.keys())
print('BASE_IPS', names)
btns = [n for n in names if 'btn' in n.lower() or 'button' in n.lower()]
print('BASE_BTN_IPS', btns)
if btns:
    from pynq import MMIO
    info = base.ip_dict[btns[0]]
    print('BASE_BTN_INFO', {k: info[k] for k in ('phys_addr', 'type') if k in info})
    m = MMIO(info['phys_addr'], 0x1000)
    print('BASE_BTN_POLL press every button in turn for 12 s')
    last = None
    t0 = time.time()
    while time.time() - t0 < 12:
        v = m.read(0) & 0xF
        if v != last:
            print('BASE_BTN %5.1fs 0x%X' % (time.time() - t0, v))
            last = v
        time.sleep(0.02)
PY
