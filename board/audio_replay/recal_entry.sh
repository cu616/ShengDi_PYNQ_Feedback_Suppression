#!/bin/bash
# One-click recalibration entry - the ONLY command a user has to run.
#
# Contract (captain, 2026-10-31):
#   * one command, no manual sub-steps
#   * every effective parameter is printed together with where it came from
#   * any failed stage returns non-zero and stops the stages that depend on it
#   * a verification FAIL never installs a model, and never prints "accepted"
#   * the model actually used by the follow-up audio run is the one this run installed
#   * each invocation gets its own run id; nothing from an earlier attempt is reused or overwritten
#
# Stages: [0] preflight  [1] floor  [2] capture  [3] fit  [4] gate  [5] verify  [6] install  [7] smoke
#
# Exit codes: 0 ok, 10 preflight, 11 floor, 12 capture, 13 fit, 14 gate, 15 verify, 16 install, 17 smoke.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1

D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
REPO=/home/xilinx/shengdi_repo

# ---- configuration, printed with its source ---------------------------------------------------
# Values come from /home/xilinx/recal_config.txt when present; otherwise the defaults below apply.
# Print both, so a leftover file can never be mistaken for the defaults.
CONFIG_FILE=/home/xilinx/recal_config.txt
LEVEL_DB_DEFAULT=-19.3
PEAK_CAP_DEFAULT=0.80
GAIN_DB_DEFAULT=-8.0
HP_VOLUME_DEFAULT=40
POSITION_DEFAULT=P1_100cm
SEGMENTS_DEFAULT=6
SECONDS_DEFAULT=0.3357
MIN_SNR_DB_DEFAULT=6.0
L1_MAX_DEFAULT=4.0

echo "RECAL_CONFIG_SOURCE $CONFIG_FILE $([ -f $CONFIG_FILE ] && echo present || echo absent-using-defaults)"
LEVEL_DB=$LEVEL_DB_DEFAULT; PEAK_CAP=$PEAK_CAP_DEFAULT; GAIN_DB=$GAIN_DB_DEFAULT
HP_VOLUME=$HP_VOLUME_DEFAULT; POSITION=$POSITION_DEFAULT
SEGMENTS=$SEGMENTS_DEFAULT; SECONDS=$SECONDS_DEFAULT
MIN_SNR_DB=$MIN_SNR_DB_DEFAULT; L1_MAX=$L1_MAX_DEFAULT
if [ -f $CONFIG_FILE ]; then
  # shellcheck disable=SC1090
  . $CONFIG_FILE
fi
echo "RECAL_CONFIG level_db=$LEVEL_DB peak_cap=$PEAK_CAP gain_db=$GAIN_DB hp_volume=$HP_VOLUME"
echo "RECAL_CONFIG position=$POSITION segments=$SEGMENTS seconds=$SECONDS"
echo "RECAL_CONFIG min_snr_db=$MIN_SNR_DB l1_max=$L1_MAX"

RUN_ID=$(date +%Y%m%d-%H%M%S)
echo "RECAL_RUN_ID $RUN_ID"
echo "RECAL_STAGE 0 preflight (checking package, driver, fitter)"

cd $D || { echo "RECAL_FAIL preflight: package directory missing"; exit 10; }
/usr/local/share/pynq-venv/bin/python - "$D" "$REPO" "$RUN_ID" "$LEVEL_DB" "$PEAK_CAP" \
    "$GAIN_DB" "$HP_VOLUME" "$POSITION" "$SEGMENTS" "$SECONDS" "$MIN_SNR_DB" "$L1_MAX" <<'PY'
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

D = Path(sys.argv[1])
REPO = Path(sys.argv[2])
RUN_ID = sys.argv[3]
LEVEL_DB = float(sys.argv[4])
PEAK_CAP = float(sys.argv[5])
GAIN_DB = float(sys.argv[6])
HP_VOLUME = int(float(sys.argv[7]))
POSITION = sys.argv[8]
SEGMENTS = int(float(sys.argv[9]))
SECONDS = float(sys.argv[10])
MIN_SNR_DB = float(sys.argv[11])
L1_MAX = float(sys.argv[12])

FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
RUN_DIR = D / ('run_' + RUN_ID)
RUN_DIR.mkdir(parents=True, exist_ok=False)
ACTIVE = D / 'model_recalibrated.json'
BASE_MODEL = D / 'rewired_512_20261026.json'
FITTER = REPO / 'scripts' / 'fit_newlayout_candidate.py'


def fail(stage, code, msg):
    print('RECAL_FAIL %s: %s' % (stage, msg))
    print('RECAL_END run=%s verdict=FAIL stage=%s' % (RUN_ID, stage))
    sys.exit(code)


# ---- [0] preflight -----------------------------------------------------------------------------
missing = [p.name for p in (D / 'audio_replay.bit', D / 'audio_replay.hwh', BASE_MODEL,
                            D / 'replay_trial.py') if not p.is_file()]
if missing:
    fail('preflight', 10, 'package files missing: %s' % missing)
if not FITTER.is_file():
    fail('preflight', 10, 'fitter missing at %s' % FITTER)
try:
    from replay_trial import replay_trial  # noqa: E402
except Exception as exc:
    fail('preflight', 10, 'driver import failed: %r' % (exc,))
print('RECAL_STAGE 0 ok  driver+package+fitter present')


def coeff_sha(model_path):
    m = json.loads(Path(model_path).read_text(encoding='utf-8'))
    c = m.get('coefficients_q20') or m.get('coefficients')
    arr = np.asarray(c, dtype=np.int64)
    if len(arr) < 512:
        arr = np.concatenate([arr, np.zeros(512 - len(arr), dtype=np.int64)])
    return hashlib.sha256(arr.astype('<i4').tobytes()).hexdigest()


# ---- [1] floor ---------------------------------------------------------------------------------
print('RECAL_STAGE 1 floor (silent capture; a failed measurement is a refusal)')
floor_path = RUN_DIR / 'floor.npz'
try:
    replay_trial(str(floor_path), FIXTURE, str(BASE_MODEL), np.zeros(16000, dtype=np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=HP_VOLUME,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    mic = np.asarray(np.load(str(floor_path))['microphone'], float)
    floor_db = float(20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12)))
except Exception as exc:
    fail('floor', 11, 'floor could not be measured (%r); not treated as acceptable' % (exc,))
print('RECAL_STAGE 1 ok  floor=%.2f dBFS (informational)' % floor_db)


def excitation(n, level_db):
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x -= np.mean(x)
    rms = float(np.sqrt(np.mean(x ** 2))) or 1.0
    x = x / rms * (10 ** (level_db / 20.0))
    peak = float(np.max(np.abs(x)))
    if peak > PEAK_CAP:
        x *= PEAK_CAP / peak
    return np.rint(x * 32767.0).astype(np.int16)


# ---- [2] capture -------------------------------------------------------------------------------
print('RECAL_STAGE 2 capture %d segments, commanded %.1f dBFS RMS, peak cap %.2f FS'
      % (SEGMENTS, LEVEL_DB, PEAK_CAP))
level, ok, metas = LEVEL_DB, False, []
for attempt in range(3):
    metas, ok = [], True
    print('RECAL_ATTEMPT level=%.1f n=%d' % (level, attempt + 1))
    for idx in range(SEGMENTS):
        src = excitation(int(SECONDS * RATE) - 5, level)
        out = RUN_DIR / ('cap_%02d.npz' % idx)
        out.unlink(missing_ok=True)
        try:
            replay_trial(str(out), FIXTURE, str(BASE_MODEL), src, bypass=False, zero_coeff=True,
                         gain_db=0.0, seconds=SECONDS, hp_volume=HP_VOLUME,
                         speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        except Exception as exc:
            print('RECAL_CAPTURE_ERR %02d %r' % (idx, exc)[:140])
            ok = False
            break
        if not out.is_file():
            ok = False
            break
        meta = json.loads(str(np.load(str(out))['metadata_json']))
        status = int(meta.get('capture_status') or 0)
        if meta.get('stop_reason') != 'completed' or (status >> 22) & 1:
            print('RECAL_CAPTURE_STOP %02d stop=%s bit22=%d'
                  % (idx, meta.get('stop_reason'), (status >> 22) & 1))
            ok = False
            break
        metas.append(meta)
    if ok:
        break
    for f in RUN_DIR.glob('cap_*.npz'):
        f.unlink(missing_ok=True)
    level -= 6.0

if not ok or len(metas) != SEGMENTS:
    fail('capture', 12, 'only %d/%d clean segments (last level %.1f)' % (len(metas), SEGMENTS, level))

first = np.load(str(sorted(RUN_DIR.glob('cap_*.npz'))[0]))
ref = np.asarray(first['reference'], float)
mic = np.asarray(first['microphone'], float)
ref_db = float(20 * np.log10(max(np.sqrt(np.mean(ref ** 2)), 1e-12)))
mic_db = float(20 * np.log10(max(np.sqrt(np.mean(mic ** 2)), 1e-12)))
pk = float(20 * np.log10(max(np.max(np.abs(first['source_pcm16'].astype(float) / 32768.0)), 1e-12)))
snr_db = mic_db - floor_db
print('RECAL_LEVEL commanded=%.1f actual_rms=%.2f actual_peak=%.2f dBFS mic=%.2f dBFS'
      % (LEVEL_DB, ref_db, pk, mic_db))
if snr_db < MIN_SNR_DB:
    fail('capture', 12, 'excitation-to-noise %.2f dB < %.1f dB' % (snr_db, MIN_SNR_DB))
print('RECAL_STAGE 2 ok  snr=%.2f dB (floor %.2f)' % (snr_db, floor_db))

# ---- [3] fit -----------------------------------------------------------------------------------
print('RECAL_STAGE 3 fit')
for cap in sorted(RUN_DIR.glob('cap_*.npz')):
    c = np.load(str(cap))
    np.savez_compressed(RUN_DIR / cap.name.replace('cap_', 'seg_'),
                        reference=np.asarray(c['reference'], float),
                        microphone=np.asarray(c['microphone'], float),
                        source_pcm16=np.asarray(c['source_pcm16'], np.int16),
                        sample_rate_hz=np.float64(RATE),
                        coefficients_q20=np.zeros(512, np.int64),
                        metadata_json=str(c['metadata_json']))
    cap.unlink()

files = {}
for p in sorted(RUN_DIR.glob('seg_*.npz')):
    files[p.name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                     'frames': int(len(np.load(str(p))['microphone']))}
(RUN_DIR / 'manifest.json').write_text(json.dumps(
    {'schema_version': 1, 'fixture_id': FIXTURE, 'files': files}, ensure_ascii=False, indent=2),
    encoding='utf-8')

cand = RUN_DIR / ('candidate_%s.json' % RUN_ID)
fit = subprocess.run([sys.executable, str(FITTER), '--packet-dir', str(RUN_DIR),
                      '--out-model', str(cand), '--out-dir', str(RUN_DIR / 'fit'),
                      '--fixture-id', FIXTURE], capture_output=True, text=True)
tail = (fit.stdout or fit.stderr).strip().splitlines()
if fit.returncode != 0 or not cand.is_file():
    fail('fit', 13, 'fitter rc=%d %s' % (fit.returncode, (tail[-2:] if tail else 'no output')))
new = json.loads(cand.read_text(encoding='utf-8'))
print('RECAL_STAGE 3 ok  taps=%s' % new.get('taps'))

# ---- [4] gate ----------------------------------------------------------------------------------
print('RECAL_STAGE 4 gate (reject, never rescale)')
base = json.loads(BASE_MODEL.read_text(encoding='utf-8'))
bc = np.asarray(base.get('coefficients_q20') or base.get('coefficients'), float) / float(1 << 20)
nc = np.asarray(new.get('coefficients_q20') or new.get('coefficients'), float) / float(1 << 20)
l1_new, l1_base = float(np.sum(np.abs(nc))), float(np.sum(np.abs(bc)))
print('RECAL_SCALE max_h=%.4f L1=%.3f (deployed %.4f / %.3f)'
      % (float(np.max(np.abs(nc))), l1_new, float(np.max(np.abs(bc))), l1_base))
if l1_new > L1_MAX:
    cand.rename(cand.with_suffix('.rejected.json'))
    fail('gate', 14, 'L1 %.2f > %.2f; model rejected (no rescale)' % (l1_new, L1_MAX))

# ---- [5] verify --------------------------------------------------------------------------------
print('RECAL_STAGE 5 verify (322 Hz three-point with THIS candidate)')
sys.path.insert(0, str(D))
import tone_round_guard as guard  # noqa: E402

n = int(2.0 * RATE)
tone = np.rint(0.15 * np.sin(2 * np.pi * 322.0 * np.arange(n) / RATE) * 32767).astype(np.int16)
rows, arms = {}, []
for tag, bypass, direct in (('open', False, True), ('bypass', True, False), ('cancel', False, False)):
    out = RUN_DIR / ('verify_%s.npz' % tag)
    try:
        replay_trial(str(out), FIXTURE, str(cand), tone, bypass=bypass, zero_coeff=False,
                     gain_db=GAIN_DB, seconds=2.2, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct)
    except Exception as exc:
        fail('verify', 15, 'arm %s raised %r' % (tag, exc))
    meta = json.loads(str(np.load(str(out))['metadata_json']))
    if meta.get('stop_reason') != 'completed':
        fail('verify', 15, 'arm %s stopped: %s' % (tag, meta.get('stop_reason')))
    rows[tag] = (np.load(str(out)), meta, None)
    arms.append({'tag': tag, 'stop': meta.get('stop_reason'),
                 'capture_status': int(meta.get('capture_status') or 0)})

tp = guard.three_point(rows, 322.0)
holds = (tp['acoustic_difference_db'] >= tp['loop_boost_db'] - 1.5
         and abs(tp['overshoot_db']) <= 1.5)
print('RECAL_THREE_POINT cd=%.2f loop_boost=%.2f acoustic=%.2f overshoot=%.2f rule=%s'
      % (tp['cd_322_db'], tp['loop_boost_db'], tp['acoustic_difference_db'], tp['overshoot_db'],
         'PASS' if holds else 'FAIL'))
if not holds:
    cand.rename(cand.with_suffix('.rejected.json'))
    print('RECAL_MODEL rejected - the installed model was NOT changed')
    fail('verify', 15, 'three-point rule not met')

# ---- [6] install -------------------------------------------------------------------------------
print('RECAL_STAGE 6 install')
prev = None
if ACTIVE.is_file():
    prev = D / ('model_prev_%s.json' % RUN_ID)
    prev.write_bytes(ACTIVE.read_bytes())
ACTIVE.write_bytes(cand.read_bytes())
active_sha = coeff_sha(ACTIVE)
cand_sha = coeff_sha(cand)
if active_sha != cand_sha:
    fail('install', 16, 'installed model coefficient hash differs from the candidate')
print('RECAL_STAGE 6 ok  active=%s coeff_sha=%s prev=%s'
      % (ACTIVE.name, active_sha[:16], prev.name if prev else 'none'))

# ---- [7] smoke: prove the follow-up run uses THIS model ----------------------------------------
print('RECAL_STAGE 7 smoke (short audio run with the installed model)')
smoke = RUN_DIR / 'smoke.npz'
try:
    replay_trial(str(smoke), FIXTURE, str(ACTIVE), np.zeros(16000, dtype=np.int16), bypass=False,
                 zero_coeff=False, gain_db=GAIN_DB, seconds=2.0, hp_volume=HP_VOLUME,
                 speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    fail('smoke', 17, 'smoke run raised %r' % (exc,))
meta = json.loads(str(np.load(str(smoke))['metadata_json']))
used = str(meta.get('coefficients_sha256') or '')
if meta.get('stop_reason') != 'completed':
    fail('smoke', 17, 'smoke stopped: %s' % meta.get('stop_reason'))
if used != active_sha:
    fail('smoke', 17, 'run used coefficients %s but installed model is %s' % (used[:16], active_sha[:16]))
print('RECAL_STAGE 7 ok  run used coeff_sha=%s (matches installed model)' % used[:16])

# ---- summary -----------------------------------------------------------------------------------
receipt = {
    'run_id': RUN_ID, 'position': POSITION, 'verdict': 'PASS',
    'config': {'level_db_commanded': LEVEL_DB, 'actual_ref_rms_dbfs': ref_db,
               'actual_ref_peak_dbfs': pk, 'peak_cap': PEAK_CAP, 'gain_db': GAIN_DB,
               'hp_volume': HP_VOLUME, 'segments': SEGMENTS, 'min_snr_db': MIN_SNR_DB,
               'l1_max': L1_MAX},
    'floor_dbfs': floor_db, 'snr_db': snr_db, 'ref_rms_dbfs': ref_db, 'mic_rms_dbfs': mic_db,
    'candidate_coeff_sha256': cand_sha, 'active_coeff_sha256': active_sha,
    'smoke_used_coeff_sha256': used, 'previous_model_backup': prev.name if prev else None,
    'L1': l1_new, 'L1_deployed': l1_base, 'three_point': tp, 'arms': arms,
}
(RUN_DIR / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print('RECAL_SUMMARY run=%s position=%s verdict=PASS snr=%.2f L1=%.2f acoustic=%.2f overshoot=%.2f'
      % (RUN_ID, POSITION, snr_db, l1_new, tp['acoustic_difference_db'], tp['overshoot_db']))
print('RECAL_MODEL_IDENTITY candidate=%s active=%s used=%s'
      % (cand_sha[:16], active_sha[:16], used[:16]))
print('RECAL_READY_FOR_SPEECH  (the new model is installed and in use)')
print('RECAL_END run=%s verdict=PASS stage=done' % RUN_ID)
PY
rc=$?
echo "RECAL_EXIT rc=$rc"
exit $rc
