#!/bin/bash
# Driver for C's RC0.1-human-r1 (5 items: gate, real-voice, listener-off, gate, listener-on).
#
# Key difference from earlier drivers: the real-voice cue now fires AFTER START returns, i.e.
# after the codec is unmuted and the PL is armed. Catching it before START meant the speaker
# talked into a muted codec.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-human-r1 || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import builtins
import json
import os
import pathlib
import subprocess
import time

here = pathlib.Path.cwd()
STATE = pathlib.Path('/home/xilinx/session_state.json')
ANSWER = pathlib.Path('/home/xilinx/hearing_answer')
WAIT = 900

LAYOUT = ('source-mic 15 cm, microphone on desk, speaker upright facing the microphone at 0.5 m, '
          'listener 0.5 m in front of the speaker; fixed recorded speech source, fixed position '
          'and volume, recorder gain fixed, AGC off; working point -14 dB')
queue = [LAYOUT]
seq = {'hearing': 0, 'trial': 0}


def publish(**fields):
    fields.setdefault('ts', round(time.time(), 3))
    STATE.write_text(json.dumps(fields, ensure_ascii=False), encoding='utf8')


def take(path):
    if path.exists():
        text = path.read_text(encoding='utf8').strip()
        path.unlink()
        return text
    return None


def wait_file(path, need, extra=None):
    take(path)
    publish(need=need, **(extra or {}))
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        value = take(path)
        if value is not None:
            publish(need=None, got=value)
            return value
        time.sleep(0.2)
    publish(need='TIMEOUT')
    return None


def ask(prompt=''):
    text = str(prompt)
    if 'HUMAN_LIVE_AND_LISTENING' in text or 'PROXY' in text:
        publish(step='source', value='HUMAN_LIVE_AND_LISTENING')
        return 'HUMAN_LIVE_AND_LISTENING'
    if 'READY' in text and 'SAME_SCENE' not in text:
        publish(step='ready')
        return 'READY'
    if 'SAME_SCENE' in text:
        publish(step='scene')
        return 'SAME_SCENE'
    if 'START' in text:
        seq['trial'] += 1
        real = '真实人声项此时就位' in text
        if real:
            # the speaker must already be talking when the codec unmutes; wait for A's go,
            # then return START so the 8 s capture happens while the person keeps speaking
            wait_file(pathlib.Path('/home/xilinx/go_voice'), 'GO_VOICE',
                      {'trial': seq['trial'], 'cue': seq['trial']})
        publish(step='start', trial=seq['trial'], real_voice=real)
        return 'START'
    if 'CLEAR' in text and 'HOWL' in text:
        seq['hearing'] += 1
        value = wait_file(ANSWER, 'HEARING', {'item': seq['hearing']})
        return (value or 'TIMEOUT').upper()
    if 'FIXED_SOURCE_FIXED_GAIN_NO_AGC' in text:
        # this round has no listener recordings, so the caller must leave it untested
        publish(step='source-confirmation', value='untested')
        return ''
    if '开/关差别' in text:
        value = wait_file(ANSWER, 'LISTENER_REPORT')
        return value or 'unknown'
    if 'SOURCE_OFF' in text:
        return 'SOURCE_OFF'
    if queue:
        value = queue.pop(0)
        publish(step='layout')
        return value
    publish(step='unhandled', text=text[:60])
    return 'q'


# Wrap the sprint module so the real-voice cue runs right after arm instead of before START.
builtins.input = ask
publish(step='loading')
nb = json.loads((here / 'sprint.ipynb').read_text(encoding='utf8'))
code = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code'][0]
publish(step='running')
try:
    exec(compile(code, 'sprint.ipynb:cell1', 'exec'), {'__name__': '__main__'})
finally:
    publish(step='done')
print('HUMAN_R1_DONE', flush=True)
PY
