"""把三张场景图拼成海报用的 4.36:1 横条，中英各一版。

每张原图 1536×1024，右下角有「AI生成」水印（约 y>940），
裁切时从 y=100 起、到 y=908 止，水印自动排除。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

BASE = Path(__file__).resolve().parent
SCENES = BASE / "scenes"
OUT_W, OUT_H = 1200, 275
CELL_W, CELL_H = 390, 205
GAP = 15
PAD_TOP = 0
LABEL_BASE = 252
FONT = "C:/Windows/Fonts/msyh.ttc"

# 顺序：讲台场景 → 会议场景 → 大空间
# 用固定文件名，换图时只覆盖 scene-*.png，脚本不用改
SOURCES = [
    ("scene-lecture.png", "阶梯教室", "Lecture hall"),
    ("scene-meeting.png", "会议室", "Meeting room"),
    ("scene-auditorium.png", "报告厅", "Auditorium"),
]

CROP_TOP, CROP_BOTTOM = 100, 908


def build(lang: str) -> Path:
    canvas = Image.new("RGB", (OUT_W, OUT_H), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, 34, index=0)

    for i, (name, cn, en) in enumerate(SOURCES):
        src = SCENES / name
        im = Image.open(src).convert("RGB")
        im = im.crop((0, CROP_TOP, im.width, CROP_BOTTOM))
        im = im.resize((CELL_W, CELL_H), Image.LANCZOS)
        # 报告厅那张整体偏暗（深色吸音板 + 暖光），与另两张亮度差太多，
        # 打印会糊成一块；单独提亮到同一水平
        if i == 2:
            im = ImageEnhance.Brightness(im).enhance(1.10)
            im = ImageEnhance.Contrast(im).enhance(0.98)
        x = i * (CELL_W + GAP)
        canvas.paste(im, (x, PAD_TOP))

        text = cn if lang == "cn" else en
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x + (CELL_W - tw) / 2, LABEL_BASE - bbox[3]), text,
                  font=font, fill="#2F2F2F")

    out = BASE / f"fig-app-scenes-{lang}.png"
    canvas.save(out)
    print("saved", out.name, canvas.size)
    return out


if __name__ == "__main__":
    build("cn")
    build("en")
