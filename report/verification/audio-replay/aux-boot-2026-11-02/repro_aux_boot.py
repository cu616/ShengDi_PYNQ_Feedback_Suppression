"""Offline reproduction of the power-on AUX failure (A line, 2026-11-02 handoff item 2).

No board needed: the codec's I2C primitives are replaced with an in-memory register file that
starts at the *power-on* value the field reported (0x400B/0x400D = 0x00). Everything else -
`hw_api.Board.get_aux_gain_db`, `hw_api.ProductHardware.mute/poll/identity`, the identity words
and the product's `_identity` comparison - is the real code.

What this answers:
  A. Does the frozen hw_api + the frozen config reproduce 'hardware_error: aux_db' with no board?
  B. If the AUX stage is written once before the first identity read, does every identity field pass?
     (That is the whole effect of the proposed "write AUX in create_product's constructor".)
  C. Is the helper_sha256 that C pins inside expected_identity the hash of hw_api.py itself?
     (If yes, editing hw_api.py alone cannot be shipped - C must re-freeze the same round.)

Run: <bundled python> repro_aux_boot.py
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import types

V3IO = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\board\audio_replay\v3-io')
FINAL = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\final_pkg')

IDENTITY = ('aux_db', 'aux_raw_left', 'aux_raw_right', 'hp_volume', 'gain_q12', 'sample_rate_hz',
            'driver_sha256', 'bit_sha256', 'hwh_sha256', 'helper_sha256')

# ---- codec register file ---------------------------------------------------------------------
CODEC = {0x400B: 0x00, 0x400D: 0x00}      # power-on value reported in the field


def _fd(self):
    return os.open(os.devnull, os.O_RDWR)


def _read8(fd, reg):
    return CODEC.get(reg, 0)


def _write8(fd, reg, value):
    CODEC[reg] = value & 0xFF


# ---- minimal MMIO stand-ins (identity only reads the control word) ----------------------------
class _Reg:
    def __init__(self, initial=0):
        self.value = initial

    def read(self, _offset):
        return self.value

    def write(self, _offset, value):
        self.value = value & 0xFFFFFFFF


# ---- C's identity comparison, copied line for line from recal_product.py L196-207 -------------
def c_identity_error(actual, expected, phase_gain_q12, scope, identity_seen=None):
    if any(k not in actual for k in IDENTITY):
        return '硬件身份回读不完整'
    for key in IDENTITY:
        value = actual[key]
        if key.endswith('sha256') and (not isinstance(value, str) or len(value) != 64
                                       or any(c not in '0123456789abcdef' for c in value)):
            return '硬件身份格式错误:' + key
        if key == 'gain_q12':
            allowed = phase_gain_q12.get(scope, [expected[key]])
            if type(value) is not int or value not in allowed:
                return '阶段数字增益回读不符'
        elif key in expected and value != expected[key]:
            return '硬件身份混搭或配置不符:' + key
    if identity_seen is not None and any(actual[k] != identity_seen[k]
                                         for k in IDENTITY if k != 'gain_q12'):
        return '标定后配置发生变化，请重新标定'
    return None


def load_hw_api(path=None, name='hw_api'):
    # hw_api imports fcntl at module scope; on Windows there is no fcntl and the I2C calls are
    # replaced below, so a no-op stub is enough to import the real file unchanged.
    if 'fcntl' not in sys.modules:
        sys.modules['fcntl'] = types.SimpleNamespace(ioctl=lambda *a, **k: None)
    spec = importlib.util.spec_from_file_location(name, path or (V3IO / 'hw_api.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.Board._fd = _fd
    mod.Board._read8 = staticmethod(_read8)
    mod.Board._write8 = staticmethod(_write8)
    return mod


def product_config():
    cfg = json.loads((FINAL / 'product-config.json').read_text(encoding='utf-8'))
    expected = cfg['expected_identity']
    return cfg, expected


def boot_once(hw, label, initialise_aux):
    CODEC[0x400B] = 0x00
    CODEC[0x400D] = 0x00
    mm = {'control': _Reg(0), 'status': _Reg(0)}
    hw.ProductHardware._ensure_mmio = lambda self, reuse=True: mm
    hw.ProductHardware._driver = lambda self: types.SimpleNamespace(
        __file__=str(V3IO / 'replay_trial_repair.py'))
    cfg = {'package_dir': str(V3IO), 'fixture': 'room_v1_20261026b', 'hp_volume': 40,
           'aux_db': 0.0, 'model_path': str(V3IO / 'model_recalibrated.json')}
    p = hw.create_product(cfg)
    if initialise_aux:                       # <- the one extra call the patch adds to __init__
        p._board.set_aux_gain_db(p.aux_db)
    p.mute()                                  # product boots muted first (recal_product.py L161)
    ident = p.poll()['identity']
    aux = p._board.get_aux_gain_db()
    print('--- %s ---' % label)
    print('  codec 0x400B/0x400D      : 0x%02X / 0x%02X' % (CODEC[0x400B], CODEC[0x400D]))
    print('  get_aux_gain_db()        : %s' % json.dumps(aux, ensure_ascii=False, default=str))
    print('  identity.aux_db          : %r' % (ident['aux_db'],))
    print('  identity.gain_q12        : %r' % (ident['gain_q12'],))
    return ident, aux


def main():
    hw = load_hw_api()
    cfg, expected = product_config()
    phase_gain_q12 = cfg.get('phase_gain_q12', {})
    scope = 'prepare' if cfg.get('runtime_profile') in ('b-heldout-v1', 'b-frozen-v1') else 'runtime'

    print('hw_api.py sha256           : %s' % __import__('hashlib').sha256(
        (V3IO / 'hw_api.py').read_bytes()).hexdigest())
    print('config expected helper_sha : %s' % expected.get('helper_sha256'))
    print('  -> helper_sha256 is the hash of hw_api.py itself, so any edit to it changes this pin')
    print('config expected aux_db     : %r (raw %s/%s)' % (expected['aux_db'],
          expected['aux_raw_left'], expected['aux_raw_right']))
    print()

    ident_a, aux_a = boot_once(hw, 'A. frozen code, codec at power-on 0x00', initialise_aux=False)
    err_a = c_identity_error(ident_a, expected, phase_gain_q12, scope)
    print('  C _identity()            : %s' % (err_a or 'PASS'))
    assert err_a is not None, 'expected the field failure to reproduce'
    print()

    ident_b, aux_b = boot_once(hw, 'B. same code + AUX written once before the first identity read',
                               initialise_aux=True)
    err_b = c_identity_error(ident_b, expected, phase_gain_q12, scope)
    print('  C _identity()            : %s' % (err_b or 'PASS'))
    print()

    patched_path = pathlib.Path(tempfile.gettempdir()) / 'shengdi-auxfix' / 'hw_api.AUXFIX.py'
    if patched_path.is_file():
        hw_p = load_hw_api(patched_path, 'hw_api_auxfix')
        ident_c, aux_c = boot_once(hw_p, 'C. patched hw_api (constructor writes AUX), codec 0x00',
                                   initialise_aux=False)
        err_c = c_identity_error(ident_c, expected, phase_gain_q12, scope)
        print('  C _identity()            : %s' % (err_c or 'PASS'))
        print('  patched get_aux_gain_db  : %s' % json.dumps(
            hw_p.Board.aux_code_to_db(0x00)) + ' for code 0x00 (None = not a gain, honest)')
        print()

    print('RESULT  A reproduces the field failure : %s' % err_a)
    print('RESULT  B passes every identity field  : %s' % (err_b or 'PASS'))
    if patched_path.is_file():
        print('RESULT  C (the actual patch) passes    : %s' % (err_c or 'PASS'))
    if err_b:
        print('        !! the constructor write alone is not enough; see the remaining field above')
    hw_id = json.loads((FINAL / 'product-manifest.json').read_text(encoding='utf-8'))
    pin = expected['helper_sha256']
    cfg_pins = json.dumps(cfg, ensure_ascii=False).count(pin)
    man_pins = json.dumps(hw_id, ensure_ascii=False).count(pin)
    print('pins of the current hw_api hash             : product-config.json x%d, product-manifest.json x%d'
          % (cfg_pins, man_pins))
    print('  -> editing hw_api.py changes all of them; C must re-pin the same round as the refreeze')


if __name__ == '__main__':
    main()
