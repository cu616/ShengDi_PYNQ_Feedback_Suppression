#!/bin/bash
# Smoke test for the structured hardware API: every call returns a dict, no terminal parsing needed.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json

from hw_api import Board

b = Board('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
checks = {}
checks['capabilities'] = b.capabilities()
checks['aux_before'] = b.get_aux_gain_db()
checks['model'] = b.load_model('/home/xilinx/jupyter_notebooks/base/audio/audio_switch/model_50cm_20250511-202024.json')
checks['init'] = b.init_and_mute()
checks['switches'] = b.read_switches()
checks['buttons'] = b.read_buttons()
checks['led'] = b.set_led(1)
checks['aux_after'] = b.get_aux_gain_db()
for k, v in checks.items():
    print('API %-14s %s' % (k, json.dumps(v, ensure_ascii=False)[:220]))
ok = all(v.get('ok', True) is not False for k, v in checks.items()
         if k not in ('buttons', 'led', 'aux_before'))
print('API_SMOKE %s' % ('PASS' if ok else 'PARTIAL'))
PY
