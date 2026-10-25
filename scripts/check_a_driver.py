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


def check(folder, output):
    folder = Path(folder).resolve()
    cases = []
    for name, guard, fault, cancel, counts, restore_error, write_error in (
        ('guard_distinct_counts', True, False, False, [0x00030002, 5, 7], False, False),
        ('bypass_prediction_only', True, False, False, [2, 0, 0], False, False),
        ('terminal_counts', False, False, False, [0x00030002, 5, 7], False, False),
        ('completed_zero_counts', False, False, False, [0, 0, 0], False, False),
        ('protocol_fault', False, True, False, [0, 0, 0], False, False),
        ('operator_cancel', False, False, True, [0, 0, 0], False, False),
        ('restore_failure', False, False, False, [0, 0, 0], True, False),
        ('capture_write_failure', False, False, False, [0, 0, 0], False, True),
    ):
        events, regs, register_address, page = [], {}, [0], [0]
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
                    return (1<<18) if fault else (0 if guard else 1)
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
                (work/'audio_replay.bit').write_bytes(b'fake-bit')
                (work/'audio_replay.hwh').write_bytes(b'fake-hwh')
                with patch.dict(sys.modules, packages):
                    spec = importlib.util.spec_from_file_location('driver_under_test', folder/'replay_trial.py')
                    driver = importlib.util.module_from_spec(spec)
                    with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(driver)
                    assert events == [], 'import touched hardware'
                    driver.__file__ = str(work/'replay_trial.py')
                    # Preserve a real source file for implementations recording driver hash.
                    (work/'replay_trial.py').write_bytes((folder/'replay_trial.py').read_bytes())
                    error = None
                    with patch.object(driver.os, 'open', return_value=1), patch.object(driver.os, 'close'), \
                         patch.object(driver.os, 'read', side_effect=read), patch.object(driver.os, 'write', side_effect=write), \
                         patch.object(driver.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                        try:
                            if write_error:
                                with patch.object(driver.np, 'savez_compressed', side_effect=OSError('injected_disk_full')):
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
                        assert m.get('driver_evidence_version') == 'a-replay-evidence-v2', 'driver evidence version missing'
                        with np.load(work/'capture.npz', allow_pickle=False) as z:
                            assert np.array_equal(z['source_pcm16'], np.zeros(1000,dtype='<i2')), 'source evidence missing'
                        assert m.get('first_frame') == 0 and m.get('completed_frames') == completed
                        assert m.get('source_end_frame_exclusive') == 1000 and m.get('source_schedule_verified') is True
                        assert m.get('early_stop') is (guard or fault), 'actual stop flag wrong'
                        status = json.loads((work/'capture.status.json').read_text())
                        assert status.get('recovery_ok') is (not restore_error), 'recovery result missing'
                        if restore_error: assert error, 'restoration failure must stop the batch'
                cases.append(dict(name=name, passed=True))
        except Exception as exc:
            cases.append(dict(name=name, passed=False, reason=type(exc).__name__+': '+str(exc),
                              raw_register_words=counts, observed_metadata_counts=observed))
    result = dict(schema_version=1, suite='c-a-driver-acceptance-v2', hardware_access=False,
                  driver_sha256=hashlib.sha256((folder/'replay_trial.py').read_bytes()).hexdigest(),
                  accepted=all(c['passed'] for c in cases), cases=cases)
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--driver-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--continuous',action='store_true')
    args = parser.parse_args()
    result = check_continuous(args.driver_dir,args.output) if args.continuous else check(args.driver_dir, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['accepted'] else 1)
