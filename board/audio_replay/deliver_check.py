"""Delivery checker (rule R2/R3), with explicit artifact binding.

Every test must run against the *delivered* artifact, not a private copy. The binding is declared
in test-bindings.json; a missing binding target or a hash mismatch is a FAILURE, never a skip.
Exit code 0 means delivered and prints one PACKAGE_COMPLETE <sha256> line.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
WORK = ROOT.parents[2]                       # .../_a_work
REPO = ROOT.parents[3]                       # .../Flushbonading_FPGA_Contest
PY = sys.executable

BINDINGS = ROOT / 'test-bindings.json'


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def resolve_binding():
    """Return the package directory plus a receipt, or raise with a precise reason."""
    if not BINDINGS.is_file():
        raise RuntimeError('missing binding file: %s' % BINDINGS)
    spec = json.loads(BINDINGS.read_text(encoding='utf-8'))
    pkg = spec['human_package']
    directory = WORK / pkg['extracted_dir']
    prompt_file = directory / pkg['prompt_source']
    if not prompt_file.is_file():
        raise RuntimeError('binding target missing: %s' % prompt_file)
    zip_path = REPO / pkg['zip_name']
    if not zip_path.is_file():
        raise RuntimeError('binding archive missing: %s' % zip_path)
    actual = sha(zip_path)
    if actual != pkg['zip_sha256']:
        raise RuntimeError('binding hash mismatch: %s != %s' % (actual, pkg['zip_sha256']))
    return directory, {'package_dir': str(directory),
                       'prompt_file': str(prompt_file),
                       'prompt_sha256': sha(prompt_file),
                       'archive_sha256': actual}


def run(path, env):
    result = subprocess.run([PY, str(path)], capture_output=True, text=True, env=env)
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    return result.returncode, (lines[-1] if lines else ''), result.stdout + result.stderr


def main():
    try:
        package_dir, receipt = resolve_binding()
    except Exception as exc:                     # binding failure is a delivery failure
        print('BINDING_FAILED %s' % exc)
        return 1
    print('binding package_dir %s' % package_dir)
    print('binding prompt_sha256 %s' % receipt['prompt_sha256'])

    env = dict(os.environ)
    env['SHENGDI_HUMAN_PKG'] = str(package_dir)
    env['SHENGDI_DRIVER'] = str(ROOT / 'run_human_r1.sh')

    failed = []
    for name in ('test_human_routing.py', 'test_start_control.py'):
        code, last, log = run(ROOT / name, env)
        print('[%s] exit=%d  %s' % (name, code, last))
        if code != 0:
            failed.append(name)
            sys.stderr.write(log[-2000:])
    if failed:
        print('DELIVERY_INCOMPLETE ' + ','.join(failed))
        return 1

    digest = hashlib.sha256()
    files = sorted(p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py', '.sh'))
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update(json.dumps(receipt, sort_keys=True).encode())
    print('files %d' % len(files))
    print('PACKAGE_COMPLETE ' + digest.hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
