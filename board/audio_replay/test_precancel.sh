#!/bin/bash
# Prove the b6107bc prepare cancel fix, without touching C's frozen package.
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export PYTHONUNBUFFERED=1
BASE=/home/xilinx/jupyter_notebooks/base/audio
rm -rf "$BASE/frozen3"
cp -a "$BASE/frozen2" "$BASE/frozen3"
cp /tmp/hw_api_new.py "$BASE/frozen3/hw_api.py"
echo "TEST_HWAPI $(sha256sum "$BASE/frozen3/hw_api.py" | cut -c1-16)"
cat > /tmp/precancel_test.py <<'PY'
import json
import threading
import sys
sys.path.insert(0, "/home/xilinx/jupyter_notebooks/base/audio/frozen3")
from hw_api import create_product
cfg = {"package_dir": "/home/xilinx/jupyter_notebooks/base/audio/frozen3",
       "fixture": "room_v1_20261026b", "hp_volume": 40, "aux_db": 0.0,
       "model_path": "/home/xilinx/jupyter_notebooks/base/audio/frozen3/bootstrap-model.json",
       "run_dir_root": "/home/xilinx/jupyter_notebooks/base/audio/frozen3/truns"}
p = create_product(cfg)
ev = threading.Event()
ev.set()
r = p.perform({"op": "prepare", "request_id": "pc1", "scene_id": "pc"}, ev)
print("PRECANCEL_PREP " + json.dumps({k: r.get(k) for k in ("ok", "status", "reason", "never_armed_again")},
                                     ensure_ascii=False))
PY
/usr/local/share/pynq-venv/bin/python /tmp/precancel_test.py 2>&1 | tail -5
