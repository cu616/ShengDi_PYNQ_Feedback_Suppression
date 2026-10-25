"""Shipped project fixture: real Q20 arithmetic and actual sprint scheduling.

No PYNQ import or board access. Signals are constructed algebraically, not an
acoustic simulation. Synthetic CLEAR/cleanup responses only exercise branches;
they are never measurements of speech, recovery or feedback suppression.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from closed_tools import gain_pcm, rounded_shift
from evaluation import sha
from model_comparison import qhash
from replay_tools import verify_replay, MAX_SOURCE_FRAMES
from sprint_experiment import POLICY, RATE, check_package, run_sprint


class SoftwareRunner:
    def __init__(self, manifest):
        self.manifest = manifest
        self.calls = []

    def __call__(self, path, fixture, model, source, **kw):
        if not kw['before_start']():
            raise RuntimeError('operator_cancel')
        q = np.asarray(json.loads(Path(model).read_text(encoding='utf8'))['coefficients_q20'], dtype='<i4')
        n = int(kw['seconds']*RATE)
        first = max(0, n-16384)
        t = np.arange(n)/RATE
        gain = 0 if kw['direct_only'] else int(np.floor(4096*10**(kw['gain_db']/20)+.5))
        reference = np.zeros(n, dtype=np.int64)
        count = min(n, len(source))
        reference[:count] = source[:count].astype(np.int64)*256
        if kw['direct_only']:
            target = np.zeros(n, dtype=np.int64)
            count = min(len(source), n-125)
            target[125:125+count] = np.rint(source[:count].astype(float)*128).astype(np.int64)
        else:
            target = np.rint(2**23*.05*(np.sin(2*np.pi*500*t)+np.sin(2*np.pi*2000*t)+
                                       np.sin(2*np.pi*8400*t))).astype(np.int64)
        reference[2:] += gain_pcm(target[:-2], gain)
        prediction = rounded_shift(np.convolve(reference, np.r_[np.int64(0), q])[:n], 20)
        microphone = target if kw['bypass'] else target+prediction
        residual = microphone if kw['bypass'] else microphone-prediction
        raw = np.column_stack((reference, microphone, prediction, residual))
        if np.any(raw <= -2**23) or np.any(raw >= 2**23-1):
            raise ValueError('software fixture exceeds signed24; product gates unchanged')
        verification = verify_replay(raw[first:], q, kw['bypass'], gain, source, first)
        if verification.get('bit_exact') is not True:
            raise ValueError('software fixture arithmetic mismatch')
        meta = dict(capture_id='software-'+path.stem, evidence_kind='software_fixture',
            driver_evidence_version='a-replay-evidence-v2', first_frame=first,
            completed_frames=n, frames=n-first, fixture_id=fixture, gain_q12=gain,
            hp_volume=kw['hp_volume'], sample_rate_hz=RATE, bypass=kw['bypass'],
            bit_sha256=self.manifest['hashes']['audio_replay.bit'], model_sha256=sha(model),
            coefficients_sha256=qhash(q), source_pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest(),
            source_frames=len(source), source_end_frame_exclusive=len(source), source_schedule_verified=True,
            clip_counts_raw=[0,0,0], guard_tripped=False, prediction_saturations=0,
            residual_saturations=0, gain_saturations=0, mix_saturations=0, verification=verification)
        np.savez_compressed(path, reference=reference[first:]/2**23, microphone=microphone[first:]/2**23,
            prediction_pcm=prediction[first:], residual_pcm=residual[first:], coefficients_q20=q,
            source_pcm16=source, sample_rate_hz=RATE, metadata_json=json.dumps(meta))
        path.with_suffix('.status.json').write_text(json.dumps(dict(recovery_ok=True, cleanup_errors=[],
            save_error=None, evidence_kind='software_fixture')), encoding='utf8')
        self.calls.append(dict(seconds=kw['seconds'], source_frames=len(source), capture_frames=n-first,
                               bit_exact=verification['bit_exact']))
        return meta


def run_selftest(base=None, require_preflight=True):
    base = Path(base or Path(__file__).resolve().parent).resolve()
    manifest = check_package(base, require_preflight=require_preflight)
    runner = SoftwareRunner(manifest)

    def answer(prompt):
        if 'HUMAN_LIVE_AND_LISTENING' in prompt:
            return 'PROXY'
        for token in ('READY','SAME_SCENE','SOURCE_OFF','START','CLEAR'):
            if token in prompt:
                return token
        if '一次填写' in prompt:
            return 'software fixture only; no physical scene or acoustic claims'
        return ''

    with tempfile.TemporaryDirectory(prefix='c-sprint-selftest-', dir=base.parent) as directory:
        work = Path(directory)
        for name in ('model.json','eq.json'):
            shutil.copy2(base/name, work/name)
        with contextlib.redirect_stdout(io.StringIO()):
            state = run_sprint(work, ask=answer, runner=runner, validator=lambda _: manifest)
        mapping = []
        controls = SoftwareRunner(manifest)
        for gain_db in (-12., -6., 0.):
            path=work/('mapping-%s.npz'%gain_db)
            m=controls(path,'room_v1_20261021',work/'model.json',np.zeros(1,dtype='<i2'),
                direct_only=False,bypass=True,gain_db=gain_db,seconds=.25,hp_volume=40,before_start=lambda:True)
            with np.load(path,allow_pickle=False) as capture:
                # Match the exact n-2 microphone samples, excluding DC before RMS.
                reference=capture['reference'][2:];mic=capture['microphone'][:-2]
                actual=float(20*np.log10(np.std(reference)/np.std(mic)))
            expected=float(20*np.log10(m['gain_q12']/4096))
            mapping.append(dict(gain_db=gain_db,gain_q12=m['gain_q12'],ref_over_mic_db=actual,
                expected_db=expected,error_db=actual-expected,bit_exact=m['verification']['bit_exact'],
                ok=abs(actual-expected)<.001 and m['verification']['bit_exact']))
    trials = []
    for row, call in zip(state['trials'], runner.calls):
        gate = row.get('path_gate')
        window = row['analysis'].get('tail_analysis_window', {})
        response=row.get('source_response')
        frames = gate['end_frame']-gate['first_frame'] if gate else response['frames'] if response else window.get('frames', 0)
        ok = (frames >= 2048 and row['recovery_ok'] is True and not row['stop_reasons'] and
              call['bit_exact'] is True and (gate['passed'] if gate else response['valid'] if response else row['category'] not in ('invalid','protection')))
        trials.append(dict(id=row['id'], role=row['role'], **call,
            transition_frames=row['analysis']['capture_window']['transition_frames'],
            window_kind='source_on_tone' if gate else 'forced_source_response' if response else 'saved_waveform',
            window_frames=frames, ok=bool(ok), category=row['category']))
    gates = [row['path_gate'] for row in state['trials'] if row.get('path_gate')]
    checks = dict(schedule_completed=state['status']=='completed_with_unmeasured_requirements',
        trials_complete=len(trials)==13 and len(runner.calls)==13, gates_passed=len(gates)==6 and all(g['passed'] for g in gates),
        fir_pairs_valid=len(state['fir_pairs'])==2 and all(p['window_comparison_valid'] for p in state['fir_pairs']),
        continuous_left_untested=state['checks']['continuous_60s']['status']=='not_tested',
        listener_left_untested=state['checks']['listener']['status']=='not_tested',
        proxy_voice_left_untested=state['checks']['real_voice']['status']=='not_tested',
        source_on_not_called_stable=all(r['category']=='unknown' and r['tail_valid'] is False
            for r in state['trials'] if r['role'].startswith('fir-')),
        gain_mapping_passed=all(c['ok'] for c in mapping))
    checks['source_buffer_fits']=all(c['source_frames']<=MAX_SOURCE_FRAMES for c in runner.calls)
    model = json.loads((base/'model.json').read_text(encoding='utf8'))
    report = dict(schema_version=1, policy=POLICY, all_ok=all(checks.values()) and all(t['ok'] for t in trials),
        evidence_kind='software_fixture', scope='package workflow, windows and deployed Q20 arithmetic only; no acoustic or board acceptance',
        source_commits=manifest['source_commits'], a_assets=manifest['a_assets'],
        gain_mapping_controls=mapping, gain_mapping_scope='software bypass control with deployed Q20; routing/arithmetic only',
        payload_hashes={k:v for k,v in manifest['hashes'].items() if k!='preflight.json'},
        model=dict(taps=model['taps'], lag_first=model['lag_first'], coefficients_sha256=qhash(model['coefficients_q20'])),
        checks=checks, trials=trials, stop_reason=state.get('stop_reason'), hardware_test='not_tested',
        continuous_60s='not_tested', acoustic_effect='not_evaluated', estimated_board_active_minutes=sum(t['seconds'] for t in trials)/60,
        estimate_scope='audio/observation time only; configuration, operator and optional recording waits additional')
    return report


def selftest_line(report):
    return 'SELFTEST %s | trials=%d | window_frames min=%d | gate=%s | 预计板端 %.3f分钟（另加配置和人工等待）' % (
        'ok' if report['all_ok'] else 'FAILED', len(report['trials']),
        min((t['window_frames'] for t in report['trials']), default=0),
        'passed' if report['checks']['gates_passed'] else 'failed', report['estimated_board_active_minutes'])


if __name__ == '__main__':
    import sys
    result = run_selftest()
    print(selftest_line(result))
    sys.exit(0 if result['all_ok'] else 2)
