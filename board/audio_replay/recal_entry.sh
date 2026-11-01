#!/bin/bash
# C-owned ONLY product entry. No legacy acoustic workflow is invoked here.
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
for profile in /etc/profile.d/xrt_setup.sh /etc/profile.d/boardname.sh; do
    if [ -f "$profile" ]; then set +u; . "$profile"; set -u; fi
done
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
PYTHON="${SHENGDI_PYTHON:-/usr/local/share/pynq-venv/bin/python}"
exec "$PYTHON" "$HERE/recal_product.py" --base "$HERE" "$@"
