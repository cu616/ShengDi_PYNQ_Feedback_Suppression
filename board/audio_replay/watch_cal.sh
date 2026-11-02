#!/bin/bash
# Watch the product state transitions for 2 minutes while the operator performs CAL.
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

p = Path('/home/xilinx/.local/state/shengdi/status.json')
last = None
t0 = time.time()
while time.time() - t0 < 120:
    try:
        raw = p.read_text(encoding='utf-8').strip()
    except Exception:
        raw = ''
    if raw and raw != last:
        last = raw
        try:
            d = json.loads(raw)
            print('WATCH %5.1fs state=%s outcome=%s reason=%s scene=%s' % (
                time.time() - t0, d.get('state'), d.get('outcome'), (d.get('reason') or '')[:60],
                (d.get('scene_id') or '')[:12]))
        except Exception:
            print('WATCH raw %s' % raw[:120])
    time.sleep(0.5)
print('WATCH_DONE')
PY
