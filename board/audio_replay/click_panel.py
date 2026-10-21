"""A's local-LAN operator panel. Startup never configures audio or plays sound."""
import argparse
from collections import deque
import contextlib
import fcntl
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import urlparse, parse_qs

from replay_session import HERE, record_source
from sweep_session import prepare_sweep, run_sweep

LOCK = threading.RLock()
WAKE = threading.Condition(LOCK)
STATE = dict(busy=False, task='待机，未发声', waiting=None, result=None, stopped=False, error=None)
LOG = deque(maxlen=70)
PLAN = None
REPLY = None
TOKEN = ''
ORIGIN = ''


def ask(prompt):
    global REPLY
    if 'RECORD' in prompt:
        options = [('RECORD', '开始录音 · 2秒'), ('STOP', '取消')]
        confirm = '我已关闭音响电源，手机在原位置播放语音。'
    elif 'READY' in prompt:
        options = [('READY', '现场已就绪，进入本批'), ('STOP', '取消')]
        confirm = '手机已停止外放，音响已供电且可立即断电；夹具未动，无其他音频程序运行，同意板卡本地采样。'
    elif 'START' in prompt:
        options = [('START', '开始本项'), ('STOP', '结束本批')]
        confirm = '我已准备听，音响电源在手边。'
    elif '听感' in prompt:
        options = [('0', '0 · 没听到音响'), ('1', '1 · 语音清楚，结束安静'),
                   ('2', '2 · 杂音 / 失真'), ('3', '3 · 啸叫 / 增长'), ('4', '4 · 结束仍响')]
        confirm = ''
    else:
        raise RuntimeError('Unknown operator prompt; stopped without guessing: '+prompt)
    with WAKE:
        if STATE['stopped']:
            return 'STOP'
        REPLY = None
        STATE['waiting'] = dict(id=secrets.token_hex(12), prompt=prompt, options=options, confirm=confirm)
        if not WAKE.wait_for(lambda: REPLY is not None or STATE['stopped'], timeout=900):
            STATE['stopped'] = True
        value = REPLY if not STATE['stopped'] else 'STOP'
        STATE['waiting'] = None
        REPLY = None
        return value


class LogStream(io.TextIOBase):
    def __init__(self):
        self.pending = ''

    def write(self, text):
        with LOCK:
            self.pending += text
            while '\n' in self.pending:
                line, self.pending = self.pending.split('\n', 1)
                if line.strip():
                    LOG.append(line)
        return len(text)

    def flush(self):
        pass


def work(action):
    global PLAN
    try:
        with contextlib.redirect_stdout(LogStream()):
            if action == 'plan':
                PLAN = prepare_sweep()
                if PLAN is None:
                    raise RuntimeError('静默选档未通过。日志有原因和摘要路径；请交给A处理。')
            elif action == 'record':
                record_source(ask=ask)
            elif action == 'run':
                result = run_sweep(PLAN, ask=ask)
                with LOCK:
                    STATE['result'] = result
            else:
                raise ValueError('unknown action')
        with LOCK:
            STATE['task'] = '本步已结束，音频任务未在运行'
    except (Exception, KeyboardInterrupt) as exc:
        with LOCK:
            STATE['error'] = type(exc).__name__+': '+str(exc)
            LOG.append(STATE['error'])
            STATE['task'] = '已停止，请保留页面交给A处理'
    finally:
        with WAKE:
            STATE['waiting'] = None
            STATE['busy'] = False
            WAKE.notify_all()


def snapshot():
    with LOCK:
        planned = PLAN is not None and PLAN.is_file()
        plan_info = json.loads(PLAN.read_text()) if planned else {}
        return {**STATE, 'log': list(LOG), 'source_exists': (HERE/'source.wav').is_file(),
                'plan_ready': plan_info.get('status') == 'planned',
                'levels': [p['gain_db'] for p in plan_info.get('plan', {}).get('points', [])],
                'summary_path': str(PLAN) if PLAN else None}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, data, content='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', content)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if self.client_address[0] not in ('192.168.2.1', '127.0.0.1'):
            return False
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            value = cookie['shengdi'].value
        except (KeyError, ValueError):
            return False
        return secrets.compare_digest(value, TOKEN)

    def do_GET(self):
        url = urlparse(self.path)
        ticket = parse_qs(url.query).get('ticket', [''])[0]
        if url.path == '/' and ticket and self.client_address[0] in ('192.168.2.1', '127.0.0.1') and secrets.compare_digest(ticket, TOKEN):
            self.send_response(303)
            self.send_header('Set-Cookie', 'shengdi='+TOKEN+'; HttpOnly; SameSite=Strict; Path=/')
            self.send_header('Location', '/')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        if not self.authorized():
            self.send(403, '请从A提供的现场链接打开。'.encode(), 'text/plain; charset=utf-8')
            return
        if url.path == '/':
            self.send(200, (HERE/'click-panel.html').read_bytes(), 'text/html; charset=utf-8')
        elif url.path == '/state':
            self.send(200, json.dumps(snapshot(), ensure_ascii=False).encode())
        else:
            self.send(404, b'{}')

    def do_POST(self):
        global REPLY
        if not self.authorized() or self.headers.get('Origin') != ORIGIN:
            self.send(403, b'{}')
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('invalid request length')
            data = json.loads(self.rfile.read(length))
            with WAKE:
                if self.path == '/answer':
                    waiting = STATE['waiting']
                    if (not waiting or data.get('id') != waiting['id'] or REPLY is not None or
                            data.get('value') not in [o[0] for o in waiting['options']]):
                        raise ValueError('提示已更新，请用当前按钮')
                    if waiting['confirm'] and data.get('value') != 'STOP' and data.get('confirmed') is not True:
                        raise ValueError('请先确认现场条件')
                    REPLY = data['value']
                    WAKE.notify_all()
                elif self.path == '/stop':
                    STATE['stopped'] = True
                    WAKE.notify_all()
                elif self.path == '/action':
                    action = data.get('action')
                    if STATE['error']:
                        raise ValueError('本步失败，请等待A处理，无需重复点击')
                    if STATE['busy'] or action not in ('plan', 'record', 'run'):
                        raise ValueError('已有任务运行或请求无效')
                    current = snapshot()
                    if action != 'plan' and not current['plan_ready']:
                        raise ValueError('请先由A完成静默选档')
                    if action == 'run' and not current['source_exists']:
                        raise ValueError('请先录音')
                    if action == 'record' and data.get('confirmed') is not True:
                        raise ValueError('录音配置前请先确认音响断电')
                    STATE.update(busy=True, stopped=False, waiting=None, result=None,
                                 task={'plan':'静默分析，不发声','record':'准备录音，音响保持断电','run':'本批运行，按提示操作'}[action])
                    threading.Thread(target=work, args=(action,), daemon=True).start()
                else:
                    raise ValueError('invalid route')
            self.send(200, b'{"ok":true}')
        except Exception as exc:
            self.send(409, json.dumps({'error':str(exc)}, ensure_ascii=False).encode())


def main():
    global TOKEN, ORIGIN, PLAN
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    # Exclusion lasts for this server, including any audio worker thread.
    lockfile = open('/run/lock/shengdi-a-panel.lock', 'w')
    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    TOKEN = os.environ['SHENGDI_UI_TOKEN']
    if len(TOKEN) < 32:
        raise ValueError('session token too short')
    if args.plan:
        PLAN = Path(args.plan).resolve()
        if PLAN.parent.parent != (HERE/'replay_results').resolve():
            raise ValueError('plan must be a local replay summary')
        json.loads(PLAN.read_text())
    # Import only: reject the wrong runtime before exposing recording controls.
    from pynq.overlays.base import BaseOverlay
    import sys
    LOG.append('PYNQ runtime ready: '+sys.executable)
    ORIGIN = 'http://192.168.2.99:'+str(args.port)
    ThreadingHTTPServer(('192.168.2.99', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
