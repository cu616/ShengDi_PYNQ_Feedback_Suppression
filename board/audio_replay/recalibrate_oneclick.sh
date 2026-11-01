#!/bin/bash
# One-click recalibration: new placement -> open-loop capture -> refit -> install -> verify.
#
# Operator experience: the whole measurement is machine-only. The board plays its own excitation, so
# nobody has to be quiet on cue or start speaking at a particular instant. One command, one verdict.
#
# Phases:
#   [0] noise    measure the room floor. A FAILED measurement is a refusal, never a pass.
#   [1] capture  6 open-loop segments (direct_only, zero coefficients, full-band white noise at RMS
#                -19.3 dBFS). The veto is the measured excitation-to-noise ratio, not an absolute floor.
#   [2] convert  rewrite each capture in the packet format the fitter reads
#   [3] fit      scripts/fit_newlayout_candidate.py
#   [4] scale    REJECT if the refit L1 exceeds 4.0. Never rescale: scaling L1 to 1 would shrink the
#                322 Hz gain by ~80x and manufacture a PASS.
#   [5] verify   322 Hz three-point with the candidate model; B's rule decides
#   [6] verdict  PASS installs model_recalibrated.json, FAIL renames the candidate .rejected.json
#
# Board prerequisites: the v3-sw package at $D, and the fitter sources at $REPO/scripts with
# $REPO/src importable.
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
REPO=/home/xilinx/shengdi_repo
cd $D || exit 1
/usr/local/share/pynq-venv/bin/python - "$D" "$REPO" <<'PY'
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from replay_trial import replay_trial

D = Path(sys.argv[1])
REPO = Path(sys.argv[2])
sys.path.insert(0, str(REPO / 'src'))
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
STAMP = time.strftime('%Y%m%d-%H%M%S')
PKT = D / ('recal_pkt_' + STAMP)
PKT.mkdir(parents=True, exist_ok=False)
BASE_MODEL = D / 'rewired_512_20261026.json'

cfg = {'level_db': -19.3, 'segments': 6, 'seconds': 0.3357, 'gain_db': 0.0, 'min_snr_db': 6.0}
cf = Path('/home/xilinx/recal.txt')
if cf.is_file():
    for line in cf.read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            if k.strip() in cfg:
                cfg[k.strip()] = float(v)


def excitation(level_db, n):
    """Full-band white noise normalised to RMS.

    Band-limiting was tried and is incompatible with this fitter: with no energy above 2 kHz the
    design matrix is unconstrained there and L1 exploded to 211 (max tap 7.57) even at 14.5 dB of
    excitation-to-noise. Full band is required for conditioning.
    """
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x -= np.mean(x)
    rms = float(np.sqrt(np.mean(x ** 2))) or 1.0
    x = x / rms * (10 ** (level_db / 20.0))
    peak = float(np.max(np.abs(x)))
    if peak > 0.8:
        x *= 0.8 / peak
    return np.rint(x * 32767.0).astype(np.int16)


def capture(idx, level_db):
    # source shorter than the run: the driver requires budget >= source + 2 and trial_parameters
    # truncates, so keep a margin below the frame budget.
    src = excitation(level_db, int(cfg['seconds'] * RATE) - 5)
    out = PKT / ('raw_%02d.npz' % idx)
    out.unlink(missing_ok=True)
    out.with_suffix('.status.json').unlink(missing_ok=True)
    try:
        replay_trial(str(out), FIXTURE, str(BASE_MODEL), src, bypass=False, zero_coeff=True,
                     gain_db=cfg['gain_db'], seconds=cfg['seconds'], hp_volume=40,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        print('CAPTURE_ERR %02d %r' % (idx, exc)[:150])
    if not out.is_file():
        return None
    return json.loads(str(np.load(str(out))['metadata_json']))


# ---- [0] room floor: measured, and a failed measurement refuses -------------------------------
_floor = D / 'noise_floor_probe.npz'
_floor.unlink(missing_ok=True)
try:
    replay_trial(str(_floor), FIXTURE, str(BASE_MODEL), np.zeros(16000, dtype=np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    _mic = np.asarray(np.load(str(_floor))['microphone'], float)
    noise_floor_dbfs = float(20 * np.log10(max(np.sqrt(np.mean(_mic ** 2)), 1e-12)))
except Exception as exc:
    print('RECAL_FAIL noise: the floor could not be measured (%r). Not treated as acceptable.' % (exc,))
    sys.exit(1)
print('[0] noise    room floor %.2f dBFS (informational; the veto is the measured ratio)'
      % noise_floor_dbfs)

# ---- [1] capture, automatic level retry -------------------------------------------------------
level, ok, metas = cfg['level_db'], False, []
for attempt in range(3):
    metas, ok = [], True
    print('CAPTURE_LEVEL %.1f dBFS (attempt %d)' % (level, attempt + 1))
    for idx in range(int(cfg['segments'])):
        meta = capture(idx, level)
        if meta is None:
            ok = False
            break
        status = int(meta.get('capture_status') or 0)
        if meta.get('stop_reason') != 'completed' or (status >> 22) & 1:
            print('CAPTURE_STOP %02d stop=%s bit22=%d'
                  % (idx, meta.get('stop_reason'), (status >> 22) & 1))
            ok = False
            break
        metas.append(meta)
    if ok:
        break
    level -= 6.0
    for f in PKT.glob('raw_*.npz'):
        f.unlink(missing_ok=True)

if not ok or len(metas) != int(cfg['segments']):
    print('RECAL_FAIL capture: could not get %d clean segments (last level %.1f dBFS)'
          % (int(cfg['segments']), level))
    sys.exit(1)

# the veto: measured excitation-to-noise, computed once from the first segment
_c = np.load(str(sorted(PKT.glob('raw_*.npz'))[0]))
_m = np.asarray(_c['microphone'], float)
_ex_db = float(20 * np.log10(max(np.sqrt(np.mean(_m ** 2)), 1e-12)))
snr_db = _ex_db - noise_floor_dbfs
print('[1] snr      excitation %.2f dBFS against floor %.2f dBFS -> %.2f dB'
      % (_ex_db, noise_floor_dbfs, snr_db))
if snr_db < cfg['min_snr_db']:
    print('RECAL_FAIL snr: only %.2f dB above the floor (need %.1f). Nothing fitted or installed.'
          % (snr_db, cfg['min_snr_db']))
    sys.exit(1)
print('[1] capture  %d/%d completed, bit22=0, excitation %.1f dBFS'
      % (len(metas), int(cfg['segments']), level))

# ---- [2] packet format ------------------------------------------------------------------------
for raw in sorted(PKT.glob('raw_*.npz')):
    cap = np.load(str(raw))
    np.savez_compressed(PKT / raw.name.replace('raw_', 'recal_'),
                        reference=np.asarray(cap['reference'], dtype=np.float64),
                        microphone=np.asarray(cap['microphone'], dtype=np.float64),
                        source_pcm16=np.asarray(cap['source_pcm16'], dtype=np.int16),
                        sample_rate_hz=np.float64(RATE),
                        coefficients_q20=np.zeros(512, dtype=np.int64),
                        metadata_json=str(cap['metadata_json']))
    raw.unlink()

files = {}
for p in sorted(PKT.glob('recal_*.npz')):
    data = np.load(str(p))
    meta = json.loads(str(data['metadata_json']))
    files[p.name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                     'frames': int(len(data['microphone'])),
                     'gain_q12': int(meta.get('gain_q12') or 0),
                     'fixture_id': meta.get('fixture_id'), 'fs': RATE}
(PKT / 'manifest.json').write_text(
    json.dumps({'schema_version': 1, 'fixture_id': FIXTURE, 'files': files},
               ensure_ascii=False, indent=2), encoding='utf-8')
_conv = np.load(str(sorted(PKT.glob('recal_*.npz'))[0]))
_r = np.asarray(_conv['reference'], float)
_m = np.asarray(_conv['microphone'], float)
ref_rms_dbfs = float(20 * np.log10(max(np.sqrt(np.mean(_r ** 2)), 1e-12)))
mic_rms_dbfs = float(20 * np.log10(max(np.sqrt(np.mean(_m ** 2)), 1e-12)))
print('[2] package  %s (%d files, gain_q12=0) ref=%.2f dBFS mic=%.2f dBFS mic/ref=%+.2f dB'
      % (PKT.name, len(files), ref_rms_dbfs, mic_rms_dbfs, mic_rms_dbfs - ref_rms_dbfs))

# ---- [3] fit ----------------------------------------------------------------------------------
cand = D / ('model_candidate_%s.json' % STAMP)
fit = subprocess.run([sys.executable, str(REPO / 'scripts/fit_newlayout_candidate.py'),
                      '--packet-dir', str(PKT), '--out-model', str(cand),
                      '--out-dir', str(PKT / 'fit'), '--fixture-id', FIXTURE],
                     capture_output=True, text=True)
lines = (fit.stdout or fit.stderr).strip().splitlines()
print('[3] fit      rc=%d %s' % (fit.returncode, lines[-1][:130] if lines else 'no output'))
if fit.returncode != 0 or not cand.is_file():
    print('RECAL_FAIL fit: %s' % (lines[-3:] if lines else 'no output'))
    sys.exit(1)
new = json.loads(cand.read_text(encoding='utf-8'))
cand_sha = hashlib.sha256(cand.read_bytes()).hexdigest()
metrics = {}
mt = PKT / 'fit' / 'metrics.json'
if mt.is_file():
    try:
        metrics = json.loads(mt.read_text(encoding='utf-8'))
    except Exception:
        metrics = {}

# ---- [4] magnitude gate: reject, never rescale ------------------------------------------------
base = json.loads(BASE_MODEL.read_text(encoding='utf-8'))
bc = np.asarray(base.get('coefficients_q20') or base.get('coefficients'), float) / float(1 << 20)
nc = np.asarray(new.get('coefficients_q20') or new.get('coefficients'), float) / float(1 << 20)
l1_new, l1_base = float(np.sum(np.abs(nc))), float(np.sum(np.abs(bc)))
print('[4] scale    max|h|(linear)=%.4f  L1=%.2f  (deployed %.4f / %.2f)'
      % (float(np.max(np.abs(nc))), l1_new, float(np.max(np.abs(bc))), l1_base))
if l1_new > 4.0:
    cand.rename(cand.with_suffix('.rejected.json'))
    print('RECAL_FAIL scale: L1=%.2f exceeds the 4.0 threshold (deployed %.2f). Rejection, not rescale.'
          % (l1_new, l1_base))
    sys.exit(1)

# ---- [5] three-point ---------------------------------------------------------------------------
import tone_round_guard as guard  # noqa: E402

n = int(2.0 * RATE)
tone = np.rint(0.15 * np.sin(2 * np.pi * 322.0 * np.arange(n) / RATE) * 32767).astype(np.int16)
rows, arms = {}, []
for tag, bypass, direct in (('open', False, True), ('bypass', True, False), ('cancel', False, False)):
    out = PKT / ('verify_%s.npz' % tag)
    try:
        replay_trial(str(out), FIXTURE, str(cand), tone, bypass=bypass, zero_coeff=False,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct)
    except Exception as exc:
        print('[5] verify   arm %s failed: %r' % (tag, exc)[:130])
        break
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    rows[tag] = (data, meta, None)
    arms.append({'tag': tag, 'stop': meta.get('stop_reason'),
                 'capture_status': int(meta.get('capture_status') or 0)})

holds, tp = False, None
if len(rows) == 3:
    tp = guard.three_point(rows, 322.0)
    holds = (tp['acoustic_difference_db'] >= tp['loop_boost_db'] - 1.5
             and abs(tp['overshoot_db']) <= 1.5)
    print('[5] verify   CD=%.2f loop_boost=%.2f acoustic_diff=%.2f overshoot=%.2f -> %s'
          % (tp['cd_322_db'], tp['loop_boost_db'], tp['acoustic_difference_db'],
             tp['overshoot_db'], 'PASS' if holds else 'FAIL'))
else:
    print('[5] verify   not all three arms completed -> FAIL')

# ---- [6] verdict -------------------------------------------------------------------------------
receipt = PKT / 'recalibration_receipt.json'
receipt.write_text(json.dumps({
    'stamp': STAMP, 'excitation': 'full_band_white_noise_rms_normalised', 'fixture_id': FIXTURE,
    'excitation_dbfs_commanded': level, 'room_floor_dbfs': noise_floor_dbfs,
    'excitation_snr_db': snr_db, 'ref_rms_dbfs': ref_rms_dbfs, 'mic_rms_dbfs': mic_rms_dbfs,
    'mic_over_ref_db': mic_rms_dbfs - ref_rms_dbfs, 'segments': len(files),
    'candidate': cand.name, 'candidate_sha256': cand_sha, 'fit_returncode': fit.returncode,
    'taps': new.get('taps'), 'L1': l1_new, 'L1_deployed': l1_base,
    'q20_sha256': (metrics.get('model_file') or {}).get('q20_sha256') or new.get('q20_sha256'),
    'fractional_spread': (metrics.get('alignment') or {}).get('fractional_spread'),
    'integer_lags': (metrics.get('alignment') or {}).get('integer_lags'),
    'arms': arms, 'three_point': tp, 'verdict': 'PASS' if holds else 'FAIL',
}, ensure_ascii=False, indent=2), encoding='utf-8')

if holds:
    active = D / 'model_recalibrated.json'
    active.write_bytes(cand.read_bytes())
    print('[6] verdict  PASS - installed as %s (sha256=%s)'
          % (active.name, hashlib.sha256(active.read_bytes()).hexdigest()[:12]))
    print('RECAL_PASS %s' % receipt)
else:
    cand.rename(cand.with_suffix('.rejected.json'))
    print('[6] verdict  FAIL - candidate rejected, previous model stays the default')
    print('RECAL_FAIL %s' % receipt)
PY
