#!/bin/bash
# Board-owned environment; startup never loads an overlay or starts audio.
set -eo pipefail
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
exec /usr/local/share/pynq-venv/bin/python "$(dirname "$0")/click_panel.py" "$@"
