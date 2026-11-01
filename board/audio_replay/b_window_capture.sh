#!/bin/bash
# B's full window: 6 training + 2 validation segments, white noise seed 4242, one shot.
#
# Frame accounting, which is a hard property of the bitstream:
#   run budget B, capture window = last 16384 frames, driver needs len(source) <= B-2
#   first_frame = B - 16384, so valid = len(source) - first_frame = 16386 - 2 - 2 = 16382
# The 2 frames are the hardware pipeline margin (the last two source frames are never played).
# Every segment therefore reports valid_frames = 16382, not 16384.
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
SEED = 4242
WINDOW = 16384            # capture window fixed by the RTL
SOURCELEN = WINDOW + 2    # driver limit: source <= budget-2, budget = window+2
BUDGET = SOURCELEN + 2
PEAK_CAP = 0.80
LEVELS = (-22.0, -19.3, -16.5)
PLAN = [('train', i) for i in range(6)] + [('valid', i) for i in range(2)]
STAMP = time.strftime('%Y%m%d-%H%M%S')
OUT = D / ('bwindow_' + STAMP)
OUT.mkdir(exist_ok=True)
SECONDS = BUDGET / RATE + 1e-6   # epsilon must add <1 frame


def rms_db(a):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(a, float) ** 2)), 1e-12)))


def make_src(level):
    rng = np.random.default_rng(SEED)
    x = rng.standard_normal(SOURCELEN)
    x -= x.mean()
    x *= 10 ** (level / 20.0) / float(np.sqrt(np.mean(x ** 2)))
    peak = float(np.max(np.abs(x)))
    if peak > PEAK_CAP:
        return None, peak
    return np.rint(x * 32767.0).astype(np.int16), peak


chosen, rows = None, []
for level in LEVELS:
    src, raw_peak = make_src(level)
    if src is None:
        print('BW_LEVEL %.1f UNREACHABLE raw_peak=%.4f > %.2f' % (level, raw_peak, PEAK_CAP))
        continue
    src_sha = hashlib.sha256(src.tobytes()).hexdigest()
    print('BW_LEVEL %.1f attempt rms=%.2f peak=%.1f dBFS src_sha=%s'
          % (level, rms_db(src / 32768.0), 20 * np.log10(raw_peak), src_sha[:16]))
    seg_rows, all_ok = [], True
    for kind, i in PLAN:
        p = OUT / ('%s_%02d.npz' % (kind, i))
        p.unlink(missing_ok=True)
        try:
            replay_trial(str(p), FIXTURE, str(D / 'model_recalibrated.json'), src, bypass=False,
                         zero_coeff=True, gain_db=0.0, seconds=SECONDS, hp_volume=40,
                         speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        except Exception as exc:
            all_ok = False
            seg_rows.append({'kind': kind, 'index': i, 'ok': False, 'error': repr(exc)[:140]})
            print('BW_SEG %s%d FAIL %s' % (kind, i, repr(exc)[:80]))
            continue
        cap = np.load(str(p))
        meta = json.loads(str(cap['metadata_json']))
        ref = np.asarray(cap['reference'], float)
        mic = np.asarray(cap['microphone'], float)
        if np.max(np.abs(ref)) > 1.5:
            ref, mic = ref / 32768.0, mic / 32768.0
        status = int(meta.get('capture_status') or 0)
        first = int(meta.get('first_frame') or 0)
        valid = min(len(ref), len(src) - first)
        md = {'first_frame': first, 'dropped_frames': int(meta.get('dropped_frames') or 0),
              'bit22': (status >> 22) & 1, 'capture_status': status,
              'prediction_saturations': meta.get('prediction_saturations'),
              'residual_saturations': meta.get('residual_saturations'),
              'gain_saturations': meta.get('gain_saturations'),
              'source_sha256': src_sha, 'valid_frames': valid,
              'content_kind': 'onboard_excitation', 'level_dbfs': level,
              'kind': kind, 'index': i}
        # rewrite in B's format
        np.savez_compressed(str(p), reference=ref.astype(np.float64),
                            microphone=mic.astype(np.float64),
                            source_pcm16=src, sample_rate_hz=np.float64(RATE),
                            metadata_json=np.str_(json.dumps(md)))
        good = (md['bit22'] == 0 and valid >= WINDOW - 2 and first == BUDGET - WINDOW and
                not any(md[k] for k in ('prediction_saturations', 'residual_saturations', 'gain_saturations')))
        all_ok = all_ok and good
        seg_rows.append({'kind': kind, 'index': i, 'ok': bool(good), **md,
                         'ref_rms': round(rms_db(ref), 2), 'mic_rms': round(rms_db(mic), 2)})
        print('BW_SEG %s%d ok=%s ff=%d valid=%d ref=%.2f mic=%.2f bit22=%d sat=%s/%s/%s'
              % (kind, i, good, first, valid, rms_db(ref), rms_db(mic), md['bit22'],
                 md['prediction_saturations'], md['residual_saturations'], md['gain_saturations']))
    rows.append({'level_dbfs': level, 'source_sha256': src_sha, 'segments': seg_rows, 'all_ok': all_ok})
    if all_ok:
        chosen = level
        print('BW_LEVEL %.1f ACCEPTED' % level)
        break
    print('BW_LEVEL %.1f rejected, trying next' % level)

summary = {'stamp': STAMP, 'seed': SEED, 'window': WINDOW, 'source_len': SOURCELEN,
           'budget': BUDGET, 'peak_cap': PEAK_CAP, 'levels': list(LEVELS), 'chosen_level': chosen,
           'attempts': rows, 'format': 'B: reference/microphone float64 +-1, source_pcm16 int16, '
                                        'sample_rate_hz float, metadata_json with first_frame/dropped_frames/bit22'}
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print('BW_RESULT chosen=%s dir=%s' % (chosen, OUT))
PY
