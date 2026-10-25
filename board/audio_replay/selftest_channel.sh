#!/bin/bash
# Exercise the human answer channel only: no overlay, no audio, no sprint.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import pathlib
import threading
import time

ANSWER = pathlib.Path('/home/xilinx/hearing_answer')


def wait_for_answer(tag, seconds=30):
    if ANSWER.exists():
        ANSWER.unlink()
    print('HEARING_WAIT %s' % tag, flush=True)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if ANSWER.exists():
            value = ANSWER.read_text(encoding='utf8').strip().upper()
            ANSWER.unlink()
            print('HEARING_GOT %s -> %s' % (tag, value), flush=True)
            return value
        time.sleep(0.25)
    print('HEARING_TIMEOUT %s' % tag, flush=True)
    return 'TIMEOUT'


def seed():
    time.sleep(2.0)
    ANSWER.write_text('CLEAR', encoding='utf8')


threading.Thread(target=seed, daemon=True).start()
got = wait_for_answer('selftest')
ok = got == 'CLEAR' and not ANSWER.exists()
print('CHANNEL_SELFTEST', 'PASS' if ok else 'FAIL', flush=True)
PY
