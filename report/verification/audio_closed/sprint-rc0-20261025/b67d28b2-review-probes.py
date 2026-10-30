"""Bounded C probes of B=67d28b2's four fixes; synthetic, read-only analysis."""
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import warnings

import numpy as np

root = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv)>2 else pathlib.Path(__file__).resolve().parent
source = root/'scripts/analyze_residual_overflow.py'
expected_sha = '3e37fb34a797361c37b376edbeb9daa0cdf47f98f987673890e8c09abb747f92'
if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha:
    raise SystemExit('Refusing another B script revision; this artifact reviews 67d28b2 only.')
spec = importlib.util.spec_from_file_location('reviewed_B', source)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
LO, HI, SCALE, N, TAPS = -(2**23), 2**23-1, 2**23, 1024, 512
data = root/'C-synthetic'
data.mkdir(exist_ok=True)
cases = []


def fixture(name, mic=None, pred=None, q=None, changes=None, drop=()):
    q = np.zeros(TAPS, dtype='<i4') if q is None else np.asarray(q, dtype='<i4')
    mic = np.ones(N, dtype=np.int64) if mic is None else np.asarray(mic, dtype=np.int64)
    pred = np.zeros(N, dtype=np.int64) if pred is None else np.asarray(pred, dtype=np.int64)
    values = dict(reference=np.zeros(N, dtype=np.float64), microphone=mic/SCALE,
                  prediction_pcm=pred, residual_pcm=np.clip(mic-pred, LO, HI),
                  coefficients_q20=q, sample_rate_hz=48828.125)
    meta = dict(first_frame=0, completed_frames=N, bypass=False, gain_q12=4096,
                coefficients_sha256=hashlib.sha256(q.tobytes()).hexdigest(),
                residual_saturations=int(np.count_nonzero((mic-pred < LO) | (mic-pred > HI))))
    meta.update(changes or {})
    for key in drop:
        meta.pop(key, None)
    values['metadata_json'] = json.dumps(meta)
    path = data/(name+'.npz')
    np.savez(path, **values)
    return path


def replace(path, **changes):
    with np.load(path, allow_pickle=False) as z:
        values = {k:z[k] for k in z.files}
    values.update(changes)
    np.savez(path, **values)


def analyze(path):
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter('ignore', RuntimeWarning)
        return tool.analyze(path, None, None, None)


def cli(path):
    p = subprocess.run([sys.executable, str(source), '--npz', str(path)], capture_output=True)
    return dict(exit_code=p.returncode, failed_prefix=b'FAILED:' in p.stdout)


def record(name, expected, observed, passed):
    cases.append(dict(case=name, expected=expected, observed=observed, passed=bool(passed)))


p = fixture('positive_float_one')
replace(p, microphone=np.ones(N), residual_pcm=np.full(N, HI, dtype=np.int64))
r = analyze(p)
record('positive_float_one_no_sign_wrap', 'positive rail; clamp count=1024, no strict overflow',
       dict(encoding=r['encoding'], primary=r['primary_capture_only'], attribution=r['attribution']),
       r['encoding']['mic_clamped']==N and r['primary_capture_only']['overflow_samples']['whole']==0
       and r['primary_capture_only']['wide_max_x']['whole']==HI/SCALE)

p = fixture('float_two')
replace(p, microphone=np.full(N, 2.0))
r = cli(p)
record('normalized_float_two_rejected', 'FAILED exit2', r, r==dict(exit_code=2, failed_prefix=True))

observed=[]
for sign in (1, -1):
    value = sign*(1+1/SCALE)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            codes, count = tool.codes_from_float(np.array([value]), 'microphone')
        observed.append(dict(value=value, accepted=True, decoded=int(codes[0]), clamped=count))
    except SystemExit as exc:
        observed.append(dict(value=value, accepted=False, exit_code=exc.code))
record('one_PCM_step_outside_normalized_range', '|x|>1 rejected rather than repaired', observed,
       all(not r['accepted'] and r['exit_code']==2 for r in observed))

# Targeted end-to-end follow-up: decoder acceptance does not imply attribution admission.
near_followup=[]
for sign in (1,-1):
    p=fixture('just_outside_%d'%sign)
    replace(p, microphone=np.full(N,sign*(1+1/SCALE)),
            residual_pcm=np.full(N,HI if sign>0 else LO,dtype=np.int64))
    r=analyze(p)
    near_followup.append(dict(value=sign*(1+1/SCALE), encoding=r['encoding'],
                              attribution=r['attribution'], **cli(p)))

observed=[]
for field in ('prediction_pcm', 'residual_pcm', 'coefficients_q20'):
    p=fixture('float_dtype_'+field)
    with np.load(p, allow_pickle=False) as z:
        changed=z[field].astype(float)
    replace(p, **{field:changed})
    observed.append(dict(field=field, **cli(p)))
record('all_three_integer_fields_reject_float_dtype', 'each FAILED exit2', observed,
       all(x['exit_code']==2 and x['failed_prefix'] for x in observed))

signed=tool.codes_from_int(np.array([LO, HI], dtype=np.int64), 'prediction_pcm').tolist()
packed=tool.codes_from_int(np.array([2**24-1, 2**23], dtype=np.uint32), 'prediction_pcm').tolist()
try:
    with contextlib.redirect_stdout(io.StringIO()):
        tool.codes_from_int(np.array([-1, 2**23], dtype=np.int64), 'prediction_pcm')
    mixed=False
except SystemExit as exc:
    mixed=exc.code==2
record('integer_signed_and_unsigned_boundaries', 'signed rails retained, unsigned24 decoded, mixed rejected',
       dict(signed=signed, packed=packed, mixed_rejected=mixed), signed==[LO,HI] and packed==[-1,LO] and mixed)

p=fixture('declared_hash_wrong', changes={'coefficients_sha256':'0'*64})
r=analyze(p); command=cli(p)
record('declared_hash_conflict_stops_attribution', 'attribution false; CLI exit2',
       dict(attribution=r['attribution'], cli=command), not r['attribution']['allowed'] and command['exit_code']==2)
p=fixture('declared_hash_matches')
r=analyze(p)
record('declared_hash_matches_actual_array', 'matching int32 LE hash; local attribution allowed',
       dict(encoding=r['encoding'], attribution=r['attribution']),
       r['encoding']['coefficients_sha256_actual']==hashlib.sha256(np.zeros(TAPS,dtype='<i4').tobytes()).hexdigest()
       and r['attribution']['allowed'])

observed=[]
for name, change in [('inconsistent',dict(first_frame=0,completed_frames=2000)),
                     ('negative',dict(first_frame=-1,completed_frames=N-1))]:
    observed.append(dict(case=name, **cli(fixture('domain_'+name, changes=change))))
record('inconsistent_or_negative_frame_domain_rejected', 'both FAILED exit2', observed,
       all(x['exit_code']==2 and x['failed_prefix'] for x in observed))

p=fixture('missing_frame_domain', drop=('first_frame','completed_frames'))
r=analyze(p)
record('missing_frame_domain_keeps_only_local_scope', 'local arithmetic retained; global range/verification unknown',
       {k:r[k] for k in ('first_frame_global','last_frame_global','completed_frames','frame_domain_ok','attribution')},
       r['first_frame_global'] is None and r['last_frame_global'] is None and r['frame_domain_ok'] is not True)

p=fixture('fractional_frame_domain', changes=dict(first_frame=.5,completed_frames=N+.5))
command=cli(p)
record('fractional_frame_domain_rejected', 'FAILED exit2; frame numbers cannot be truncated', command,
       command['exit_code']==2 and command['failed_prefix'])

q=np.zeros(TAPS,dtype='<i4'); q[0]=2**20
mic=np.ones(N,dtype=np.int64); pred=np.zeros(N,dtype=np.int64)
mic[16:24]=HI; pred[16:24]=-16
p=fixture('prefix_only_event',mic=mic,pred=pred,q=q)
r=analyze(p); a=r['primary_capture_only']; b=r['post_gain']; sl=slice(TAPS+1,None)
wide=mic-pred
expected=dict(whole_peak=float(np.max(np.abs(wide))/SCALE),
              valid_peak=float(np.max(np.abs(wide[sl]))/SCALE),
              valid_headroom=float(-20*np.log10(np.max(np.abs(wide[sl]))/SCALE)))
ok=(a['overflow_samples']==dict(whole=8,valid=0,history=8) and
    a['wide_max_x']['whole']==expected['whole_peak'] and a['wide_max_x']['valid']==expected['valid_peak'] and
    abs(a['wide_headroom_db']['valid']-expected['valid_headroom'])<1e-12 and
    a['mic_peak_dbfs']['valid']==20*np.log10(1/SCALE) and a['pred_peak_dbfs']['valid']==20*np.log10(1/SCALE) and
    b['overflow_samples']==dict(whole=8,valid=0) and b['max_abs']['valid']==1/SCALE and
    r['secondary_model_replay']['prediction_mismatches']==0 and r['secondary_model_replay']['mismatches_in_prefix']==8)
record('observed_prefix_and_valid_margins_separated', expected,
       dict(primary=a,post_gain=b,secondary=r['secondary_model_replay']),ok)

report=dict(B_commit='67d28b2610f606845d4f16280cfd1607800415ab',
            script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            fixtures='synthetic boundaries only; no A voice PCM or board operations',
            cases=cases, passed=sum(x['passed'] for x in cases), total=len(cases),
            near_rail_followup=near_followup)
pathlib.Path(sys.argv[1]).write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print('C bounded probes: %d/%d passed' % (report['passed'],report['total']))
for case in cases:
    if not case['passed']:
        print('remaining:',case['case'])
