"""Walk every prompt of C's human package through the driver's routing table.

Pure software: no board, no audio, no overlay. This is the check that should have run before
the last three field attempts, where the routing was wrong three times in a row.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work')
DRIVER = ROOT / 'run_human_r1.sh'
PACKAGE = ROOT / 'h1' / 'sprint_experiment.py'

# ---------------------------------------------------------------- load the driver's ask()
shell = DRIVER.read_text(encoding='utf-8')
body = shell.split("<<'PY'\n", 1)[1].split("builtins.input = ask", 1)[0]

namespace = {'__name__': 'driver'}


class _Path:
    def __init__(self, *a):
        self.args = a

    def exists(self):
        return False

    def read_text(self, **kw):
        return ''

    def unlink(self):
        pass

    def write_text(self, *a, **kw):
        pass


import time  # noqa: E402

stub = {
    'json': __import__('json'),
    'os': __import__('os'),
    'pathlib': type('m', (), {'Path': _Path}),
    'time': time,
    'builtins': __import__('builtins'),
}
namespace['__builtins__'] = __import__('builtins')
for name, module in stub.items():
    namespace[name] = module
exec(compile(body, str(DRIVER), 'exec'), namespace)
ask = namespace['ask']

# ------------------------------------------------- the driver's waits, captured not performed
needs = []


def fake_publish(**fields):
    if fields.get('need'):
        needs.append(fields['need'])


def fake_wait_file(path, need, extra=None):
    needs.append(need)
    return None


namespace['publish'] = fake_publish
namespace['wait_file'] = fake_wait_file
namespace['take'] = lambda path: None

# ------------------------------------------------------------------ real prompts from the package
source = PACKAGE.read_text(encoding='utf-8')
raw = re.findall(r"ask\('([^']*)'", source)
prompts = []
for text in raw:
    rendered = text.replace('%02d', '03').replace('%s', 'real-voice').replace('%index', '03')
    prompts.append(rendered)

prompts.append('03 real-voice 此项现场听感：CLEAR / DISTORTED / NO_AMPLIFICATION / HOWL / UNKNOWN：')

EXPECT = [
    ('READY', 'READY', None),
    ('SAME_SCENE', 'SAME_SCENE', None),
    ('一次填写声源-麦克风距离', None, None),          # layout: falls through to the queue
    ('HUMAN_LIVE_AND_LISTENING', 'HUMAN_LIVE_AND_LISTENING', None),
    ('path-gate', 'START', 'no-go'),                  # gate must NOT wait for a voice go
    ('真实人声项此时就位', 'START', 'GO_VOICE'),        # real voice waits for A's go
    ('此项现场听感：CLEAR / DISTORTED / NO_AMPLIFICATION / HOWL / UNKNOWN', None, 'HEARING'),
    ('FIXED_SOURCE_FIXED_GAIN_NO_AGC', '', None),     # no recordings -> untested, never a fake
    ('开/关差别', None, 'LISTENER_REPORT'),
    ('SOURCE_OFF', 'SOURCE_OFF', None),
]

print('prompts found in the package:', len(prompts))
failures = 0
seen = set()
for marker, value, need in EXPECT:
    match = next((p for p in prompts if marker in p), None)
    if match is None:
        print('SKIP    no prompt contains %r' % marker)
        continue
    seen.add(marker)
    needs.clear()
    namespace['queue'] = ['LAYOUT']
    got = ask(match)
    got_need = needs[0] if needs else None
    ok_value = (value is None) or (got == value)
    if need == 'no-go':
        ok_need = 'GO_VOICE' not in needs
    elif need is None:
        ok_need = True
    else:
        ok_need = got_need == need
    status = 'OK  ' if (ok_value and ok_need) else 'FAIL'
    if status == 'FAIL':
        failures += 1
    print('%s  %-22s -> %-26r need=%-15s' % (status, marker, got, got_need))

print('\nROUTING_RESULT', 'PASS' if failures == 0 else 'FAIL (%d)' % failures)
sys.exit(0 if failures == 0 else 1)
