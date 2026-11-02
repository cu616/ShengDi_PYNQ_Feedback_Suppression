#!/bin/bash
# Direct 30 s amplification with the model that CAL just installed, bypassing the product state
# machine. Answers one question: does the hardware run itself complete, or does it trip protection
# the way the product's START did (0.4 s, 0 frames)?
set -u
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export XILINX_XRT=${XILINX_XRT:-/usr}
TEST=/home/xilinx/shengdi-test
PIDF=/home/xilinx/shengdi-install/manual.pid
LOG=/home/xilinx/shengdi-install/direct_run.log

if [ -f "$PIDF" ]; then
  kill "$(cat "$PIDF")" 2>/dev/null || true
  sleep 3
  kill -9 "$(cat "$PIDF")" 2>/dev/null || true
fi
systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2
ps -eo pid,args | grep recal_product | grep -v grep || echo 'no product running'

export PYTHONUNBUFFERED=1
/usr/local/share/pynq-venv/bin/python - "$LOG" <<'PY'
import glob, json, os, sys, time, traceback
LOG = sys.argv[1]
log = open(LOG, 'a', buffering=1)


def say(m):
    print(m, flush=True)
    log.write(m + '\n')


D = '/home/xilinx/shengdi-test'
sys.path.insert(0, D)
say('=== DIRECT RUN %s ===' % time.strftime('%H:%M:%S'))
try:
    import hw_api
    models = sorted(glob.glob('/home/xilinx/.local/state/shengdi/models/archive/*/model.json'),
                    key=os.path.getmtime)
    model = models[-1]
    say('MODEL %s  %d bytes' % (model, os.path.getsize(model)))
    md = json.load(open(model, encoding='utf-8'))
    fx = md.get('fixture_id') or 'room_v1_20261026b'
    say('fixture_id=%s  taps=%d' % (fx, len(md.get('coefficients_q20') or md.get('coefficients') or [])))

    p = hw_api.create_product({'package_dir': D, 'fixture': fx, 'hp_volume': 40,
                               'aux_db': 0.0, 'model_path': model})
    p._ensure_mmio()
    say('MMIO ready; pre-run status = 0x%08X mode=%s' % (p._status_word(), p.effective_mode()))

    t0 = time.time()
    r = p.perform({'op': 'run', 'request_id': 'direct1', 'scene_id': 'direct',
                   'seconds': 30.0, 'gain_q12': 1631})
    dt = time.time() - t0
    for k in ('ok', 'status', 'effective_mode', 'audio_frames', 'elapsed_seconds',
              'wall_seconds', 'requested_seconds', 'note'):
        if k in r:
            say('  %-18s %s' % (k, json.dumps(r.get(k), ensure_ascii=True)))
    say('DIRECT_RESULT wall=%.1fs status_word=0x%08X' % (dt, p._status_word()))
    st = r.get('status')
    say('DIRECT_VERDICT %s' % ('completed' if r.get('ok') else str(st)))
    try:
        p.mute()
        say('muted; status_word=0x%08X' % p._status_word())
    except Exception as exc:
        say('mute failed %r' % (exc,))
except Exception:
    say('DIRECT_FAILED ' + traceback.format_exc()[-800:])
finally:
    log.close()
PY
echo "python_exit=$?"
