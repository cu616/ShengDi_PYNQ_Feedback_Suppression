#!/bin/bash
# Reproduce the product's START without the product: same 20 ms poll() loop, same run request.
# Records the exact status word and the protection bits that fire, if any.
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export XILINX_XRT=${XILINX_XRT:-/usr}
TEST=/home/xilinx/shengdi-test
LOG=/home/xilinx/shengdi-install/start_repro.log
PIDF=/home/xilinx/shengdi-install/manual.pid

if [ -f "$PIDF" ]; then
  kill "$(cat "$PIDF")" 2>/dev/null || true
  sleep 3
  kill -9 "$(cat "$PIDF")" 2>/dev/null || true
fi
systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2

export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - "$LOG" <<'PY'
import glob, json, os, sys, threading, time, traceback
LOG = sys.argv[1]
log = open(LOG, 'w', buffering=1)


def say(m):
    print(m, flush=True)
    log.write(m + '\n')


D = '/home/xilinx/shengdi-test'
sys.path.insert(0, D)
say('=== START REPRO %s ===' % time.strftime('%H:%M:%S'))
try:
    import hw_api
    models = sorted(glob.glob('/home/xilinx/.local/state/shengdi/models/archive/*/model.json'),
                    key=os.path.getmtime)
    model = models[-1]
    md = json.load(open(model, encoding='utf-8'))
    fx = md.get('fixture_id') or 'room_v1_20261026b'
    say('MODEL %s fixture=%s' % (os.path.basename(os.path.dirname(model)), fx))

    p = hw_api.create_product({'package_dir': D, 'fixture': fx, 'hp_volume': 40,
                               'aux_db': 0.0, 'model_path': model})
    p._ensure_mmio()
    say('pre-run status=0x%08X mode=%s' % (p._status_word(), p.effective_mode()))

    stop = threading.Event()
    seen = []
    polls = [0]

    def poller():
        while not stop.is_set():
            try:
                r = p.poll()
                polls[0] += 1
                if r.get('protected'):
                    seen.append((round(time.time() - t0, 2), r.get('protection'),
                                 r.get('saturation'), p._status_word()))
                    if len(seen) <= 4:
                        say('PROTECTED t=%.2f protection=%s saturation=%s word=0x%08X'
                            % (seen[-1][0], json.dumps(seen[-1][1], ensure_ascii=True),
                               json.dumps(seen[-1][2], ensure_ascii=True), seen[-1][3]))
            except Exception as exc:
                seen.append(('exc', repr(exc)[:80]))
            time.sleep(0.02)

    t0 = time.time()
    th = threading.Thread(target=poller, daemon=True)
    th.start()
    time.sleep(2.0)                     # let the baseline settle, as it does in 'ready'
    say('baseline settled after %d polls' % polls[0])

    r = p.perform({'op': 'run', 'request_id': 'repro1', 'scene_id': 'repro',
                   'seconds': 15.0, 'gain_q12': 1631})
    dt = time.time() - t0
    stop.set()
    say('RUN reply ok=%s status=%s frames=%s wall=%.1fs'
        % (r.get('ok'), r.get('status'), r.get('audio_frames'), dt))
    say('polls=%d protected_events=%d' % (polls[0], len(seen)))
    say('post status=0x%08X' % p._status_word())
    try:
        p.mute()
    except Exception:
        pass
except Exception:
    say('REPRO_FAILED ' + traceback.format_exc()[-800:])
finally:
    log.close()
PY
echo "python_exit=$?"
