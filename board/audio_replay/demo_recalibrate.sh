#!/bin/bash
# Demo entry: one-click recalibration, then a same-voice A/B on the physical switch.
#
# Why this is the piece worth filming: the recalibration is machine-only. The board plays its own
# excitation, so nobody has to be quiet on cue or start speaking at the right instant; the operator
# starts one command and the board measures, refits and accepts or rejects the new model by itself.
#
# What the camera follows:
#   PHASE 1  recalibration, no human action (~90 s)
#   PHASE 2  speech with the freshly fitted model, canceller ON
#   PHASE 3  the same voice with SW0 UP (forced bypass) - same gain, same geometry, same person
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
cd $D || exit 1

echo "DEMO_PHASE 1  recalibration (machine only - nobody needs to be quiet on cue)"
./recalibrate_oneclick.sh
if [ $? -ne 0 ]; then
  echo "DEMO_STOP  recalibration failed. Nothing was switched; the deployed model still runs."
  exit 1
fi
echo "DEMO_CUE   recalibration accepted - the board now runs the freshly fitted model"

echo "DEMO_PHASE 2  speech, canceller ON. Operator: stand 20 cm from the microphone and talk normally."
echo "DEMO_CUE   say_now - keep talking for 20 seconds"
/usr/local/share/pynq-venv/bin/python - cancel <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
model = D / 'model_recalibrated.json'
if not model.is_file():
    print('DEMO_STOP  model_recalibrated.json is missing; run the recalibration first')
    sys.exit(1)
out = D / ('demo_speech_%s.npz' % ('bypass' if sys.argv[1] == 'bypass' else 'cancel'))
out.unlink(missing_ok=True)
out.with_suffix('.status.json').unlink(missing_ok=True)
silent = np.zeros(16000, dtype=np.int16)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(model), silent, bypass=(sys.argv[1] == 'bypass'),
                 zero_coeff=False, gain_db=-8.0, seconds=20.0, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    print('DEMO_STOP  capture raised %r' % (exc,))
    sys.exit(1)
cap = np.load(str(out))
meta = json.loads(str(cap['metadata_json']))
mic = np.asarray(cap['microphone'], float)
print('DEMO_ARM   %s  stop=%s  mic_rms=%+.2f dBFS  capture_status=0x%08x'
      % (sys.argv[1], meta.get('stop_reason'),
         20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12)), int(meta.get('capture_status') or 0)))
PY

echo "DEMO_PHASE 3  the switch. Operator: flip SW0 UP now, then keep talking normally."
echo "DEMO_CUE   switch_up - same voice, same gain, canceller forced off"
sleep 2
/usr/local/share/pynq-venv/bin/python - bypass <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
model = D / 'model_recalibrated.json'
out = D / 'demo_speech_switch_up.npz'
out.unlink(missing_ok=True)
out.with_suffix('.status.json').unlink(missing_ok=True)
try:
    replay_trial(str(out), 'room_v1_20261026b', str(model), np.zeros(16000, dtype=np.int16),
                 bypass=True, zero_coeff=False, gain_db=-8.0, seconds=20.0, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True)
    cap = np.load(str(out))
    meta = json.loads(str(cap['metadata_json']))
    mic = np.asarray(cap['microphone'], float)
    print('DEMO_ARM   switch_up  stop=%s  mic_rms=%+.2f dBFS  capture_status=0x%08x'
          % (meta.get('stop_reason'),
             20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12)), int(meta.get('capture_status') or 0)))
except Exception as exc:
    print('DEMO_STOP  the switch arm raised %r' % (exc,))
PY

echo "DEMO_END   flip SW0 back DOWN to return to the cancelling configuration"
echo "DEMO_NOTE  the two mic_rms values above are one short window each; they are evidence, not a claim"
echo "DEMO_NOTE  of audible benefit. Do not state a benefit number from them."
