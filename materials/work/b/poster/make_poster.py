"""在 AMD 模板上做纯文字替换：形状、图片、坐标、颜色一律不动。

原则
----
1. 段落数量与模板完全一致。模板左栏用 4 个空段落跳过中间那张图、
   结尾用 3 个空段落留白；这些空段落必须原样保留，否则整栏排版会塌。
2. 只改 <a:t> 的文字内容。字号、字体、行距、段前段后、缩进、
   颜色全部继承模板的 rPr —— 除非该段中文用 Calibri 会 fallback，
   这时只补一个东亚字体名，不改字号。
3. 五张图片原位、原尺寸换成标注框，不移动、不缩放。
4. 只删模板自带的黄色填写说明（"校名""校徽""背景，关键信息摘要"等）
   与母版的 [Copyright <Year>] 占位。其余一个形状都不删。

对照关系（形状索引来自模板，见 docs 里 dump 出的清单）：
  [0]  左栏正文 13 段    [1] INTRODUCTION     [2] 主标题
  [22] 姓名              [24] 学校            [23] 右上平台标注
  [4]  典型应用场景       [36] System Architecture
  [39] 上卡片            [38] 下卡片           [34] 右栏正文
  [33][38][40][35][37] 五张图片
  [41]-[49] 黄色填写说明（删）
"""
import sys
from copy import deepcopy
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

SRC = Path(r"C:\Users\whybz\Downloads\AMD_poster_template.pptx")
OUT = Path(r"D:\Always\QianSai\ShengDi_PYNQ_Feedback_Suppression\materials\final")
TMP = Path(r"D:\Always\QianSai\ShengDi_PYNQ_Feedback_Suppression\tmp")

LATIN = "Calibri"          # 模板正文西文字体
CN_FACE = "微软雅黑"        # 只作为东亚字体补丁，不改字号

# 黄色填写说明的形状索引（模板自带，成品里不该出现）
NOTES = (41, 42, 43, 44, 45, 46, 47, 48, 49)


def _patch_para(p, text, size_pt=None, ea_font=None, latin_font=None):
    """把段落 p 的文字换成 text，其余属性全部沿用模板。

    模板一段可能被拆成多个 run（因为局部加粗或换字体），这里只保留
    第一个 run 的 rPr，其余删掉，避免样式打架。
    """
    runs = p.findall(qn("a:r"))
    for r in runs[1:]:
        p.remove(r)
    for tag in ("a:br", "a:fld"):
        for el in p.findall(qn(tag)):
            p.remove(el)

    if runs:
        r = runs[0]
        rPr = r.find(qn("a:rPr"))
    else:                                    # 空段落：补 run 与 rPr
        r = etree.SubElement(p, qn("a:r"))
        rPr = etree.SubElement(r, qn("a:rPr"))
        etree.SubElement(r, qn("a:t"))
    if rPr is None:
        rPr = etree.Element(qn("a:rPr"))
        r.insert(0, rPr)

    t = r.find(qn("a:t"))
    if t is None:
        t = etree.SubElement(r, qn("a:t"))
    t.text = text

    if size_pt:
        rPr.set("sz", str(int(round(size_pt * 100))))
    if latin_font or ea_font:
        for tag in ("a:latin", "a:ea"):
            for el in rPr.findall(qn(tag)):
                rPr.remove(el)
        # CT_TextCharacterProperties 的子元素是有序的：
        # ln, fill, effect, highlight, uLn, uFill, latin, ea, cs, sym, hlink...
        # 新元素必须插在 a:cs / a:sym / a:hlink* 之前，追加到末尾会被判非法。
        anchor = None
        for tag in ("a:cs", "a:sym", "a:hlinkClick", "a:hlinkMouseOver",
                    "a:rtl", "a:extLst"):
            found = rPr.find(qn(tag))
            if found is not None:
                anchor = found
                break
        new = []
        if latin_font:
            el = etree.Element(qn("a:latin"))
            el.set("typeface", latin_font)
            new.append(el)
        if ea_font:
            el = etree.Element(qn("a:ea"))
            el.set("typeface", ea_font)
            new.append(el)
        if anchor is not None:
            idx = list(rPr).index(anchor)
            for el in new:
                rPr.insert(idx, el)
                idx += 1
        else:
            for el in new:
                rPr.append(el)


def set_text(shape, lines, size_pt=None, ea_font=None, latin_font=None):
    """按行填文字；行数必须与模板段落数一致（多了补段、少了清空）。"""
    txBody = shape.text_frame._txBody
    paras = txBody.findall(qn("a:p"))
    proto = deepcopy(paras[-1]) if paras else None

    for i, line in enumerate(lines):
        if i < len(paras):
            _patch_para(paras[i], line, size_pt, ea_font, latin_font)
        elif proto is not None:
            p = deepcopy(proto)
            txBody.append(p)
            _patch_para(p, line, size_pt, ea_font, latin_font)
    for j in range(len(lines), len(paras)):
        _patch_para(paras[j], "", size_pt, ea_font, latin_font)
    return shape


def clear(shape):
    set_text(shape, [""])


def drop(shape):
    shape._element.getparent().remove(shape._element)


def mark(slide, pic, label, note, tag):
    """在原图位置放一个同尺寸的标注框，然后删掉原图。

    字号按框宽自适应：校徽那个框只有 2 cm 宽，11pt 会折成五行溢出。
    """
    narrow = pic.width < 3000000          # < 3 cm
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                 Emu(pic.left), Emu(pic.top),
                                 Emu(pic.width), Emu(pic.height))
    box.name = "placeholder-" + label
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0xF7, 0xF7, 0xF7)
    box.line.color.rgb = RGBColor(0xBF, 0xBF, 0xBF)
    box.line.width = Pt(1)
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.clear()
    p1 = tf.paragraphs[0]
    p1.alignment = 2
    r1 = p1.add_run()
    r1.text = label
    r1.font.size = Pt(8 if narrow else 11)
    r1.font.color.rgb = RGBColor(0x9A, 0x9A, 0x9A)
    r1.font.name = CN_FACE
    p2 = tf.add_paragraph()
    p2.alignment = 2
    r2 = p2.add_run()
    r2.text = note
    r2.font.size = Pt(7 if narrow else 9)
    r2.font.color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
    r2.font.name = CN_FACE
    drop(pic)
    return box


# ---------------------------------------------------------------- 文案

TITLE_CN = ["声堤：声反馈抑制与稳定裕度提升"]
TITLE_EN = ["HUSH: Acoustic Feedback Suppression",
            "with Enhanced Stability Margin"]

NAMES_CN = ["刘北辰   王浩宇   陈致远"]
NAMES_EN = ["Liu Beichen, Wang Haoyu, Chen Zhiyuan"]

SCHOOL_CN = ["华中科技大学", "", ""]
SCHOOL_EN = ["Huazhong University", "of Science and Technology", ""]

PLATFORM_CN = ["Zynq-7020 实时运行"]
PLATFORM_EN = ["Real-time on Zynq-7020"]

SEC1_CN = ["简介"]
SEC1_EN = ["INTRODUCTION"]

CASE_CN = ["典型应用场景"]
CASE_EN = ["Typical application case"]

SEC2_CN = ["系统架构"]
SEC2_EN = ["System Architecture"]

# 左栏 13 段：模板用 p01-p04 四个空段跳过中间的图，p11-p13 三个空段留白
BODY_CN = [
    "声反馈是正反馈。只要某个频点的环路增益超过 1，几百毫秒内就会自激啸叫，"
    "不会逐渐变差，事后也无法把信号恢复回来。",
    "", "", "", "",
    "在讲台、会议桌这类位置固定的扩声场景里，声学路径是稳定的、可以被辨识。"
    "难点在于抵消器本身就在环路里——它的延迟先吃掉稳定裕度，然后才谈得上收益。"
    "所以延迟是能否工作的前提，不是性能优化。",
    "针对三个关键问题：",
    "1. 环路内的延迟：512 抽头、1539 拍，在每帧 2048 拍预算内完成；",
    "2. 换摆位后的现场重辨识：一键重标定，训练与验证捕获分开；",
    "3. 区分抵消与音量：同增益三臂对照，不靠调小声音。",
    "我们估计并抵消的是回传分量；直达语音不在估计里，所以也不会被减掉。",
    "", "", "",
]
BODY_EN = [
    "Acoustic feedback is positive feedback: once the loop gain passes unity at "
    "any single frequency, howling appears within a few hundred milliseconds.",
    "", "", "", "",
    "In a fixed layout such as a lectern or a meeting table the acoustic path is "
    "stable and can be identified. What is hard is that the canceller sits inside "
    "the loop: its own latency is subtracted from the stability margin before any "
    "benefit is counted, so delay is a precondition, not an optimisation.",
    "Three issues addressed:",
    "1. Latency inside the loop: 512 taps, 1539 of a 2048-frame budget;",
    "2. Re-identification after the loudspeaker or microphone moves;",
    "3. Telling cancellation apart from attenuation, not turning the volume down.",
    "What is estimated and removed is the returning component; direct speech is "
    "never in the estimate, so it is never removed.",
    "", "", "",
]

CARD_UP_CN = ["PL 侧（可编程逻辑）",
              "1. 512 抽头 FIR，每拍一次乘加；",
              "2. 宽残差，饱和放在数字增益之后；",
              "3. 预测流按 lag_first = 1 对齐；",
              "4. 每帧 2048 拍，1539 拍跑完。"]
CARD_UP_EN = ["PL side (programmable logic):",
              "1. 512-tap FIR, one MAC per sample;",
              "2. Wide residual, saturation after digital gain;",
              "3. Prediction stream aligned to lag_first = 1;",
              "4. 1539 of the 2048-frame budget."]

CARD_DN_CN = ["PS 侧（处理器）",
              "1. 回读实际硬件身份，不把请求值当回读；",
              "2. 下发系数与增益，写模型 bundle；",
              "3. 记录运行与原始捕获，保留原件；",
              "4. 判定输入满幅并停声。"]
CARD_DN_EN = ["PS side (processor):",
              "1. Reads back the actual hardware identity;",
              "2. Loads coefficients and gain, stages the model bundle;",
              "3. Logs the run and keeps the original captures;",
              "4. Decides the input-overload stop."]

RESULT_CN = [
    "两种夹具（箱体、房间）在固定位置实测。",
    "322 Hz 三臂（纯音、单摆位、数字增益 −8 dB）：无环路 45.44 dB，"
    "环路闭合未抵消 49.19 dB，环路闭合已抵消 44.43 dB；环路提升 +3.75 dB。",
    "房间夹具、512 抽头、逐段时域残差：150 Hz–10 kHz −11.24 dB；"
    "8.2–8.6 kHz −23.4 dB；300 Hz–1 kHz −4.0 dB。",
    "XC7Z020：BRAM 80 %，DSP 3，LUT 3 588，FF 5 018，WNS +0.287 ns。",
    "口径：不宣称稳定增益提升（ASG）。报告的是留出数据上的预测抑制，"
    "不是听感结论；保护停声与抵消收益是两个机制，分开陈述。",
]
RESULT_EN = [
    "Two fixtures (enclosure, room), fixed layouts.",
    "322 Hz three-arm, single tone, gain -8 dB: open 45.44, no cancellation "
    "49.19, cancelling 44.43 dB -> loop boost +3.75 dB.",
    "Room, 512 taps, per-segment residual: 150 Hz-10 kHz -11.24 dB; "
    "8.2-8.6 kHz -23.4 dB; 300 Hz-1 kHz -4.0 dB.",
    "XC7Z020: BRAM 80 %, DSP 3, LUT 3 588, FF 5 018, WNS +0.287 ns.",
    "Scope: no ASG figure is claimed; reported is prediction suppression on "
    "held-out captures, not a listening result. Protection stop and "
    "cancellation benefit are stated separately.",
]


def build(lang, out_dir=OUT):
    cn = lang == "cn"
    prs = Presentation(str(SRC))
    s = prs.slides[0]
    sh = list(s.shapes)

    # 1) 黄色填写说明 + 母版版权占位
    for i in NOTES:
        drop(sh[i])
    for m in prs.slide_master.shapes:
        if m.has_text_frame and "[Copyright" in m.text_frame.text:
            clear(m)

    # 2) 标题（模板 24pt Times New Roman，autosize 会自己长高）
    if cn:
        set_text(sh[2], TITLE_CN, size_pt=20, ea_font=CN_FACE)
    else:
        set_text(sh[2], TITLE_EN, size_pt=18, latin_font="Times New Roman")

    # 3) 姓名（模板 12pt；英文全名 12pt 会撞学校，降到 10）
    if cn:
        set_text(sh[22], NAMES_CN, ea_font=CN_FACE)
    else:
        set_text(sh[22], NAMES_EN, size_pt=9, latin_font="Times New Roman")

    # 4) 学校（模板 2 段 + 1 空段）
    if cn:
        set_text(sh[24], SCHOOL_CN, ea_font=CN_FACE)
    else:
        set_text(sh[24], SCHOOL_EN, latin_font="Times New Roman")

    # 5) 右上平台标注（10pt，不换行）
    if cn:
        set_text(sh[23], PLATFORM_CN, ea_font=CN_FACE)
    else:
        set_text(sh[23], PLATFORM_EN, latin_font="Times New Roman")

    # 6) 章节标题 / 小节标题：只换字，不改颜色（模板是深底白字）
    set_text(sh[1], SEC1_CN if cn else SEC1_EN, ea_font=CN_FACE)
    set_text(sh[4], CASE_CN if cn else CASE_EN, ea_font=CN_FACE)
    set_text(sh[36], SEC2_CN if cn else SEC2_EN, ea_font=CN_FACE)

    # 7) 左栏正文：13 段骨架保持不变
    set_text(sh[0], BODY_CN if cn else BODY_EN, ea_font=CN_FACE)
    if not cn:
        for pa in sh[0].text_frame.paragraphs:      # 中文版不用动，英文统一 10.5
            for r in pa.runs:
                r.font.size = Pt(11)

    # 8) 两张圆角卡（模板首行 12pt 红字，其余 11pt）
    set_text(sh[39], CARD_UP_CN if cn else CARD_UP_EN, ea_font=CN_FACE)
    set_text(sh[38], CARD_DN_CN if cn else CARD_DN_EN, ea_font=CN_FACE)
    if cn:                                   # 中文行距宽，11pt 会把第 4 条挤出卡片
        for card in (sh[39], sh[38]):
            for pa in card.text_frame.paragraphs[1:]:
                for r in pa.runs:
                    r.font.size = Pt(10)

    # 左栏最后一段是独立论述，补 10pt 段前距（模板里 p06 小标题就是这个值）
    sh[0].text_frame.paragraphs[10].space_before = Pt(10)

    # 9) 右栏正文（模板 2 段）
    set_text(sh[34], RESULT_CN if cn else RESULT_EN, ea_font=CN_FACE)
    if not cn:
        for pa in sh[34].text_frame.paragraphs:
            for r in pa.runs:
                r.font.size = Pt(10)

    # 10) 五张图片：原位原尺寸换成标注框（索引只取 PICTURE，别碰圆角卡）
    for pic, label_cn, label_en, note_cn, note_en in (
        (sh[33], "校徽", "Logo", "待提供", "to be supplied"),
        (sh[32], "测试平台示意图", "Test platform", "待插入", "to be supplied"),
        (sh[40], "作品实物照片", "Hardware photo", "待插入", "to be supplied"),
        (sh[35], "应用场景配图", "Application photo", "待插入", "to be supplied"),
        (sh[37], "系统框图", "System block diagram", "待绘制", "to be drawn"),
    ):
        if pic.shape_type != 13:
            raise SystemExit("索引 %s 不是图片：%s" % (pic.name, pic.shape_type))
        mark(s, pic, label_cn if cn else label_en, note_cn if cn else note_en,
             pic.name)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"poster-hush-{lang}.pptx"
    prs.save(str(out))
    print("saved", out.name, out.stat().st_size // 1024, "KB")
    return out


if __name__ == "__main__":
    target = TMP if "--preview" in sys.argv else OUT
    for lang in ("cn", "en"):
        build(lang, target)
