"""按视频剧本（materials/planning/video-shotlist.xlsx）的时间线拼完整粗剪。

九段顺序即现场演示顺序：片头 → 重标定 → 扩声 → 拨码啸叫 → 原理动画 →
板卡分工 → 资源 → 可复用流程 → 片尾。

素材只有两种：
  1. 占位卡（PIL 画，标明镜头编号/内容/状态）
  2. 已渲染的 core-loop.mp4（截 0–25 s，停在"相减完成"）
缺的实拍一律用占位卡，不伪造画面。

两张数据图（322 Hz 三臂、换模型）不再进这条时间线：现剧本的对照是
"同一增益拨 SW0 起振"，不是 322 Hz 单频三臂，硬塞会有拼接口径的问题。
它们保留在目录里作为备用数据图，口径见 README。

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
    ("S1", 0,   12, "card",  "a01 板卡与外设全貌", "实物慢摇 · 待实拍",
     "声堤 · 实时声反馈抑制原型 / AMD Zynq-7020 · PYNQ-Z2"),
    ("S2", 12,  20, "card",  "a02 按 Button 0 + 平板计时", "一键重标定 · 待实拍（实测约 150 s，本段加速）",
     "Button 0 · 一键重标定 / 实际耗时 __:__ / 本段 N× 加速"),
    ("S3", 32,  30, "card",  "a03 扩声：手机音乐 + 平板电平 + Button 1", "一镜到底 · 待实拍",
     "音源 = 手机音乐 / 增益 +1.0 dB · 抵消开启 / 平板实测电平"),
    ("S4", 62,  30, "card",  "a04 拨 SW0：起振 → 停声", "一镜到底 · 待实拍（拨上即起振，随后停声）",
     "SW0 拨上 = 旁路 / 拨上即起振 · 输出饱和保护停声"),
    ("S5", 92,  25, "clip",  "core-loop.mp4", "原理动画 · 已有",
     "原理示意（非实测波形）"),
    ("S6", 117,  8, "card",  "a05 板卡正面与接线近景", "待实拍",
     "PL：音频通路与反馈预测 / PS：配置 · 记录 · 判定停声"),
    ("S7", 125, 18, "card",  "a06 运行记录与资源表", "待实拍 / 录屏",
     "XC7Z020 · BRAM 80 % · DSP 3 · LUT 3 588 · FF 5 018"),
    ("S8", 143, 14, "card",  "C 的技能包片段", "待提供",
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
