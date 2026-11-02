"""Verify the C-delivered ZIP against its own manifests, and against the previous package.

Checks
  1. product-manifest.json hashes        -> every file in the archive matches its recorded sha256
  2. product-manifest.json adapters      -> hardware adapter hashes/expected_identity match too
  3. manifest.json (A's package manifest)-> all 8 payload hashes match
  4. archive inventory                   -> no file present that the manifest does not cover
  5. delta vs the previous frozen package-> exactly which files changed (A/B bytes must be unchanged)
  6. upstream-product-adapter.json       -> byte-identical to A's docs/contracts copy
"""
import hashlib
import json
import pathlib
import sys

PKG = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\tmp\zipcheck\8799f40b')
OLD = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\final_pkg')
A_CONTRACT = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\docs\contracts\product-adapter.json')

HELPER = '8799f40b6d9f7ecbfa8f9b2491b084f046b4b9d8d7ffd013feca0c84dbca95e0'
OLD_HELPER = '784acc6ba96ea598d6f7d54522f6aafd7aee526787e0a19180024f480528a1be'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check(label, recorded, actual):
    bad = [k for k, h in recorded.items() if actual.get(k) != h]
    missing = [k for k in recorded if k not in actual]
    print('%-38s files=%-3d bad=%-2d missing=%d  %s'
          % (label, len(recorded), len(bad), len(missing), 'PASS' if not bad and not missing else 'FAIL'))
    for k in (bad + missing)[:6]:
        print('    %-34s recorded=%s actual=%s' % (k, recorded[k][:16], (actual.get(k) or 'ABSENT')[:16]))
    return not bad and not missing


def main():
    files = {str(p.relative_to(PKG)).replace('\\', '/'): p
             for p in PKG.rglob('*') if p.is_file()}
    actual = {k: sha(v) for k, v in files.items()}
    man = json.loads((PKG / 'product-manifest.json').read_text(encoding='utf-8'))
    pkg_man = json.loads((PKG / 'manifest.json').read_text(encoding='utf-8'))
    hw = man['adapters']['hardware']

    print('archive: %d files, %d bytes'
          % (len(files), sum(p.stat().st_size for p in files.values())))
    print('source_commit recorded: %s' % man['source_commit'])
    print()
    ok = True
    ok &= check('1 product-manifest hashes', man['hashes'], actual)
    ok &= check('2 hardware adapter hashes', hw['hashes'], actual)
    ok &= check("3 A's manifest.json", pkg_man['hashes'], actual)

    # product-manifest.json cannot contain its own hash; every other file must be covered.
    extra = sorted(set(actual) - set(man['hashes']) - {'product-manifest.json'})
    print('%-38s %d  %s' % ('4 uncovered files (self-manifest allowed)', len(extra),
                            'PASS' if not extra else 'FAIL ' + ', '.join(extra[:6])))
    ok &= not extra

    print()
    print('5 pins')
    pins = {
        'archive hw_api.py': actual.get('hw_api.py'),
        'manifest.json hashes.hw_api.py': pkg_man['hashes']['hw_api.py'],
        'product-manifest hashes.hw_api.py': man['hashes'].get('hw_api.py'),
        'adapters.hardware.hashes.hw_api.py': hw['hashes'].get('hw_api.py'),
        'adapters.hardware.expected_identity.helper_sha256': hw['expected_identity'].get('helper_sha256'),
    }
    cfg = json.loads((PKG / 'product-config.json').read_text(encoding='utf-8'))
    pins['product-config expected_identity.helper_sha256'] = \
        cfg['expected_identity'].get('helper_sha256')
    for k, v in pins.items():
        print('  %-52s %s  %s' % (k, v, 'OK' if v == HELPER else 'MISMATCH'))
        ok &= v == HELPER

    print()
    print('6 delta vs previous package (7bd365b)')
    old_files = {str(p.relative_to(OLD)).replace('\\', '/'): p
                 for p in OLD.rglob('*') if p.is_file()}
    old_actual = {k: sha(v) for k, v in old_files.items()}
    changed = sorted(k for k in actual if k in old_actual and actual[k] != old_actual[k])
    added = sorted(set(actual) - set(old_actual))
    removed = sorted(set(old_actual) - set(actual))
    for k in changed:
        was = old_actual[k]
        tag = 'A-owned' if k in pkg_man['hashes'] else 'C-owned'
        print('  changed  %-34s %-11s %s -> %s' % (k, tag, was[:16], actual[k][:16]))
    for k in added:
        print('  added    %s' % k)
    for k in removed:
        print('  removed  %s' % k)
    a_owned_changed = [k for k in changed if k in pkg_man['hashes']]
    print('  A-owned files changed: %s' % (a_owned_changed or 'none'))
    ok &= a_owned_changed == ['hw_api.py']

    print()
    a_bytes = man['hashes']
    unchanged = [k for k in pkg_man['hashes'] if k != 'hw_api.py' and actual[k] == pkg_man['hashes'][k]]
    print('  A package entries unchanged vs their manifest: %d/%d'
          % (len(unchanged), len(pkg_man['hashes']) - 1))

    print()
    up = PKG / 'upstream-product-adapter.json'
    if up.is_file():
        same = up.read_bytes() == A_CONTRACT.read_bytes()
        print('7 upstream-product-adapter.json == A docs/contracts copy: %s'
              % ('YES' if same else 'NO (differs: %d vs %d bytes)' % (up.stat().st_size, A_CONTRACT.stat().st_size)))
    else:
        print('7 upstream-product-adapter.json: ABSENT')

    print()
    print('VERDICT', 'PASS' if ok else 'FAIL')


if __name__ == '__main__':
    main()
