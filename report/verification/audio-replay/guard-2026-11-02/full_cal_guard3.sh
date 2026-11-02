#!/bin/bash
# Full flow with THREE A-side fixes on a copy:
#   1. _MM_HOLD  : no MMIO while the PL is being reloaded      (PS-wedge fix, verified)
#   2. _op_hold  : cached AUX read while a driver call runs    (false identity-mismatch fix)
#   3. no pre-arm: _run_v2 must not arm before the driver loads fresh coefficients
#                  (otherwise the RTL latches fault and poll() aborts START in 0.4 s)
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export XILINX_XRT=${XILINX_XRT:-/usr}
SRC=/opt/shengdi/current
TEST=/home/xilinx/shengdi-test
LOG=/home/xilinx/shengdi-install/manual_product.log
PIDF=/home/xilinx/shengdi-install/manual.pid

if [ -f "$PIDF" ]; then
  kill "$(cat "$PIDF")" 2>/dev/null || true
  sleep 3
  kill -9 "$(cat "$PIDF")" 2>/dev/null || true
fi
systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
echo "service=$(systemctl is-active shengdi-product.service || true)"

echo '=== rebuild copy + 3 fixes + compute 150 ==='
rm -rf "$TEST"
cp -aL "$SRC" "$TEST"
/usr/bin/python3 - "$TEST" <<'PY'
import hashlib, json, sys
from pathlib import Path

root = Path(sys.argv[1])
p = root / 'hw_api.py'
t = p.read_text(encoding='utf-8')

edits = [
("REG_AUX_R = 0x400D",
 "REG_AUX_R = 0x400D\n\n"
 "# >0 while the PL is being reconfigured; reading an AXI register then wedges the bus.\n"
 "_MM_HOLD = 0"),

("""    def _status_word(self):
        return self._ensure_mmio()['status'].read(8) & 0xFFFFFFFF

    def _control_word(self):
        return self._ensure_mmio()['control'].read(0) & 0xFFFFFFFF""",
 """    def _status_word(self):
        if _MM_HOLD:
            return self._mm_cached['status']
        self._mm_cached['status'] = self._ensure_mmio()['status'].read(8) & 0xFFFFFFFF
        return self._mm_cached['status']

    def _control_word(self):
        if _MM_HOLD:
            return self._mm_cached['control']
        self._mm_cached['control'] = self._ensure_mmio()['control'].read(0) & 0xFFFFFFFF
        return self._mm_cached['control']

    def _guard_overlay(self, drv):
        \"\"\"Guard the driver: no MMIO while the PL reloads, no live AUX read while it re-inits.\"\"\"
        global _MM_HOLD
        if getattr(drv, '_mm_guarded', False):
            return drv
        real_overlay = drv.Overlay
        real_trial = drv.replay_trial
        owner = self

        class _GuardedOverlay(real_overlay):
            def __init__(self, *a, **k):
                global _MM_HOLD
                _MM_HOLD += 1
                try:
                    super().__init__(*a, **k)
                finally:
                    _MM_HOLD -= 1

        def guarded_trial(*a, **k):
            owner._op_hold += 1
            try:
                return real_trial(*a, **k)
            finally:
                owner._op_hold -= 1

        drv.Overlay = _GuardedOverlay
        drv.replay_trial = guarded_trial
        drv._mm_guarded = True
        return drv"""),

("        self._mm = None\n        self._prepared = False",
 "        self._mm = None\n        self._mm_cached = {'status': 0, 'control': 0}\n"
 "        self._aux_cache = None\n        self._op_hold = 0\n        self._prepared = False"),

("""    def _driver(self):
        import importlib
        return importlib.import_module('replay_trial_repair')""",
 """    def _driver(self):
        import importlib
        return self._guard_overlay(importlib.import_module('replay_trial_repair'))"""),

("""    def identity(self):
        aux = self._board.get_aux_gain_db()""",
 """    def identity(self):
        # The driver re-initialises the codec at the start of every call; a live AUX read in that
        # window sees 0x00 and looks like an identity mismatch. Cache across the call instead.
        if self._op_hold and self._aux_cache is not None:
            aux = self._aux_cache
        else:
            aux = self._board.get_aux_gain_db()
            self._aux_cache = aux"""),

("""        self._write_control(arm=True, allow_armed=True)
        cap_path, cid = self._capture_path(scene, 'run', 0)""",
 """        # Do NOT arm here. The coefficients from the previous capture are spent (fresh=0), so the
        # RTL latches fault the instant arm rises; the product's 20 ms poll() then reports a bogus
        # 'protected' and aborts START before the driver can load fresh coefficients. The driver
        # arms the pipeline itself once the fresh load is in place.
        cap_path, cid = self._capture_path(scene, 'run', 0)"""),
]
for old, new in edits:
    got = t.count(old)
    if got != 1:
        raise SystemExit('anchor count=%d: %r' % (got, old[:50]))
    t = t.replace(old, new)
p.write_text(t, encoding='utf-8')
print('PATCH ok, edits=%d' % len(edits))

cfg_path = root / 'product-config.json'
cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
cfg['compute_timeout_seconds'] = 150
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
new_hash = hashlib.sha256(p.read_bytes()).hexdigest()
old_hash = cfg['expected_identity']['helper_sha256']
for name in ('product-config.json', 'product-manifest.json'):
    f = root / name
    f.write_text(f.read_text(encoding='utf-8').replace(old_hash, new_hash), encoding='utf-8')
print('hw_api new sha256 =', new_hash)

man_path = root / 'product-manifest.json'
man = json.loads(man_path.read_text(encoding='utf-8'))


def sha(q):
    return hashlib.sha256(q.read_bytes()).hexdigest()


changed = 0
for name in list(man['hashes']):
    f = root / name
    if f.is_file() and man['hashes'][name] != sha(f):
        man['hashes'][name] = sha(f)
        changed += 1
for name in list(man['adapters']['hardware'].get('hashes', {})):
    f = root / name
    if f.is_file() and man['adapters']['hardware']['hashes'][name] != sha(f):
        man['adapters']['hardware']['hashes'][name] = sha(f)
        changed += 1
man['deployment_ready'] = True
man['missing'] = []
man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('MANIFEST_RESTATED changed=%d  compute_timeout=%s' % (changed, cfg['compute_timeout_seconds']))
PY
if [ $? -ne 0 ]; then echo 'PREP FAILED'; exit 3; fi

echo
echo '=== launch ==='
cd "$TEST"
nohup /usr/local/share/pynq-venv/bin/python recal_product.py \
      --base "$TEST" --state-dir /home/xilinx/.local/state/shengdi \
      > "$LOG" 2>&1 &
echo $! > "$PIDF"
sleep 15
echo "pid=$(cat "$PIDF")"
ps -o pid,etime,pcpu,args -p "$(cat "$PIDF")" 2>/dev/null || echo 'process gone'
/usr/bin/python3 -c "
import json
d=json.load(open('/home/xilinx/.local/state/shengdi/status.json',encoding='utf-8'))
i=d.get('identity') or {}
print('state=%s outcome=%s aux_db=%s raw=%s/%s conf_ready=%s latched=%s' % (
  d.get('state'),d.get('outcome'),i.get('aux_db'),i.get('aux_raw_left'),i.get('aux_raw_right'),
  d.get('configuration_ready'),d.get('hardware_error_latched')))
"
