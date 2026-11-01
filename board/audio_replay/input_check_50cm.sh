#!/bin/bash
# 50 cm input-headroom check with the 0 dB AUX setting, WITH an audible cue.
# Output stays muted (silent source, no feedback), so this measures only how loud the voice reaches the ADC.
# NOTE: the driver keeps only the LAST 16384 frames (~0.34 s), so the talker must still be speaking at the
# very end of the window. The cue is therefore followed by a 10 s talk window and the caller keeps talking
# through it.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time
from pathlib import Path

import numpy as np

from replay_trial_repair import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
MODEL = D / 'model_50cm_20250511-172202.json'
RATE = 48828.125
TALK_SECONDS = 8.0          # driver keeps the last 16384 frames, so this is generous
CUE_FS = 0.08


def stats(a):
    a = np.asarray(a, float)
    return (float(20 * np.log10(max(np.max(np.abs(a)), 1e-12))),
            float(20 * np.log10(max(np.sqrt(np.mean(a ** 2)), 1e-12))),
            int((np.abs(a) >= 0.999).sum()))


p = D / 'in50_floor.npz'
p.unlink(missing_ok=True)
replay_trial(str(p), 'room_v1_20261026b', str(MODEL), np.zeros(16000, np.int16), bypass=False,
             zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40, speaker_confirmed=True,
             local_capture_confirmed=True, direct_only=True)
fpeak, frms, ffull = stats(np.load(str(p))['microphone'])
print('IN50_FLOOR rms=%.2f dBFS' % frms)

# audible cue: ascending C5-G5-C6 twice
parts = []
for _ in range(2):
    for f in (523.25, 783.99, 1046.50):
        parts.append(np.rint(CUE_FS * np.sin(2 * np.pi * f * np.arange(int(0.16 * RATE)) / RATE)
                             * 32767).astype(np.int16))
        parts.append(np.zeros(int(0.05 * RATE), np.int16))
    parts.append(np.zeros(int(0.35 * RATE), np.int16))
cue = np.concatenate(parts)
cp = D / 'in50_cue.npz'
cp.unlink(missing_ok=True)
try:
    replay_trial(str(cp), 'room_v1_20261026b', str(MODEL), cue, bypass=True, zero_coeff=False,
                 gain_db=0.0, seconds=2.6, hp_volume=40, speaker_confirmed=True,
                 local_capture_confirmed=True, direct_only=True)
    print('IN50_CUE_OK peak=%.2f dBFS' % stats(np.load(str(cp))['microphone'])[0])
except Exception as exc:
    print('IN50_CUE_FAIL %r' % (exc,))

print('IN50_CAN_SPEAK >>> three rising notes: talk now and KEEP TALKING until the end <<<')
time.sleep(1.5)
cap = D / 'in50_voice.npz'
cap.unlink(missing_ok=True)
ok_run, err = True, None
try:
    replay_trial(str(cap), 'room_v1_20261026b', str(MODEL), np.zeros(16000, np.int16), bypass=False,
                 zero_coeff=False, gain_db=0.0, seconds=TALK_SECONDS, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
except Exception as exc:
    ok_run, err = False, repr(exc)[:150]

if cap.is_file():
    vpeak, vrms, vfull = stats(np.load(str(cap))['microphone'])
    above = vrms - frms
    print('IN50_RESULT run_ok=%s peak=%.2f rms=%.2f above_floor=%.2f full=%d'
          % (ok_run, vpeak, vrms, above, vfull))
    ok = ok_run and vfull == 0 and above >= 10.0 and vpeak >= -26.0
    print('IN50_%s' % ('PASS' if ok else 'FAIL'))
    if not ok:
        print('IN50_REASON no usable voice' if above < 10.0 else 'IN50_REASON peak too high or clipped')
else:
    print('IN50_FAIL no capture; %s' % err)
PY
