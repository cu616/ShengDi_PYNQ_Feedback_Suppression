"""Walk every prompt of the bound package through the driver's routing table.

Pure software: no board, no audio. The package comes from SHENGDI_HUMAN_PKG and the driver from
SHENGDI_DRIVER, so the object under test is the delivered artifact. A missing prompt is a
FAILURE, never a skip.
"""
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DRIVER = pathlib.Path(os.environ.get('SHENGDI_DRIVER') or (HERE / 'run_human_r1.sh'))
PKG = pathlib.Path(os.environ['SHENGDI_HUMAN_PKG']) if os.environ.get('SHENGDI_HUMAN_PKG') else None

if PKG is None or not (PKG / 'sprint_experiment.py').is_file():
    print('BINDING_MISSING sprint_experiment.py (SHENGDI_HUMAN_PKG=%r)'
          % os.environ.get('SHENGDI_HUMAN_PKG'))
    sys.exit(1)
if not DRIVER.is_file():
    print('BINDING_MISSING driver %s' % DRIVER)
    sys.exit(1)

body = DRIVER.read_text(encoding='utf-8').split("<<'PY'\n", 1)[1].split("builtins.input = ask", 1)[0]


class _Path:
    def __init__(self, *a):
        pass

    def exists(self):
        return False

    def read_text(self, **kw):
        return ''

    def unlink(self):
        pass

    def write_text(self, *a, **kw):
        pass


import time  # noqa: E402

ns = {'__name__': 'driver', '__builtins__': __import__('builtins'),
      'json': __import__('json'), 'os': os, 'time': time,
      'pathlib': type('m', (), {'Path': _Path})}
exec(compile(body, str(DRIVER), 'exec'), ns)
ask = ns['ask']
needs = []


def publish(**fields):
    if fields.get('need'):
        needs.append(fields['need'])


def wait_none(path, need, extra=None):
    needs.append(need)
    return None


def wait_go(path, need, extra=None):
    needs.append(need)
    return 'GO'


ns['publish'] = publish
ns['take'] = lambda p: None
ns['wait_file'] = wait_none

prompts = [t.replace('%02d', '03').replace('%s', 'real-voice')
           for t in re.findall(r"ask\('([^']*)'",
                               (PKG / 'sprint_experiment.py').read_text(encoding='utf-8'))]
prompts.append('03 real-voice 此项现场听感：CLEAR / DISTORTED / NO_AMPLIFICATION / HOWL / UNKNOWN：')

EXPECT = [
    ('READY', 'READY', None),
    ('SAME_SCENE', 'SAME_SCENE', None),
    ('一次填写声源-麦克风距离', 'LAYOUT', None),
    ('HUMAN_LIVE_AND_LISTENING', 'HUMAN_LIVE_AND_LISTENING', None),
    ('path-gate', 'START', 'no-go'),
    ('真实人声项此时就位', 'START', 'GO_VOICE'),
    ('此项现场听感', 'TIMEOUT', 'HEARING'),
    ('FIXED_SOURCE_FIXED_GAIN_NO_AGC', '', None),
    ('开/关差别', 'unknown', 'LISTENER_REPORT'),
    ('SOURCE_OFF', 'SOURCE_OFF', None),
]

print('bound package %s' % PKG)
print('prompts found %d' % len(prompts))
failures = 0
for marker, value, need in EXPECT:
    match = next((p for p in prompts if marker in p), None)
    if match is None:
        print('FAIL    prompt containing %r not found in the bound package' % marker)
        failures += 1
        continue
    needs.clear()
    ns['queue'] = ['LAYOUT']
    if marker == '真实人声项此时就位':
        ns['wait_file'] = wait_go
    elif marker == '此项现场听感':
        ns['wait_file'] = wait_none
    else:
        ns['wait_file'] = wait_none
    got = ask(match)
    got_need = needs[0] if needs else None
    ok = got == value
    if need == 'no-go':
        ok = ok and 'GO_VOICE' not in needs
    elif need is not None:
        ok = ok and got_need == need
    if not ok:
        failures += 1
    print('%s  %-22s -> %-24r need=%s' % ('OK  ' if ok else 'FAIL', marker[:22], got, got_need))

print('\nROUTING_RESULT', 'PASS' if failures == 0 else 'FAIL (%d)' % failures)
sys.exit(0 if failures == 0 else 1)
