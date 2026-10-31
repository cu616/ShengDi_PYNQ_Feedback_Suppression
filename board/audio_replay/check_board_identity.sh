#!/bin/bash
# What is actually on the board: file bytes versus the driver's pinned expectations.
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
sha256sum "$D/audio_replay.bit" "$D/audio_replay.hwh" "$D/replay_trial.py" "$D/manifest.json"
grep -n "EXPECTED_BIT_SHA256\|EXPECTED_HWH_SHA256" "$D/replay_trial.py" | head -4
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path
D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
man = json.loads((D / 'manifest.json').read_text())
print('manifest bit:', man['hashes']['audio_replay.bit'][:16])
print('manifest drv:', man['hashes']['replay_trial.py'][:16])
PY
