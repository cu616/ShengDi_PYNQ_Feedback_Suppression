#!/bin/bash
# Run C's official entry under sudo with the XRT environment, adapter check with the bootstrap model.
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/frozen2 || exit 1
SHA=$(sha256sum bootstrap-model.json | cut -d' ' -f1)
echo "MODEL_SHA $SHA"
if [ "${1:-}" = "check" ]; then
    bash recal_entry.sh --check 2>&1 | tail -6
else
    bash recal_entry.sh --adapter-check --model bootstrap-model.json --model-sha256 "$SHA" 2>&1 | tail -40
fi
