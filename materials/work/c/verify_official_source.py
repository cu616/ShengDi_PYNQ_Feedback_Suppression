"""Offline audit of the outer submission; never imports hardware modules."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ZIP_SHA = 'b167d0b579df94e76065b067ada8feb2b3e050f7c44aa3541f57a47319d615b4'
MANIFEST_SHA = 'beb36216d26b6cbb510f6f211d139424943863693e48fee44511ad200d62d9ef'
BIT_SHA = '322350656986d91f25a63735f87e5b0b9cc2f7ea977356ce9e988014648e738e'
ZIP_NAME = 'shengdi-recal-0cabfc17-alg1102-resume3-gain1-60s-final.zip'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'submission-manifest.json').read_text(encoding='utf-8'))
    expected = set(manifest['files']) | {'submission-manifest.json'}
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('outer file set mismatch: ' + str(sorted(actual ^ expected)))
    for name, item in manifest['files'].items():
        path = root / name
        path.resolve().relative_to(root)
        data = path.read_bytes()
        if len(data) != item['bytes'] or digest(data) != item['sha256']:
            raise ValueError('outer hash mismatch: ' + name)
    archive = root / 'board/packages' / ZIP_NAME
    if digest(archive.read_bytes()) != ZIP_SHA:
        raise ValueError('frozen ZIP hash mismatch')
    source_map = json.loads((root / 'board/provenance/resume3-source-map.json').read_text(encoding='utf-8-sig'))
    frozen = root / 'board/audio_replay'
    with zipfile.ZipFile(archive) as zipped:
        names = {x.filename for x in zipped.infolist() if not x.is_dir()}
        mapped = {x['file'] for x in source_map['files']}
        extracted = {p.relative_to(frozen).as_posix() for p in frozen.rglob('*') if p.is_file()}
        if names != mapped or extracted != names or len(names) != 41:
            raise ValueError('frozen 41-file set mismatch')
        for item in source_map['files']:
            name = item['file']
            data = zipped.read(name)
            if digest(data) != item['sha256'] or len(data) != item['bytes']:
                raise ValueError('source-map mismatch: ' + name)
            if (frozen / name).read_bytes() != data:
                raise ValueError('extraction changed frozen bytes: ' + name)
        if digest(zipped.read('product-manifest.json')) != MANIFEST_SHA:
            raise ValueError('product manifest mismatch')
        if digest(zipped.read('audio_replay.bit')) != BIT_SHA:
            raise ValueError('bitstream mismatch')
        cfg = json.loads(zipped.read('product-config.json'))
        if cfg['expected_identity']['gain_q12'] != 4596 or cfg['run_seconds'] != 60:
            raise ValueError('frozen gain/time differs')
        if any(a['training']['segments'] != 4 or a['validation']['segments'] != 2 for a in cfg['attempts']):
            raise ValueError('frozen segment counts differ')
        if any(len(p['training']['captures']) != 4 or len(p['validation']['captures']) != 2 for p in cfg['capture_plans']):
            raise ValueError('frozen capture plans differ')
        if cfg['phase_gain_q12']['runtime'] != [0, 4596]:
            raise ValueError('frozen runtime whitelist differs')
    evidence_root = root / 'report/verification/recal-product-v1/frozen-bitstream-32235065'
    implementation = json.loads((evidence_root / 'implementation-report-copies.json').read_text(encoding='utf-8'))
    for item in implementation['copies']:
        if digest((evidence_root / item['file']).read_bytes()) != item['delivery_sha256']:
            raise ValueError('implementation delivery hash mismatch: ' + item['file'])
    if list(root.rglob('*.dcp')):
        raise ValueError('DCP must remain repository-only')
    implementation_check = dict(delivery_copies=len(implementation['copies']),
        locally_verified_originals=len(implementation['checked_originals']),
        source_listed_originals=implementation['listed_originals'],
        source_references_not_in_supplied_commit=implementation['unavailable_originals'],
        dcp_in_archive=False, resources=implementation['resources'], timing_ns=implementation['timing_ns'],
        scope=implementation['wording'])
    return dict(ok=True, outer_files=len(actual), frozen_files=41, zip_sha256=ZIP_SHA,
                product_manifest_sha256=MANIFEST_SHA, bit_sha256=BIT_SHA,
                submission_manifest_sha256=digest((root / 'submission-manifest.json').read_bytes()),
                implementation_check=implementation_check,
                upload_ready=manifest['upload_ready'], missing=manifest['missing'], hardware_operations=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', help='extracted shengdi-source directory')
    args = parser.parse_args()
    print(json.dumps(verify(args.root), ensure_ascii=False, indent=2))
