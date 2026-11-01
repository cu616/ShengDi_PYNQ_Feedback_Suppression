#!/bin/bash
# Fix the calibration excitation level for the 50 cm / 0 dB-AUX configuration, deterministically.
#
# Rule (not a judgement call): with the input stage fixed at 0 dB, raise the excitation until the loop is
# measurable, then stop. "Measurable" = the strongest 1/3-octave loop boost (bypass - open) is at least
# 3 dB, with no full-scale samples in any arm. The first level that satisfies both is written to the
# config file and used from then on by every entry.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_switch || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
from pathlib import Path

import numpy as np

from replay_trial_repair import replay_trial

D = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_switch')
MODEL = D / 'model_50cm_20250511-202024.json'
RATE = 48828.125
SECONDS = 0.3357
LEVELS = (-13.3, -7.3, -4.3)
MIN_BOOST_DB = 3.0
PEAK_CAP = 0.80
FILTER_HZ = (200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000)


def stim(level_db, n):
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x -= x.mean()
    x = x / (np.sqrt(np.mean(x ** 2)) or 1.0) * (10 ** (level_db / 20.0))
    pk = float(np.max(np.abs(x)))
    if pk > PEAK_CAP:
        x *= PEAK_CAP / pk
    return np.rint(x * 32767).astype(np.int16)


def bands(mic):
    n = len(mic)
    spec = np.abs(np.fft.rfft(np.asarray(mic, float) * np.hanning(n))) ** 2
    f = np.fft.rfftfreq(n, 1 / RATE)
    out = {}
    for fc in FILTER_HZ:
        m = (f >= fc / 2 ** (1 / 6)) & (f < fc * 2 ** (1 / 6))
        out[fc] = 10 * np.log10(max(np.mean(spec[m]), 1e-30)) if m.any() else -200.0
    return out


def run(tag, src, bypass, direct, level_label):
    p = D / ('pick_%s_%s.npz' % (level_label, tag))
    p.unlink(missing_ok=True)
    try:
        replay_trial(str(p), 'room_v1_20261026b', str(MODEL), src, bypass=bypass, zero_coeff=False,
                     gain_db=-8.0, seconds=SECONDS, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct)
    except Exception as exc:
        print('PICK_ARM_FAIL level=%s arm=%s %r' % (level_label, tag, exc))
        return None
    cap = np.load(str(p))
    mic = np.asarray(cap['microphone'], float)
    meta = json.loads(str(cap['metadata_json']))
    full = int((np.abs(mic) >= 0.999).sum())
    return {'bands': bands(mic), 'full': full, 'stop': meta.get('stop_reason')}


chosen = None
for lv in LEVELS:
    label = ('%+.1f' % lv).replace('.', 'p')
    src = stim(lv, int(SECONDS * RATE) - 5)
    o = run('open', src, False, True, label)
    b = run('bypass', src, True, False, label)
    if o is None or b is None:
        continue
    boosts = {fc: b['bands'][fc] - o['bands'][fc] for fc in FILTER_HZ}
    best_fc = max(boosts, key=boosts.get)
    clipped = o['full'] + b['full'] > 0
    print('PICK_LEVEL %.1f dBFS best_boost=%+.2f dB at %d Hz clipped=%s'
          % (lv, boosts[best_fc], best_fc, clipped))
    if boosts[best_fc] >= MIN_BOOST_DB and not clipped:
        chosen = (lv, best_fc, boosts[best_fc])
        break

if chosen is None:
    print('PICK_NONE no level in %s gave >= %.1f dB of loop boost without clipping' % (LEVELS, MIN_BOOST_DB))
else:
    lv, fc, boost = chosen
    print('PICK_CHOSEN level=%.1f dBFS strongest_loop_boost=%+.2f dB at %d Hz' % (lv, boost, fc))
    cfg = Path('/home/xilinx/recal_config.txt')
    lines = [ln for ln in cfg.read_text().splitlines() if not ln.startswith('LEVEL_DB=')]
    lines.insert(0, 'LEVEL_DB=%.1f' % lv)
    cfg.write_text('\n'.join(lines) + '\n')
    print('PICK_WRITTEN %s' % cfg)
PY
