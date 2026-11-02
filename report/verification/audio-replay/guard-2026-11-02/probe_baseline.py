"""Software sequence from C's guard150-baseline-probe.json, replayed against the patched hw_api.

No board, no pynq: the MMIO leaves are replaced by two registers. The identity is stubbed so poll()
does not touch I2C.

Before the fix the old baseline (0x40000) was latched while idle, so a real fault that appears
during the run was masked and poll() returned protected=False. After the fix, the driver's
before_start callback (_arm_baseline) re-takes the baseline at the actual arm point, so the same
fault is reported.
"""
import importlib.util
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest')
SRC = ROOT / 'board' / 'audio_replay' / 'hw_api.py'
FAULT = 1 << 18


def load():
    sys.modules.setdefault('fcntl', types.SimpleNamespace(ioctl=lambda *a, **k: None))
    spec = importlib.util.spec_from_file_location('hw_api_guard', SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Reg:
    def __init__(self):
        self.v = 0

    def read(self, _off):
        return self.v

    def write(self, _off, val):
        self.v = val & 0xFFFFFFFF


def main():
    hw = load()

    def run_once(rebaseline):
        mm = {'control': Reg(), 'status': Reg()}
        p = hw.create_product({'package_dir': str(ROOT / 'board' / 'audio_replay' / 'v3-io')})
        p._ensure_mmio = lambda reuse=True: mm
        p.identity = lambda: {k: 0 for k in hw.IDENTITY} if hasattr(hw, 'IDENTITY') else {}
        # poll() calls self.identity(); give it a complete dict either way.
        p.identity = lambda: {'aux_db': 0.0, 'aux_raw_left': 5, 'aux_raw_right': 5,
                              'hp_volume': 40, 'gain_q12': 0, 'sample_rate_hz': 48828.125,
                              'driver_sha256': '0' * 64, 'bit_sha256': '0' * 64,
                              'hwh_sha256': '0' * 64, 'helper_sha256': '0' * 64}
        rows = {}

        mm['status'].v = FAULT
        mm['control'].v = 1631 << 16
        r = p.poll()
        rows['idle'] = {'protected': r['protected'], 'protection': r['protection'],
                        'capture_status': r['capture_status'], 'mmio_held': r['mmio_held']}

        p._current_op = 'run'
        mm['status'].v = 0
        mm['control'].v = (1631 << 16) | 1
        r = p.poll()
        rows['after_reset'] = {'protected': r['protected'], 'protection': r['protection'],
                               'protect_baseline': r['protect_baseline']}

        if rebaseline:
            armed = p._arm_baseline(None)
            rows['arm_baseline'] = {'returned': armed, 'protect_baseline': p._protect_baseline}

        mm['status'].v = FAULT
        r = p.poll()
        rows['new_fault_in_run'] = {'protected': r['protected'], 'protection': r['protection'],
                                    'capture_status': r['capture_status'],
                                    'mmio_held': r['mmio_held']}
        return rows

    old = run_once(rebaseline=False)
    new = run_once(rebaseline=True)

    # cancellation semantics must survive the new callback
    mm = {'control': Reg(), 'status': Reg()}
    p = hw.create_product({'package_dir': str(ROOT / 'board' / 'audio_replay' / 'v3-io')})
    p._ensure_mmio = lambda reuse=True: mm
    ev = __import__('threading').Event()
    ev.set()
    before = p._protect_baseline
    cancelled = p._arm_baseline(ev)
    keep = (cancelled is False and p._protect_baseline == before)

    out = {'helper_sha256': __import__('hashlib').sha256(SRC.read_bytes()).hexdigest(),
           'without_rebaseline': old, 'with_rebaseline': new,
           'cancel_still_refuses': keep}
    print(json.dumps(out, ensure_ascii=False, indent=2))

    ok = (old['idle']['protected'] is True
          and old['new_fault_in_run']['protected'] is False        # the旧bug
          and new['new_fault_in_run']['protected'] is True         # 修后
          and new['new_fault_in_run']['protection'].get('fault') == 1
          and keep)
    print('VERDICT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
