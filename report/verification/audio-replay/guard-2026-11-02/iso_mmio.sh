#!/bin/bash
# Isolation A: 8 captures with per-capture re-download, plus a background thread reading ONLY the
# PL registers (MMIO) every 20 ms - i.e. what the product's tick() does, minus I2C and file hashing.
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export XILINX_XRT=${XILINX_XRT:-/usr}
SRC=/opt/shengdi/current
TEST=/home/xilinx/shengdi-test
LOG=/home/xilinx/shengdi-install/iso_mmio.log

echo '=== stop service ==='
systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
echo "service=$(systemctl is-active shengdi-product.service || true)"

echo '=== fresh unpatched copy ==='
rm -rf "$TEST"
cp -aL "$SRC" "$TEST"
sha256sum "$TEST/hw_api.py"

echo
echo '=== 8 captures + MMIO-only poller every 20 ms ==='
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
say('=== ISO_A(mmio) start %s ===' % time.strftime('%H:%M:%S'))
try:
    import hw_api
    model = D + '/bootstrap-model.json'
    fx = json.load(open(model, encoding='utf-8')).get('fixture_id') or 'room_v1_20261026b'
    p = hw_api.create_product({'package_dir': D, 'fixture': fx, 'hp_volume': 40,
                               'aux_db': 0.0, 'model_path': model})
    t0 = time.time()
    mm = p._ensure_mmio()
    say('ENSURE_MMIO ok %.2fs' % (time.time() - t0))

    stop = threading.Event()
    reads = [0]
    errs = []

    def poller():
        while not stop.is_set():
            try:
                mm['status'].read(8)
                mm['control'].read(0)
                reads[0] += 1
            except Exception as exc:
                errs.append(repr(exc)[:80])
            time.sleep(0.02)

    th = threading.Thread(target=poller, daemon=True)
    th.start()
    say('POLLER started (MMIO only, 20 ms)')

    ok = 0
    for i in range(8):
        t = time.time()
        try:
            path, cap, meta = p._capture(0.4, tag='iso%02d' % i, zero=True, direct_only=True)
            st = hw_api.Board.decode_status(int(meta.get('capture_status') or 0))
            say('CAP %02d frames=%d stop=%s %.2fs raw=%s clip22=%s fault18=%s reads=%d'
                % (i, len(cap['microphone']), meta.get('stop_reason'), time.time() - t,
                   st['raw'], st['input_clip_seen'], st['fault'], reads[0]))
            ok += 1
        except Exception as exc:
            say('CAP %02d FAILED %r' % (i, exc))
            break
    stop.set()
    say('ISO_A_RESULT ok=%d/8 total=%.1fs reads=%d errs=%s'
        % (ok, time.time() - t0, reads[0], errs[:3]))
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
