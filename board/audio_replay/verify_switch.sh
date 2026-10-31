#!/bin/bash
# Identity + switch check for the v3-sw package (SW0 physical algorithm switch).
#
# It answers two questions with no audible output:
#   1 does the package on the board match its own manifest byte for byte?
#   2 does capture_status[23] follow PYNQ-Z2 SW0? Run it, flip SW0, run it again: the bit must
#     change. That is the only way to prove the physical input is really wired to the design.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path

import numpy as np

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
man = json.loads((DIR / 'manifest.json').read_text())
bad = []
for name, expected in man['hashes'].items():
    p = DIR / name
    got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    if got != expected:
        bad.append((name, expected[:12], (got or 'missing')[:12]))
print('PKG %s | files %d | mismatched %d' % (man['package'], len(man['hashes']), len(bad)))
for b in bad:
    print('  MISMATCH', b)

from replay_trial import replay_trial, verify_paired_bitstream, INPUT_CLIP_BIT

# 1 mixed pair must be refused before any overlay is downloaded
try:
    wrong = DIR / 'wrong_pair.bit'
    wrong.write_bytes((DIR / 'audio_replay.bit').read_bytes() + b'\x00')
    verify_paired_bitstream(wrong)
    print('MIXED_PAIR NOT REFUSED (FAIL)')
except Exception as exc:
    print('MIXED_PAIR refused (= PASS):', repr(exc)[:100])
finally:
    wrong.unlink(missing_ok=True)

# 2 silent bring-up: no output, zero coefficients, 1.2 s.
# The output name is fixed so repeated runs overwrite it, but a FAILED run would leave the
# previous capture in place and it would then be read as if it were this run. Delete both the
# capture and its sidecar first, so a stale file can never be mistaken for fresh evidence.
out = DIR / 'sw_bringup_down.npz'
out.unlink(missing_ok=True)
out.with_suffix('.status.json').unlink(missing_ok=True)
err = None
try:
    replay_trial(str(out), 'room_v1_20261026b', str(DIR / 'rewired_512_20261026.json'),
                 np.zeros(1000, dtype=np.int16), bypass=False, zero_coeff=True, gain_db=-8.0,
                 seconds=1.2, hp_volume=40, speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    err = repr(exc)[:200]
if not out.is_file():
    print('SW_BRINGUP_FAILED', err)
    raise SystemExit(1)
meta = json.loads(str(np.load(str(out))['metadata_json']))
st = int(meta.get('capture_status') or 0)
print('SW_RUN stop=%-11s frames=%d capture_status=0x%08x bit22=%d SW0raw_bit25=%d SW0sync_bit24=%d SW1sync_bit23=%d'
      % (meta.get('stop_reason'), int(meta.get('completed_frames') or 0), st,
         (st >> INPUT_CLIP_BIT) & 1, (st >> 25) & 1, (st >> 24) & 1, (st >> 23) & 1))
print('SW_RUN identity driver=%s bit=%s' % (
    hashlib.sha256(Path(__file__).with_name('replay_trial.py').read_bytes()).hexdigest()[:8]
    if False else 'reported in metadata',
    str(meta.get('bit_sha256', ''))[:8]))
print('SW_MEANING bit24=0 -> SW0 down (cancellation allowed); bit24=1 -> SW0 up (forced bypass)')
PY
