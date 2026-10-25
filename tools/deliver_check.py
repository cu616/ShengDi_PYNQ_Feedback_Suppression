"""Two ShengDi offline deliveries. Python standard library only; never imports PYNQ.

Run `python tools/deliver_check.py cold-start` or `... listener-pipeline`.
A ZIP path verifies an already produced delivery. Only a successful complete
verification prints PACKAGE_COMPLETE, and its digest is the ZIP's SHA256.
"""
import argparse
from array import array
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tempfile
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIRM = 'FIXED_SOURCE_FIXED_GAIN_NO_AGC'
KINDS = ('cold-start', 'listener-pipeline')


class DeliveryError(Exception):
    def __init__(self, defect, message):
        self.defect = defect
        super().__init__(message)


def require(condition, defect, message):
    if not condition:
        raise DeliveryError(defect, message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf8')


def source_bytes(path):
    return Path(path).read_bytes().replace(b'\r\n', b'\n')


def config():
    cfg = json.loads((ROOT/'tools/delivery-freeze.json').read_text(encoding='utf8'))
    for name, expected in cfg['source_sha256'].items():
        require(digest(source_bytes(ROOT/name)) == expected, 'D2', 'source hash mismatch: '+name)
    return cfg


def identity():
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.PIPE).decode('utf8').strip()
    require(Path(git('rev-parse','--show-toplevel')).resolve() == ROOT, 'D3', 'run from a complete clean Git checkout')
    status = git('status','--porcelain','--untracked-files=normal')
    require(not status, 'D4', 'checkout is not clean: '+status)
    return dict(repository_commit=git('rev-parse','HEAD'), clean_checkout=True,
                python=platform.python_version(), platform=platform.platform(),
                dependencies='Python standard library and Git; no NumPy, network, PYNQ or board required')


def asset_checks(package, cfg):
    require(digest(package) == cfg['package']['sha256'], 'D2', 'frozen human archive hash mismatch')
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        manifest = json.loads(z.read('sprint-manifest.json'))
        preflight = json.loads(z.read('preflight.json'))
        checks = {n:digest(z.read(n)) == h for n,h in manifest['hashes'].items()}
        require(all(checks.values()), 'D2', 'frozen archive payload hash mismatch')
        model = json.loads(z.read('model.json'))
        q = model['coefficients_q20']
        qhash = digest(struct.pack('<%di'%len(q), *q))
        assets = dict(preflight['a_assets'])
        require(assets == manifest['a_assets'] == cfg['assets'], 'D2', 'asset binding differs from frozen manifest')
        if 'assets' in preflight:
            require(preflight['assets'] == assets, 'D2', 'assets/a_assets aliases disagree')
        require(digest(z.read('audio_replay.bit')) == assets['bit_sha256'] and
                digest(z.read('audio_replay.hwh')) == assets['hwh_sha256'], 'D2', 'bit/hwh bytes differ')
        require(digest(z.read('model.json')) == cfg['model']['file_sha256'] and
                qhash == cfg['model']['q20_sha256'] and len(q) == model['taps'] == 512 and
                model['lag_first'] == 1, 'D2', 'deployed model identity differs')
        require(preflight['all_ok'] is True and len(preflight['trials']) == 5 and
                all(r['ok'] and r['window_frames'] > 0 for r in preflight['trials']), 'D1', 'frozen preflight fails')
        require(preflight['payload_hashes'] == {k:v for k,v in manifest['hashes'].items() if k!='preflight.json'},
                'D2', 'preflight payload inventory differs')
    return dict(all_ok=True, payload_count=len(checks), payload_hashes=manifest['hashes'],
                assets=assets, model=dict(taps=512,lag_first=1,file_sha256=cfg['model']['file_sha256'],q20_sha256=qhash),
                preflight_original_asset_key='a_assets', preflight_assets_alias_present='assets' in preflight,
                window_frames=[r['window_frames'] for r in preflight['trials']], q=q)


def mapping_controls(q):
    """Bypass mapping plus deployed FIR arithmetic, with independent history indexing."""
    rows=[]; taps=len(q); n=1024
    mic=[((i*8191)%1000001)-500000 for i in range(n)]
    def rounded(v,bits):
        return (1 if v>=0 else -1)*((abs(v)+(1<<(bits-1)))>>bits)
    for db in (-12,-6,0):
        gain=int(math.floor(4096*10**(db/20)+.5)); ref=[]; pred=[]; history=[0]*taps
        for i in range(n):
            current=rounded(mic[i-2]*gain,12) if i>=2 else 0
            pred.append(rounded(sum(a*b for a,b in zip(q,history)),20))
            ref.append(current);history=[current]+history[:-1]
        mismatch=0
        for i in range(taps,n):
            acc=sum(q[k]*ref[i-1-k] for k in range(taps))
            expected=(abs(acc)+(2**20//2))//2**20
            if acc<0:expected=-expected
            mismatch += pred[i] != expected
        a=ref[2:];b=mic[:-2]
        mean_a=math.fsum(a)/len(a);mean_b=math.fsum(b)/len(b)
        measured=10*math.log10(math.fsum((x-mean_a)**2 for x in a)/math.fsum((x-mean_b)**2 for x in b))
        expected_db=20*math.log10(gain/4096)
        require(mismatch==0 and abs(measured-expected_db)<.001, 'D4', 'Q20/bypass fixture mismatch')
        rows.append(dict(gain_db=db,gain_q12=gain,ref_over_mic_db=measured,expected_db=expected_db,
                         error_db=measured-expected_db,prediction_mismatches=mismatch,evaluated_frames=n-taps,ok=True))
    return rows


def write_wav(path, samples, rate):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(struct.pack('<%dh'%len(samples),*samples))


def metrics():
    spec=importlib.util.spec_from_file_location('c_listener_production',ROOT/'board/audio_replay/listener_metrics.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.listener_metrics


def listener_fixture(work):
    rate=16000;n=rate*2
    noise=[round(300*math.sin(2*math.pi*2300*i/rate)) for i in range(n)]
    signals={m:[round(a*math.sin(2*math.pi*1000*i/rate)) for i in range(n)]
             for m,a in (('off',3000),('on',3000*10**(3/20)))}
    data={m+'-'+kind:([a+b for a,b in zip(signals[m],noise)] if kind=='speech' else noise)
          for m in ('off','on') for kind in ('speech','noise')}
    for case in ('positive','length-mismatch','clipped','rate-mismatch'):
        for key,original in data.items():
            samples=list(original);sr=rate
            if case=='length-mismatch' and key=='on-speech':samples=samples[:-16]
            if case=='clipped' and key=='on-speech':samples[123]=32767
            if case=='rate-mismatch' and key=='on-noise':sr=22050
            write_wav(work/case/(key+'.wav'),samples,sr)
    measure=metrics();positive=measure(work/'positive',CONFIRM)
    require(positive['status']=='passed', 'D4', 'positive WAV fixture rejected: '+str(positive))
    # Truth uses known separate components, not the pipeline's noise subtraction.
    truth=10*math.log10(math.fsum(v*v for v in signals['on'])/math.fsum(v*v for v in signals['off']))
    snr_delta=positive['snr_db']['on']-positive['snr_db']['off']
    error=positive['relative_speech_change_db']-3.0
    require(abs(error)<.5 and abs(snr_delta-3)<.5, 'D4', 'known +3 dB control outside tolerance')
    failures={case:measure(work/case,CONFIRM) for case in ('length-mismatch','clipped','rate-mismatch')}
    require(all(v['status']=='failed' and v.get('reason') for v in failures.values()),
            'D4', 'a malformed WAV set silently passed')
    return dict(all_ok=True,evidence_kind='synthetic_WAV_only',analytic_snr_delta_db=3.0,
                independent_quantized_component_truth_db=truth,positive=positive,
                relative_change_error_db=error,total_to_background_delta_db=snr_delta,
                total_to_background_error_db=snr_delta-3,tolerance_db=.5,negative_cases=failures,
                snr_definition='legacy snr_db=10log10(total speech-recording power/background power); speech change subtracts background power',
                real_listener_test='not_tested',absolute_spl=None)


def report_markdown(kind, report):
    if kind=='cold-start':
        a=report['assets'];m=report['model']
        body=(f"# 冷启动软件复现报告\n\n固定检出：`{report['repository_commit']}`；clean_checkout=true。\n\n"
              f"bit SHA256：`{a['bit_sha256']}`\n\nhwh SHA256：`{a['hwh_sha256']}`\n\n"
              f"模型文件：`{m['file_sha256']}`；Q20：`{m['q20_sha256']}`；taps=512，lag_first=1。\n\n"
              f"原包{report['payload_count']}个载荷逐项一致，三点部署算术与增益映射通过。\n\n"
              "原冻结preflight的资产字段为a_assets；本报告assets为其经实际文件哈希核验的兼容映射。\n\n"
              "仅离线资产/软件夹具复现；未操板，不完成另一位队友的现场独立复现。\n")
    else:
        body=(f"# 合成WAV管线验证\n\n固定检出：`{report['repository_commit']}`。\n\n"
              f"真值+3dB；relative_speech_change_db={report['positive']['relative_speech_change_db']:.9f}，"
              f"误差={report['relative_change_error_db']:.9f}dB，要求绝对误差<0.5dB。\n\n"
              "长度不等、削顶、采样率不同三组均返回failed及明确原因。\n\n"
              "全部WAV为合成；未做真人/听众验收，不报绝对SPL。\n")
    return body.encode('utf8')


def verify_artifact(path, cfg):
    data=Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        manifest=json.loads(z.read('artifact-manifest.json'));kind=manifest['kind']
        require(kind in KINDS, 'D3', 'unknown artifact kind')
        require(set(z.namelist())==set(manifest['sha256'])|{'artifact-manifest.json'}, 'D3', 'artifact inventory differs')
        require(all(digest(z.read(k))==v for k,v in manifest['sha256'].items()), 'D2', 'artifact payload mismatch')
        require(json.loads(z.read('tools/delivery-freeze.json'))==cfg, 'D2', 'artifact freeze manifest differs')
        for name,h in cfg['source_sha256'].items():
            require(digest(z.read(name))==h, 'D2', 'artifact source differs: '+name)
        r=json.loads(z.read(kind+'.json'))
        require(r.get('all_ok') is True and r.get('clean_checkout') is True and
                re.fullmatch('[0-9a-f]{40}',r.get('repository_commit','')) is not None, 'D3', 'missing successful provenance')
        if kind=='cold-start':
            current=asset_checks(z.read(cfg['package']['path']),cfg);q=current.pop('q')
            for k,v in current.items():require(r.get(k)==v,'D2','cold-start report mismatch: '+k)
            controls=mapping_controls(q)
            require(len(r['mapping_controls'])==len(controls),'D3','mapping control missing')
            for saved,actual in zip(r['mapping_controls'],controls):
                require(set(saved)==set(actual),'D3','mapping fields differ')
                require(all(abs(saved[k]-v)<1e-10 if isinstance(v,float) else saved[k]==v
                            for k,v in actual.items()),'D4','mapping report differs from recomputation')
        else:
            base=ROOT/'build/generated';base.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=base,prefix='verify-listener-') as temp:
                work=Path(temp)
                for name in manifest['sha256']:
                    if not name.startswith('wav/') or not name.endswith('.wav'):continue
                    rel=Path(name).relative_to('wav')
                    require('..' not in rel.parts and not rel.is_absolute(), 'D3', 'unsafe WAV path')
                    target=work/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
                measure=metrics();actual=measure(work/'positive',CONFIRM)
                require(actual==r['positive'],'D4','positive listener result differs on replay')
                require(abs(actual['relative_speech_change_db']-3)<.5,'D4','relative-change tolerance failed')
                require(abs(actual['snr_db']['on']-actual['snr_db']['off']-3)<.5,'D4','SNR-difference tolerance failed')
                require(r['analytic_snr_delta_db']==3 and abs(r['independent_quantized_component_truth_db']-3)<.01,
                        'D4','synthetic truth definition differs')
                for case in ('length-mismatch','clipped','rate-mismatch'):
                    bad=measure(work/case,CONFIRM)
                    require(bad==r['negative_cases'][case] and bad['status']=='failed' and bool(bad.get('reason')),
                            'D4','malformed listener set not rejected: '+case)
    return digest(data)


def build(kind, cfg):
    who=identity();out=ROOT/'build/generated/delivery';out.mkdir(parents=True,exist_ok=True)
    payload={n:source_bytes(ROOT/n) for n in cfg['source_sha256']}
    payload['tools/delivery-freeze.json']=encoded(cfg)
    if kind=='cold-start':
        package=(ROOT/cfg['package']['path']).read_bytes();report=asset_checks(package,cfg)
        q=report.pop('q');report['mapping_controls']=mapping_controls(q)
        report.update(evidence_kind='offline_frozen_assets_and_software_fixture',
                      hardware_test='not_tested',independent_teammate_reproduction='not_tested')
        payload[cfg['package']['path']]=package
    else:
        with tempfile.TemporaryDirectory(dir=out,prefix='listener-') as temp:
            work=Path(temp);report=listener_fixture(work)
            payload.update({'wav/'+p.relative_to(work).as_posix():p.read_bytes() for p in work.rglob('*.wav')})
    report.update(who,kind=kind)
    payload[kind+'.json']=encoded(report)
    doc='docs/cold-start-reproduction.md' if kind=='cold-start' else 'docs/listener-pipeline.md'
    payload[doc]=report_markdown(kind,report)
    manifest=dict(schema_version=1,kind=kind,sha256={n:digest(b) for n,b in payload.items()})
    archive=out/(kind+'.zip');temporary=out/(kind+'.zip.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(payload.items()):
            item=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,data)
        item=zipfile.ZipInfo('artifact-manifest.json',date_time=(1980,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(item,encoded(manifest))
    temporary.replace(archive)
    checksum=verify_artifact(archive,cfg)
    (out/(kind+'.json')).write_bytes(payload[kind+'.json'])
    docs=out/'docs';docs.mkdir(exist_ok=True);(docs/Path(doc).name).write_bytes(payload[doc])
    return archive,checksum


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact',help='cold-start, listener-pipeline, or an existing delivery ZIP')
    args=parser.parse_args(argv)
    try:
        cfg=config()
        if args.artifact in KINDS:
            path,checksum=build(args.artifact,cfg)
            print('ARTIFACT '+str(path.resolve()))
        else:
            path=Path(args.artifact);checksum=verify_artifact(path,cfg)
        print('PACKAGE_COMPLETE '+checksum)
        return 0
    except (DeliveryError,OSError,ValueError,KeyError,zipfile.BadZipFile,subprocess.CalledProcessError) as exc:
        defect=exc.defect if isinstance(exc,DeliveryError) else 'D3' if isinstance(exc,(OSError,KeyError)) else 'D4'
        detail=str(exc)
        if isinstance(exc,subprocess.CalledProcessError) and exc.stderr:
            detail+=' | '+exc.stderr.decode('utf8',errors='replace').strip()
        print('DELIVERY_FAILED '+defect+' | command='+subprocess.list2cmdline([sys.executable,*sys.argv])+' | '+detail)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
