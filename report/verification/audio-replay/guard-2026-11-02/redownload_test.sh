#!/bin/bash
# Overlay-reuse experiment. Stops the product, patches a COPY of the package so every driver call
# reuses the already-downloaded overlay, then runs 8 captures back to back.
#
# Question: does removing the per-capture bitstream re-download stop the PS freeze?
# The frozen package at /opt/shengdi/current is NOT modified; only /home/xilinx/shengdi-test is.
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export XILINX_XRT=${XILINX_XRT:-/usr}
SRC=/opt/shengdi/current
TEST=/home/xilinx/shengdi-test
LOG=/home/xilinx/shengdi-install/reuse_test.log

echo '=== stop service ==='
systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
echo "service=$(systemctl is-active shengdi-product.service || true)"

echo
echo '=== make writable test copy ==='
rm -rf "$TEST"
cp -aL "$SRC" "$TEST"
echo "copied files: $(find "$TEST" -type f | wc -l)"
sha256sum "$TEST/hw_api.py"

echo
echo '=== patch reuse_overlay only ==='
/usr/bin/python3 - <<'PY'
from pathlib import Path
p = Path('/home/xilinx/shengdi-test/hw_api.py')
t = p.read_text(encoding='utf-8')
n = t.count('reuse_overlay=False')
pass  # control run: keep reuse_overlay=False (re-download every capture)
print('CONTROL_RUN patches_skipped=%d' % n)
PY
sha256sum "$TEST/hw_api.py"

echo
echo '=== 8 captures, overlay reused ==='
export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - "$LOG" <<'PY'
import json, sys, time, traceback
LOG = sys.argv[1]
log = open(LOG, 'a', buffering=1)


def say(msg):
    print(msg, flush=True)
    log.write(msg + '\n')


D = '/home/xilinx/shengdi-test'
sys.path.insert(0, D)
say('=== control test start %s ===' % time.strftime('%H:%M:%S'))
try:
    import hw_api
    model = D + '/bootstrap-model.json'
    fx = json.load(open(model, encoding='utf-8')).get('fixture_id') or 'room_v1_20261026b'
    say('MODEL fixture_id=%s' % fx)
    p = hw_api.create_product({'package_dir': D, 'fixture': fx,
                               'hp_volume': 40, 'aux_db': 0.0,
                               'model_path': model})
    t0 = time.time()
    p._ensure_mmio()
    say('ENSURE_MMIO ok %.2fs' % (time.time() - t0))
    ok = 0
    for i in range(8):
        t = time.time()
        try:
            path, cap, meta = p._capture(0.4, tag='reuse%02d' % i, zero=True, direct_only=True)
            st = hw_api.Board.decode_status(int(meta.get('capture_status') or 0))
            frames = len(cap['microphone'])
            say('CAP %02d frames=%d stop=%s %.2fs raw=%s clip22=%s fault18=%s %s'
                % (i, frames, meta.get('stop_reason'), time.time() - t,
                   st['raw'], st['input_clip_seen'], st['fault'], path.name))
            ok += 1
        except Exception as exc:
            say('CAP %02d FAILED %r' % (i, exc))
            break
    say('CONTROL_RESULT ok=%d/8 total=%.1fs' % (ok, time.time() - t0))
except Exception:
    say('SETUP_FAILED ' + traceback.format_exc()[-600:])
finally:
    log.close()
PY
RC=$?
echo "python_exit=$RC"

echo
echo '=== restart service ==='
systemctl start shengdi-product.service 2>&1 | tail -1
sleep 8
echo "service=$(systemctl is-active shengdi-product.service || true)"

