#!/bin/bash
# Analyse exactly the three files that tone_arms_v3.sh wrote in ONE round.
# All the eligibility rules live in tone_round_guard.py, which is unit-tested off-board by
# test_tone_round_guard.py, so the checks that guard a real round are the same checks C reviewed.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_wide
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import sys
from pathlib import Path

DIR = Path('/home/xilinx/jupyter_notebooks/base/audio/audio_wide')
sys.path.insert(0, str(DIR))
from tone_round_guard import load_round, validate, three_point

MANIFEST = DIR / 'tone_round.json'
try:
    man, rows = load_round(MANIFEST)
except ValueError as exc:
    print('TONE_FAIL', exc)
    sys.exit(1)

problems = validate(rows)
if problems:
    print('TONE_FAIL refusing to compute a depth:')
    for p in problems:
        print('  -', p)
    sys.exit(1)

tone = float(man.get('tone_hz') or 322.0)
tp = three_point(rows, tone)
for tag, lv in tp['levels'].items():
    print('TONE_%s mic@%.0f=%.2f pred@%.0f=%.2f residual@%.0f=%.2f'
          % (tag, tone, lv['mic'], tone, lv['pred'], tone, lv['residual']))
print('TONE_THREE cancel-vs-bypass: CD(%.0f)=%+.2f dB residual depth (model fit, NOT benefit); '
      'loop_boost=%+.2f dB (bypass mic - open mic, the audible-benefit scale); '
      'acoustic_difference=%+.2f dB (= loop_boost + overshoot %+.2f, NOT benefit)'
      % (tone, tp['cd_322_db'], tp['loop_boost_db'], tp['acoustic_difference_db'], tp['overshoot_db']))
print('TONE_VERDICT %s (rule: acoustic_difference >= loop_boost - 1.5 dB and |overshoot| <= 1.5 dB)'
      % ('cancellation_holds' if (tp['acoustic_difference_db'] >= tp['loop_boost_db'] - 1.5
                                  and abs(tp['overshoot_db']) <= 1.5) else 'cancellation_fails_rule'))
print('TONE_NOTE round %s confirmation %s' % (man.get('round_id'), man.get('operator_confirmation')))
PY
