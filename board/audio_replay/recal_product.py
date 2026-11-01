"""Resident C product orchestrator. Import is silent; A alone accesses hardware."""
import argparse
import contextlib
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from recal_policy_consumer import consume_reply

CONTRACT = 'recal-product-v1'
IDENTITY = ('aux_db','aux_raw_left','aux_raw_right','hp_volume','gain_q12','sample_rate_hz',
            'driver_sha256','bit_sha256','hwh_sha256','helper_sha256')
CAPS = ('buttons','indicator','nonintrusive_events','abort_mutes','prepared_capture','bounded_run','mode_readback')
PROMPTS = {
    'uncalibrated': ('white','slow/1','待标定：移动设备后按CAL'),
    'preparing': ('yellow','4','正在准备，请稍候'),
    'speaking': ('cyan','blink/2','准备完成，请自然讲话'),
    'quiet': ('blue','blink/3','请保持安静，系统可能播放测试声'),
    'capturing': ('blue','blink/3','正在采样，请保持安静'),
    'fitting': ('yellow','4','正在计算，STOP仍可停止'),
    'validating': ('yellow','4','正在独立验证，请保持安静'),
    'installing': ('yellow','4','正在安装已验证模型'),
    'ready': ('green','steady','验收通过，按START开始扩声'),
    'running': ('green','steady','扩声运行中，STOP停止'),
    'ended': ('green','slow','本次扩声已结束，按START重新开始'),
    'cancelled': ('white','slow/1','已取消并静音，按CAL重新标定'),
    'inconclusive': ('yellow','error/2','无法评价并已静音，按CAL重新标定'),
    'failed': ('red','error','未通过并已静音，按CAL重新标定'),
    'protected': ('red','fast','保护停声，排除过载后按CAL重新标定'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def contained(path, root):
    path=Path(path).resolve();root=Path(root).resolve()
    try: path.relative_to(root)
    except ValueError: raise ValueError('artifact escaped run directory')
    return path


class Failure(Exception):
    def __init__(self, outcome, reason):
        self.outcome=outcome;super().__init__(reason)


class ModelStore:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.pointer=self.root/'current.json'

    def invalidate(self, scene, reason):
        write_json(self.pointer,dict(eligible=False,scene_id=scene,reason=reason))

    def stage(self, path, expected, scene, identity, validation, simulation=False):
        from residual_tools import load_candidate
        import numpy as np
        if sha(path)!=expected: raise Failure('model_rejected','候选文件身份不一致')
        try: model,q=load_candidate(path,scene,identity['hp_volume'],identity['sample_rate_hz'])
        except (ValueError,KeyError): raise Failure('model_rejected','候选模型格式或Q20不兼容')
        if model.get('simulation') is True and not simulation:
            raise Failure('model_rejected','模拟模型不得安装到实体产品')
        if model['taps']!=512: raise Failure('model_rejected','模型抽头数不兼容')
        qsha=hashlib.sha256(np.asarray(q,dtype='<i4').tobytes()).hexdigest()
        folder=self.root/'archive'/(scene+'-'+expected)
        folder.mkdir(parents=True,exist_ok=False)
        target=folder/'model.json'
        with target.open('wb') as f:
            f.write(Path(path).read_bytes());f.flush();os.fsync(f.fileno())
        bundle=dict(eligible=True,scene_id=scene,model_path=str(target.resolve()),model_sha256=expected,
                    coefficients_sha256=qsha,identity=identity,validation=validation)
        write_json(folder/'bundle.json',bundle)
        return bundle

    def commit(self, bundle):
        if sha(bundle['model_path'])!=bundle['model_sha256']:
            raise Failure('model_rejected','安装过程模型字节改变')
        write_json(self.pointer,bundle)  # One atomic pointer: model/config never half-update.


class Calculator:
    """B runs in a killable process, never on the button/stop polling thread."""
    def __init__(self, module, folder, module_dir=None):
        self.module=module;self.folder=Path(folder);self.process=None;self.lock=threading.Lock()
        self.module_dir=Path(module_dir) if module_dir else Path(__file__).resolve().parent

    def evaluate(self, request, cancel):
        request_path=self.folder/(request['request_id']+'-request.json')
        reply_path=self.folder/(request['request_id']+'-reply.json')
        write_json(request_path,request)
        with self.lock:
            if cancel.is_set(): return {}
            log=(self.folder/(request['request_id']+'-worker.txt')).open('wb')
            try:
                self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),
                    '--algorithm-worker',self.module,str(request_path),str(reply_path),str(self.module_dir)],stdout=log,stderr=log)
            finally: log.close()
            process=self.process
        deadline=time.monotonic()+float(request.get('compute_timeout_seconds',120))
        while process.poll() is None:
            if cancel.wait(.02) or time.monotonic()>deadline:
                process.terminate();process.wait(timeout=2)
                raise Failure('hardware_error','计算已停止或超时')
        with self.lock:
            if self.process is process: self.process=None
        if process.returncode or not reply_path.is_file():
            raise Failure('model_rejected','数值接口未返回有效结果')
        return json.loads(reply_path.read_text(encoding='utf-8'))

    def cancel(self):
        with self.lock:
            if self.process and self.process.poll() is None: self.process.terminate()


class Product:
    def __init__(self, hardware, config, state_dir, calculator=None, clock=time.monotonic):
        initial_mute=hardware.mute()  # First action, even if persistence later fails.
        self.hw=hardware;self.cfg=config;self.root=Path(state_dir);self.root.mkdir(parents=True,exist_ok=True)
        self.clock=clock;self.store=ModelStore(self.root/'models');self.results=queue.Queue()
        self.calculator=calculator or Calculator(config['algorithm_module'],self.root/'compute',config.get('package_dir'))
        self.cancel=threading.Event();self.epoch=0;self.pending=None;self.mode='muted'
        self.scene=uuid.uuid4().hex;self.run_dir=None;self.training=[];self.validation=[]
        self.bundle=None;self.candidate=None;self.attempt=0;self.cue_end=0;self.quiet_deadline=None
        self.state='uncalibrated';self.outcome=None;self.reason='';self.events=[];self.identity=None
        self.listening=[];self.run_result=None;self.fatal=False
        self.input_records=[]
        self.capture_history=[]
        self.hardware_receipts=[]
        self.algorithm_receipts=[];self.cause=None
        self.job_deadline=None
        self.gain_scope='runtime'
        self.store.invalidate(self.scene,'boot_requires_calibration')
        try:
            self._muted(initial_mute)
            if set(config['expected_identity'])!=set(IDENTITY):
                raise Failure('hardware_error','部署身份白名单不完整')
            caps=self.hw.capabilities()
            if caps.get('contract')!=CONTRACT or not all(caps.get(k) is True for k in CAPS):
                raise Failure('hardware_error','实体按键/提示/停止接口尚不可用')
            from residual_tools import load_candidate  # Resolve dependencies before asking for speech.
            if not callable(getattr(importlib.import_module(config['algorithm_module']),'evaluate',None)):
                raise Failure('hardware_error','数值接口尚不可用')
            attempts=config['attempts']
            if not 1<=len(attempts)<=3 or not all('training' in p and 'validation' in p for p in attempts):
                raise Failure('model_rejected','缺少B批准的有界策略')
            if not 0<float(config['run_seconds'])<=60 or not 0<=float(config['quiet_seconds'])<=30:
                raise Failure('model_rejected','时限策略无效')
            self._identity(self.hw.poll()['identity'])
            self._state('uncalibrated')
        except Exception as exc:
            self.fatal=True;self.fail(exc)

    def _muted(self, result):
        if result.get('ok') is not True or result.get('muted') is not True:
            self.fatal=True;raise Failure('hardware_error','硬件未确认静音，禁止启动')
        self.mode='muted'

    def _identity(self, actual):
        if any(k not in actual for k in IDENTITY): raise Failure('hardware_error','实际配置回读不完整')
        for key in IDENTITY:
            value=actual[key]
            if key.endswith('sha256') and (not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value)):
                raise Failure('hardware_error','硬件身份格式错误:'+key)
            if key=='gain_q12':
                allowed=self.cfg.get('phase_gain_q12',{}).get(self.gain_scope,[self.cfg['expected_identity'][key]])
                if type(value) is not int or value not in allowed:
                    raise Failure('hardware_error','阶段数字增益回读不符')
            elif key in self.cfg['expected_identity'] and value!=self.cfg['expected_identity'][key]:
                raise Failure('hardware_error','硬件身份混搭或配置不符:'+key)
        if self.identity is not None and any(actual[k]!=self.identity[k] for k in IDENTITY if k!='gain_q12'):
            raise Failure('hardware_error','标定后配置发生变化，请重新标定')
        self.identity={k:actual[k] for k in IDENTITY}

    def checkpoint(self):
        status=dict(contract=CONTRACT,simulation=self.cfg.get('simulation',False),scene_id=self.scene,
            package_manifest_sha256=self.cfg.get('package_manifest_sha256'),
            runtime_identity=self.cfg['expected_identity'],gain_scope=self.gain_scope,
            state=self.state,outcome=self.outcome,reason=self.reason,identity=self.identity,
            effective_mode=self.mode,attempt=self.attempt,training=self.training,validation=self.validation,
            bundle=self.bundle,run=self.run_result,listening=self.listening,events=self.events,
            candidate=self.candidate,capture_history=self.capture_history,
            hardware_receipts=self.hardware_receipts,
            algorithm_receipts=self.algorithm_receipts,cause=self.cause,
            waveform_policy='PCM stays on board; file paths and original hashes retained',hardware_error_latched=self.fatal)
        write_json(self.root/'status.json',status)
        if self.run_dir: write_json(self.run_dir/'result.json',status)

    def _state(self, state):
        self.state=state;self.events.append(dict(state=state,effective_mode=self.mode,time_monotonic=self.clock()))
        color,pattern,text=PROMPTS[state]
        if state in ('failed','protected','inconclusive'):
            pattern={'data_insufficient':'error/2','model_rejected':'error/3','input_overload':'error/4',
                     'hardware_error':'error/5','protected':'error/6','measurement_inapplicable':'error/7'}.get(self.outcome,'error/5')
            text={'data_insufficient':'无法评价：保持安静后按CAL重试',
                  'measurement_inapplicable':'本次条件无法评价：已静音，按CAL重标定；仍相同请联系维护',
                  'model_rejected':'本次模型未通过：保持静音，按CAL重试',
                  'input_overload':'输入过载：先停止讲话，按CAL重新检查，勿提高音量',
                  'hardware_error':'设备异常：保持静音，按CAL重试，仍失败联系维护',
                  'protected':'保护停声：保持静音，按CAL重新检查'}.get(self.outcome,text)
            if self.fatal: text='设备异常：保持静音，请联系维护；当前不能启动'
        answer=self.hw.indicate(dict(state=state,color=color,pattern=pattern,text=text,mode=self.mode))
        if answer.get('ok') is not True: raise Failure('hardware_error','实体提示不可用')
        self.checkpoint()

    def fail(self, exc):
        self.cancel.set();self.epoch+=1;self.pending=None;self.quiet_deadline=None
        self.calculator.cancel()
        try: self._abort()
        except Exception: self.fatal=True
        self.outcome=exc.outcome if isinstance(exc,Failure) else 'hardware_error'
        self.reason=str(exc);self.store.invalidate(self.scene,self.outcome)
        self.state=('protected' if self.outcome in ('input_overload','protected') else
                    'inconclusive' if self.outcome in ('data_insufficient','measurement_inapplicable') else 'failed')
        try: self._state(self.state)
        except Exception: self.checkpoint()

    def stop(self, cancelled=True, record=True):
        was_running=self.state=='running'
        self.cancel.set();self.epoch+=1;self.pending=None;self.quiet_deadline=None;self.calculator.cancel()
        self._abort()
        if not was_running: self.store.invalidate(self.scene,'cancelled')
        if not record: return
        self.outcome='user_cancelled';self.reason='用户停止，未自动重启'
        self._state('ended' if was_running else 'cancelled')

    def _abort(self):
        result=self.hw.abort();self._muted(result)
        if result.get('quiescent') is not True:
            self.fatal=True;raise Failure('hardware_error','硬件未确认旧任务结束，禁止启动新任务')

    def event(self, kind):
        try:
            if kind in ('stop','cancel'): self.stop();return
            if self.fatal: return
            if kind=='recalibrate':
                self.stop(record=self.state not in ('uncalibrated','ready','ended','failed','protected','cancelled','inconclusive'))
                self.scene=uuid.uuid4().hex;self.identity=None
                self.store.invalidate(self.scene,'scene_changed')
                self.gain_scope='prepare'
                self._identity(self.hw.poll()['identity'])
                self.run_dir=self.root/'runs'/self.scene;self.run_dir.mkdir(parents=True)
                self.training=[];self.validation=[];self.bundle=None;self.candidate=None
                self.input_records=[]
                self.capture_history=[];self.events=[];self.listening=[]
                self.hardware_receipts=[]
                self.algorithm_receipts=[];self.cause=None
                self.attempt=0;self.cue_end=0;self.outcome=None;self.reason='';self.run_result=None
                self.cancel=threading.Event();self._state('preparing');self._hw('prepare',phase='input')
            elif kind=='start' and self.state in ('ready','ended') and self.bundle:
                current=json.loads(self.store.pointer.read_text(encoding='utf-8'))
                if not current.get('eligible') or current['scene_id']!=self.scene:
                    raise Failure('model_rejected','当前场景无有效模型')
                self.gain_scope='runtime';self._identity(self.hw.poll()['identity']);self.cancel=threading.Event()
                self.outcome=None;self._state('running')
                self._hw('run',model_path=self.bundle['model_path'],model_sha256=self.bundle['model_sha256'],
                    coefficients_sha256=self.bundle['coefficients_sha256'],seconds=self.cfg['run_seconds'])
            elif kind=='confirm_quiet' and self.state=='quiet' and self.quiet_deadline is not None:
                self.quiet_deadline=self.clock()
        except Exception as exc: self.fail(exc)

    def _submit(self, kind, request, function):
        if self.pending: raise Failure('hardware_error','硬件任务尚未完成')
        epoch=self.epoch;cancel=self.cancel;self.pending=(kind,request)
        self.job_deadline=self.clock()+float(self.cfg.get('io_timeout_seconds',30) if kind=='hw' else self.cfg.get('compute_timeout_seconds',120))+1
        def worker():
            try: value=function(request,cancel);error=None
            except Exception as exc: value=None;error=exc
            self.results.put((epoch,kind,request,value,error))
        threading.Thread(target=worker,daemon=True).start()

    def _request(self, **extra):
        return dict(contract=CONTRACT,request_id=uuid.uuid4().hex,scene_id=self.scene,
            run_dir=str(self.run_dir.resolve()),identity=self.identity,attempt=self.attempt,
            plan=self.cfg['attempts'][self.attempt],**extra)

    def _hw(self, op, **extra):
        self.gain_scope=op;self._submit('hw',self._request(op=op,**extra),self.hw.perform)
    def _alg(self, phase):
        request=self._request(phase=phase,training=self.training,validation=self.validation,
            input=self.input_records,
            model_path=self.candidate['path'] if self.candidate else None,
            model_sha256=self.candidate['sha256'] if self.candidate else None,
            compute_timeout_seconds=self.cfg.get('compute_timeout_seconds',120))
        self._submit('algorithm',request,self.calculator.evaluate)

    def _envelope(self, req, reply):
        if any(reply.get(k)!=req[k] for k in ('contract','request_id','scene_id')):
            raise Failure('hardware_error','返回值的任务/场景身份不匹配')

    def _captures(self, reply):
        records=reply.get('captures')
        if not isinstance(records,list) or not records: raise Failure('data_insufficient','没有有效捕获')
        ids=[]
        for item in records:
            path=contained(item['path'],self.run_dir)
            if sha(path)!=item['sha256']: raise Failure('hardware_error','捕获文件身份改变')
            if type(item['first_frame']) is not int or type(item['end_frame']) is not int or item['first_frame']<0 or item['end_frame']<=item['first_frame']:
                raise Failure('data_insufficient','有效测量窗未知')
            source=item.get('source_sha256')
            if not isinstance(source,str) or len(source)!=64 or any(c not in '0123456789abcdef' for c in source) or not item.get('capture_id'):
                raise Failure('data_insufficient','捕获来源身份缺失')
            ids.append(item['capture_id'])
        if len(set(ids))!=len(ids): raise Failure('data_insufficient','捕获身份重复')
        return records

    def _hw_done(self, req, reply):
        self._envelope(req,reply)
        self.hardware_receipts.append(dict(request=req,reply=reply))
        self.checkpoint()  # Preserve protection/failure metadata before rejecting it.
        self._identity(reply['identity'])
        if reply.get('input_clip'): raise Failure('input_overload','输入过载，已保护停声')
        if reply.get('status')=='protected': raise Failure('protected','硬件保护停声')
        if reply.get('ok') is not True or reply.get('status')!='completed':
            raise Failure('hardware_error',reply.get('reason','硬件操作未完成'))
        op=req['op']
        if op=='prepare':
            phase=req['phase']
            if phase=='input' and self.cfg.get('cue') and not self.cue_end: self._hw('cue');return
            if phase=='input':
                self._state('speaking');self._hw('input',not_before_frame=self.cue_end)
            else:
                self._state('capturing' if phase=='training' else 'validating')
                self._hw(phase)
        elif op=='cue':
            if type(reply.get('end_frame')) is not int or type(reply.get('tail_frames')) is not int or reply['end_frame']<=0 or reply['tail_frames']<0:
                raise Failure('hardware_error','提示音尾声帧域未知')
            self.cue_end=reply['end_frame']+reply['tail_frames']
            self._hw('prepare',phase='input',not_before_frame=self.cue_end)
        elif op=='input':
            records=self._captures(reply)
            if type(reply.get('valid_first_frame')) is not int or reply['valid_first_frame']<self.cue_end or any(x['first_frame']<self.cue_end for x in records):
                raise Failure('data_insufficient','讲话窗口混入提示音或尾声')
            self.training=[];self.validation=[];self.input_records=records
            self._state('quiet');self._alg('input')
        elif op=='training':
            self.training=self._captures(reply)
            self.capture_history.append(dict(stage=op,attempt=self.attempt,captures=self.training))
            self._state('fitting');self._alg('fit')
        elif op=='validation':
            self.validation=self._captures(reply)
            self.capture_history.append(dict(stage=op,attempt=self.attempt,captures=self.validation))
            for field in ('capture_id','source_sha256'):
                if {r[field] for r in self.training}&{r[field] for r in self.validation}:
                    raise Failure('data_insufficient','独立验证重用了训练数据/声源')
            self._state('validating');self._alg('validate')
        elif op=='install':
            for key in ('model_sha256','coefficients_sha256'):
                if reply.get(key)!=self.bundle[key]: raise Failure('model_rejected','安装实际身份不一致')
            self._muted(self.hw.mute());self.gain_scope='runtime';self._identity(self.hw.poll()['identity'])
            self.store.commit(self.bundle)
            self.outcome='valid_pass';self.reason='独立验证与安装通过';self._state('ready')
        elif op=='run':
            if any(reply.get(k)!=self.bundle[k] for k in ('model_sha256','coefficients_sha256')):
                raise Failure('hardware_error','运行实际模型不符')
            elapsed=reply.get('elapsed_seconds')
            if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or not 0<elapsed<=float(req['seconds'])+.1:
                raise Failure('hardware_error','实际运行时长未知或越界')
            if abs(elapsed-float(req['seconds']))>.1:
                raise Failure('data_insufficient','实际运行提前结束，未达到本次时限；没有自动拼段')
            self._muted(self.hw.mute());self.gain_scope='runtime';self.run_result=reply;self.outcome='completed'
            self.reason='单次运行已真实结束，未拼段重启';self._state('ended')

    def _algorithm_done(self, req, reply):
        self._envelope(req,reply)
        self.algorithm_receipts.append(dict(request=req,reply=reply));self.checkpoint()
        following=self.cfg['attempts'][self.attempt+1] if self.attempt+1<len(self.cfg['attempts']) else {}
        decision,self.cause,reason=consume_reply(reply,req['phase'],
            next_excitation=following.get('training',{}).get('excitation'),attempt=self.attempt)
        if self.cause=='HARDWARE_ERROR': self.fatal=True
        if not reply.get('reason'): raise Failure('model_rejected','数值判断缺少依据')
        if decision=='retry':
            if self.attempt+1>=len(self.cfg['attempts']): raise Failure('data_insufficient','已达到预定重试上限')
            self.attempt+=1;self.training=[];self.validation=[];self.candidate=None
            if req['phase']=='input':
                self._state('preparing');self._hw('prepare',phase='input')
            else:
                self._state('quiet');self.quiet_deadline=self.clock()+self.cfg['quiet_seconds']
            return
        if decision!='valid_pass':
            raise Failure(decision if decision in ('data_insufficient','model_rejected','measurement_inapplicable',
                'hardware_error','input_overload') else 'data_insufficient',reason)
        if req['phase']=='input':
            self.quiet_deadline=self.clock()+self.cfg['quiet_seconds']
        elif req['phase']=='fit':
            path=contained(reply['model_path'],self.run_dir)
            if sha(path)!=reply['model_sha256']: raise Failure('model_rejected','拟合模型哈希不一致')
            self.candidate=dict(path=str(path),sha256=reply['model_sha256'])
            self._state('validating');self._hw('prepare',phase='validation')
        else:
            ids=[r['capture_id'] for r in self.validation]
            if reply.get('qualifies_cancellation') is not True or reply.get('model_sha256')!=self.candidate['sha256'] or reply.get('validation_ids')!=ids or not reply.get('evidence'):
                raise Failure('data_insufficient','独立效果判断/验证身份不足，未启用候选')
            self.bundle=self.store.stage(self.candidate['path'],self.candidate['sha256'],self.scene,self.cfg['expected_identity'],reply,
                                         simulation=self.cfg.get('simulation',False))
            self._state('installing');self._hw('install',**{k:self.bundle[k] for k in ('model_path','model_sha256','coefficients_sha256')})

    def tick(self):
        try:
            poll=self.hw.poll()
            if poll.get('ok') is not True: raise Failure('hardware_error','硬件状态读取失败')
            events=poll.get('events',[])
            if any(e['kind'] in ('stop','cancel') for e in events): self.event('stop');return
            if self.fatal: return
            if self.state in ('failed','protected','cancelled','inconclusive'):
                for event in events: self.event(event['kind'])
                return
            if self.pending and self.clock()>self.job_deadline: raise Failure('hardware_error','阶段超时，已停止')
            if poll.get('protected'):
                raise Failure('input_overload' if poll.get('input_clip') else 'protected','硬件保护停声')
            self._identity(poll['identity'])
            mode=poll.get('effective_mode')
            if mode not in ('muted','cancel','bypass'): raise Failure('hardware_error','实际模式未知')
            if mode!=self.mode:
                self.mode=mode;self._state(self.state)
            if self.state=='running' and self.bundle and any(poll.get(k)!=self.bundle[k] for k in ('model_sha256','coefficients_sha256')):
                raise Failure('hardware_error','运行模型实际回读改变')
            for event in events: self.event(event['kind'])
            while True:
                try: epoch,kind,req,reply,error=self.results.get_nowait()
                except queue.Empty: break
                if epoch!=self.epoch: continue
                self.pending=None
                if error: raise error
                if kind=='hw': self._hw_done(req,reply)
                else: self._algorithm_done(req,reply)
            if self.state=='quiet' and self.quiet_deadline is not None and self.clock()>=self.quiet_deadline and not self.pending:
                self.quiet_deadline=None;self._hw('prepare',phase='training')
        except Exception as exc: self.fail(exc)

    def record_listening(self, words, provenance):
        self.listening.append(dict(words=str(words),provenance=str(provenance),scene_id=self.scene,
                                   scope='qualitative only; never used for automatic pass'))
        self.checkpoint()


def verify_package(base):
    base=Path(base).resolve();manifest=json.loads((base/'product-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('contract')!=CONTRACT: raise ValueError('unsupported product contract')
    for name,digest in manifest['hashes'].items():
        if sha(contained(base/name,base))!=digest: raise ValueError('package identity mismatch: '+name)
    return manifest


def export_return(state, output, package_sha256):
    """One return for all layouts: original non-speech captures, JSON, no human PCM."""
    import zipfile
    state=Path(state).resolve();output=Path(output)
    if output.exists(): raise ValueError('return file already exists; preserve prior evidence')
    records=[];payload={};artifacts=[]
    for path in sorted((state/'runs').glob('*/result.json')):
        record=json.loads(path.read_text(encoding='utf-8'));records.append(record)
        payload['results/'+path.parent.name+'.json']=path.read_bytes()
        captures=[c for h in record.get('capture_history',[]) for c in h['captures']]
        captures+=record.get('training',[])+record.get('validation',[])
        for item in captures:
            # Unknown provenance is not permission to transmit audio.
            if item.get('content_kind') not in ('onboard_excitation','software_fixture'): continue
            source=contained(item['path'],state)
            if sha(source)!=item['sha256']: raise ValueError('saved capture changed; original retained')
            name='captures/'+source.relative_to(state).as_posix()
            payload[name]=source.read_bytes()
            artifacts.append(dict(original_path=str(source),payload_path=name,sha256=item['sha256']))
        model=record.get('candidate')
        if model:
            source=contained(model['path'],state)
            if sha(source)!=model['sha256']: raise ValueError('candidate changed; original retained')
            name='models/'+path.parent.name+'/'+source.name;payload[name]=source.read_bytes()
            artifacts.append(dict(original_path=str(source),payload_path=name,sha256=model['sha256']))
    for path in sorted((state/'compute').glob('*-reply.json')):
        payload['algorithm/'+path.name]=path.read_bytes()
    for path in sorted((state/'compute').glob('*-request.json')):
        request=json.loads(path.read_text(encoding='utf-8'))
        if request.get('phase')!='input': payload['algorithm/'+path.name]=path.read_bytes()
    summary=dict(contract=CONTRACT,package_manifest_sha256=package_sha256,records=records,artifacts=artifacts,
        scope='structured record and original non-speech captures; no ASG/effect pass inferred',
        private_policy='human input PCM omitted; unknown capture provenance omitted; originals remain on board')
    payload['summary.json']=(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    inventory={name:hashlib.sha256(data).hexdigest() for name,data in payload.items()}
    payload['return-manifest.json']=json.dumps(dict(contract=CONTRACT,sha256=inventory)).encode('utf-8')
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as archive:
        for name,data in payload.items(): archive.writestr(name,data)
    return dict(path=str(output),sha256=sha(output),records=len(records))


def review_return(path, package_sha256):
    import zipfile
    with zipfile.ZipFile(path) as archive:
        manifest=json.loads(archive.read('return-manifest.json'))
        if manifest.get('contract')!=CONTRACT or set(archive.namelist())!=set(manifest['sha256'])|{'return-manifest.json'}:
            raise ValueError('return inventory mismatch')
        for name,digest in manifest['sha256'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest: raise ValueError('return payload identity mismatch')
        summary=json.loads(archive.read('summary.json'))
    if summary['package_manifest_sha256']!=package_sha256: raise ValueError('return belongs to a different product package')
    issues=[];layouts=[]
    for r in summary['records']:
        if r.get('package_manifest_sha256')!=package_sha256: issues.append(r['scene_id']+':package unknown/mismatch')
        modes=sorted({e.get('effective_mode') for e in r.get('events',[]) if e.get('state')=='running' and e.get('effective_mode') in ('bypass','cancel')})
        validation=r.get('bundle',{}).get('validation',{}) if r.get('bundle') else {}
        layouts.append(dict(scene_id=r['scene_id'],state=r['state'],outcome=r.get('outcome'),
            observed_modes=modes,numeric_validation=validation,listening=r.get('listening',[]),
            raw_paths_retained=[c['path'] for c in r.get('training',[])+r.get('validation',[])]))
    return dict(identity_ok=not issues,issues=issues,layouts=layouts,layout_count=len(layouts),
        scope='independent return identity/scope audit; numerical re-analysis uses included originals with the frozen B interface',
        effect_pass_inferred=False,hardware_operations=0)


@contextlib.contextmanager
def instance_lock(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with (folder/'service.lock').open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            f.seek(0);f.write(b'0');f.flush();f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--algorithm-worker':
        module,src,dst,folder=sys.argv[2:6]
        sys.path.insert(0,folder)
        write_json(dst,importlib.import_module(module).evaluate(json.loads(Path(src).read_text(encoding='utf-8'))));return 0
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--state-dir',type=Path);p.add_argument('--check',action='store_true');p.add_argument('--simulate',action='store_true');p.add_argument('--once',action='store_true')
    p.add_argument('--export',type=Path);p.add_argument('--review-return',type=Path)
    args=p.parse_args();manifest=verify_package(args.base)
    sys.path.insert(0,str(args.base.resolve()))
    package_sha=sha(args.base/'product-manifest.json')
    if args.export:
        if args.state_dir is None: raise ValueError('export requires the installed state directory')
        print(json.dumps(export_return(args.state_dir,args.export,package_sha)));return 0
    if args.review_return:
        result=review_return(args.review_return,package_sha);print(json.dumps(result,ensure_ascii=False));return 0 if result['identity_ok'] else 2
    if args.check:
        print(json.dumps(dict(identity_ok=True,deployment_ready=manifest['deployment_ready'],missing=manifest['missing'])));return 0 if manifest['deployment_ready'] else 2
    if not args.simulate and not manifest['deployment_ready']: raise ValueError('physical adapters not ready: '+','.join(manifest['missing']))
    if manifest['simulation']!=args.simulate: raise ValueError('simulation/physical package mismatch')
    config=json.loads((args.base/'product-config.json').read_text(encoding='utf-8'))
    config['package_manifest_sha256']=package_sha
    config['package_dir']=str(args.base.resolve())
    module=importlib.import_module(config['hardware_module']);hw=module.create_product(config)
    state=args.state_dir or args.base/'state'
    with instance_lock(state):
        app=Product(hw,config,state)
        shutdown=threading.Event()
        def quit_service(*_):
            app.event('stop');shutdown.set()
        for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,quit_service)
        if args.simulate: app.event('recalibrate')
        try:
            while not shutdown.is_set():
                app.tick()
                if args.simulate and args.once and app.state in ('ready','failed','protected','cancelled','inconclusive'):
                    print(json.dumps(dict(state=app.state,outcome=app.outcome,reason=app.reason),ensure_ascii=False));return 0 if app.state=='ready' else 2
                time.sleep(.02)
            return 0
        finally: app.stop()


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print('PRODUCT_STOPPED '+str(exc),file=sys.stderr);raise SystemExit(2)
