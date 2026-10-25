"""Delivery checker required by A's own rule R2/R3.

Runs every software regression that guards the live-session driver, hashes the delivered files and,
only if everything passes, prints a single PACKAGE_COMPLETE <sha256> line on stdout.
Exit code 0 means delivered; anything else means not delivered.
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PY = sys.executable

CHECKS = [
    ('routing', ROOT / 'test_human_routing.py'),
    ('start_control', ROOT / 'test_start_control.py'),
]


def run(path):
    result = subprocess.run([PY, str(path)], capture_output=True, text=True)
    tail = [line for line in result.stdout.strip().splitlines() if line.strip()][-1:] or ['']
    return result.returncode, tail[0].strip(), result.stdout + result.stderr


def main():
    failed = []
    for name, path in CHECKS:
        code, last, log = run(path)
        print('[%s] exit=%d  %s' % (name, code, last))
        if code != 0:
            failed.append(name)
            sys.stderr.write(log[-2000:])
    if failed:
        print('DELIVERY_INCOMPLETE ' + ','.join(failed))
        return 1

    files = sorted(p for p in ROOT.iterdir()
                   if p.is_file() and p.suffix in ('.py', '.sh'))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    print('files %d  sha256 %s' % (len(files), digest.hexdigest()))
    print('PACKAGE_COMPLETE ' + digest.hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
