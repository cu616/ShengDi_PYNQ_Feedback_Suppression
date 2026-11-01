#!/bin/bash
# Fit a candidate from an existing 50 cm calibration packet, then run the band comparison against it.
# This is the captain's "key feedback band" experiment: same frozen excitation, three arms, band by band,
# with a model that was actually fitted for this geometry.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
REPO=/home/xilinx/shengdi_repo
cd $D || exit 1

RUN=${1:-}
if [ -z "$RUN" ]; then
  RUN=$(ls -1dt run_* 2>/dev/null | head -1)
fi
echo "BAND_SOURCE_RUN $RUN"
ls -1 "$D/$RUN" | grep -c '^seg_' | sed 's/^/BAND_SEGMENTS /'

/usr/local/share/pynq-venv/bin/python - "$D" "$REPO" "$RUN" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

D = Path(sys.argv[1]); REPO = Path(sys.argv[2]); RUN = sys.argv[3]
pkt = D / RUN
out = D / ('model_50cm_%s.json' % RUN.replace('run_', ''))
proc = subprocess.run([sys.executable, str(REPO / 'scripts/fit_newlayout_candidate.py'),
                       '--packet-dir', str(pkt), '--out-model', str(out),
                       '--out-dir', '/home/xilinx/fit50_' + RUN, '--fixture-id', 'room_v1_20261026b'],
                      capture_output=True, text=True)
print('BAND_FIT rc=%d' % proc.returncode)
if proc.returncode != 0:
    print((proc.stdout or proc.stderr)[-800:])
    sys.exit(1)
m = json.loads(out.read_text(encoding='utf-8'))
import numpy as np
c = np.asarray(m.get('coefficients_q20') or m.get('coefficients'), float) / float(1 << 20)
print('BAND_MODEL %s taps=%d max_h=%.4f L1=%.3f' % (out.name, len(c), float(np.max(np.abs(c))), float(np.sum(np.abs(c)))))
PY
echo "BAND_MODEL_PATH $D/model_50cm_${RUN#run_}.json"
