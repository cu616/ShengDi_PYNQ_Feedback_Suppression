"""Review the existing A JSON; not a local re-analysis of unavailable PCM."""
from pathlib import Path
import hashlib
import json
import math
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent

def main():
    raw=(HERE/'tone-return.json').read_bytes(); d=json.loads(raw)
    m=json.loads(subprocess.check_output(['git','show','facd3de:board/audio_replay/v3/manifest.json'],cwd=ROOT))
    checks=[]
    def check(name,ok): checks.append(dict(name=name,passed=bool(ok)))
    check('round selected exactly', d['round_id']==1746930178556850644)
    check('pairing and numeric review clear',d['pairing_integrity_clear'] and d['captured_numeric_checks_clear'] and not d['pairing_issues'])
    producer=subprocess.check_output(['git','show','330e135:scripts/review_itemized_20261027.py'],cwd=ROOT)
    transformed=b'\xef\xbb\xbf'+producer.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    check('producer BOM/CRLF transformation exact',hashlib.sha256(transformed).hexdigest()==d['producer_sha256'])
    source_hashes=set(); starts=[]; ends=[]; configs={}
    for arm,r in d['capture_reviews'].items():
        meta=r['original_metadata']; prov=d['provenance'][arm]
        check(arm+' original hash binds review',r['original_sha256']==prov['original_sha256'] and r['original_status_sha256']==prov['status_sha256'])
        for key,filename in [('bit_sha256','audio_replay.bit'),('hwh_sha256','audio_replay.hwh'),('driver_sha256','replay_trial.py'),('replay_tools_sha256','replay_tools.py')]:
            check(arm+' '+key,meta[key]==m['hashes'][filename])
        check(arm+' model and fixture',meta['model_sha256']==m['model']['sha256'] and meta['fixture_id']==m['model']['fixture_id'])
        check(arm+' completed without protection',not meta['early_stop'] and meta['stop_reason']=='completed' and not meta['input_full_scale_seen'] and all(meta[k]==0 for k in ('prediction_saturations','residual_saturations','gain_saturations','mix_saturations')))
        check(arm+' captured extent',meta['first_frame']+meta['frames']==meta['completed_frames'] and meta['frames']==16384)
        source_hashes.add(meta['source_pcm16_sha256']); starts.append(meta['first_frame']); ends.append(min(meta['completed_frames'],meta['source_end_frame_exclusive']))
        configs[arm]={key:meta[key] for key in ('gain_q12','hp_volume','bypass','zero_coeff','coefficients_sha256','source_frames','source_pcm16_sha256')}
    check('one actual source identity',len(source_hashes)==1)
    check('open is gain zero',configs['open']['gain_q12']==0)
    check('paired gain and Codec',configs['bypass']['gain_q12']==configs['cancel']['gain_q12'] and len({c['hp_volume'] for c in configs.values()})==1)
    check('bypass/cancel semantic switch',configs['bypass']['bypass'] and not configs['cancel']['bypass'])
    active=d['views']['common_source_active']
    check('common interval intersection',active['first_frame']==max(starts) and active['end_frame']==min(ends) and active['scheduled_source_frames']==6619 and not active['includes_source_free_frames'])
    arithmetic={}
    for view,v in d['views'].items():
        o,b,c=(v['levels_peak_dbfs'][x] for x in ('open','bypass','cancel'))
        independently=dict(cd_322_db=b['residual']-c['residual'],loop_boost_db=b['microphone']-o['microphone'],
            acoustic_difference_db=b['microphone']-c['microphone'],overshoot_db=o['microphone']-c['microphone'],
            played_bypass_minus_cancel_db=b['reference']-c['reference'])
        check(view+' five differences',all(math.isclose(value,v['three_point'][key],abs_tol=1e-10) for key,value in independently.items()))
        check(view+' decomposition',math.isclose(independently['acoustic_difference_db'],independently['loop_boost_db']+independently['overshoot_db'],abs_tol=1e-10))
        arithmetic[view]=independently
    result=dict(ok=all(c['passed'] for c in checks),review_level='C local identity/window/derived-arithmetic audit of A board-produced JSON; PCM not obtained by C',
        source_commit='facd3de',source_json_sha256=hashlib.sha256(raw).hexdigest(),producer_git_sha256=hashlib.sha256(producer).hexdigest(),
        producer_returned_sha256=d['producer_sha256'],checks=checks,configs=configs,arithmetic=arithmetic,
        active_frames=6619,active_duration_seconds=6619/48828.125,hardware_operations=0,
        unexecuted=['local original PCM recalculation','new recording','listening benefit/SPL','MSG/ASG'],limits=d['limits'])
    (HERE/'tone-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'ok':result['ok'],'checks':len(checks),'passed':sum(c['passed'] for c in checks),'configs':configs,'active':arithmetic['common_source_active']},ensure_ascii=False))
    raise SystemExit(0 if result['ok'] else 2)

if __name__=='__main__': main()
