"""One silent command for existing board NPZs. Never imports a PYNQ API."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
CODE=ROOT/'board/audio_replay'
if (Path(__file__).resolve().parent/'evaluation.py').is_file():CODE=Path(__file__).resolve().parent
sys.path.insert(0,str(CODE))
from evaluation import analyze_npz, VERSION
from model_comparison import load_registry, flat_trial, pair_models, export_csv, SUMMARY_VERSION, SUMMARY_REVISION, MODEL_SELECTION


def summarize(input_root, output, registry_folder, evidence_path=None):
    source=Path(input_root).resolve(); output=Path(output).resolve()
    if not source.is_dir():raise ValueError('input root must be an existing directory')
    if output.exists():raise ValueError('choose a new output directory; original results are never replaced')
    registry=load_registry(registry_folder)
    evidence=json.loads(Path(evidence_path).read_text(encoding='utf8')) if evidence_path else {}
    # Resolve the input set before creating output, so results cannot be rescanned.
    files=sorted(source.rglob('*.npz'))
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for index,path in enumerate(files,1):
        relative=str(path.relative_to(source)).replace('\\','/')
        supplement=evidence.get('captures',{}).get(relative)
        analysis=analyze_npz(path,metadata_evidence=supplement)
        row=flat_trial(dict(index=index,file=relative,analysis=analysis),registry)
        row['analysis']=analysis
        rows.append(row)
    pairs=pair_models(rows)
    state=dict(schema_version=SUMMARY_VERSION,summary_revision=SUMMARY_REVISION,calculation_version=VERSION,
               artifact_kind='offline_existing_capture_summary',status='completed',
               board_actions=False,source_root=str(source),trials=rows,model_pairs=pairs,
               input_files=len(files),configuration_matched_pairs=sum(p['configuration_matches'] for p in pairs),
               effect_eligible_pairs=sum(p['effect_eligible'] for p in pairs),msg_db=None,asg_db=None,
               model_registry=registry,
               model_selection=MODEL_SELECTION,
               evidence_sha256=hashlib.sha256(Path(evidence_path).read_bytes()).hexdigest() if evidence_path else None,
               interpretation='Real capture validity is determined per row; no fabricated measured pair or ASG')
    (output/'summary.json').write_text(json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    export_csv(output/'summary.csv',rows)
    with zipfile.ZipFile(output/'return-results.zip','x',zipfile.ZIP_DEFLATED) as z:
        z.write(output/'summary.json','summary.json');z.write(output/'summary.csv','summary.csv')
    print('SILENT_REVIEW_COMPLETE',len(rows),'CAPTURES',state['effect_eligible_pairs'],'ELIGIBLE_PAIRS')
    print('RETURN_ONE_FILE',str(output/'return-results.zip'))
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--models',type=Path,default=CODE/'models' if (CODE/'models').is_dir() else ROOT/'models')
    p.add_argument('--evidence',type=Path)
    a=p.parse_args()
    summarize(a.input_root,a.output,a.models,a.evidence)
