#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""group.py —— 三台电脑共用的 AI 群聊板（单文件，只用标准库）。

一台电脑当"群主"（`serve`，窗口别关），其余两台和所有 agent 都只是客户端。
消息按行追加进 JSONL；每条必须指名收件人；agent 只取"发给自己的新消息"。

快速上手（详见同目录 README.md）
    群主：  python group.py serve --port 8765 --token 你们定的口令
    其他人：set GROUP_URL=http://<群主IP>:8765
            set GROUP_TOKEN=你们定的口令
            set GROUP_ME=B1
            python group.py send --to A1 --text "三个文件拷好了，路径在 D:\\tmp"
            python group.py read

子命令
    serve    起群
    send     发一条（--to 必填：某人，或 all）
    read     取"上次读到之后、发给我的"消息，并推进游标
    watch    阻塞等新消息，有就打印并退出（适合挂成后台任务自动叫醒 agent）
    status   群在不在、有谁出现过、一共多少条
    check    自检：还差哪一步连不上
    ui       打印浏览器地址（人看群用）

环境变量
    GROUP_URL    群地址，如 http://192.168.1.23:8765
    GROUP_TOKEN  共享口令
    GROUP_ME     我是谁，如 B1 / C1 / A2
    GROUP_DATA   群主存消息的目录（默认 ~/.ai-group）
"""

import argparse
import json
import os
import sys
import socket
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=8))
HOME = os.path.join(os.path.expanduser("~"), ".ai-group")
MAX_TEXT = 8000

try:  # Windows 控制台默认 GBK，中文和 emoji 会炸
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass


# --------------------------------------------------------------------------- #
# 本机状态（游标）
# --------------------------------------------------------------------------- #


_STATE_DIR = None


def state_dir():
    """游标放哪。优先用户目录；被沙箱/权限挡住时退到当前目录、再退到临时目录。"""
    global _STATE_DIR
    if _STATE_DIR:
        return _STATE_DIR
    candidates = []
    env = os.environ.get("GROUP_STATE")
    if env:
        candidates.append(env)
    candidates += [
        os.path.join(os.path.expanduser("~"), ".ai-group"),
        os.path.join(os.getcwd(), ".ai-group-state"),
        os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "ai-group-state"),
    ]
    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".w")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            _STATE_DIR = cand
            return cand
        except Exception:
            continue
    _STATE_DIR = ""
    return ""


def _cursor_path(me):
    root = state_dir()
    if not root:
        return ""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in me)
    return os.path.join(root, "cursor-%s.json" % safe)


def load_cursor(me):
    path = _cursor_path(me)
    if not path:
        return 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return int(json.load(fh).get("last", 0))
    except Exception:
        return 0


def save_cursor(me, last):
    path = _cursor_path(me)
    if not path:
        return False
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"last": int(last)}, fh)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 客户端
# --------------------------------------------------------------------------- #


class GroupError(Exception):
    pass


def _base_url(args):
    url = (args.url or os.environ.get("GROUP_URL") or "").strip().rstrip("/")
    if not url:
        raise GroupError(
            "没有群地址。设置环境变量 GROUP_URL=http://<群主IP>:8765 ，或用 --url 传入。"
        )
    if not url.startswith("http"):
        url = "http://" + url
    return url


def _token(args):
    return (args.token or os.environ.get("GROUP_TOKEN") or "").strip()


def _me(args, required=True):
    me = (args.me or os.environ.get("GROUP_ME") or "").strip()
    if required and not me:
        raise GroupError("不知道我是谁。设置 GROUP_ME=B1，或用 --me 传入。")
    return me


def _request(url, token, payload=None, timeout=10, method=None):
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Group-Token"] = token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(
        url, data=data, headers=headers, method=method or ("POST" if data else "GET")
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
            detail = json.loads(body).get("error", "")
        except Exception:
            detail = body[:200]
        if exc.code == 401:
            raise GroupError("口令不对（GROUP_TOKEN 与群主不一致）。")
        raise GroupError("群主返回 %s：%s" % (exc.code, detail or "无详情"))
    except urllib.error.URLError as exc:
        raise GroupError(
            "连不上群 %s（%s）。常见原因：群主没开 serve、端口/IP 填错、"
            "防火墙拦了、没连同一个网络。" % (url, exc.reason)
        )
    except socket.timeout:
        raise GroupError("连群超时：%s" % url)


def api_send(args, text, to):
    base = _base_url(args)
    sender = _me(args)
    res = _request(
        base + "/api/send",
        _token(args),
        {"from": sender, "to": to, "text": text},
    )
    return res


def api_fetch(args, me, since, limit=200, include_self=False):
    base = _base_url(args)
    query = urllib.parse.urlencode(
        {
            "since": int(since),
            "me": me,
            "limit": int(limit),
            "include_self": "1" if include_self else "0",
        }
    )
    return _request("%s/api/messages?%s" % (base, query), _token(args))


def api_status(args):
    base = _base_url(args)
    me = _me(args, required=False)
    query = urllib.parse.urlencode({"me": me} if me else {})
    return _request("%s/api/status?%s" % (base, query), _token(args))


def fmt_time(ts):
    try:
        dt = datetime.fromisoformat(ts)
        return dt.astimezone(LOCAL_TZ).strftime("%m-%d %H:%M:%S")
    except Exception:
        return ts


def render(messages):
    out = []
    for m in messages:
        out.append("#%-4d %s  %s → %s" % (m["id"], fmt_time(m["ts"]), m["from"], m["to"]))
        for line in str(m["text"]).splitlines() or [""]:
            out.append("      " + line)
        out.append("")
    return "\n".join(out).rstrip()


# --------------------------------------------------------------------------- #
# 服务端
# --------------------------------------------------------------------------- #


class Store:
    def __init__(self, data_dir):
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(data_dir, "messages.jsonl")
        self.lock = threading.Lock()
        self.presence = {}
        self.last_id = 0
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.last_id = max(self.last_id, int(json.loads(line)["id"]))
                    except Exception:
                        continue

    def append(self, sender, to, text):
        now = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        with self.lock:
            self.last_id += 1
            rec = {"id": self.last_id, "ts": now, "from": sender, "to": to, "text": text}
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return rec

    def all(self):
        if not os.path.exists(self.path):
            return []
        recs = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except Exception:
                    continue
        return recs

    def touch(self, me):
        if me:
            with self.lock:
                self.presence[me] = time.time()


PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 群 —— 三个人 + 一堆 agent</title>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.55 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
       background:#14161a;color:#e6e8eb;height:100vh;display:flex;flex-direction:column}
  header{padding:10px 16px;background:#1b1e24;border-bottom:1px solid #2a2f38;
         display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  header b{color:#7cc4ff}
  .pill{padding:2px 8px;border-radius:99px;background:#23272f;color:#9aa4b2;font-size:12px}
  .live{background:#173322;color:#5ddc9a}
  main{flex:1;overflow-y:auto;padding:14px 16px}
  .msg{margin:0 0 12px;max-width:min(760px,92%)}
  .meta{font-size:12px;color:#7d8794;margin-bottom:2px}
  .meta .who{color:#9ad0ff;font-weight:600}
  .meta .to{color:#c7a6ff}
  .bubble{background:#1e232b;border:1px solid #2a3038;border-radius:10px;
          padding:8px 11px;white-space:pre-wrap;word-break:break-word}
  .msg.mine .bubble{background:#1d2b3a;border-color:#31506b}
  .msg.mine .meta .who{color:#ffd479}
  footer{padding:10px 12px;background:#1b1e24;border-top:1px solid #2a2f38}
  .row{display:flex;gap:8px;align-items:center}
  input,textarea,button,select{font:inherit;border-radius:8px;border:1px solid #313842;
       background:#161a20;color:#e6e8eb;padding:7px 9px}
  input[type=text]{width:130px}
  textarea{flex:1;resize:none;height:52px}
  button{background:#2563eb;border-color:#2563eb;color:#fff;cursor:pointer;padding:7px 14px}
  button:disabled{opacity:.5;cursor:default}
  .err{color:#ff7b72;font-size:12px;padding:4px 2px 0}
</style></head>
<body>
<header>
  <b>AI 群</b>
  <span class="pill live" id="live">连接中…</span>
  <span class="pill" id="count">0 条</span>
  <span class="pill" id="roster"></span>
</header>
<main id="log"></main>
<footer>
  <div class="row">
    <input type="text" id="me" placeholder="我是谁" title="例如 B1">
    <span style="color:#7d8794">→</span>
    <input type="text" id="to" placeholder="发给谁 / all" value="all">
    <textarea id="text" placeholder="说清楚：要什么、阻塞什么、怎么算完成（Enter 发送，Shift+Enter 换行）"></textarea>
    <button id="send">发送</button>
  </div>
  <div class="err" id="err"></div>
</footer>
<script>
const TOKEN = "__TOKEN__";
const log = document.getElementById('log');
const live = document.getElementById('live');
const errBox = document.getElementById('err');
const meEl = document.getElementById('me');
const toEl = document.getElementById('to');
const textEl = document.getElementById('text');
meEl.value = localStorage.getItem('group.me') || 'A1';
toEl.value = localStorage.getItem('group.to') || 'all';
let lastId = 0, ready = false;

function api(p){ return p + (p.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(TOKEN); }
function esc(s){ return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function addMsg(m){
  const d = document.createElement('div');
  d.className = 'msg' + (m.from === meEl.value ? ' mine' : '');
  d.innerHTML = '<div class="meta"><span class="who">' + esc(m.from) + '</span> → '
    + '<span class="to">' + esc(m.to) + '</span> · ' + new Date(m.ts).toLocaleTimeString('zh-CN', {hour12:false})
    + '</div><div class="bubble">' + esc(m.text) + '</div>';
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

async function poll(){
  try{
    const r = await fetch(api('/api/messages?since=' + lastId + '&limit=500'));
    const j = await r.json();
    if(!r.ok) throw new Error(j.error || r.status);
    j.messages.forEach(m => { addMsg(m); lastId = Math.max(lastId, m.id); });
    document.getElementById('count').textContent = lastId + ' 条';
    live.textContent = '在线';
    errBox.textContent = '';
    ready = true;
  }catch(e){
    live.textContent = '断开';
    errBox.textContent = '取不到消息：' + e.message;
  }
}

async function send(){
  const text = textEl.value.trim();
  if(!text) return;
  const body = {from: meEl.value.trim() || 'anon', to: toEl.value.trim() || 'all', text};
  localStorage.setItem('group.me', body.from);
  localStorage.setItem('group.to', body.to);
  document.getElementById('send').disabled = true;
  try{
    const r = await fetch(api('/api/send'), {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    if(!r.ok) throw new Error((await r.json()).error || r.status);
    textEl.value = '';
    await poll();
  }catch(e){ errBox.textContent = '发送失败：' + e.message; }
  finally{ document.getElementById('send').disabled = false; }
}

document.getElementById('send').onclick = send;
textEl.addEventListener('keydown', e => {
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
});
poll();
setInterval(poll, 2000);
</script>
</body></html>
"""


def make_handler(store, token):
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        server_version = "ai-group/1"
        protocol_version = "HTTP/1.1"
        timeout = 30  # 浏览器/健康检查断连时别把线程挂着

        def log_message(self, fmt, *a):  # 安静点：只报错误
            pass

        def handle_one_request(self):
            # 客户端半路关连接（刷新页面、Ctrl+C）是常态，不该打整段堆栈
            try:
                super().handle_one_request()
            except (ConnectionResetError, ConnectionAbortedError,
                    BrokenPipeError, TimeoutError, socket.timeout):
                self.close_connection = True

        # -- helpers ---------------------------------------------------
        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _text(self, code, body, ctype="text/html; charset=utf-8"):
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _authed(self, query):
            if not token:
                return True
            got = self.headers.get("X-Group-Token") or (query.get("token") or [""])[0]
            return got == token

        def _params(self):
            parsed = urllib.parse.urlparse(self.path)
            return parsed.path, urllib.parse.parse_qs(parsed.query)

        # -- GET -------------------------------------------------------
        def do_GET(self):
            path, query = self._params()
            if path == "/api/health":
                return self._json(200, {"ok": True, "messages": store.last_id})
            if not self._authed(query):
                return self._json(401, {"error": "口令不对"})
            if path == "/":
                return self._text(200, PAGE.replace("__TOKEN__", token))
            if path == "/api/messages":
                try:
                    since = int((query.get("since") or ["0"])[0])
                    limit = max(1, min(1000, int((query.get("limit") or ["200"])[0])))
                except ValueError:
                    return self._json(400, {"error": "since/limit 必须是整数"})
                me = (query.get("me") or [""])[0].strip()
                include_self = (query.get("include_self") or ["0"])[0] == "1"
                store.touch(me)
                out = []
                for rec in store.all():
                    if rec["id"] <= since:
                        continue
                    if me:
                        to = rec["to"]
                        if not (to == me or to in ("all", "*") or (include_self and rec["from"] == me)):
                            continue
                    out.append(rec)
                return self._json(200, {"next": store.last_id, "messages": out[-limit:]})
            if path == "/api/status":
                me = (query.get("me") or [""])[0].strip()
                store.touch(me)
                now = time.time()
                roster = [
                    {"who": who, "idle_s": int(now - ts)}
                    for who, ts in sorted(store.presence.items(), key=lambda kv: -kv[1])
                ]
                return self._json(
                    200,
                    {"ok": True, "messages": store.last_id, "roster": roster, "now": now},
                )
            return self._json(404, {"error": "没有这个地址"})

        # -- POST ------------------------------------------------------
        def do_POST(self):
            path, query = self._params()
            if not self._authed(query):
                return self._json(401, {"error": "口令不对"})
            if path != "/api/send":
                return self._json(404, {"error": "没有这个地址"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._json(400, {"error": "Content-Length 不对"})
            if length <= 0 or length > 200_000:
                return self._json(400, {"error": "消息体为空或过大"})
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return self._json(400, {"error": "不是合法 JSON"})
            sender = str(payload.get("from") or "").strip()
            to = str(payload.get("to") or "").strip()
            text = str(payload.get("text") or "").strip()
            if not sender or not to:
                return self._json(400, {"error": "from 和 to 都不能空"})
            if not text:
                return self._json(400, {"error": "text 不能空"})
            if len(text) > MAX_TEXT:
                return self._json(400, {"error": "text 超过 %d 字" % MAX_TEXT})
            rec = store.append(sender, to, text)
            store.touch(sender)
            return self._json(200, {"ok": True, "id": rec["id"], "ts": rec["ts"]})

    return Handler


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def is_cgnat(ip):
    """100.64.0.0/10：Tailscale / ZeroTier 这类虚拟网段都落在这里。"""
    try:
        parts = [int(x) for x in ip.split(".")]
    except Exception:
        return False
    return len(parts) == 4 and parts[0] == 100 and 64 <= parts[1] <= 127


def _is_loopback(ip):
    return ip.startswith("127.") or ip in ("::1", "localhost")


def describe_ip(ip):
    if is_cgnat(ip):
        return "（虚拟网卡：Tailscale/ZeroTier 之类，跨 WiFi 时用这个）"
    if ip.startswith("192.168.2."):
        return "（可能是虚拟网卡，别用这个）"
    return ""


def resolve_data_dir(explicit):
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("GROUP_DATA"):
        candidates.append(os.environ["GROUP_DATA"])
    candidates += [
        os.path.join(os.path.expanduser("~"), ".ai-group"),
        os.path.join(os.getcwd(), ".ai-group-state"),
        os.path.join(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp", "ai-group-state"),
    ]
    for cand in candidates:
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".w")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            return cand
        except Exception:
            continue
    raise GroupError("找不到可写目录存消息，用 --data 指定一个。")


def cmd_serve(args):
    from http.server import ThreadingHTTPServer

    data_dir = resolve_data_dir(args.data or "")
    store = Store(data_dir)
    token = (args.token or os.environ.get("GROUP_TOKEN") or "").strip()
    if not token:
        print("! 没设口令：同网段任何人都能看和发。建议加 --token 或 GROUP_TOKEN。")
    class Server(ThreadingHTTPServer):
        # Windows 上 SO_REUSEADDR 会让第二个 serve 抢同一个端口，两边各写各的文件。
        allow_reuse_address = False
        daemon_threads = True

        def handle_error(self, request, client_address):
            exc = sys.exc_info()[1]
            if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                                BrokenPipeError, TimeoutError)):
                return  # 断连不是错误，别刷屏
            super().handle_error(request, client_address)

    try:
        httpd = Server((args.bind, args.port), make_handler(store, token))
    except OSError as exc:
        print("起不来：%s（这个端口已经有群在跑了？换 --port）" % exc)
        return 2
    print("群已开，消息存在 %s" % store.path)
    print("本机浏览器：  http://127.0.0.1:%d/?token=%s" % (args.port, token))
    for ip in lan_ips():
        print("给同伴的地址：http://%s:%d %s" % (ip, args.port, describe_ip(ip)))
    print("同一个 WiFi 用 192.168/10.x；不在一个网就用 100.x（Tailscale）那条。")
    print("把地址填进 GROUP_URL，口令填进 GROUP_TOKEN。Ctrl+C 结束。")
    print("")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n群已关。")
    return 0


def cmd_send(args):
    to = (args.to or "").strip()
    if not to:
        raise GroupError("--to 必填：发给谁（如 B1）或 all。")
    text = args.text
    if text is None or text == "-":
        text = sys.stdin.read()
    text = (text or "").strip()
    if not text:
        raise GroupError("消息是空的。")
    res = api_send(args, text, to)
    print("已发出 #%d → %s" % (res["id"], to))
    return 0


def cmd_read(args):
    me = _me(args)
    since = args.since if args.since is not None else load_cursor(me)
    res = api_fetch(args, me, since, limit=args.limit, include_self=args.include_self)
    msgs = res["messages"]
    if args.json:
        print(json.dumps({"next": res["next"], "messages": msgs}, ensure_ascii=False, indent=2))
    elif not msgs:
        print("（没有发给 %s 的新消息，最近 id=%d）" % (me, res["next"]))
    else:
        print(render(msgs))
    if not args.peek and msgs:
        if not save_cursor(me, res["next"]):
            print("（提示：游标写不进本机，下次 read 会重复返回这批消息）", file=sys.stderr)
    return 0


def cmd_watch(args):
    me = _me(args)
    poll = max(0.5, float(args.poll))
    deadline = time.time() + args.timeout if args.timeout else None
    since = load_cursor(me)
    while True:
        try:
            res = api_fetch(args, me, since, limit=args.limit, include_self=args.include_self)
        except GroupError as exc:
            print("watch: %s" % exc, file=sys.stderr)
            return 2
        if res["messages"]:
            print(render(res["messages"]))
            save_cursor(me, res["next"])
            return 0
        if deadline and time.time() >= deadline:
            print("watch: %.0f 秒内没有新消息（%s）" % (args.timeout, me), file=sys.stderr)
            return 1
        time.sleep(poll)


def cmd_status(args):
    res = api_status(args)
    print("群在线，共 %d 条消息。" % res["messages"])
    if res.get("roster"):
        print("出现过的人：")
        for row in res["roster"]:
            idle = row["idle_s"]
            when = "%ds 前" % idle if idle < 120 else "%d 分钟前" % (idle // 60)
            print("  %-10s %s" % (row["who"], when))
    else:
        print("还没人发过消息。")
    return 0


def find_tailscale():
    """新装的 Tailscale 常常不在当前 shell 的 PATH 里（要重开终端），这里兜底找。"""
    p = shutil.which("tailscale")
    if p:
        return p, True
    for cand in (
        r"C:\Program Files\Tailscale\tailscale.exe",
        r"C:\Program Files (x86)\Tailscale\tailscale.exe",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
        "/usr/bin/tailscale",
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
    ):
        if os.path.exists(cand):
            return cand, False
    return None, False


def cmd_check(args):
    """一条命令告诉你"还差哪一步"。新人第一次连群时跑这个。"""
    url = (args.url or os.environ.get("GROUP_URL") or "").strip()
    token = (args.token or os.environ.get("GROUP_TOKEN") or "").strip()
    me = (args.me or os.environ.get("GROUP_ME") or "").strip()
    problems = []

    def line(name, value, good, fix="", required=True):
        mark = "OK " if good else "!! "
        print("%s %-12s %-52s %s" % (mark, name, value, "" if good else fix))
        if not good and required:
            problems.append(name)

    print("环境：")
    line("GROUP_URL", url or "（空）", bool(url), "setx GROUP_URL http://<群主IP>:8765")
    line("GROUP_TOKEN", ("已设置 %d 位" % len(token)) if token else "（空）", bool(token),
         "setx GROUP_TOKEN <和群主一样的口令>")
    line("GROUP_ME", me or "（空）", bool(me), "setx GROUP_ME B1（每个人的 agent 用不同名字）")

    if url:
        base = url if url.startswith("http") else "http://" + url
        base = base.rstrip("/")
        host = urllib.parse.urlparse(base).hostname or ""
        print("\n连通：")
        line("地址形式", base, base.startswith("http://") or base.startswith("https://"),
             "地址要以 http:// 开头")
        if is_cgnat(host or ""):
            print("      （这是 Tailscale/ZeroTier 虚拟地址，需要三台都装了并登录同一账号）")
        t0 = time.time()
        try:
            _request(base + "/api/health", "", timeout=5)
            ms = int((time.time() - t0) * 1000)
            line("到达群主", "%d ms" % ms, True)
        except GroupError as exc:
            line("到达群主", "失败", False, "")
            print("      %s" % exc)
        else:
            try:
                st = _request(
                    "%s/api/status?%s" % (base, urllib.parse.urlencode({"me": me} if me else {})),
                    token,
                    timeout=5,
                )
                line("口令与读写", "共 %d 条消息" % st["messages"], True)
            except GroupError as exc:
                line("口令与读写", "失败", False, "")
                print("      %s" % exc)

    print("\n本机网络：")
    need_virtual = bool(url) and is_cgnat(host or "")
    ts, on_path = find_tailscale()
    line("tailscale 命令", (ts or "没装") + ("" if (ts is None or on_path) else "（不在 PATH，重开终端）"),
         bool(ts), "装 https://tailscale.com/download/windows 后重开终端", required=need_virtual)
    virtual = [ip for ip in lan_ips() if is_cgnat(ip)]
    line("100.x 虚拟地址", ", ".join(virtual) if virtual else "没有", bool(virtual),
         "没登录 / 没启动。装好后跑 tailscale up，登录同一个账号", required=need_virtual)
    if need_virtual and not virtual:
        print("      群地址是 100.x，但本机没有 100.x 地址：这台机器还没进 Tailscale 网络。")
    elif url and host and not is_cgnat(host) and not _is_loopback(host):
        print("      群地址是 %s，走的是局域网直连；不在同一个 WiFi 就必须改用 100.x。" % host)
    candidates = [ip for ip in lan_ips() if not is_cgnat(ip) and not _is_loopback(ip)]
    if candidates:
        print("      本机可发出去的地址：%s" % ", ".join(candidates))

    print("")
    if problems:
        print("结论：还没通（%s）。先修上面标 !! 的项。" % "、".join(problems))
        return 2
    print("结论：通了。开工先跑：python %s read --me %s" % (os.path.basename(__file__), me))
    return 0


def cmd_ui(args):
    base = _base_url(args)
    print("%s/?token=%s" % (base, _token(args)))
    return 0


# --------------------------------------------------------------------------- #


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--url", help="群地址，默认读 GROUP_URL")
    common.add_argument("--token", help="口令，默认读 GROUP_TOKEN")
    common.add_argument("--me", help="我是谁，默认读 GROUP_ME")

    p = argparse.ArgumentParser(
        prog="group.py",
        description="三台电脑共用的 AI 群聊板（一台当群主，其余当客户端）。",
        epilog="例：python group.py serve --port 8765 --token 口令   |   "
               "python group.py send --to B1 --text '...'   |   python group.py read",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="起群（一台机器跑，窗口别关）")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--bind", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    s.add_argument("--token", default="", help="共享口令")
    s.add_argument("--data", default="", help="消息文件目录，默认 ~/.ai-group")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("send", parents=[common], help="发一条消息")
    s.add_argument("--to", required=False, help="收件人（B1 / all）")
    s.add_argument("--text", help="消息正文；传 - 从 stdin 读")
    s.set_defaults(func=cmd_send)

    s = sub.add_parser("read", parents=[common], help="取发给我的新消息")
    s.add_argument("--since", type=int, default=None, help="从哪个 id 之后取（默认用本机游标）")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--peek", action="store_true", help="只看，不推进游标")
    s.add_argument("--include-self", action="store_true", help="连自己发的也返回")
    s.add_argument("--json", action="store_true", help="输出 JSON，给程序读")
    s.set_defaults(func=cmd_read)

    s = sub.add_parser("watch", parents=[common], help="等新消息，有就打印并退出")
    s.add_argument("--timeout", type=float, default=900, help="最多等多少秒，0=一直等")
    s.add_argument("--poll", type=float, default=3.0)
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--include-self", action="store_true")
    s.set_defaults(func=cmd_watch)

    s = sub.add_parser("status", parents=[common], help="群是否在线、谁出现过")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("check", parents=[common], help="自检：还差哪一步连不上")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("ui", parents=[common], help="打印浏览器看群的地址")
    s.set_defaults(func=cmd_ui)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except GroupError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
