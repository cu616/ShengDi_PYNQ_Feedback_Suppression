"""把 core-loop.html 逐帧渲染成 PNG 序列，再用 ffmpeg 合成 mp4。

原理：HTML 里 `#t=<秒>` 会渲染该时刻的静态帧（不依赖 CSS 动画，所以截图一定对得上）。
用 Chrome headless 逐帧截图，并行 4 路。

用法：
  python materials/work/b/video/render_frames.py --fps 12
  （输出 tmp/vid/frames/ 与 materials/work/b/video/core-loop.mp4）

依赖：本机 Chrome/Edge、imageio-ffmpeg 自带的 ffmpeg。都不需要联网。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
VIDEO = ROOT / "materials/work/b/video"
HTML = VIDEO / "core-loop.html"
CHROME_CANDIDATES = [
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
]


def chrome_exe():
    for p in CHROME_CANDIDATES:
        if p.exists():
            return p
    raise SystemExit("找不到 Chrome 或 Edge")


def ffmpeg_exe():
    import imageio_ffmpeg
    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def shoot(exe, url, out, profile, size="1920,1080"):
    # 每个 worker 用独立 profile：共用默认 profile 时 Chrome 会互相等锁，并行等于串行
    cmd = [str(exe), "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check",
           f"--user-data-dir={profile}",
           "--force-device-scale-factor=1", f"--window-size={size}",
           f"--screenshot={out}", "--virtual-time-budget=700", url]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return Path(out).exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--duration", type=float, default=33.0)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out-fps", type=int, default=25,
                    help="合成时的输出帧率；高于渲染帧率时用 minterpolate 补间")
    ap.add_argument("--out", default=str(VIDEO / "core-loop.mp4"))
    args = ap.parse_args()

    exe = chrome_exe()
    ff = ffmpeg_exe()
    frames = ROOT / "tmp/vid/frames"
    frames.mkdir(parents=True, exist_ok=True)
    for old in frames.glob("*.png"):
        old.unlink()

    n = int(round(args.duration * args.fps))
    base = "file:///" + str(HTML).replace("\\", "/")

    def job(i):
        t = i / args.fps
        out = frames / f"f{i:05d}.png"
        profile = ROOT / "tmp/vid/prof" / f"w{i % args.workers}"
        profile.mkdir(parents=True, exist_ok=True)
        ok = shoot(exe, f"{base}#t={t:.3f}", out, profile)
        if not ok:
            print("FAIL", i, t, file=sys.stderr)
        return ok

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(job, range(n)))
    print(f"帧 {sum(results)}/{n} 成功，输出目录 {frames}")
    if not all(results):
        raise SystemExit("有帧没截到，检查 Chrome 是否被占用")

    cmd = [str(ff), "-y", "-framerate", str(args.fps), "-i", str(frames / "f%05d.png"),
           "-vf", f"scale=1920:1080:flags=lanczos,"
                  f"minterpolate=fps={args.out_fps}:mi_mode=blend,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-movflags", "+faststart", args.out]
    print("ffmpeg:", " ".join(cmd[-6:]))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    size = Path(args.out).stat().st_size / 1e6
    print(f"合成完成 {args.out}  {size:.1f} MB")


if __name__ == "__main__":
    main()
