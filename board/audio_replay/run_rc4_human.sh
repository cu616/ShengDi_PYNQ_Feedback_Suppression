#!/bin/bash
# Human-in-the-loop driver for C's RC0.1-r4 sprint.
#
# Differences from run_rc4_auto.sh:
#   * hearing prompts are NOT answered automatically. The driver waits for an answer file
#     (/home/xilinx/hearing_answer) so A can relay the listener's judgement from chat.
#   * the "source" prompt is answered HUMAN_LIVE_AND_LISTENING (a person is present).
#   * SELFTEST=1 exercises the answer channel without touching the audio path.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/c-sprint-rc01-r4 || exit 1
# mode: "run" (default) or "selftest"; passed through the environment because the
# heredoc below cannot read $1 directly.
MODE="${1:-run}" /usr/local/share/pynq-venv/bin/python - <<'PY'
import builtins
import json
import os
import pathlib
import time

here = pathlib.Path.cwd()
ANSWER = pathlib.Path('/home/xilinx/hearing_answer')
WAIT_SECONDS = 240

LAYOUT = ('source-mic 15 cm, microphone on desk, speaker upright facing the microphone at 0.5 m, '
          'listener 0.5 m in front of the speaker; working point -14 dB, phone AGC off')
queue = [LAYOUT]
seq = {'hearing': 0, 'real': 0}


def wait_for_answer(tag):
    """Block until A writes the listener's judgement, then consume the file."""
    if ANSWER.exists():
        ANSWER.unlink()
    print('HEARING_WAIT %s' % tag, flush=True)
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if ANSWER.exists():
            value = ANSWER.read_text(encoding='utf8').strip().upper()
            ANSWER.unlink()
            print('HEARING_GOT %s -> %s' % (tag, value), flush=True)
            return value
        time.sleep(0.25)
    print('HEARING_TIMEOUT %s' % tag, flush=True)
    return 'TIMEOUT'


def ask(prompt=''):
    text = str(prompt)
    if 'HUMAN_LIVE_AND_LISTENING' in text or 'PROXY' in text:
        print('ASK -> HUMAN_LIVE_AND_LISTENING', flush=True)
        return 'HUMAN_LIVE_AND_LISTENING'
    if 'READY' in text and 'SAME_SCENE' not in text:
        print('ASK -> READY', flush=True)
        return 'READY'
    if 'SAME_SCENE' in text:
        print('ASK -> SAME_SCENE', flush=True)
        return 'SAME_SCENE'
    if 'START' in text:
        if 'real' in text.lower() or 'voice' in text.lower() or '人声' in text:
            seq['real'] += 1
            print('REAL_VOICE_CUE %d 现在开始讲话，5 秒' % seq['real'], flush=True)
            for k in range(5, 0, -1):
                print('  SPEAK_%02d' % k, flush=True)
                time.sleep(1)
        print('ASK -> START', flush=True)
        return 'START'
    if 'CLEAR' in text and 'HOWL' in text:
        seq['hearing'] += 1
        return wait_for_answer('item%d' % seq['hearing'])
    if 'FIXED_SOURCE' in text:
        return 'FIXED_SOURCE_FIXED_GAIN_NO_AGC'
    if 'SOURCE_OFF' in text:
        return 'SOURCE_OFF'
    if queue:
        value = queue.pop(0)
        print('ASK -> %s' % value[:40], flush=True)
        return value
    print('ASK_UNHANDLED -> q : %s' % text[:70], flush=True)
    return 'q'


if os.environ.get('MODE') == 'selftest':
    # prove the answer channel end to end without running any audio
    import threading

    def seed():
        time.sleep(2.0)
        ANSWER.write_text('CLEAR', encoding='utf8')

    threading.Thread(target=seed, daemon=True).start()
    got = wait_for_answer('selftest')
    print('CHANNEL_SELFTEST', 'PASS' if got == 'CLEAR' and not ANSWER.exists() else 'FAIL',
          flush=True)
    raise SystemExit(0)

builtins.input = ask
nb = json.loads((here / 'sprint.ipynb').read_text(encoding='utf8'))
code = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code'][0]
print('RUNNING_CELL1_CHARS', len(code), flush=True)
exec(compile(code, 'sprint.ipynb:cell1', 'exec'), {'__name__': '__main__'})
print('RC4_HUMAN_DONE', flush=True)
PY
