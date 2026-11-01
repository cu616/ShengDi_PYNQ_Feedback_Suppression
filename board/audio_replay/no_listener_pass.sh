#!/bin/bash
# No-listener pass: capabilities, prepare, 6+2 calibration plan, install with load verification, poll, mute.
source /etc/profile.d/xrt_setup.sh
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/audio_io || exit 1
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json
import time

from hw_api import create_product

cfg = {'package_dir': '/home/xilinx/jupyter_notebooks/base/audio/audio_io',
       'fixture': 'room_v1_20261026b', 'hp_volume': 40, 'aux_db': 0.0,
       'model_path': '/home/xilinx/jupyter_notebooks/base/audio/audio_io/model_recalibrated.json'}
p = create_product(cfg)
J = lambda d: json.dumps(d, ensure_ascii=False)
scene = 'nolisten-' + time.strftime('%H%M%S')
run_dir = '/home/xilinx/jupyter_notebooks/base/audio/audio_io/fieldwin/' + scene

c = p.capabilities()
print('NL_CAPS %s' % J({'contract': c.get('contract'), 'buttons': c.get('buttons'),
                        'indicator': c.get('indicator'), 'prepared_capture': c.get('prepared_capture'),
                        'abort_mutes': c.get('abort_mutes'), 'bounded_run': c.get('bounded_run')}))

pr = p.perform({'op': 'prepare', 'request_id': 'n0', 'scene_id': scene, 'run_dir': run_dir})
print('NL_PREP %s' % J({k: pr.get(k) for k in ('ok', 'status')}))

plan = {'peak_cap': 0.80, 'seed': 4242, 'validation_seed': 4243,
        'training': [{'seed': 4242, 'frames': 16384} for _ in range(6)],
        'validation': [{'seed': 4243, 'frames': 16384} for _ in range(2)]}
srcs = {}
for op in ('training', 'validation'):
    t0 = time.monotonic()
    r = p.perform({'op': op, 'request_id': 'n-' + op, 'scene_id': scene, 'run_dir': run_dir, 'plan': plan})
    caps = r.get('captures') or []
    srcs[op] = sorted({c.get('source_sha256') for c in caps if c.get('source_sha256')})
    print('NL_%s %s' % (op.upper(), J({'ok': r.get('ok'), 'status': r.get('status'),
                                       'level': r.get('level_accepted_dbfs'), 'n': len(caps),
                                       'valid': sorted({c.get('valid_frames') for c in caps}),
                                       'bit22': sorted({c.get('bit22') for c in caps}),
                                       'wall_s': round(time.monotonic() - t0, 1)})))
print('NL_INDEPENDENT %s' % (srcs.get('training') != srcs.get('validation')))

ins = p.perform({'op': 'install', 'request_id': 'n2', 'scene_id': scene, 'run_dir': run_dir,
                 'model_path': cfg['model_path'], 'run_gain_q12': 2303})
print('NL_INSTALL %s' % J({k: ins.get(k) for k in ('ok', 'status', 'loaded_count', 'taps',
                                                   'run_gain_q12', 'applies_at', 'reason')} |
                          {'model': (ins.get('model_sha256') or '')[:12],
                           'coeff': (ins.get('coefficients_sha256') or '')[:12],
                           'reported': (ins.get('reported_coefficients_sha256') or '')[:12],
                           'identity_gain': (ins.get('identity') or {}).get('gain_q12')}))

pl = p.poll()
print('NL_POLL %s' % J({'protected': pl.get('protected'), 'mode': pl.get('effective_mode'),
                        'saturation': pl.get('saturation'), 'open_loop_gain': pl.get('open_loop_gain_q12_allowed')}))
print('NL_MUTE %s' % J(p.mute()))
print('NL_ABORT %s' % J({k: p.abort().get(k) for k in ('muted', 'quiescent', 'elapsed_ms')}))
print('NL_DONE scene=%s' % scene)
PY
