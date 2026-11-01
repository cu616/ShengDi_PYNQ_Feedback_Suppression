#!/bin/bash
# Phase 1 of B's calibration spec: six open-loop segments, one shot, no batching.
#
# Spec (B, 2026-10-31):
#   white noise, seed 4242, RMS-normalised to -19.3 dBFS (NOT peak), peak ceiling 0.80
#   source length == run length == 16384 frames, so first_frame does not eat source frames
#   record ref_rms / mic_rms / mic_over_ref_db / bit22 / prediction+residual+gain saturations / first_frame
#   a segment counts only if bit_exact, bit22=0 and all three saturation counters are 0
# If the target RMS cannot be met under the peak ceiling with this seed, report UNREACHABLE instead of
# clipping the stimulus down to a different level.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from replay_trial_repair import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_io')
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
TARGET_DBFS = -19.3          # RMS, per spec
PEAK_CAP = 0.80
FRAMES = 16384
SEED = 4242
SEGMENTS = 6
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('phase1_' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)

# seconds chosen so int(seconds*RATE) == FRAMES exactly (trial_parameters truncates)
SECONDS = FRAMES / RATE + 1e-4
budget = int(SECONDS * RATE)
assert budget >= FRAMES, 'frame budget too small: %d' % budget
SRC_LEN = budget - 2          # driver requires budget >= len(source)+2

rng = np.random.default_rng(SEED)
x = rng.standard_normal(SRC_LEN)
x -= x.mean()
rms = float(np.sqrt(np.mean(x ** 2)))
scale = 10 ** (TARGET_DBFS / 20.0) / rms
x *= scale
peak = float(np.max(np.abs(x)))
print('PH1_STIM budget=%d source_len=%d target_rms=%.1f dBFS raw_peak=%.4f' % (budget, SRC_LEN, TARGET_DBFS, peak))
if peak > PEAK_CAP:
    print('PH1_UNREACHABLE seed=%d cannot reach %.1f dBFS RMS without exceeding the %.2f peak ceiling '
          '(would need peak %.3f)' % (SEED, TARGET_DBFS, PEAK_CAP, peak))
    raise SystemExit(2)
src = np.rint(x * 32767.0).astype(np.int16)
src_sha = hashlib.sha256(src.tobytes()).hexdigest()
print('PH1_STIM ok source_sha256=%s actual_rms=%.2f dBFS peak=%.2f dBFS'
      % (src_sha[:16], 20 * np.log10(np.sqrt(np.mean((src / 32768.0) ** 2))),
         20 * np.log10(np.max(np.abs(src / 32768.0)))))


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


rows, ok_all = [], True
for i in range(SEGMENTS):
    p = OUT / ('seg_%02d.npz' % i)
    p.unlink(missing_ok=True)
    rec = {'segment': i, 'source_sha256': src_sha}
    try:
        replay_trial(str(p), FIXTURE, str(D / 'model_recalibrated.json'), src, bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=SECONDS, hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        rec['ok'] = False
        rec['error'] = repr(exc)[:160]
        rows.append(rec)
        ok_all = False
        print('PH1_SEG %d FAIL %s' % (i, rec['error']))
        continue
    cap = np.load(str(p))
    meta = json.loads(str(cap['metadata_json']))
    mic, ref = np.asarray(cap['microphone'], float), np.asarray(cap['reference'], float)
    ver = meta.get('verification') or {}
    rec.update({'ok': True, 'stop': meta.get('stop_reason'),
                'first_frame': meta.get('first_frame'),
                'frames': int(len(mic)),
                'ref_rms': rms_db(ref), 'mic_rms': rms_db(mic),
                'mic_over_ref_db': rms_db(mic) - rms_db(ref),
                'bit22': int(meta.get('capture_status') or 0) >> 22 & 1,
                'prediction_saturations': meta.get('prediction_saturations'),
                'residual_saturations': meta.get('residual_saturations'),
                'gain_saturations': meta.get('gain_saturations'),
                'bit_exact': ver.get('bit_exact')})
    good = (rec['stop'] == 'completed' and rec['bit22'] == 0 and rec['bit_exact'] is True
            and not any(rec[k] for k in ('prediction_saturations', 'residual_saturations', 'gain_saturations')))
    rec['ok'] = bool(good)
    ok_all = ok_all and good
    rows.append(rec)
    print('PH1_SEG %d ok=%s ff=%s ref=%.2f mic=%.2f over_ref=%.2f bit22=%d sat=%s/%s/%s exact=%s'
          % (i, good, rec['first_frame'], rec['ref_rms'], rec['mic_rms'], rec['mic_over_ref_db'],
             rec['bit22'], rec['prediction_saturations'], rec['residual_saturations'],
             rec['gain_saturations'], rec['bit_exact']))

summary = {'stamp': STAMP, 'package': 'audio-replay-v3-io', 'fixture': FIXTURE,
           'stimulus': {'seed': SEED, 'target_rms_dbfs': TARGET_DBFS, 'peak_cap': PEAK_CAP,
                        'source_len': SRC_LEN, 'run_frames': budget, 'seconds': SECONDS,
                        'source_sha256': src_sha},
           'segments': rows, 'all_ok': ok_all}
(OUT / 'phase1.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print('PH1_RESULT all_ok=%s dir=%s' % (ok_all, OUT))
print('PH1_RETURN %s' % (OUT / 'phase1.json'))
PY
