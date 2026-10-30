"""Operator-paced A/B batches. Import does not access hardware or play audio."""
import csv
import hashlib
import json
from pathlib import Path
import uuid

GAINS = (-30, -24, -18, -12)
SUMMARY_SCHEMA_VERSION = 2
ACTUAL_CONFIG_FIELDS = ('gain_q12', 'hp_volume', 'bit_sha256')
MATCH_KEYS = ('bit_sha256', 'model_sha256', 'coefficients_sha256',
              'fixture_id', 'hp_volume', 'sample_rate_hz', 'gain_q12',
              'completed_frames', 'sound_seconds_nominal')
HEARING = {'0': 'inaudible', '1': 'speech', '2': 'noise',
           '3': 'howl_or_growth', '4': 'not_quiet_at_end', 'q': 'operator_stop'}


def rejection(result):
    """Fail closed on missing telemetry as well as explicit failure."""
    v = result.get('verification', {})
    if v.get('bit_exact') is not True:
        return 'arithmetic_check_failed'
    for key in ('prediction_mismatches', 'residual_mismatches', 'output_mismatches'):
        if v.get(key) != 0:
            return key
    for key in ('prediction_saturations', 'residual_saturations',
                'gain_saturations', 'mic_full_scale_samples'):
        if result.get(key) != 0:
            return key
    if result.get('zero_coeff') is not False:
        return 'wrong_coefficients'
    if any(result.get(k) is None for k in MATCH_KEYS):
        return 'missing_configuration_metadata'
    return None


def export_summary(folder, state):
    """Save after every transition; a new UUID directory protects previous batches."""
    folder = Path(folder)
    state['schema_version'] = SUMMARY_SCHEMA_VERSION
    for row in state['trials']:
        # Driver telemetry is authoritative; cancellation/unknown values stay null.
        # Retain metadata for existing consumers and expose aliases for flat exports.
        metadata = row.get('metadata', {})
        for key in ACTUAL_CONFIG_FIELDS:
            row[key] = metadata.get(key)
    pairs = []
    for gain in GAINS:
        rows = [r for r in state['trials'] if r['gain_db_requested'] == gain]
        if len(rows) != 2 or any('metadata' not in r for r in rows):
            continue
        a, b = rows
        comparable = all(a['metadata'].get(k) is not None and
                         a['metadata'].get(k) == b['metadata'].get(k) for k in MATCH_KEYS)
        pairs.append(dict(gain_db_requested=gain, configuration_matches=comparable,
                          bypass_hearing=a.get('hearing'), cancel_hearing=b.get('hearing'),
                          digital_checks_pass=not rejection(a['metadata']) and not rejection(b['metadata']),
                          asg_db=None))
    state['pairs'] = pairs
    temp = folder / 'summary.json.tmp'
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(folder / 'summary.json')
    fields = ['index', 'gain_db_requested', 'mode', 'hearing', 'error',
              *ACTUAL_CONFIG_FIELDS, 'gain_db_actual',
              'mic_rms_dbfs', 'mic_peak_dbfs', 'prediction_saturations',
              'residual_saturations', 'gain_saturations', 'bit_exact', 'file']
    with (folder / 'summary.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for row in state['trials']:
            m = row.get('metadata', {})
            out = {k: row.get(k, m.get(k)) for k in fields}
            out['bit_exact'] = m.get('verification', {}).get('bit_exact')
            writer.writerow(out)


def run_batch(fixture_id='box_v1_20261016',
              model_path='../audio_calibrate/candidate_box_v1_256.json',
              output_root='batch_results', ask=input, runner=None):
    """Eight trials maximum, 2 seconds each; every trial requires a fresh START.

    Fixed coarse gains are for initial operating-range exploration, NOT MSG.
    No automatic resumption, no unattended gain escalation, no raw-data upload.
    Injectable runner/ask support offline tests without PYNQ.
    """
    print('计划：-30 / -24 / -18 / -12 dB，每档先旁路再抵消，每项2秒，共最多8项。')
    print('保持箱体、接线和手机循环人声不变；不戴耳机；可立即切断音响电源。')
    print('采样只保存在板卡。输入 READY 确认现场条件和本地保存；其他输入退出。')
    if ask('现场就绪：').strip().upper() != 'READY':
        return None
    if runner is None:
        from closed_trial import closed_trial
        runner = closed_trial
    model_path = Path(model_path).resolve()
    model_digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    folder = Path(output_root) / ('batch_' + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    state = dict(schema_version=SUMMARY_SCHEMA_VERSION, batch_id=folder.name, status='running', trials=[],
                 gains_db=list(GAINS), seconds=2.0, hp_volume=40,
                 interpretation='operating-range exploration; NOT measured MSG/ASG',
                 monitoring='no continuous spectral monitor; only tail PCM and full-run saturation counts',
                 fixture_id=fixture_id, model_sha256=model_digest)
    export_summary(folder, state)
    active_row = None
    try:
        for gain in GAINS:
            pair = []
            for bypass in (True, False):
                mode = 'bypass' if bypass else 'cancel'
                index = len(state['trials']) + 1
                path = folder / ('%02d_%s_%ddB.npz' % (index, mode, gain))
                active_row = dict(index=index, gain_db_requested=gain, mode=mode, file=path.name)
                state['trials'].append(active_row)
                export_summary(folder, state)
                if hashlib.sha256(model_path.read_bytes()).hexdigest() != model_digest:
                    raise RuntimeError('model file changed during batch')

                def ready():
                    print('\n[%d/8] %s，%d dB，2秒。配置已完成，当前静音。' % (index, mode, gain))
                    return ask('准备听时输入 START 并回车；其他输入停止整批：').strip().upper() == 'START'

                result = runner(path, fixture_id, str(model_path), bypass=bypass,
                                zero_coeff=False, gain_db=gain, seconds=2.0, hp_volume=40,
                                speaker_confirmed=True, local_capture_confirmed=True,
                                before_start=ready)
                active_row['metadata'] = result
                reason = rejection(result)
                if result.get('bypass') is not bypass or result.get('model_sha256') != model_digest:
                    reason = 'unexpected_mode_or_model'
                if pair and any(pair[0].get(k) != result.get(k) for k in MATCH_KEYS):
                    reason = 'pair_configuration_mismatch'
                export_summary(folder, state)
                if reason:
                    raise RuntimeError(reason)
                pair.append(result)
                print('本项结束。若尖叫仍在持续，立即切断音响电源。')
                answer = ask('听感：0无声 / 1人声（均已安静） / 2杂音 / 3尖叫或增长 / 4结束未静 / q停止：').strip().lower()
                while answer not in HEARING:
                    answer = ask('请输入0、1、2、3、4或q；等待期间不会播放：').strip().lower()
                active_row['hearing'] = HEARING[answer]
                export_summary(folder, state)
                if answer not in ('0', '1'):
                    state['status'] = 'stopped'; state['stop_reason'] = HEARING[answer]
                    return state
        state['status'] = 'completed'
    except (Exception, KeyboardInterrupt) as exc:
        state['status'] = 'stopped'
        state['stop_reason'] = type(exc).__name__ + ': ' + str(exc)
        if active_row is not None:
            active_row['error'] = state['stop_reason']
        print('整批已停止：', state['stop_reason'])
    finally:
        export_summary(folder, state)
        print('汇总保存在：', str(folder / 'summary.json'))
        print('请只返回 summary.json；原始NPZ留板。未计算MSG/ASG。')
    return state
