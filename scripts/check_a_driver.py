"""A-owned driver acceptance by fake I2C/MMIO; never opens actual devices.

Run on A's returned package. This is a consumer test, not a driver patch.
Nonzero means the package must not be enabled for C's field experiment.
"""
import argparse
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def check(folder, output, v3=False, extras_only=False, only=None):
    folder = Path(folder).resolve()
    cases = []
    specs = [
        ('guard_distinct_counts', True, False, False, [0x00030002, 5, 7], False, False),
        ('bypass_prediction_only', True, False, False, [2, 0, 0], False, False),
        ('terminal_counts', False, False, False, [0x00030002, 5, 7], False, False),
        ('completed_zero_counts', False, False, False, [0, 0, 0], False, False),
        ('protocol_fault', False, True, False, [0, 0, 0], False, False),
        ('operator_cancel', False, False, True, [0, 0, 0], False, False),
        ('restore_failure', False, False, False, [0, 0, 0], True, False),
        ('capture_write_failure', False, False, False, [0, 0, 0], False, True),
    ]
    if v3:
        extra = [
            ('v3_residual_only_continues', False, False, False, [8 << 16, 0, 0], False, False, 0, True),
            ('v3_input_sticky_recorded_with_clean_tail', False, False, False, [0, 0, 0], False, False, 1 << 22, False),
            ('v3_input_sticky_survives_save_failure', False, False, False, [0, 0, 0], False, True, 1 << 22, False),
            ('v3_identity_in_failure_sidecar', False, False, False, [0, 0, 0], False, True, 0, False),
        ]
        specs = extra if extras_only else specs + extra
    oracle_names = ('v3_oracle_legal_negative_rail', 'v3_oracle_truncated_output_domain',
                    'v3_oracle_wide_count_uses_recorded_prediction') if v3 else ()
    if only:
        unknown = set(only) - {s[0] for s in specs} - set(oracle_names)
        if unknown:
            raise ValueError('unknown acceptance cases: ' + ','.join(sorted(unknown)))
        specs = [s for s in specs if s[0] in only]
    for spec in specs:
        name, guard, fault, cancel, counts, restore_error, write_error = spec[:7]
        status_extra, active_then_done = spec[7:] if len(spec) > 7 else (0, False)
        events, regs, register_address, page = [], {}, [0], [0]
        poll_reads = [0]
        observed = None
        completed = 640 if guard or fault else 2441
        class MMIO:
            def __init__(self, addr, size): self.addr = addr
            def write(self, offset, value):
                events.append((self.addr, offset, value))
                if self.addr == 3 and offset == 0: page[0] = value
            def read(self, offset):
                if self.addr == 3:
                    if offset != 8: return page[0]
                    poll_reads[0] += 1
                    return status_extra | ((1<<18) if fault else
                        0 if guard or (active_then_done and poll_reads[0] <= 2) else 1)
                if self.addr == 4: return (512<<4) | 0xb
                if self.addr == 5 and offset == 8: return completed
                if self.addr == 6: return counts[0] if offset == 0 else counts[1]
                if self.addr == 7: return (0x52<<24) | (1<<19) | 1000
                if self.addr == 8 and offset == 8: return counts[2]
                return 0
        class Overlay:
            def __init__(self, *a, **kw):
                self.ip_dict = {n: {'phys_addr': i} for i, n in enumerate(
                    ('audio_control', 'audio_samples', 'audio_calibrate_cmd', 'audio_coefficients',
                     'audio_runtime', 'audio_clips', 'audio_source', 'audio_source_length'), 1)}
        def restore(*a, **kw):
            events.append(('restore', 0, 0))
            if restore_error: raise RuntimeError('injected_restore_failure')
        def write(fd, payload):
            register_address[0] = int.from_bytes(payload[:2], 'big')
            if len(payload) > 2:
                value = payload[2:]
                if register_address[0] == 0x4002: value = value[:-1] + bytes([value[-1]|2])
                regs[register_address[0]] = value
            return len(payload)
        def read(fd, n): return regs.get(register_address[0], b'\x01'*n)
        packages = {n: types.ModuleType(n) for n in ('pynq','pynq.overlays','pynq.overlays.base','fcntl')}
        packages['pynq'].MMIO, packages['pynq'].Overlay = MMIO, Overlay
        packages['pynq.overlays.base'].BaseOverlay = restore
        packages['fcntl'].ioctl = lambda *a: None
        for module_name in ('residual_tools', 'closed_tools', 'replay_tools'):
            spec = importlib.util.spec_from_file_location(module_name, folder/(module_name+'.py'))
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, packages): spec.loader.exec_module(module)
            packages[module_name] = module
        tmp = ROOT/'tmp'; tmp.mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=tmp, prefix='a-acceptance-') as d:
                work = Path(d)
                model = dict(taps=512, lag_first=1, coefficient_format='signed24_fraction20',
                             training_source='board', fixture_id='mock', hp_volume=40,
                             sample_rate_hz=48828.125, coefficients=[0.]*512,
                             coefficients_q20=[0]*512, bias=0.)
                (work/'model.json').write_text(json.dumps(model))
                for asset, fallback in (('audio_replay.bit', b'fake-bit'), ('audio_replay.hwh', b'fake-hwh')):
                    supplied = folder/asset
                    (work/asset).write_bytes(supplied.read_bytes() if v3 and supplied.is_file() else fallback)
                with patch.dict(sys.modules, packages):
                    spec = importlib.util.spec_from_file_location('driver_under_test', folder/'replay_trial.py')
                    driver = importlib.util.module_from_spec(spec)
                    with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(driver)
                    assert events == [], 'import touched hardware'
                    driver.__file__ = str(work/'replay_trial.py')
                    # Preserve a real source file for implementations recording driver hash.
                    (work/'replay_trial.py').write_bytes((folder/'replay_trial.py').read_bytes())
                    for helper in ('replay_tools.py', 'closed_tools.py', 'residual_tools.py'):
                        (work/helper).write_bytes((folder/helper).read_bytes())
                    error = None
                    with patch.object(driver.os, 'open', return_value=1), patch.object(driver.os, 'close'), \
                         patch.object(driver.os, 'read', side_effect=read), patch.object(driver.os, 'write', side_effect=write), \
                         patch.object(driver.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                        try:
                            if write_error:
                                def fail_save(*args, **kwargs):
                                    starts = [i for i,(addr,offset,value) in enumerate(events)
                                              if addr == 1 and offset == 0 and value & 1]
                                    assert starts, 'fixture never armed'
                                    assert any(i > starts[-1] and event == (1,0,0)
                                               for i,event in enumerate(events)), 'save attempted before post-start PL mute'
                                    assert any(i > starts[-1] and event == ('restore',0,0)
                                               for i,event in enumerate(events)), 'save attempted before recovery'
                                    events.append(('save_attempt',0,0))
                                    raise OSError('injected_disk_full')
                                with patch.object(driver.np, 'savez_compressed', side_effect=fail_save):
                                    driver.replay_trial(work/'capture.npz','mock',work/'model.json',np.zeros(1000,dtype='<i2'),
                                        bypass=True,gain_db=-36,seconds=.05,hp_volume=40,
                                        speaker_confirmed=True,local_capture_confirmed=True,before_start=lambda: not cancel)
                            else:
                                driver.replay_trial(work/'capture.npz','mock',work/'model.json',np.zeros(1000,dtype='<i2'),
                                    bypass=True,gain_db=-36,seconds=.05,hp_volume=40,
                                    speaker_confirmed=True,local_capture_confirmed=True,before_start=lambda: not cancel)
                        except (Exception, KeyboardInterrupt) as exc: error = str(exc)
                    assert ('restore',0,0) in events, 'restoration was not attempted'
                    assert (1,0,0) in events, 'PL mute was not attempted'
                    if cancel:
                        assert not any(a==1 and o==0 and v&1 for a,o,v in events), 'cancel started audio'
                        assert error, 'cancel must stop the batch'
                    elif write_error:
                        assert error, 'write failure must not report success'
                        assert (work/'capture.status.json').is_file(), 'save failure needs finalized status sidecar'
                        status = json.loads((work/'capture.status.json').read_text())
                        assert status.get('save_error'), 'disk failure reason missing'
                        if name == 'v3_input_sticky_survives_save_failure':
                            assert status.get('input_full_scale_seen') is True, 'input full-scale evidence lost when NPZ save fails'
                            assert status.get('capture_status', 0) & (1 << 22), 'raw bit22 lost in failure sidecar'
                        if name == 'v3_identity_in_failure_sidecar':
                            for key, identity_path in (('bit_sha256', work/'audio_replay.bit'),
                                    ('hwh_sha256', work/'audio_replay.hwh'),
                                    ('driver_sha256', folder/'replay_trial.py'),
                                    ('replay_tools_sha256', folder/'replay_tools.py')):
                                assert status.get(key) == hashlib.sha256(identity_path.read_bytes()).hexdigest(), key + ' missing or incorrect in failure sidecar'
                            assert status.get('package_version') == 'audio-replay-v3' or status.get('replay_abi_version') == 3, 'v3 package not identified in failure sidecar'
                    else:
                        assert (work/'capture.npz').is_file(), 'post-start failure lost capture'
                        with np.load(work/'capture.npz', allow_pickle=False) as z:
                            m = json.loads(str(z['metadata_json'].item()))
                            observed = {k: m.get(k) for k in ('prediction_saturations','residual_saturations','gain_saturations','mix_saturations')}
                            assert len(z['reference']) == completed, 'capture extent mismatch'
                        expected = [counts[0]&65535, counts[0]>>16, counts[1], counts[2]]
                        keys = ('prediction_saturations','residual_saturations','gain_saturations','mix_saturations')
                        assert [m.get(k) for k in keys] == expected, 'count unpacking/alias error'
                        assert m.get('clip_counts_raw') == counts, 'raw counters missing or wrong'
                        versions = ('a-replay-evidence-v2', 'a-replay-evidence-v3') if v3 else ('a-replay-evidence-v2',)
                        assert m.get('driver_evidence_version') in versions, 'driver evidence version missing'
                        with np.load(work/'capture.npz', allow_pickle=False) as z:
                            assert np.array_equal(z['source_pcm16'], np.zeros(1000,dtype='<i2')), 'source evidence missing'
                        assert m.get('first_frame') == 0 and m.get('completed_frames') == completed
                        assert m.get('source_end_frame_exclusive') == 1000 and m.get('source_schedule_verified') is True
                        assert m.get('early_stop') is (guard or fault or bool(status_extra & (1<<22))), 'actual stop flag wrong'
                        if name == 'v3_input_sticky_recorded_with_clean_tail':
                            assert m.get('input_full_scale_seen') is True, 'raw bit22 not decoded'
                            assert m.get('mic_full_scale_samples') == 0, 'fixture must have a clean captured tail'
                            assert m.get('stop_reason') == 'input_clip' and error, 'input full scale did not stop the run'
                        if name == 'v3_residual_only_continues':
                            assert error is None and m.get('stop_reason') == 'completed', 'pre-gain residual alone stopped v3'
                        status = json.loads((work/'capture.status.json').read_text())
                        assert status.get('recovery_ok') is (not restore_error), 'recovery result missing'
                        if restore_error: assert error, 'restoration failure must stop the batch'
                cases.append(dict(name=name, passed=True))
        except Exception as exc:
            cases.append(dict(name=name, passed=False, reason=type(exc).__name__+': '+str(exc),
                              raw_register_words=counts, observed_metadata_counts=observed))
    if v3:
        pure_spec = importlib.util.spec_from_file_location('closed_tools', folder/'closed_tools.py')
        pure_closed = importlib.util.module_from_spec(pure_spec)
        pure_spec.loader.exec_module(pure_closed)
        with patch.dict(sys.modules, {'closed_tools': pure_closed}):
            pure_spec = importlib.util.spec_from_file_location('v3_oracle_under_test', folder/'replay_tools.py')
            tool = importlib.util.module_from_spec(pure_spec)
            pure_spec.loader.exec_module(tool)
        for name in oracle_names:
            if only and name not in only:
                continue
            try:
                ver = None
                raw = np.zeros((640, 4), dtype=np.int64)
                q = np.zeros(512, dtype=np.int64)
                source = np.zeros(1, dtype=np.int16)
                first = 1000 if name != 'v3_oracle_legal_negative_rail' else 0
                expected_wide = 0
                if name == 'v3_oracle_legal_negative_rail':
                    raw[:, 1] = raw[:, 3] = -2**23
                if name == 'v3_oracle_wide_count_uses_recorded_prediction':
                    q[-1] = 1 << 20
                    raw[:, 1] = raw[:, 3] = 2**23-51
                    raw[:512, 2] = -256
                    raw[:512, 3] = 2**23-1
                    source = np.full(1000, -1, dtype=np.int16)
                    expected_wide = 512
                ver = tool.verify_replay(raw, q, False, 0, source, first)
                assert ver['bit_exact'], 'oracle rejected a valid integer trace'
                assert ver.get('wide_residual_frames') == expected_wide, 'wide diagnostic disagrees with strict observed mic-pred range'
                expected_checked = 126 if first else 638
                assert ver.get('output_checked_frames') == expected_checked, 'truncated output must begin at skip+2'
                cases.append(dict(name=name, passed=True))
            except Exception as exc:
                cases.append(dict(name=name, passed=False, reason=str(exc), observed=ver))
    result = dict(schema_version=1, suite='c-a-driver-acceptance-v3' if v3 else 'c-a-driver-acceptance-v2', hardware_access=False,
                  driver_sha256=hashlib.sha256((folder/'replay_trial.py').read_bytes()).hexdigest(),
                  package_hashes={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                                  for name in ('replay_trial.py','replay_tools.py','audio_replay.bit','audio_replay.hwh')
                                  if (folder/name).is_file()},
                  accepted=bool(cases) and all(c['passed'] for c in cases), cases=cases)
    Path(output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf8')
    return result


def check_continuous(folder, output):
    """Consume A's exact fake register fixture, plus independent callback/save controls."""
    folder=Path(folder).resolve();source=(folder/'condition4_injection.py').read_text(encoding='utf8')
    tree=ast.parse(source);nodes=[]
    for node in tree.body:
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='print':
            break
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HERE' for t in node.targets):
            node.value=ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),args=[ast.Constant(str(folder))],keywords=[])
        nodes.append(node)
    cases=[];tmp=ROOT/'tmp';tmp.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp,prefix='c-continuous-review-') as d, \
            patch.dict(sys.modules),patch.dict(os.environ,{'TMPDIR':d}),contextlib.redirect_stdout(io.StringIO()):
        scope={'__name__':'a_exact_register_fixture'}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(folder/'condition4_injection.py'),'exec'),scope)
        driver=scope['live_run'];original_run=driver.live_run
        scenario=scope['scenario'];mmio=scope['FakeMMIO'];fake_os=scope['FakeOS']
        original_write=mmio.write;original_i2c=fake_os.write;events=[];armed=[False];fail_shutdown=[False]
        def write(self,offset,value):
            events.append(('pl',self.addr,offset,value))
            if self.addr==0x41200000 and offset==0 and value&1:armed[0]=True
            return original_write(self,offset,value)
        def i2c(fd,payload):
            addr=int.from_bytes(payload[:2],'big')
            if len(payload)>2:
                events.append(('codec',addr,bytes(payload[2:])))
                if fail_shutdown[0] and armed[0] and addr==0x401C:raise OSError('C injected shutdown mute failure')
            return original_i2c(fd,payload)
        mmio.write=write;fake_os.write=i2c
        def execute(name,packed=0,done=True,callback=None,save_fail=False,shutdown_fail=False):
            events.clear();armed[0]=False;fail_shutdown[0]=shutdown_fail
            callback_facts={}
            def before():
                regs={e[1]:e[2] for e in events if e[0]=='codec'}
                callback_facts.update(armed=armed[0],codec_muted=all(regs.get(a)==bytes([v]) for a,v in
                    ((0x401C,0),(0x401E,0),(0x4023,0xE5),(0x4024,0xE5))))
                return callback
            def run(*args,**kwargs):
                kwargs['stop_file']=str(Path(d)/'not-requested.stop')
                if callback is not None:kwargs['before_start']=before
                return original_run(*args,**kwargs)
            driver.live_run=run
            with patch.object(driver.np,'savez_compressed',side_effect=OSError('C injected disk full')) if save_fail else contextlib.nullcontext():
                scenario(name,packed=packed,gain_word=5 if packed and done else 0,mix_word=0,done=done)
            state=json.loads((Path(d)/('inject_'+name)/('run_'+name+'.status.json')).read_text(encoding='utf8'))
            return state,dict(callback_facts)
        for name,packed,done in (('saturation',0x30002,False),('terminal_saturation',0x30002,True),('clean',0,True)):
            s,_=execute(name,packed,done)
            expected='saturation' if not done else 'completed_with_protection' if packed else 'completed'
            cases.append(dict(name=name,passed=s['stop_reason']==expected and s['counts']['prediction']==(packed&65535)
                and s['counts']['residual']==packed>>16 and s['recovered'] is True,stop_reason=s['stop_reason'],counts=s['counts']))
        s,_=execute('shutdown_mute_failure',0x30002,False,shutdown_fail=True)
        cases.append(dict(name='armed_shutdown_mute_failure',passed='t_arm' in s and s.get('muted') is False and s['recovered'] is False,
            arm_reached='t_arm' in s,muted=s.get('muted'),recovered=s['recovered'],cleanup_errors=s['cleanup_errors']))
        s,_=execute('save_failure',save_fail=True)
        cases.append(dict(name='npz_save_failure_sidecar',passed=bool(s.get('save_error')),save_error=s.get('save_error')))
        s,facts=execute('callback_start',callback=True)
        cases.append(dict(name='callback_before_codec_unmute',passed=facts.get('codec_muted') is True and facts.get('armed') is False,
            callback_facts=facts))
        s,facts=execute('callback_cancel',callback=False)
        cases.append(dict(name='cancel_records_verified_cleanup',passed='t_arm' not in s and s.get('disarm_ok') is True
            and s.get('mute_ok') is True and s['recovered'] is True,stop_reason=s['stop_reason'],callback_facts=facts,
            disarm_ok=s.get('disarm_ok'),mute_ok=s.get('mute_ok'),recovered=s['recovered']))
    result=dict(suite='c-a-continuous-consumer-acceptance',hardware_access=False,
        driver_sha256=hashlib.sha256((folder/'live_run.py').read_bytes()).hexdigest(),
        a_fixture_sha256=hashlib.sha256(source.encode()).hexdigest(),cases=cases,accepted=all(c['passed'] for c in cases))
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


def check_field_failures(folder, output):
    """Exercise reviewed Python payloads with a failed driver; no shell or board."""
    folder = Path(folder).resolve()
    (ROOT/'tmp').mkdir(exist_ok=True)
    cases = []
    for name in ('field_stationary_v3_l8.sh', 'field_human_both.sh', 'tone_arms_v3.sh'):
        source = (folder/name).read_text(encoding='utf-8')
        payload = source.split("<<'PY'", 1)[1].split('\n', 1)[1].rsplit('\nPY', 1)[0]
        calls = []
        module = types.ModuleType('replay_trial')
        def failed_driver(*args, **kwargs):
            calls.append(dict(path=str(args[0]), direct_only=kwargs.get('direct_only'),
                              zero_coeff=kwargs.get('zero_coeff')))
            raise RuntimeError('C synthetic gate/trial failure')
        module.replay_trial = failed_driver
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp', prefix='c-field-failure-') as work:
            class RedirectDirectory(ast.NodeTransformer):
                def visit_Assign(self, node):
                    if any(isinstance(t, ast.Name) and t.id == 'DIR' for t in node.targets):
                        node.value = ast.Call(func=ast.Name(id='Path', ctx=ast.Load()),
                                              args=[ast.Constant(work)], keywords=[])
                    return node
            tree = ast.fix_missing_locations(RedirectDirectory().visit(ast.parse(payload)))
            error = None
            with patch.dict(sys.modules, {'replay_trial': module}), \
                    patch.object(sys, 'argv', [name, 'zero']), patch('builtins.input', return_value='CANCEL'), \
                    patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
                try:
                    exec(compile(tree, str(folder/name), 'exec'), {'__name__': '__main__'})
                except SystemExit:
                    pass
                except Exception as exc:
                    error = type(exc).__name__ + ': ' + str(exc)
            cases.append(dict(name=name, passed=error is None and len(calls) <= 1,
                              driver_calls=len(calls), calls=calls, error=error,
                              source_sha256=hashlib.sha256((folder/name).read_bytes()).hexdigest()))
    result = dict(suite='c-v3-field-failure-exits', hardware_access=False,
                  scope='Python payload only; synthetic CANCEL/failure, no operator action inferred',
                  accepted=all(c['passed'] for c in cases), cases=cases)
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--driver-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--continuous',action='store_true')
    parser.add_argument('--v3', action='store_true', help='include v3 diagnostic/input/identity controls')
    parser.add_argument('--extras-only', action='store_true', help='only v3 controls, after unchanged legacy eight passed')
    parser.add_argument('--only-case', action='append', help='repeat only changed or previously failing cases')
    parser.add_argument('--field-failures', action='store_true', help='review v3 script failure exits with a stub driver')
    args = parser.parse_args()
    result = (check_field_failures(args.driver_dir,args.output) if args.field_failures else
              check_continuous(args.driver_dir,args.output) if args.continuous else
              check(args.driver_dir, args.output, args.v3, args.extras_only, args.only_case))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['accepted'] else 1)
