#!/bin/bash
# Run C's official entry checks against the final package under sudo with the XRT environment.
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/final || exit 1
SHA=$(sha256sum bootstrap-model.json | cut -d' ' -f1)
echo "MODEL_SHA $SHA"
echo "HERE_SHA $(sha256sum hw_api.py | cut -c1-16)"
echo "=== CHECK ==="
bash recal_entry.sh --check 2>&1 | tail -4
echo "=== ADAPTER ==="
bash recal_entry.sh --adapter-check --model bootstrap-model.json --model-sha256 "$SHA" 2>&1 | tail -6
