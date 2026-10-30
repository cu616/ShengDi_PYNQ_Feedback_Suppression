"""Immutable historical review, including summary-only failures. No board access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CODE = Path(__file__).resolve().parent
if not (CODE/'evaluation.py').is_file():
    CODE = ROOT/'board/audio_replay'
sys.path.insert(0, str(CODE))
from evaluation import VERSION, classify, analyze_npz, unpack_counts


def review(folder):
    rows, hashes = [], {}
    for p in sorted(Path(folder).rglob('*.json')):
        hashes[str(p.relative_to(folder))] = hashlib.sha256(p.read_bytes()).hexdigest()
        obj = json.loads(p.read_text(encoding='utf8'))
        if not isinstance(obj, dict):
            continue
        for i, row in enumerate(obj.get('trials', [])):
            m = dict(row.get('metadata') or {})
            error = str(row.get('error', ''))
            if error:
                m['error'] = error
            # Preserve protection as an execution event, never an acoustic label.
            if re.search(r'guard|stopped playback|sustained saturation', error, re.I):
                m['protection_triggered'] = True
            source = obj.get('source', {})
            if isinstance(source, dict) and 'frames' in source:
                m.setdefault('source_frames', source['frames'])
            new = classify(m, rate=m.get('sample_rate_hz', 48828.125))
            match = re.search(r'packed_prediction_residual=(\d+) gain=(\d+) mix=(\d+)', error)
            if match:
                new['recovered_raw_counts'] = unpack_counts([int(v) for v in match.groups()])
            rows.append(dict(source_file=str(p.relative_to(folder)), row=i,
                             index=row.get('index'), mode=row.get('mode'),
                             gain_db=row.get('gain_db_requested', row.get('gain_db')),
                             original_status=row.get('status'), original_error=error or None,
                             original_metadata=row.get('metadata'), derived=new,
                             raw_pcm_available=False,
                             decision='No waveform-based instability or MSG/ASG can be reconstructed from summary alone'))
    categories = {}
    for r in rows:
        key = r['derived']['category']
        categories[key] = categories.get(key, 0) + 1
    return dict(calculation_version=VERSION, input_sha256=hashes, rows=rows,
                totals=dict(trials=len(rows), categories=categories),
                policy='original files unchanged; no threshold inferred from protection or missing PCM')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('output already exists; choose a new derived file')
    result = analyze_npz(args.input) if args.input.suffix == '.npz' else review(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result.get('totals', {'category': result.get('category')}), ensure_ascii=False))


if __name__ == '__main__':
    main()
