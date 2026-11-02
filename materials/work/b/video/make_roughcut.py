"""按 video-plan §8 的时间线拼一条完整粗剪（静音轨，占位卡标状态）。

素材只有三种：
  1. 占位卡（PIL 画，标明镜头编号/内容/状态）
  2. 已渲染的 core-loop.mp4（截 0–25 s）
  3. 两张数据图（PNG，当作静态镜头）
缺的实拍一律用占位卡，不伪造画面。

用法：python materials/work/b/video/make_roughcut.py
输出：materials/work/b/video/roughcut.mp4 + roughcut-timeline.json
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
VID = ROOT / "materials/work/b/video"
TMP = ROOT / "tmp/vid/rough"
W, H = 1920, 1080

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

INK, MUTED, BG, ACCENT = "#1f2933", "#5b6672", "#f6f7f9", "#2f7ed8"

# (id, 起, 时长, 类型, 主素材, 场景说明, 屏幕字幕)
TL = [
    ("S1", 0,   12, "card",  "a01 整体装配与连接全貌", "实物慢摇 · 待实拍",
     "声堤 · 实时声反馈抑制原型 / AMD Zynq-7020 · PYNQ-Z2"),
    ("S2", 12,  30, "card",  "a02 真人扩声（长镜头）", "静音 → 扩声 → 静音 · 待实拍",
     "真人现场讲话 · 普通扩声（零系数）· 数字增益 −8 dB · Codec 40"),
    ("S3", 42,  25, "clip",  "core-loop.mp4", "原理动画 · 已有",
     "原理示意（非实测波形）"),
    ("S4", 67,  35, "image", "fig-data-1-three-arm.png", "配 a03 实测操作 · 待实拍",
     "322 Hz 纯音 · 增益 −8 dB · 单摆位 · 数字待 C 定稿"),
    ("S5", 102, 12, "image", "fig-data-2-model-quality.png", "配 a07 重标定+拨码 · 待实拍",
     "重标定 · 状态提示 · 拨码切换（SW0）"),
    ("S6", 114,  8, "card",  "a04 板卡正面与接线", "待实拍",
     "PL：音频通路与反馈预测 · PS：配置／记录／判定停声"),
    ("S7", 122, 20, "card",  "a05 连续运行节选", "待实拍",
     "零系数连续运行 60 s · BRAM 80% · DSP 3 · LUT 3 588 · FF 5 018"),
    ("S8", 142, 15, "card",  "C 的技能包片段", "待提供",
     "可复用流程 · 失败原件保留"),
    ("S9", 157,  8, "card",  "a01 复用（全貌）", "待实拍",
     "声堤 / 面向固定布局语音扩声"),
]


def ffmpeg():
    import imageio_ffmpeg
    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def card(idx, title, note, caption, dur):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_tag = ImageFont.truetype(FONT_B, 34)
    f_big = ImageFont.truetype(FONT_B, 76)
    f_note = ImageFont.truetype(FONT, 40)
    f_cap = ImageFont.truetype(FONT, 32)
    f_small = ImageFont.truetype(FONT, 26)

    d.rectangle([0, 0, W, 128], fill="#ffffff")
    d.text((100, 44), "声堤 · 粗剪占位", font=f_tag, fill=INK)
    d.text((W - 100, 46), f"{idx}  ·  {dur:.0f} s", font=f_tag, fill=ACCENT, anchor="ra")
    d.line([0, 128, W, 128], fill="#dfe3e8", width=3)

    d.text((W // 2, 420), title, font=f_big, fill=INK, anchor="mm")
    d.text((W // 2, 520), note, font=f_note, fill=MUTED, anchor="mm")

    d.rounded_rectangle([220, 640, W - 220, 700], radius=10, fill="#fff4e6", outline="#f0c9a0")
    d.text((W // 2, 670), "此处等待实拍素材 · 非最终画面", font=f_small, fill="#a35a1a", anchor="mm")

    d.line([100, 900, W - 100, 900], fill="#dfe3e8", width=2)
    d.text((W // 2, 952), caption, font=f_cap, fill=MUTED, anchor="mm")
    return img


def main():
    ff = ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    parts, meta = [], []
    total = 0

    for idx, start, dur, kind, src, note, caption in TL:
        outp = TMP / f"{idx}.mp4"
        if kind == "card":
            png = TMP / f"{idx}.png"
            card(idx, src, note, caption, dur).save(png)
            cmd = [str(ff), "-y", "-loop", "1", "-t", str(dur), "-i", str(png),
                   "-vf", f"scale={W}:{H},format=yuv420p", "-r", "25",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(outp)]
        elif kind == "clip":
            cmd = [str(ff), "-y", "-i", str(VID / src), "-t", str(dur),
                   "-vf", f"scale={W}:{H},format=yuv420p", "-r", "25",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                   "-an", str(outp)]
        else:
            cmd = [str(ff), "-y", "-loop", "1", "-t", str(dur), "-i", str(VID / src),
                   "-vf", f"scale={W}:{H},format=yuv420p", "-r", "25",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(outp)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        parts.append(outp)
        meta.append({"id": idx, "start_s": start, "duration_s": dur, "kind": kind,
                     "source": src, "note": note, "status": "placeholder" if kind == "card" else "available"})
        total += dur

    lst = TMP / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = VID / "roughcut.mp4"
    subprocess.run([str(ff), "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(out)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    (VID / "roughcut-timeline.json").write_text(
        json.dumps({"total_s": total, "segments": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}  {out.stat().st_size/1e6:.1f} MB  总时长 {total}s  "
          f"可用 {sum(1 for m in meta if m['status']=='available')}/{len(meta)} 段")


if __name__ == "__main__":
    main()
