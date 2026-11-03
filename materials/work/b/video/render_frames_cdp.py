"""用 CDP 直连 Chrome 连续截帧，替代"每帧启动一次浏览器"的慢办法。

原来的 render_frames.py 每帧都要起一个新 Chrome 进程（含 profile 初始化），
单帧约 3.5 秒，只能降到 5 fps 渲染再补到 25 fps——补出来的帧是复制的，
快速转场会顿。本脚本只启动一次浏览器，然后对每帧调 render(t) + captureScreenshot，
单帧约 0.1–0.2 秒，可以按 25 fps 原生渲染。

前提：core-loop.html 的 render(t) 是全局函数（当前如此），且页面用 `#t=0` 打开时
停在静态帧、不启动 requestAnimationFrame 循环。

用法：
  python materials/work/b/video/render_frames_cdp.py --fps 25 --duration 32.8
  python materials/work/b/video/render_frames_cdp.py --fps 10 --half   # 只渲 0-16s 试水
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
import websocket

ROOT = Path(__file__).resolve().parents[4]
VID = ROOT / "materials/work/b/video"
OUT = ROOT / "tmp/vid/frames"
HTML = VID / "core-loop.html"

CHROME_CANDIDATES = [
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]


def find_chrome():
    for p in CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit("没找到 Chrome/Edge")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30, max_size=64 * 1024 * 1024)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError("%s -> %s" % (method, msg["error"]))
                return msg.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True)
        if r.get("exceptionDetails"):
            raise RuntimeError("JS 异常: %s" % r["exceptionDetails"].get("text"))
        return r.get("result", {}).get("value")

    def shot(self, path: Path):
        r = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        path.write_bytes(base64.b64decode(r["data"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--duration", type=float, default=32.8)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--keep", action="store_true", help="保留已存在的帧，只补缺的")
    ap.add_argument("--half", action="store_true", help="只渲前一半（试水）")
    args = ap.parse_args()

    dur = args.duration / 2 if args.half else args.duration
    out = Path(args.out)
    if not args.keep and out.exists():
        for f in out.glob("f*.png"):
            f.unlink()
    out.mkdir(parents=True, exist_ok=True)

    n = int(round(dur * args.fps))
    print("目标 %d 帧（%.1f s @ %d fps）" % (n, dur, args.fps))

    exe = find_chrome()
    port = free_port()
    profile = ROOT / "tmp/vid/cdp-profile"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    url = HTML.as_uri() + "#t=0"
    proc = subprocess.Popen(
        [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check", "--mute-audio",
         "--force-device-scale-factor=1", "--window-size=1920,1080",
         "--remote-debugging-port=%d" % port,
         "--user-data-dir=%s" % profile, url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    t0 = time.time()
    while time.time() - t0 < 25:
        try:
            tabs = requests.get("http://127.0.0.1:%d/json" % port, timeout=1).json()
            for tb in tabs:
                if tb.get("type") == "page" and "core-loop" in tb.get("url", ""):
                    ws_url = tb["webSocketDebuggerUrl"]
                    break
            if ws_url:
                break
        except Exception:
            pass
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        raise SystemExit("连不上 Chrome 调试端口")

    cdp = CDP(ws_url)
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")
    cdp.call("Emulation.setDeviceMetricsOverride", width=1920, height=1080,
             deviceScaleFactor=1, mobile=False)
    time.sleep(0.5)

    ok = cdp.js("typeof render === 'function'")
    if not ok:
        proc.kill()
        raise SystemExit("页面里没有全局 render(t)，先用旧脚本")

    t_start = time.time()
    done = 0
    for i in range(n):
        t = i / args.fps
        cdp.js("render(%f)" % t)
        p = out / ("f%05d.png" % i)
        for attempt in range(3):
            try:
                cdp.shot(p)
                if p.exists() and p.stat().st_size > 10000:
                    break
            except Exception:
                time.sleep(0.05)
        done += 1
        if done % max(1, n // 20) == 0 or done == n:
            el = time.time() - t_start
            print("  %4d/%d  %.0f%%  已用 %.0fs  预计剩余 %.0fs" % (
                done, n, 100 * done / n, el, el / done * (n - done)))

    cdp.ws.close()
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    have = len(list(out.glob("f*.png")))
    print("完成：%d 帧，用时 %.1f s" % (have, time.time() - t_start))
    if have < n:
        print("警告：缺 %d 帧" % (n - have))
        sys.exit(2)


if __name__ == "__main__":
    main()
