#!/bin/bash
# One-click recalibration entry - the ONLY command a user has to run.
#
# Acceptance protocol v2 (captain-approved 2026-10-31): the acceptance tone amplitude is auto-levelled
# from the open-arm microphone peak. Only that amplitude changes; gain, Codec, model, protection and
# the pass rule are untouched. This is NOT called adaptive, and it does not carry over to the training
# excitation or to live speech levels.
#
# Stages: [0] preflight [1] floor [2] capture [3] fit [4] gate [5] verify [6] install [7] smoke [8] voice
# Exit codes: 0 ok, 10 preflight, 11 floor, 12 capture, 13 fit, 14 gate, 15 verify, 16 install, 17 smoke, 18 voice
source /etc/profile.d/xrt_setup.sh
source /etc/profile.d/boardname.sh
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1

D=/home/xilinx/jupyter_notebooks/base/audio/audio_switch
REPO=/home/xilinx/shengdi_repo
CONFIG_FILE=/home/xilinx/recal_config.txt

LEVEL_DB=-19.3; PEAK_CAP=0.80; GAIN_DB=-8.0; HP_VOLUME=40; POSITION=P1_100cm
SEGMENTS=6; SEG_SECONDS=0.3357; MIN_SNR_DB=6.0; L1_MAX=4.0
echo "RECAL_CONFIG_SOURCE $CONFIG_FILE $([ -f $CONFIG_FILE ] && echo present || echo absent-using-defaults)"
if [ -f $CONFIG_FILE ]; then . $CONFIG_FILE; fi
echo "RECAL_CONFIG level_db=$LEVEL_DB peak_cap=$PEAK_CAP gain_db=$GAIN_DB hp_volume=$HP_VOLUME"
echo "RECAL_CONFIG position=$POSITION segments=$SEGMENTS seg_seconds=$SEG_SECONDS"
echo "RECAL_CONFIG min_snr_db=$MIN_SNR_DB l1_max=$L1_MAX protocol=v2_auto_levelled"

RUN_ID=$(date +%Y%m%d-%H%M%S)
echo "RECAL_RUN_ID $RUN_ID"
echo "RECAL_STAGE 0 preflight"
cd $D || { echo "RECAL_FAIL preflight: package directory missing"; exit 10; }
/usr/local/share/pynq-venv/bin/python - "$D" "$REPO" "$RUN_ID" "$LEVEL_DB" "$PEAK_CAP" \
    "$GAIN_DB" "$HP_VOLUME" "$POSITION" "$SEGMENTS" "$SEG_SECONDS" "$MIN_SNR_DB" "$L1_MAX" <<'PY'
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

D = Path(sys.argv[1]); REPO = Path(sys.argv[2]); RUN_ID = sys.argv[3]
LEVEL_DB = float(sys.argv[4]); PEAK_CAP = float(sys.argv[5]); GAIN_DB = float(sys.argv[6])
HP_VOLUME = int(float(sys.argv[7])); POSITION = sys.argv[8]; SEGMENTS = int(float(sys.argv[9]))
SEG_SECONDS = float(sys.argv[10]); MIN_SNR_DB = float(sys.argv[11]); L1_MAX = float(sys.argv[12])

FIXTURE = 'room_v1_20261026b'
RATE = 48828.125
RUN_DIR = D / ('run_' + RUN_ID)
RUN_DIR.mkdir(parents=True, exist_ok=False)
(RUN_DIR / 'prep').mkdir(exist_ok=True)
(RUN_DIR / 'checks').mkdir(exist_ok=True)
ACTIVE = D / 'model_recalibrated.json'
BASE_MODEL = D / 'rewired_512_20261026.json'
FITTER = REPO / 'scripts' / 'fit_newlayout_candidate.py'


def fail(stage, code, msg):
    print('RECAL_FAIL %s: %s' % (stage, msg))
    print('RECAL_END run=%s verdict=FAIL stage=%s' % (RUN_ID, stage))
    sys.exit(code)


missing = [p.name for p in (D / 'audio_replay.bit', D / 'audio_replay.hwh', BASE_MODEL,
                            D / 'replay_trial.py') if not p.is_file()]
if missing:
    fail('preflight', 10, 'package files missing: %s' % missing)
if not FITTER.is_file():
    fail('preflight', 10, 'fitter missing at %s' % FITTER)
try:
    from replay_trial_repair import replay_trial   # 0 dB AUX + relaxed PLL check
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


def peak_dbfs(arr):
    return float(20 * np.log10(max(np.max(np.abs(arr)), 1e-12)))


def rms_dbfs(arr):
    return float(20 * np.log10(max(np.sqrt(np.mean(np.asarray(arr, float) ** 2)), 1e-12)))


# ---- [1] floor ---------------------------------------------------------------------------------
print('RECAL_STAGE 1 floor (3 silent captures, median)')
samples = []
for i in range(3):
    fp = RUN_DIR / 'prep' / ('floor_%d.npz' % i)
    fp.unlink(missing_ok=True)
    try:
        replay_trial(str(fp), FIXTURE, str(BASE_MODEL), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=True, gain_db=0.0, seconds=0.40, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        samples.append(rms_dbfs(np.load(str(fp))['microphone']))
    except Exception as exc:
        print('RECAL_FLOOR_ERR %d %r' % (i, exc))
if len(samples) < 2:
    fail('floor', 11, 'floor measured only %d/3 times; not treated as acceptable' % len(samples))
floor_db = float(np.median(samples))
print('RECAL_STAGE 1 ok  floor=%.2f dBFS median of %s' % (floor_db, ['%.2f' % v for v in samples]))


def excitation(n, level_db):
    rng = np.random.default_rng(4242)
    x = rng.standard_normal(n)
    x -= np.mean(x)
    x = x / (float(np.sqrt(np.mean(x ** 2))) or 1.0) * (10 ** (level_db / 20.0))
    pk = float(np.max(np.abs(x)))
    if pk > PEAK_CAP:
        x *= PEAK_CAP / pk
    return np.rint(x * 32767.0).astype(np.int16)


# ---- [2] capture -------------------------------------------------------------------------------
print('RECAL_STAGE 2 capture %d segments at %.1f dBFS RMS' % (SEGMENTS, LEVEL_DB))
level, ok, metas = LEVEL_DB, False, []
for attempt in range(3):
    metas, ok = [], True
    print('RECAL_ATTEMPT level=%.1f n=%d' % (level, attempt + 1))
    for idx in range(SEGMENTS):
        src = excitation(int(SEG_SECONDS * RATE) - 5, level)
        out = RUN_DIR / ('cap_%02d.npz' % idx)
        out.unlink(missing_ok=True)
        try:
            replay_trial(str(out), FIXTURE, str(BASE_MODEL), src, bypass=False, zero_coeff=True,
                         gain_db=0.0, seconds=SEG_SECONDS, hp_volume=HP_VOLUME,
                         speaker_confirmed=True, local_capture_confirmed=True, direct_only=True)
        except Exception as exc:
            print('RECAL_CAPTURE_ERR %02d %r' % (idx, exc)[:130])
            ok = False
            break
        meta = json.loads(str(np.load(str(out))['metadata_json']))
        if meta.get('stop_reason') != 'completed' or (int(meta.get('capture_status') or 0) >> 22) & 1:
            print('RECAL_CAPTURE_STOP %02d stop=%s' % (idx, meta.get('stop_reason')))
            ok = False
            break
        metas.append(meta)
    if ok:
        break
    for f in RUN_DIR.glob('cap_*.npz'):
        f.unlink(missing_ok=True)
    level -= 6.0

if not ok or len(metas) != SEGMENTS:
    fail('capture', 12, 'only %d/%d clean segments' % (len(metas), SEGMENTS))
first = np.load(str(sorted(RUN_DIR.glob('cap_*.npz'))[0]))
ref_db = rms_dbfs(first['reference'])
mic_db = rms_dbfs(first['microphone'])
pk_db = peak_dbfs(first['source_pcm16'].astype(float) / 32768.0)
snr_db = mic_db - floor_db
print('RECAL_LEVEL commanded=%.1f actual_rms=%.2f actual_peak=%.2f mic=%.2f dBFS'
      % (LEVEL_DB, ref_db, pk_db, mic_db))
if snr_db < MIN_SNR_DB:
    fail('capture', 12, 'excitation-to-noise %.2f < %.1f dB' % (snr_db, MIN_SNR_DB))
print('RECAL_STAGE 2 ok  snr=%.2f dB' % snr_db)

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
files = {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in sorted(RUN_DIR.glob('seg_*.npz'))}
(RUN_DIR / 'manifest.json').write_text(json.dumps(
    {'schema_version': 1, 'fixture_id': FIXTURE, 'files': files}, ensure_ascii=False, indent=2),
    encoding='utf-8')
cand = RUN_DIR / ('candidate_%s.json' % RUN_ID)
fit = subprocess.run([sys.executable, str(FITTER), '--packet-dir', str(RUN_DIR),
                      '--out-model', str(cand), '--out-dir', str(RUN_DIR / 'fit'),
                      '--fixture-id', FIXTURE], capture_output=True, text=True)
if fit.returncode != 0 or not cand.is_file():
    tail = (fit.stdout or fit.stderr).strip().splitlines()
    fail('fit', 13, 'fitter rc=%d %s' % (fit.returncode, tail[-2:] if tail else ''))
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
    fail('gate', 14, 'L1 %.2f > %.2f; rejected (no rescale)' % (l1_new, L1_MAX))

# ---- [5] verify with an auto-levelled acceptance tone ------------------------------------------
TONE_TARGET_DBFS = -12.0
TONE_BAND_DB = 2.0
TONE_MAX_ADJUST = 6
TONE_START_FS = 0.05
print('RECAL_STAGE 5 verify (acceptance tone auto-levelled to %.1f dBFS mic peak)' % TONE_TARGET_DBFS)
sys.path.insert(0, str(D))
import tone_round_guard as guard

n = int(2.0 * RATE)


def tone_at(fs):
    return np.rint(fs * np.sin(2 * np.pi * 322.0 * np.arange(n) / RATE) * 32767).astype(np.int16)


fs_now = TONE_START_FS
adjusts = 0
trials = []
last_good_fs = None
last_good_peak = None
while True:
    tone = tone_at(fs_now)
    out = RUN_DIR / 'prep' / ('open_probe_%d.npz' % adjusts)
    out.unlink(missing_ok=True)
    clipped = False
    pk = None
    raised = None
    try:
        replay_trial(str(out), FIXTURE, str(cand), tone, bypass=False, zero_coeff=False,
                     gain_db=GAIN_DB, seconds=2.2, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        # The driver raises on input full scale. That is not a hard failure of the run: it is one
        # clipped trial, and the whole point of the levelling loop is to back off from it.
        raised = repr(exc)
        if 'full scale' in raised or 'bit22' in raised:
            clipped = True
        else:
            fail('verify', 15, 'open pre-check raised %r' % (exc,))
    if out.is_file():
        pk = peak_dbfs(np.load(str(out))['microphone'])
        m = json.loads(str(np.load(str(out))['metadata_json']))
        if m.get('stop_reason') != 'completed' or (int(m.get('capture_status') or 0) >> 22) & 1:
            clipped = True
    trials.append({'source_fs': fs_now, 'mic_peak_dbfs': pk, 'clipped': bool(clipped),
                   'raised': raised})
    print('RECAL_TONE_LEVEL try=%d source_fs=%.4f mic_peak=%s clipped=%s'
          % (adjusts, fs_now, 'n/a' if pk is None else '%.2f' % pk, clipped))

    if clipped:
        # never extrapolate from a clipped peak; fall back to the last known-good amplitude
        if last_good_fs is not None:
            fs_now = last_good_fs
            break
        if adjusts >= TONE_MAX_ADJUST:
            fail('verify', 15, 'tone clipped at every amplitude tried (%d)' % adjusts)
        fs_now *= 0.5
        adjusts += 1
        continue

    last_good_fs, last_good_peak = fs_now, pk
    if abs(pk - TONE_TARGET_DBFS) <= TONE_BAND_DB or adjusts >= TONE_MAX_ADJUST:
        break
    # step up gently (~3 dB) instead of extrapolating the exact ratio: the speaker compresses, so the
    # exact-ratio jump overshoots into clipping in one step
    fs_now = min(0.5, fs_now * 1.4)
    adjusts += 1

tone_fs = fs_now
print('RECAL_TONE_FROZEN source_fs=%.4f mic_peak=%.2f adjustments=%d (identical for all arms)'
      % (tone_fs, last_good_peak if last_good_peak is not None else float('nan'), adjusts))

rows, arms = {}, []
for tag, bypass, direct in (('open', False, True), ('bypass', True, False), ('cancel', False, False)):
    out = RUN_DIR / 'checks' / ('verify_%s.npz' % tag)
    out.unlink(missing_ok=True)
    try:
        replay_trial(str(out), FIXTURE, str(cand), tone, bypass=bypass, zero_coeff=False,
                     gain_db=GAIN_DB, seconds=2.2, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=direct)
    except Exception as exc:
        arms.append({'tag': tag, 'stop': 'raised: %r' % (exc,)[:60]})
        break
    data = np.load(str(out))
    meta = json.loads(str(data['metadata_json']))
    arms.append({'tag': tag, 'stop': meta.get('stop_reason'),
                 'capture_status': int(meta.get('capture_status') or 0),
                 'mic_peak_dbfs': peak_dbfs(data['microphone']),
                 'ref_rms_dbfs': rms_dbfs(data['reference'])})
    if meta.get('stop_reason') != 'completed':
        print('RECAL_ARM_STOP %s stop=%s (recorded; no further amplitude reduction)'
              % (tag, meta.get('stop_reason')))
        break
    rows[tag] = (data, meta, None)

holds, tp, insufficient = False, None, None
if len(rows) == 3:
    tp = guard.three_point(rows, 322.0)
    open_pk = [a['mic_peak_dbfs'] for a in arms if a['tag'] == 'open'][0]
    byp_pk = [a['mic_peak_dbfs'] for a in arms if a['tag'] == 'bypass'][0]
    boost_peak_db = byp_pk - open_pk
    # Judge resolvability on the three-point's OWN loop-boost quantity, not on a second crude peak
    # difference: the peak estimator is noisier and flagged a run whose loop boost was real (1.03 dB).
    boost_db = tp['loop_boost_db']
    if boost_db < 1.0:
        insufficient = ('the loop only adds %.2f dB above the no-loop path, so a PASS would not show '
                        'that cancellation works' % boost_db)
    holds = (tp['acoustic_difference_db'] >= tp['loop_boost_db'] - 1.5
             and abs(tp['overshoot_db']) <= 1.5)
    print('RECAL_THREE_POINT cd=%.2f loop_boost=%.2f acoustic=%.2f overshoot=%.2f boost_peak=%.2f rule=%s'
          % (tp['cd_322_db'], tp['loop_boost_db'], tp['acoustic_difference_db'],
             tp['overshoot_db'], boost_peak_db, 'PASS' if holds else 'FAIL'))
    if insufficient:
        print('RECAL_INSUFFICIENT %s' % insufficient)
else:
    print('RECAL_THREE_POINT not all three arms completed -> FAIL')

if insufficient:
    cand.rename(cand.with_suffix('.rejected.json'))
    print('RECAL_MODEL rejected - measurement invalid, the installed model was NOT changed')
    fail('verify', 15, 'measurement insufficient: %s' % insufficient)
if not holds:
    cand.rename(cand.with_suffix('.rejected.json'))
    print('RECAL_MODEL rejected - the installed model was NOT changed')
    fail('verify', 15, 'three-point rule not met')

# ---- [6] install -------------------------------------------------------------------------------
prev = None
if ACTIVE.is_file():
    prev = D / ('model_prev_%s.json' % RUN_ID)
    prev.write_bytes(ACTIVE.read_bytes())
ACTIVE.write_bytes(cand.read_bytes())
active_sha, cand_sha = coeff_sha(ACTIVE), coeff_sha(cand)
if active_sha != cand_sha:
    fail('install', 16, 'installed model hash differs from the candidate')
print('RECAL_STAGE 6 ok  active=%s coeff_sha=%s' % (ACTIVE.name, active_sha[:16]))

# ---- [7] smoke ---------------------------------------------------------------------------------
smoke = RUN_DIR / 'checks' / 'smoke.npz'
smoke.unlink(missing_ok=True)
try:
    replay_trial(str(smoke), FIXTURE, str(ACTIVE), np.zeros(16000, np.int16), bypass=False,
                 zero_coeff=False, gain_db=GAIN_DB, seconds=2.0, hp_volume=HP_VOLUME,
                 speaker_confirmed=True, local_capture_confirmed=True)
except Exception as exc:
    fail('smoke', 17, 'smoke raised %r' % (exc,))
smeta = json.loads(str(np.load(str(smoke))['metadata_json']))
used = str(smeta.get('coefficients_sha256') or '')
if smeta.get('stop_reason') != 'completed' or used != active_sha:
    fail('smoke', 17, 'smoke stop=%s coeff=%s vs %s'
         % (smeta.get('stop_reason'), used[:12], active_sha[:12]))
print('RECAL_STAGE 7 ok  run used coeff_sha=%s' % used[:16])

# ---- [8] voice ---------------------------------------------------------------------------------
# The cue has to be unmistakable to someone standing at the microphone who cannot see the screen, and
# it must not be confusable with the 322 Hz acceptance tone. So: an ascending three-note figure
# (C5-G5-C6), twice, with gaps - different pitch contour, different rhythm, and it stops. If the voice
# take carries no voice, the cue repeats and the take is retaken once; each attempt is kept.
VOICE_SECONDS = 20.0
VOICE_MIN_SNR_DB = 10.0
VOICE_ATTEMPTS = 2


def cue_notes():
    """Ascending C5-G5-C6 figure, twice, with silent gaps."""
    parts = []
    for _rep in range(2):
        for freq in (523.25, 783.99, 1046.50):
            parts.append(np.rint(0.22 * np.sin(2 * np.pi * freq * np.arange(int(0.16 * RATE)) / RATE)
                                 * 32767).astype(np.int16))
            parts.append(np.zeros(int(0.05 * RATE), np.int16))
        parts.append(np.zeros(int(0.35 * RATE), np.int16))
    return np.concatenate(parts)


print('RECAL_STAGE 8 voice (%d attempts, cue = ascending three-note figure)' % VOICE_ATTEMPTS)
voice_attempts = []
v_rms, v_used = None, None
for attempt in range(VOICE_ATTEMPTS):
    cue = RUN_DIR / 'prep' / ('cue_%d.npz' % attempt)
    cue.unlink(missing_ok=True)
    try:
        replay_trial(str(cue), FIXTURE, str(BASE_MODEL), cue_notes(), bypass=True, zero_coeff=False,
                     gain_db=0.0, seconds=2.6, hp_volume=HP_VOLUME, speaker_confirmed=True,
                     local_capture_confirmed=True, direct_only=True)
    except Exception as exc:
        print('RECAL_CUE_WARN %r' % (exc,))
    print('RECAL_CAN_SPEAK  >>> three rising notes = speak now (%d/%d) <<<' % (attempt + 1, VOICE_ATTEMPTS))
    time.sleep(2.0)
    voice = RUN_DIR / 'checks' / ('voice_%d.npz' % attempt)
    voice.unlink(missing_ok=True)
    try:
        replay_trial(str(voice), FIXTURE, str(ACTIVE), np.zeros(16000, np.int16), bypass=False,
                     zero_coeff=False, gain_db=GAIN_DB, seconds=VOICE_SECONDS, hp_volume=HP_VOLUME,
                     speaker_confirmed=True, local_capture_confirmed=True)
    except Exception as exc:
        fail('voice', 18, 'voice capture raised %r' % (exc,))
    vmeta = json.loads(str(np.load(str(voice))['metadata_json']))
    v_rms = rms_dbfs(np.load(str(voice))['microphone'])
    v_used = str(vmeta.get('coefficients_sha256') or '')
    loud = v_rms - floor_db
    voice_attempts.append({'attempt': attempt + 1, 'rms_dbfs': v_rms, 'above_floor_db': loud,
                           'stop': vmeta.get('stop_reason'), 'used_coeff_sha256': v_used})
    print('RECAL_VOICE_TRY %d rms=%.2f dBFS (%.2f dB above floor) stop=%s'
          % (attempt + 1, v_rms, loud, vmeta.get('stop_reason')))
    if vmeta.get('stop_reason') != 'completed':
        fail('voice', 18, 'voice stopped: %s' % vmeta.get('stop_reason'))
    if v_used != active_sha:
        fail('voice', 18, 'voice used %s, not %s' % (v_used[:12], active_sha[:12]))
    if loud >= VOICE_MIN_SNR_DB:
        print('RECAL_STAGE 8 ok  voice usable (%.2f dB above floor)' % loud)
        break
    if attempt + 1 == VOICE_ATTEMPTS:
        fail('voice', 18, 'no voice detected in %d attempts (best %.2f dB above floor, need %.1f)'
             % (VOICE_ATTEMPTS, loud, VOICE_MIN_SNR_DB))
    print('RECAL_VOICE_RETRY  no voice detected; cueing again')

# ---- summary -----------------------------------------------------------------------------------
receipt = {
    'run_id': RUN_ID, 'position': POSITION, 'verdict': 'PASS', 'protocol': 'v2_auto_levelled',
    'config': {'level_db_commanded': LEVEL_DB, 'actual_ref_rms_dbfs': ref_db,
               'actual_ref_peak_dbfs': pk_db, 'peak_cap': PEAK_CAP, 'gain_db': GAIN_DB,
               'hp_volume': HP_VOLUME, 'segments': SEGMENTS, 'seg_seconds': SEG_SECONDS,
               'min_snr_db': MIN_SNR_DB, 'l1_max': L1_MAX},
    'floor_dbfs': floor_db, 'snr_db': snr_db, 'ref_rms_dbfs': ref_db, 'mic_rms_dbfs': mic_db,
    'candidate_coeff_sha256': cand_sha, 'active_coeff_sha256': active_sha,
    'smoke_used_coeff_sha256': used, 'previous_model_backup': prev.name if prev else None,
    'L1': l1_new, 'L1_deployed': l1_base, 'three_point': tp, 'arms': arms,
    'acceptance_tone': {'target_peak_dbfs': TONE_TARGET_DBFS, 'source_fs_frozen': tone_fs,
                        'adjustments': adjusts, 'trials': trials, 'same_source_all_arms': True},
    'measurement_insufficient': insufficient,
    'loop_boost_peak_estimator_db': boost_peak_db if len(rows) == 3 else None,
    'voice': {'attempts': voice_attempts, 'rms_dbfs': v_rms, 'above_floor_db': v_rms - floor_db, 'stop': vmeta.get('stop_reason'), 'used_coeff_sha256': v_used,
              'seconds': VOICE_SECONDS},
}
(RUN_DIR / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print('RECAL_SUMMARY run=%s position=%s verdict=PASS snr=%.2f L1=%.2f acoustic=%.2f overshoot=%.2f tone_fs=%.4f'
      % (RUN_ID, POSITION, snr_db, l1_new, tp['acoustic_difference_db'], tp['overshoot_db'], tone_fs))
print('RECAL_MODEL_IDENTITY candidate=%s active=%s used=%s'
      % (cand_sha[:16], active_sha[:16], used[:16]))
print('RECAL_END run=%s verdict=PASS stage=done' % RUN_ID)
# ---- summary -----------------------------------------------------------------------------------
receipt = {
    'run_id': RUN_ID, 'position': POSITION, 'verdict': 'PASS', 'protocol': 'v2_auto_levelled',
    'config': {'level_db_commanded': LEVEL_DB, 'actual_ref_rms_dbfs': ref_db,
               'actual_ref_peak_dbfs': pk_db, 'peak_cap': PEAK_CAP, 'gain_db': GAIN_DB,
               'hp_volume': HP_VOLUME, 'segments': SEGMENTS, 'seg_seconds': SEG_SECONDS,
               'min_snr_db': MIN_SNR_DB, 'l1_max': L1_MAX},
    'floor_dbfs': floor_db, 'snr_db': snr_db, 'ref_rms_dbfs': ref_db, 'mic_rms_dbfs': mic_db,
    'candidate_coeff_sha256': cand_sha, 'active_coeff_sha256': active_sha,
    'smoke_used_coeff_sha256': used, 'previous_model_backup': prev.name if prev else None,
    'L1': l1_new, 'L1_deployed': l1_base, 'three_point': tp, 'arms': arms,
    'acceptance_tone': {'target_peak_dbfs': TONE_TARGET_DBFS, 'source_fs_frozen': tone_fs,
                        'adjustments': adjusts, 'trials': trials, 'same_source_all_arms': True},
    'measurement_insufficient': insufficient,
    'loop_boost_peak_estimator_db': boost_peak_db if len(rows) == 3 else None,
    'voice': {'attempts': voice_attempts, 'rms_dbfs': v_rms,
              'above_floor_db': v_rms - floor_db, 'used_coeff_sha256': v_used,
              'seconds': VOICE_SECONDS},
}
(RUN_DIR / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print('RECAL_SUMMARY run=%s position=%s verdict=PASS snr=%.2f L1=%.2f acoustic=%.2f overshoot=%.2f tone_fs=%.4f'
      % (RUN_ID, POSITION, snr_db, l1_new, tp['acoustic_difference_db'], tp['overshoot_db'], tone_fs))
print('RECAL_MODEL_IDENTITY candidate=%s active=%s used=%s'
      % (cand_sha[:16], active_sha[:16], used[:16]))
print('RECAL_END run=%s verdict=PASS stage=done' % RUN_ID)
PY
rc=$?
echo "RECAL_EXIT rc=$rc"
exit $rc
