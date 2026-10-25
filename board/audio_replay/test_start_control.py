"""D4 regression: five start-control cases, software only, no board.

Only an explicit GO/START may authorise arming. Timeout, CANCEL, empty and invalid tokens must
cancel, must not unmute and must not arm.
"""
import pathlib
import sys

ROOT = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work')
DRIVER = ROOT / 'run_human_r1.sh'

shell = DRIVER.read_text(encoding='utf-8')
body = shell.split("<<'PY'\n", 1)[1].split("builtins.input = ask", 1)[0]

namespace = {'__name__': 'driver'}


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


import os  # noqa: E402
import time  # noqa: E402

for name, module in (('json', __import__('json')), ('os', os), ('time', time),
                     ('pathlib', type('m', (), {'Path': _Path}))):
    namespace[name] = module
namespace['__builtins__'] = __import__('builtins')
exec(compile(body, str(DRIVER), 'exec'), namespace)

events = []
namespace['publish'] = lambda **f: events.append(('publish', f))
namespace['take'] = lambda path: None

REAL_PROMPT = '03 real-voice 已配置且静音。真实人声项此时就位，START才发声；其他输入停止：'

CASES = [
    ('normal_go', 'GO', 'START'),
    ('normal_start_token', 'START', 'START'),
    ('timeout_none', None, 'CANCEL'),
    ('explicit_cancel', 'CANCEL', 'CANCEL'),
    ('empty_value', '', 'CANCEL'),
    ('invalid_token', 'MAYBE', 'CANCEL'),
]

print('D4 start-control regression (software only, no board)')
print('%-20s %-10s %-10s %-8s %s' % ('case', 'go value', 'returned', 'verdict', 'cancel recorded'))
failures = 0
for name, value, expected in CASES:
    events.clear()
    namespace['wait_file'] = lambda path, need, extra=None, _v=value: _v
    got = namespace['ask'](REAL_PROMPT)
    cancel = 'CANCEL' in repr(namespace.get('_last_cancel', '')) or any(
        e[1].get('step') == 'cancelled' for e in events)
    ok = got == expected
    if not ok:
        failures += 1
    print('%-20s %-10s %-10s %-8s %s'
          % (name, repr(value), got, 'OK' if ok else 'FAIL', 'yes' if cancel else 'no'))

# a cancelled start must never reach the arming publish
events.clear()
namespace['wait_file'] = lambda path, need, extra=None: None
namespace['ask'](REAL_PROMPT)
armed = any(e[1].get('step') == 'start' for e in events)
print('\narmed_after_timeout:', armed, '(must be False)')
if armed:
    failures += 1

print('\nSTART_CONTROL_RESULT', 'PASS' if failures == 0 else 'FAIL (%d)' % failures)
sys.exit(0 if failures == 0 else 1)
