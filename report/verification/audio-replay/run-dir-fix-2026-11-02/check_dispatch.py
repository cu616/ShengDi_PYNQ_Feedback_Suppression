"""Offline check of the C 81b47e3 one-liner: every op must take request.run_dir before dispatch.

No board needed. The driver is never called: the three affected op handlers are replaced with a
recorder that just reports what `self.run_dir` was when dispatch reached them.

Pre-fix module is pulled straight out of git (rev 4467906 = the commit before this change), so the
"before" column is the code that was actually frozen, not a paraphrase of it.

Run: <bundled python> check_dispatch.py
"""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import types

REPO = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int')
NEW = REPO / 'board' / 'audio_replay' / 'v3-io' / 'hw_api.py'
PRE_REV = '4467906'             # last commit that shipped hw_api.py 784acc6b (pre-fix)
REL = 'board/audio_replay/hw_api.py'

# (op in request, request extra fields, V2 method the op dispatches to)
OPS = [('input', {'cue': True}, '_cue_input'),
       ('install', {}, '_install'),
       ('run', {}, '_run_v2')]

_SCRATCH = pathlib.Path(tempfile.gettempdir()) / 'shengdi-run-dir'
STALE = str(_SCRATCH / 'previous-scene' / '1' / 'input')
FRESH = str(_SCRATCH / 'resay-scene' / '2' / 'input')


def load(path, name):
    # hw_api imports fcntl at module scope; Windows has no fcntl and no hardware call is made here.
    if 'fcntl' not in sys.modules:
        sys.modules['fcntl'] = types.SimpleNamespace(ioctl=lambda *a, **k: None)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pre_fix_copy():
    out = pathlib.Path(tempfile.gettempdir()) / 'shengdi-run-dir' / 'hw_api_pre_dispatch_fix.py'
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = subprocess.run(['git', 'show', '%s:%s' % (PRE_REV, REL)], cwd=str(REPO),
                          capture_output=True)
    if blob.returncode != 0:
        raise SystemExit('git show failed: %s' % blob.stderr.decode('utf-8', 'replace')[:300])
    out.write_bytes(blob.stdout)
    return out


def probe(mod, label):
    print('--- %s ---' % label)
    print('  module bytes : %d' % len(pathlib.Path(mod.__file__).read_bytes()))
    p = mod.create_product({'package_dir': str((REPO / 'board' / 'audio_replay' / 'v3-io'))})
    rows = {}
    for op, extra, method in OPS:
        seen = {}

        def recorder(request, cancel_event=None, _seen=seen):
            _seen['run_dir'] = p.run_dir
            return {'ok': True, 'contract': 'stub'}

        p.run_dir = STALE
        setattr(p, method, recorder)
        p.perform(dict(op=op, run_dir=FRESH, **extra))
        rows[op] = seen.get('run_dir')
    for op, _, _ in OPS:
        state = 'took the request run_dir' if rows[op] == FRESH else 'STILL ON THE OLD ONE'
        print('  op %-8s self.run_dir=%s   -> %s' % (op, rows[op], state))
    return rows


def main():
    pre = pre_fix_copy()
    old = load(pre, 'hw_api_pre')
    new = load(NEW, 'hw_api_new')
    print('pre-fix  : %s (from %s)' % (pre, PRE_REV))
    print('post-fix : %s' % NEW)
    print()
    before = probe(old, 'BEFORE (frozen hw_api.py, 784acc6b)')
    print()
    after = probe(new, 'AFTER (this change)')
    print()

    # what that means for the file name on disk
    p = new.create_product({'package_dir': str(NEW.parent)})
    for label, rd in (('stale run_dir', STALE), ('request run_dir', FRESH)):
        p.run_dir = rd
        path, cid = p._capture_path('scene-A', 'input', 0)
        print('  _capture_path with %-15s -> %s' % (label, path))
    print()

    bad = [op for op, _, _ in OPS if before[op] != FRESH]
    good = [op for op, _, _ in OPS if after[op] != FRESH]
    print('RESULT before: %d/%d ops stay on the stale directory (%s)'
          % (len(bad), len(OPS), ', '.join(bad)))
    print('RESULT after : %d/%d ops take the request directory' % (len(OPS) - len(good), len(OPS)))
    if good:
        raise SystemExit('FAIL: still stale after the fix: %s' % good)


if __name__ == '__main__':
    main()
