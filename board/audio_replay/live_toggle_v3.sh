#!/bin/bash
# Live algorithm switch for the demo: ONE armed run in which the canceller is toggled on and off
# by writing control[1] (bypass) from a background thread, so the listener hears cancellation and
# plain amplification back to back with no gap between runs.
#
# Why this is safe for the frozen payload:
#   - the PL takes bypass directly from control[1] every frame (.bypass(control[1]) in the RTL);
#   - the fault conditions cover changing the gain field, the frame limit, writing source or
#     coefficients, and config errors -- they do NOT cover control[1];
#   - nothing in the bitstream, the driver or v3/manifest.json changes. This is a DEMO entry that
#     calls the existing driver, not part of the v3 payload.
#
# Parameters come from /home/xilinx/live_toggle.txt, one per line:
#   period=2.0     seconds between toggles
#   total=20       total run length in seconds
#   gain_db=-8     must match the driver call below
#   start_bypass=0 0 = begin with cancellation on, 1 = begin bypassed
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
TOKEN=/home/xilinx/OPERATOR_READY
if [ ! -s "$TOKEN" ]; then echo "NO_OPERATOR_CONFIRMATION: refusing to arm"; exit 3; fi
CONF=$(cat "$TOKEN"); rm -f "$TOKEN"
echo "OPERATOR_CONFIRMATION: $CONF"
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$CONF" <<'PY'
import json
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial, trial_parameters

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
MODEL = DIR / 'rewired_512_20261026.json'
FIXTURE = 'room_v1_20261026b'
CONF = sys.argv[1]

cfg = {'period': 2.0, 'total': 20.0, 'gain_db': -8.0, 'start_bypass': 0}
cfgfile = Path('/home/xilinx/live_toggle.txt')
if cfgfile.is_file():
    for line in cfgfile.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        if k.strip() in cfg:
            cfg[k.strip()] = float(v) if k.strip() != 'start_bypass' else int(float(v))
print('LIVE_CFG', json.dumps(cfg))

gain_q12, budget = trial_parameters(cfg['gain_db'], cfg['total'])


def control_phys_addr():
    """Read the AXI-GPIO base address from the .hwh without programming the PL.

    Opening a second Overlay would reconfigure the PL and kill the running trial, so the address is
    parsed out of the hand-off file instead. In the hwh each register block is a MEMRANGE element
    carrying INSTANCE="audio_control" and BASEVALUE="0x...".
    """
    text = (DIR / 'audio_replay.hwh').read_text(errors='replace')
    for pattern in (r'<MEMRANGE[^>]*INSTANCE="audio_control"[^>]*BASEVALUE="(0x[0-9A-Fa-f]+)"',
                    r'<MEMRANGE[^>]*BASEVALUE="(0x[0-9A-Fa-f]+)"[^>]*INSTANCE="audio_control"'):
        m = re.search(pattern, text)
        if m:
            return int(m.group(1), 16)
    raise RuntimeError('audio_control base address not found in audio_replay.hwh')


from pynq import MMIO  # noqa: E402  (imported late so the address parse fails fast)

state = {'running': False, 'events': []}


def toggler():
    ctrl = MMIO(control_phys_addr(), 0x1000)
    bypass = int(cfg['start_bypass'])
    t0 = time.monotonic()
    time.sleep(0.35)                      # let the driver arm first
    while state['running']:
        ctrl.write(0, 1 | (bypass << 1) | (gain_q12 << 16))
        t = time.monotonic() - t0
        state['events'].append((round(t, 2), bypass))
        print('TOGGLE %6.2fs bypass=%d (cancellation %s)' % (t, bypass, 'OFF' if bypass else 'ON'))
        bypass ^= 1
        for _ in range(int(cfg['period'] * 10)):
            if not state['running']:
                return
            time.sleep(0.1)


def before_start():
    state['running'] = True
    threading.Thread(target=toggler, daemon=True).start()
    return True


out = DIR / ('live_toggle_%d.npz' % time.time_ns())
err = None
try:
    replay_trial(str(out), FIXTURE, str(MODEL), np.zeros(1000, dtype=np.int16), bypass=False,
                 zero_coeff=False, gain_db=cfg['gain_db'], seconds=cfg['total'], hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, before_start=before_start)
except Exception as exc:
    err = repr(exc)[:200]
finally:
    state['running'] = False

print('LIVE error:', err)
if out.is_file():
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    st = int(meta.get('capture_status') or 0)
    print('LIVE stop=%-11s frames=%d bit22=%d events=%d'
          % (meta.get('stop_reason'), int(meta.get('completed_frames') or 0), (st >> 22) & 1,
             len(state['events'])))
    print('LIVE_TIMELINE', json.dumps(state['events']))
    # the timeline is saved next to the capture so the edit can align picture with the switch
    Path(str(out).replace('.npz', '.timeline.json')).write_text(
        json.dumps({'period': cfg['period'], 'total': cfg['total'], 'gain_q12': gain_q12,
                    'events': state['events'], 'stop_reason': meta.get('stop_reason'),
                    'bit22': (st >> 22) & 1}, indent=2))
    print('LIVE_TIMELINE_SAVED', str(out).replace('.npz', '.timeline.json'))
PY
