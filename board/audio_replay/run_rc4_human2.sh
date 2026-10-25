#!/bin/bash
# Human-in-the-loop driver, v2: every wait is observable through /home/xilinx/session_state.json
# so A can poll it over SSH instead of relying on buffered stdout.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-r4 || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import builtins
import json
import pathlib
import time

here = pathlib.Path.cwd()
STATE = pathlib.Path('/home/xilinx/session_state.json')
ANSWER = pathlib.Path('/home/xilinx/hearing_answer')
GO = pathlib.Path('/home/xilinx/go_voice')
WAIT_SECONDS = 900

LAYOUT = ('source-mic 15 cm, microphone on desk, speaker upright facing the microphone at 0.5 m, '
          'listener 0.5 m in front of the speaker; working point -14 dB, phone AGC off')
queue = [LAYOUT]
seq = {'hearing': 0, 'real': 0, 'trial': 0}


def publish(**fields):
    fields.setdefault('ts', round(time.time(), 3))
    STATE.write_text(json.dumps(fields, ensure_ascii=False), encoding='utf8')


def consume(path):
    if path.exists():
        path.unlink()
        return True
    return False


def wait_file(path, need, extra=None, seconds=WAIT_SECONDS):
    consume(path)
    publish(need=need, **(extra or {}))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(encoding='utf8').strip()
            path.unlink()
            publish(need=None, got=text)
            return text
        time.sleep(0.2)
    publish(need='TIMEOUT')
    return None


def ask(prompt=''):
    text = str(prompt)
    if 'HUMAN_LIVE_AND_LISTENING' in text or 'PROXY' in text:
        publish(need=None, step='source', value='HUMAN_LIVE_AND_LISTENING')
        return 'HUMAN_LIVE_AND_LISTENING'
    if 'READY' in text and 'SAME_SCENE' not in text:
        publish(need=None, step='ready')
        return 'READY'
    if 'SAME_SCENE' in text:
        publish(need=None, step='scene')
        return 'SAME_SCENE'
    if 'START' in text:
        # only the real-voice prompt carries this exact phrase; gate prompts also say '人声'
        if '真实人声项此时就位' in text:
            seq['real'] += 1
            # wait for A to say "start speaking" before running the trial
            wait_file(GO, 'GO_VOICE', {'cue': seq['real']})
            publish(need=None, step='speaking', cue=seq['real'])
            for k in range(5, 0, -1):
                publish(need=None, step='speaking', cue=seq['real'], countdown=k)
                time.sleep(1)
        publish(need=None, step='start')
        return 'START'
    if 'CLEAR' in text and 'HOWL' in text:
        seq['hearing'] += 1
        value = wait_file(ANSWER, 'HEARING', {'item': seq['hearing']})
        return (value or 'TIMEOUT').upper()
    if 'FIXED_SOURCE' in text:
        return 'FIXED_SOURCE_FIXED_GAIN_NO_AGC'
    if 'SOURCE_OFF' in text:
        return 'SOURCE_OFF'
    if queue:
        value = queue.pop(0)
        publish(need=None, step='layout')
        return value
    publish(need=None, step='unhandled', text=text[:60])
    return 'q'


builtins.input = ask
publish(need=None, step='loading')
nb = json.loads((here / 'sprint.ipynb').read_text(encoding='utf8'))
code = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code'][0]
publish(need=None, step='running')
exec(compile(code, 'sprint.ipynb:cell1', 'exec'), {'__name__': '__main__'})
publish(need=None, step='done')
print('RC4_HUMAN_DONE', flush=True)
PY
