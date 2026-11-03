"""Non-private vectors from existing v3 arithmetic tests; no hardware access."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np

SOURCE = '4efd43036555c667924fc415d31cf95d785fbb24:board/audio_replay/v3/test_verify_replay_v3.py'
HELPERS = {
    'replay_tools.py': 'bba221020c154968939aba0f23b21a0bbe38fb0ba8051448553388210d7aa246',
    'closed_tools.py': 'a95265b90c83a07d439d5b8f6b6a1f227ff94177dda97c4bbb5e81db0635cd54',
}
CASES = [
    ('ordinary', [1000, -2000, 3000, -4000, 5000, -6000, 7000, -8000], 0, 0, 0),
    ('negative-rail', [-2**23, 0, -2**23, 0, 0, 0, 0, 0], 0, 0, 0),
    ('prefix-overflow', [2**23, 0] + [0] * 8, 1000, 1, 1),
]


def helpers(root):
    directory = root / 'board/audio_replay'
    for name, expected in HELPERS.items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError('reference helper identity mismatch: ' + name)
    sys.path.insert(0, str(directory))
    from replay_tools import verify_replay
    from closed_tools import rounded_shift
    return verify_replay, rounded_shift


def write(root):
    checker, rounded_shift = helpers(root)
    folder = root / 'data/reference'
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, samples, first, overflows, prefix in CASES:
        # Same zero-coefficient capture construction as the source test above.
        mic = np.asarray(samples, dtype=np.int64)
        played = np.zeros(len(mic), dtype=np.int64)
        for i in range(2, len(mic)):
            played[i] = int(np.clip(rounded_shift(mic[i-2] * np.int64(4096), 12), -2**23, 2**23-1))
        raw = np.column_stack((played, mic, np.zeros(len(mic), dtype=np.int64),
                               np.clip(mic, -2**23, 2**23-1)))
        expected = dict(bit_exact=True, wide_residual_frames=overflows, wide_residual_frames_prefix=prefix)
        result = checker(raw, np.zeros(2, dtype=np.int64), False, 4096, [], first)
        if any(result[k] != v for k, v in expected.items()):
            raise ValueError('reference construction differs: ' + name)
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['frame', 'played_pcm24', 'microphone_pcm24', 'prediction_pcm24', 'residual_pcm24'])
        writer.writerows([first+i, *[int(x) for x in row]] for i, row in enumerate(raw))
        data = stream.getvalue().encode()
        path = folder / (name + '.csv')
        path.write_bytes(data)
        entries.append(dict(file=path.name, sha256=hashlib.sha256(data).hexdigest(),
            rows=len(raw), first_frame=first, gain_q12=4096, bypass=False,
            coefficients_q20=[0, 0], source_pcm16=[], expected=expected))
    manifest = dict(schema_version=1, kind='synthetic_software_reference', is_board_capture=False,
        source=SOURCE, sample_rate_hz=48828.125, helper_sha256=HELPERS,
        meaning='integer arithmetic and overflow accounting only; not acoustic performance',
        parameter_scope='two zero taps and unity gain are offline test parameters, not deployment configuration',
        files=entries)
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n',
                                          encoding='utf-8', newline='\n')
    return verify(root)


def verify(root):
    checker, _ = helpers(root)
    folder = root / 'data/reference'
    manifest = json.loads((folder / 'manifest.json').read_bytes())
    results = []
    for item in manifest['files']:
        path = folder / item['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('reference data hash mismatch: ' + item['file'])
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != item['rows'] or [int(r['frame']) for r in rows] != list(range(item['first_frame'], item['first_frame']+len(rows))):
            raise ValueError('reference frame range differs: ' + item['file'])
        raw = np.asarray([[int(r[k]) for k in ('played_pcm24', 'microphone_pcm24', 'prediction_pcm24', 'residual_pcm24')] for r in rows], dtype=np.int64)
        result = checker(raw, item['coefficients_q20'], item['bypass'], item['gain_q12'],
                         item['source_pcm16'], item['first_frame'])
        if any(result[k] != v for k, v in item['expected'].items()):
            raise ValueError('reference result differs: ' + item['file'])
        results.append(dict(file=item['file'], ok=True, expected=item['expected']))
    return dict(ok=True, cases=results, source=manifest['source'], hardware_operations=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--write', action='store_true')
    action.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    print(json.dumps(write(args.root.resolve()) if args.write else verify(args.root.resolve()), ensure_ascii=False, indent=2))
