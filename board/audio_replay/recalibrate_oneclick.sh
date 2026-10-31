#!/bin/bash
# One-click recalibration: new placement -> open-loop capture -> refit -> install -> verify.
#
# Why the operator experience is smooth:
#   * NOTHING here needs a person to speak. The board plays the excitation itself, so the
#     "be quiet, now speak" ritual does not exist in this flow at all.
#   * There is no gate blocking a take. If the excitation capture trips input_clip, the level is
#     halved and the capture repeats automatically (3 attempts), with no human involvement.
#   * One command, one verdict line, one receipt file. A rejected refit leaves no half-installed
#     state: the previous model stays the default.
#
# Phases, one line each:
#   [1] capture   6 open-loop segments (direct_only, zero coefficients, fixed-seed noise)
#   [2] package   manifest.json with per-file sha256, the format the fitter expects
#   [3] fit       scripts/fit_newlayout_candidate.py -> candidate model json
#   [4] install   stash as a candidate; nothing is switched yet
#   [5] verify    322 Hz three-point WITH the candidate model, B's rule decides
#   [6] verdict   PASS installs it as model_recalibrated.json, FAIL marks it rejected
#
# Prerequisites on the board:
#   * the repository checkout at $REPO (the fitter lives there: scripts/fit_newlayout_candidate.py)
#   * the v3-sw package at $D with the current model as rewired_512_20261026.json
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
FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
STAMP = time.strftime('%Y%m%d-%H%M%S')
PKT = D / ('recal_pkt_' + STAMP)
PKT.mkdir(parents=True, exist_ok=False)
BASE_MODEL = D / 'rewired_512_20261026.json'

# Defaults follow B's calibration batch: source -19.3 dBFS (mic about -29.2), and a run of
# exactly one capture window so all 16384 frames stay source-active.
cfg = {'level_db': -19.3, 'segments': 6, 'seconds': 0.3357, 'gain_db': 0.0,
       'max_floor_dbfs': -55.0}
cf = Path('/home/xilinx/recal.txt')
if cf.is_file():
    for line in cf.read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            if k.strip() in cfg:
                cfg[k.strip()] = float(v)


def excitation(level_db, n):
    """White noise normalised to RMS, not peak.

    Two mistakes are folded into this one function, both found by measurement:
      * the multitone had a crest factor of about 11.4 dB, so normalising it by PEAK put the actual RMS
        11.4 dB below the level asked for (ref_rms -30.73 against a -19.3 target);
      * the multitone's discrete lines are not comparable to the white-noise batch B's fitter was built
        on, which made |H(322)| and the cross-correlation delay look different for reasons that have
        nothing to do with the room.

    B confirmed the calibration batch level is an RMS (-19.3 dBFS, six segments -18.88 to -20.12), so
    normalise by RMS and only scale down if the peak would clip.
    """
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x -= np.mean(x)
    rms = float(np.sqrt(np.mean(x ** 2))) or 1.0
    x = x / rms * (10 ** (level_db / 20.0))
    peak = float(np.max(np.abs(x)))
    if peak > 0.5:                          # keep 6 dB of headroom, never let the source clip
        x *= 0.5 / peak
        print('EXCITATION_CLIPPED target %.1f dBFS RMS -> peak %.1f dBFS, scaled down'
              % (level_db, 20 * np.log10(peak)))
    return np.rint(x * 32767.0).astype(np.int16)


def capture(idx, level_db):
    # The driver requires frame_limit >= source_length + 2, so the excitation must be SHORTER than
    # the run. The capture keeps the last 16384 frames, which therefore start inside the source and
    # may end after it; the fitter trims that tail itself via source_frames_in_window.
    # source must stay strictly below the run length (driver rule frame_limit >= source + 2)
    # trial_parameters truncates, so keep 5 frames of margin below the frame budget
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


# ---- [0] room noise floor: measured, never assumed ---------------------------------------------
# A silent capture with the source muted. The excitation has to beat this floor by a wide margin or
# the least-squares fit is being fed mostly noise, which shows up as a flat oversized impulse
# response rather than as an error. Measured on 2026-10-31: floor -38.0 dBFS against a mic level of
# -32.4 dBFS, i.e. only 5.6 dB of excitation-to-noise, and the fit blew up exactly as that predicts.
# Nobody has to be quiet on cue: this runs before any excitation and simply refuses to continue.
_floor_path = D / 'noise_floor_probe.npz'
_floor_path.unlink(missing_ok=True)
try:
    replay_trial(str(_floor_path), FIXTURE, str(BASE_MODEL), np.zeros(16000, dtype=np.int16),
                 bypass=False, zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=40,
                 speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
    _mic = np.asarray(np.load(str(_floor_path))['microphone'], float)
    noise_floor_dbfs = float(20 * np.log10(max(np.sqrt(np.mean(_mic ** 2)), 1e-12)))
except Exception as _exc:
    noise_floor_dbfs = None
    print('[0] noise    could not measure the floor: %r' % (_exc,))

if noise_floor_dbfs is not None:
    print('[0] noise    room floor %.2f dBFS (need <= %.1f for a usable open-loop fit)'
          % (noise_floor_dbfs, cfg['max_floor_dbfs']))
    if noise_floor_dbfs > cfg['max_floor_dbfs']:
        print('RECAL_FAIL noise: the room floor is %.1f dBFS, above the %.1f dBFS limit. The excitation '
              'would be only about %.1f dB above it, and the fit would produce a flat oversized model. '
              'Silence the room (AC, fans, people) and rerun. Nothing was captured or fitted.'
              % (noise_floor_dbfs, cfg['max_floor_dbfs'],
                 (level + 13.0) - noise_floor_dbfs))
        sys.exit(1)

# ---- [1] capture, automatic level retry instead of a gate ------------------------------------
level = cfg['level_db']
metas, ok = [], False
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
    for p in PKT.glob('raw_*.npz'):
        p.unlink(missing_ok=True)

if not ok or len(metas) != int(cfg['segments']):
    print('RECAL_FAIL capture: could not get %d clean open-loop segments (level %.1f dBFS)'
          % (int(cfg['segments']), level))
    sys.exit(1)
print('[1] capture  %d/%d completed, bit22=0, excitation %.1f dBFS'
      % (len(metas), int(cfg['segments']), level))

# The fitter reads B's calibration packet format, not our driver's capture format: it needs
# sample_rate_hz and coefficients_q20 in the npz as well. Convert rather than patch the fitter.
for raw in sorted(PKT.glob('raw_*.npz')):
    cap = np.load(str(raw))
    meta_json = str(cap['metadata_json'])
    np.savez_compressed(PKT / raw.name.replace('raw_', 'recal_'),
                        reference=np.asarray(cap['reference'], dtype=np.float64),
                        microphone=np.asarray(cap['microphone'], dtype=np.float64),
                        source_pcm16=np.asarray(cap['source_pcm16'], dtype=np.int16),
                        sample_rate_hz=np.float64(RATE),
                        coefficients_q20=np.zeros(512, dtype=np.int64),
                        metadata_json=meta_json)
    raw.unlink()
print('CONVERT      %d segments rewritten in the packet format' % len(files_ready := list(PKT.glob('recal_*.npz'))))

# ---- [2] package manifest --------------------------------------------------------------------
files = {}
for p in sorted(PKT.glob('recal_*.npz')):
    data = np.load(str(p))
    meta = json.loads(str(data['metadata_json']))
    files[p.name] = {
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
        'first_frame': int(meta.get('first_frame') or 0),
        'frames': int(len(data['microphone'])),
        'completed_frames': int(meta.get('completed_frames') or 0),
        'fixture_id': meta.get('fixture_id'),
        'gain_q12': int(meta.get('gain_q12') or 0),
        'bypass': bool(meta.get('bypass')),
        'pll_readback': meta.get('pll_readback'),
        'fs': RATE,
    }
(PKT / 'manifest.json').write_text(json.dumps(
    {'schema_version': 1, 'fixture_id': FIXTURE, 'files': files}, ensure_ascii=False, indent=2),
    encoding='utf-8')
_probe = np.load(str(sorted(PKT.glob('recal_*.npz'))[0]))
_r = np.asarray(_probe['reference'], float)
_m = np.asarray(_probe['microphone'], float)
ref_rms_dbfs = float(20 * np.log10(max(np.sqrt(np.mean(_r ** 2)), 1e-12)))
mic_rms_dbfs = float(20 * np.log10(max(np.sqrt(np.mean(_m ** 2)), 1e-12)))
print('[2] package  %s (%d files, gain_q12=0 open loop)  ref=%.2f dBFS mic=%.2f dBFS  mic/ref=%+.2f dB'
      % (PKT.name, len(files), ref_rms_dbfs, mic_rms_dbfs, mic_rms_dbfs - ref_rms_dbfs))

# ---- [3] fit ---------------------------------------------------------------------------------
cand = D / ('model_candidate_%s.json' % STAMP)
fit = subprocess.run([sys.executable, str(REPO / 'scripts/fit_newlayout_candidate.py'),
                      '--packet-dir', str(PKT), '--out-model', str(cand),
                      '--out-dir', str(PKT / 'fit'), '--fixture-id', FIXTURE],
                     capture_output=True, text=True)
lines = (fit.stdout or fit.stderr).strip().splitlines()
print('[3] fit      rc=%d %s' % (fit.returncode, lines[-1][:150] if lines else 'no output'))
if fit.returncode != 0 or not cand.is_file():
    print('RECAL_FAIL fit: %s' % (lines[-3:] if lines else 'no output'))
    sys.exit(1)
new = json.loads(cand.read_text(encoding='utf-8'))
metrics = {}
mt = PKT / 'fit' / 'metrics.json'
if mt.is_file():
    try:
        metrics = json.loads(mt.read_text(encoding='utf-8'))
    except Exception:
        metrics = {}
cand_sha = hashlib.sha256(cand.read_bytes()).hexdigest()
print('             taps=%s lag_first=%s q20_sha=%s'
      % (new.get('taps'), new.get('lag_first'), str(new.get('q20_sha256'))[:12]))
print('[4] install  %s sha256=%s (previous model untouched)' % (cand.name, cand_sha[:12]))
# Pre-install magnitude gate. A refit that is tens of times larger than the deployed model
# overflows the FIR prediction and gets stopped by the hardware guard, which wastes the verify arms
# and tells nobody why. Compare against the deployed model before anything is switched.
base_model = json.loads(BASE_MODEL.read_text(encoding='utf-8'))
base_c = np.asarray(base_model.get('coefficients_q20') or base_model.get('coefficients'), float) / float(1 << 20)
new_c = np.asarray(new.get('coefficients_q20') or new.get('coefficients'), float) / float(1 << 20)
ratio_peak = float(np.max(np.abs(new_c))) / max(float(np.max(np.abs(base_c))), 1e-12)
ratio_l1 = float(np.sum(np.abs(new_c))) / max(float(np.sum(np.abs(base_c))), 1e-12)
l1_new = float(np.sum(np.abs(new_c)))
print('[4] scale    max|h|(linear)=%.4f  L1=%.2f  (deployed %.4f / %.2f)'
      % (float(np.max(np.abs(new_c))), l1_new, float(np.max(np.abs(base_c))),
         float(np.sum(np.abs(base_c)))))
# B's rule: reject, never rescale. Deployed L1 is 2.29 and the 10-26 new layout is 2.15, so 4.0 leaves
# a factor of two of headroom without letting a pathological fit through.
if l1_new > 4.0:
    rejected = cand.with_suffix('.rejected.json')
    cand.rename(rejected)
    print('RECAL_FAIL scale: refit L1=%.2f exceeds the 4.0 rejection threshold (deployed %.2f); '
          'refusing to install it. This is a rejection, not a rescale: scaling L1 down to 1 would '
          'shrink the 322 Hz gain by 82x and fake a PASS.' % (l1_new, float(np.sum(np.abs(base_c)))))
    sys.exit(1)


# ---- [5] verify: 322 Hz three-point with the candidate model ---------------------------------
import tone_round_guard as guard  # noqa: E402  (kept next to the driver)

n = int(2.0 * RATE)
tone = np.rint(0.15 * np.sin(2 * np.pi * 322.0 * np.arange(n) / RATE) * 32767).astype(np.int16)
rows, arms = {}, []
for tag, bypass, direct in (('open', False, True), ('bypass', True, False),
                            ('cancel', False, False)):
    out = PKT / ('verify_%s.npz' % tag)
    try:
        replay_trial(str(out), FIXTURE, str(cand), tone, bypass=bypass, zero_coeff=False,
                     gain_db=-8.0, seconds=2.2, hp_volume=40, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct)
    except Exception as exc:
        print('[5] verify   arm %s failed: %r' % (tag, exc)[:140])
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

# ---- [6] verdict ------------------------------------------------------------------------------
receipt = PKT / 'recalibration_receipt.json'
receipt.write_text(json.dumps({
    'stamp': STAMP, 'excitation': 'white_noise_rms_normalised', 'fixture_id': FIXTURE, 'excitation_dbfs_commanded': level,
    'ref_rms_dbfs': ref_rms_dbfs, 'mic_rms_dbfs': mic_rms_dbfs,
    'room_floor_dbfs': noise_floor_dbfs,
    'mic_over_ref_db': mic_rms_dbfs - ref_rms_dbfs,
    'segments': len(files), 'candidate': cand.name, 'candidate_sha256': cand_sha,
    'fit_returncode': fit.returncode, 'taps': new.get('taps'), 'lag_first': new.get('lag_first'),
    'q20_sha256': (metrics.get('model_file') or {}).get('q20_sha256') or new.get('q20_sha256'),
    'fractional_spread': (metrics.get('alignment') or {}).get('fractional_spread'),
    'integer_lags': (metrics.get('alignment') or {}).get('integer_lags'),
    'arms': arms, 'three_point': tp,
    'verdict': 'PASS' if holds else 'FAIL',
}, ensure_ascii=False, indent=2), encoding='utf-8')

if holds:
    active = D / 'model_recalibrated.json'
    active.write_bytes(cand.read_bytes())
    print('[6] verdict  PASS - installed as %s (sha256=%s)'
          % (active.name, hashlib.sha256(active.read_bytes()).hexdigest()[:12]))
    print('RECAL_PASS %s' % receipt)
else:
    rejected = cand.with_suffix('.rejected.json')
    cand.rename(rejected)
    print('[6] verdict  FAIL - candidate rejected (%s), previous model stays the default'
          % rejected.name)
    print('RECAL_FAIL %s' % receipt)
PY
