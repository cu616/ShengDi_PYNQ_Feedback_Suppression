#!/bin/bash
# Trial fix for the PS freeze, applied to a COPY only.
#
# Mechanism (proven by the three-arm experiment): re-downloading the bitstream is safe, and reading
# PL registers is safe, but reading them while the bitstream is being reloaded wedges the AXI bus and
# the PS never comes back. So: while the driver is reconfiguring the PL, MMIO reads return the last
# value instead of touching the fabric. The window is one Overlay() construction, ~1 s.
#
# The guard is installed inside _driver(), so every call site is covered without touching any of them.
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export XILINX_XRT=${XILINX_XRT:-/usr}
SRC=/opt/shengdi/current
TEST=/home/xilinx/shengdi-test
LOG=/home/xilinx/shengdi-install/iso_guard.log

echo '=== stop service ==='
systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
echo "service=$(systemctl is-active shengdi-product.service || true)"

echo '=== fresh copy + guard patch ==='
rm -rf "$TEST"
cp -aL "$SRC" "$TEST"
/usr/bin/python3 - "$TEST" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
p = root / 'hw_api.py'
t = p.read_text(encoding='utf-8')
edits = []

edits.append((
    "REG_AUX_R = 0x400D",
    "REG_AUX_R = 0x400D\n\n"
    "# >0 while the PL is being reconfigured. Reading an AXI register in that window wedges the bus.\n"
    "_MM_HOLD = 0"))

edits.append((
    """    def _status_word(self):
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
        \"\"\"Let the driver's bitstream download bump _MM_HOLD so poll() leaves the bus alone.\"\"\"
        global _MM_HOLD
        if getattr(drv, '_mm_guarded', False):
            return drv
        real = drv.Overlay

        class _GuardedOverlay(real):
            def __init__(self, *a, **k):
                global _MM_HOLD
                _MM_HOLD += 1
                try:
                    super().__init__(*a, **k)
                finally:
                    _MM_HOLD -= 1

        drv.Overlay = _GuardedOverlay
        drv._mm_guarded = True
        return drv"""))

edits.append((
    "        self._mm = None\n        self._prepared = False",
    "        self._mm = None\n        self._mm_cached = {'status': 0, 'control': 0}\n        self._prepared = False"))

edits.append((
    """    def _driver(self):
        import importlib
        return importlib.import_module('replay_trial_repair')""",
    """    def _driver(self):
        import importlib
        return self._guard_overlay(importlib.import_module('replay_trial_repair'))"""))

for old, new in edits:
    got = t.count(old)
    if got != 1:
        raise SystemExit('anchor count=%d: %r' % (got, old[:50]))
    t = t.replace(old, new)
p.write_text(t, encoding='utf-8')
print('GUARD_PATCH applied %d edits' % len(edits))
PY
if [ $? -ne 0 ]; then echo 'PATCH FAILED - aborting before touching hardware'; exit 3; fi
sha256sum "$TEST/hw_api.py"
/usr/bin/python3 -c "
import sys; sys.path.insert(0,'$TEST')
import hw_api; print('import ok, _MM_HOLD =', getattr(hw_api,'_MM_HOLD','MISSING'))
"

echo
echo '=== 8 captures + MMIO poller (same stress that wedged the board) ==='
export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - "$LOG" <<'PY'
import json, sys, threading, time, traceback
LOG = sys.argv[1]
log = open(LOG, 'a', buffering=1)


def say(m):
    print(m, flush=True)
    log.write(m + '\n')


D = '/home/xilinx/shengdi-test'
sys.path.insert(0, D)
say('=== ISO_GUARD start %s ===' % time.strftime('%H:%M:%S'))
try:
    import hw_api
    model = D + '/bootstrap-model.json'
    fx = json.load(open(model, encoding='utf-8')).get('fixture_id') or 'room_v1_20261026b'
    p = hw_api.create_product({'package_dir': D, 'fixture': fx, 'hp_volume': 40,
                               'aux_db': 0.0, 'model_path': model})
    t0 = time.time()
    p._ensure_mmio()
    say('ENSURE_MMIO ok %.2fs' % (time.time() - t0))

    stop = threading.Event()
    reads = [0]
    held = [0]
    errs = []

    def poller():
        while not stop.is_set():
            try:
                if getattr(hw_api, '_MM_HOLD', 0):
                    held[0] += 1
                p._status_word()
                p._control_word()
                reads[0] += 1
            except Exception as exc:
                errs.append(repr(exc)[:80])
            time.sleep(0.02)

    threading.Thread(target=poller, daemon=True).start()
    say('POLLER started (status+control, 20 ms, guarded)')

    ok = 0
    for i in range(8):
        t = time.time()
        try:
            path, cap, meta = p._capture(0.4, tag='grd%02d' % i, zero=True, direct_only=True)
            st = hw_api.Board.decode_status(int(meta.get('capture_status') or 0))
            say('CAP %02d frames=%d stop=%s %.2fs raw=%s clip22=%s fault18=%s reads=%d held=%d'
                % (i, len(cap['microphone']), meta.get('stop_reason'), time.time() - t,
                   st['raw'], st['input_clip_seen'], st['fault'], reads[0], held[0]))
            ok += 1
        except Exception as exc:
            say('CAP %02d FAILED %r' % (i, exc))
            break
    stop.set()
    say('ISO_GUARD_RESULT ok=%d/8 total=%.1fs reads=%d held=%d errs=%s'
        % (ok, time.time() - t0, reads[0], held[0], errs[:3]))
except Exception:
    say('SETUP_FAILED ' + traceback.format_exc()[-600:])
finally:
    log.close()
PY

echo
echo '=== restart service ==='
systemctl start shengdi-product.service 2>&1 | tail -1
sleep 8
echo "service=$(systemctl is-active shengdi-product.service || true)"
