"""Condition 4: validate the saturation-protection path with simulated registers.

No board, no audio. A fake MMIO layer feeds live_run the same register words the PL would
produce, so the stop/mute/evidence logic is exercised exactly as on hardware.
"""
import json
import os
import sys
import types
from pathlib import Path

HERE = Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-a\board\audio_replay')


# ---------------------------------------------------------------- fake pynq
class FakeMMIO:
    """Register file for one AXI GPIO block, addressed by the phys_addr of the IP."""

    def __init__(self, addr, size):
        self.addr = addr
        self.regs = {}
        self.plan = FakeMMIO.plan.setdefault(addr, {})

    def write(self, offset, value):
        self.regs[offset] = int(value)

    def read(self, offset):
        return int(self.plan.get(offset, self.regs.get(offset, 0)))

    plan = {}


class FakeOverlay:
    def __init__(self, path, download=True):
        base = {"audio_control": 0x41200000, "audio_samples": 0x41210000,
                "audio_calibrate_cmd": 0x41220000, "audio_coefficients": 0x41230000,
                "audio_runtime": 0x41240000, "audio_clips": 0x41250000,
                "audio_source": 0x41260000, "audio_source_length": 0x41270000}
        self.ip_dict = {k: {"phys_addr": v} for k, v in base.items()}


class OSP:
    """Proxy the real os module, overriding only the I2C file-descriptor calls."""

    _real = os

    def __getattr__(self, name):
        return getattr(self._real, name)

    @staticmethod
    def open(path, flags, *a):
        return FakeOS.current

    @staticmethod
    def write(fd, payload):
        return FakeOS.write(fd, payload)

    @staticmethod
    def read(fd, count):
        return FakeOS.read(fd, count)

    @staticmethod
    def close(fd):
        return None


class FakeOS:
    """Stand-in for the I2C file descriptor used by the codec mute path."""

    class Fd:
        def __init__(self, fail_write=False):
            self.fail_write = fail_write
            self.writes = 0

    current = None

    @staticmethod
    def open(path, flags):
        return FakeOS.current

    @staticmethod
    def write(fd, payload):
        fd.writes = getattr(fd, 'writes', 0) + 1
        # the startup mute must succeed; only the shutdown mute is made to fail
        if getattr(fd, 'fail_write', False) and fd.writes > 4:
            raise OSError('simulated I2C failure')
        return len(payload)

    @staticmethod
    def read(fd, count):
        # PLL status needs bit1 set in byte 5; route/power checks compare to b'\x01'
        if count == 6:
            return bytes.fromhex('000000002803')   # PLL locked, matches PLL_EXPECTED
        return b'\x01' * count

    @staticmethod
    def close(fd):
        pass

    path = types.SimpleNamespace(exists=lambda p: False, remove=lambda p: None)


fake_pynq = types.ModuleType('pynq')
fake_pynq.MMIO = FakeMMIO
fake_pynq.Overlay = FakeOverlay
sys.modules['pynq'] = fake_pynq
sys.modules['fcntl'] = types.SimpleNamespace(ioctl=lambda *a: 0)

sys.path.insert(0, str(HERE))
import live_run  # noqa: E402

live_run.MMIO = FakeMMIO
live_run.Overlay = FakeOverlay
live_run.os = OSP()


def scenario(name, *, packed, gain_word, mix_word, done, mute_fails=False):
    """Run one simulated session and report the evidence fields that matter."""
    FakeMMIO.plan.clear()
    tmp = Path(os.environ.get('TMPDIR', r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work')) \
        / ('inject_' + name)
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / 'audio_replay.bit').write_bytes(b'fake')
    (tmp / 'audio_replay.hwh').write_text(
        '<PARAMETER NAME="MAX_RUN_FRAMES" VALUE="488281"/>', encoding='utf-8')
    model = tmp / 'model.json'
    model.write_text(json.dumps({'coefficients_q20': [0] * 512, 'taps': 512,
                                 'lag_first': 1, 'fixture_id': 'room_v1_20261021',
                                 'hp_volume': 40}), encoding='utf-8')

    status = 0x8001 if done else 0x0000
    # clips: low word = packed prediction/residual, high word = gain clip counter
    FakeMMIO.plan[0x41250000] = {0: packed, 8: gain_word}
    FakeMMIO.plan[0x41220000] = {8: status}
    FakeMMIO.plan[0x41240000] = {8: 48828}
    FakeMMIO.plan[0x41260000] = {8: 0x52000000 | 1 | (1 << 19)}
    FakeMMIO.plan[0x41270000] = {8: mix_word}
    FakeMMIO.plan[0x41230000] = {8: 0x200B}

    FakeOS.current = FakeOS.Fd(fail_write=mute_fails)
    out = tmp / ('run_%s.npz' % name)
    if out.exists():
        out.unlink()
    state = live_run.live_run(str(out), 'room_v1_20261021', str(model), gain_db=0.0,
                              seconds=0.5, hp_volume=40, bypass=True, zero_coeff=False,
                              speaker_confirmed=True, local_capture_confirmed=True,
                              label=name, poll_seconds=0.01)
    keep = {k: state.get(k) for k in ('stop_reason', 'counts', 'muted', 'disarm_ok',
                                      'mute_ok', 'recovered', 'status', 'error')}
    print('%-24s %s' % (name, json.dumps(keep, ensure_ascii=False)))
    return keep


print('condition 4: simulated-register fault injection (no board, no audio)')
a = scenario('saturation_only', packed=0x00030002, gain_word=0, mix_word=0, done=False)
b = scenario('done_plus_saturation', packed=0x00030002, gain_word=5, mix_word=0, done=True)
c = scenario('mute_failure', packed=0x00030002, gain_word=0, mix_word=0, done=False,
             mute_fails=True)
d = scenario('clean_completion', packed=0, gain_word=0, mix_word=0, done=True)

print()
ok = True
if a['stop_reason'] != 'saturation':
    print('FAIL 1: expected saturation, got', a['stop_reason']); ok = False
if b['stop_reason'] != 'completed_with_protection':
    print('FAIL 2: expected completed_with_protection, got', b['stop_reason']); ok = False
if c['muted'] or c['recovered']:
    print('FAIL 3: mute failure must not report muted/recovered true'); ok = False
if d['stop_reason'] != 'completed' or d['counts']['prediction'] != 0:
    print('FAIL 4: clean run misclassified'); ok = False
if a['counts']['prediction'] != 2 or a['counts']['residual'] != 3:
    print('FAIL 5: counter unpack wrong:', a['counts']); ok = False
if b['counts']['gain'] != 5:
    print('FAIL 6: gain counter must keep the full 32-bit value:', b['counts']); ok = False
print('CONDITION4_RESULT', 'PASS' if ok else 'FAIL')
