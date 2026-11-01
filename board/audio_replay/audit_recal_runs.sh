#!/bin/bash
# Audit every recalibration run on the board and classify WHY each one failed.
# Captain's categories: (a) refused by the absolute floor gate before capture, (b) capture clipped or
# SNR too low, (c) fit failed, (d) install refused, (e) post-install verification failed.
# A missing record is reported as UNKNOWN, never guessed.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
pkts = sorted([p for p in D.glob('recal_pkt_*') if p.is_dir()])
print('runs on board:', len(pkts))
for p in pkts:
    raw = sorted(p.glob('raw_*.npz'))
    conv = sorted(p.glob('recal_*.npz'))
    ver = sorted(p.glob('verify_*.npz'))
    rec = p / 'recalibration_receipt.json'
    parts = []
    parts.append('raw=%d conv=%d verify=%d' % (len(raw), len(conv), len(ver)))

    # capture outcome from the raw status files
    stops = []
    for s in sorted(p.glob('raw_*.status.json')):
        try:
            stops.append(json.loads(s.read_text()).get('stop_reason'))
        except Exception:
            stops.append('unreadable')
    if stops:
        bad = [s for s in stops if s not in ('completed', None)]
        parts.append('capture=%s' % ('completed' if not bad else 'stopped:%s' % sorted(set(map(str, bad)))))

    # excitation level actually used (from a raw capture, if any)
    if raw:
        try:
            c = np.load(str(raw[0]))
            m = json.loads(str(c['metadata_json']))
            parts.append('zeros_coeff=%s gain_q12=%s' % (m.get('zero_coeff'), m.get('gain_q12')))
        except Exception:
            parts.append('capture=unreadable')

    if rec.is_file():
        r = json.loads(rec.read_text())
        tp = r.get('three_point') or {}
        parts.append('verdict=%s' % r.get('verdict'))
        parts.append('floor=%s snr=%s override=%s' % (r.get('room_floor_dbfs'), r.get('excitation_snr_db'),
                                                      r.get('floor_gate_overridden')))
        parts.append('arms=%d' % len(r.get('arms') or []))
        if tp:
            parts.append('ac=%.2f over=%.2f' % (tp.get('acoustic_difference_db') or 0,
                                                tp.get('overshoot_db') or 0))
    else:
        parts.append('verdict=NO_RECEIPT')
    print('%-30s %s' % (p.name, ' | '.join(parts)))

cands = sorted(D.glob('model_candidate_*'))
print('candidate models: %d' % len(cands))
for c in cands:
    print('  ', c.name)
PY
