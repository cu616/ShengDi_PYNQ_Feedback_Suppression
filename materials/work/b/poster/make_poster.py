"""在 AMD 模板上做替换：版式、配色、竖排字母、分隔线全部保持不动。

按**形状对象**定位，不按索引（删元素会让索引错位）。
只改文字、换掉五张示例图、清掉给做题人的提示与母版版权行。
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Cm, Pt

SRC = Path(r"C:\Users\whybz\Downloads\AMD_poster_template.pptx")
OUT = Path(r"D:\Always\QianSai\ShengDi_PYNQ_Feedback_Suppression\materials\final")

INK = RGBColor(0x2F, 0x2F, 0x2F)
GREY = RGBColor(0x88, 0x88, 0x88)
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
BORDER = RGBColor(0xC0, 0xC0, 0xC0)
CN = "微软雅黑"


def remember(shape):
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            f = r.font
            try:
                col = f.color.rgb if f.color and f.color.type is not None else None
            except AttributeError:
                col = None
            return dict(name=f.name, size=f.size, bold=f.bold, color=col)
    return dict(name=None, size=None, bold=None, color=None)


def fill(shape, lines, size=None, bold=None, name=None, color=None,
         align=PP_ALIGN.LEFT, space_after=4, line_spacing=1.12):
    t = remember(shape)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.clear()
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = line
        f = r.font
        f.name = name or t["name"]
        f.size = Pt(size) if size else (t["size"] or Pt(11))
        f.bold = bold if bold is not None else t["bold"]
        f.color.rgb = color or t["color"] or INK


def kill(shape):
    shape._element.getparent().remove(shape._element)


def add_placeholder(slide, x, y, w, h, label, note, label_pt=13, note_pt=10):
    ph = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    ph.fill.solid()
    ph.fill.fore_color.rgb = LIGHT
    ph.line.color.rgb = BORDER
    ph.line.width = Pt(1.25)
    ph.shadow.inherit = False
    tf = ph.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(label_pt)
    r.font.bold = True
    r.font.color.rgb = GREY
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    r2.text = note
    r2.font.size = Pt(note_pt)
    r2.font.color.rgb = GREY


def build(lang):
    cn = lang == "cn"
    prs = Presentation(str(SRC))
    s = prs.slides[0]
    sh = {i: x for i, x in enumerate(s.shapes)}

    # ---------- 先删：五张示例图 + 九条提示文字（用对象引用，后续不受索引影响）
    pics = {}
    for i in (32, 33, 35, 37, 40):
        p = sh[i]
        pics[i] = (p.left, p.top, p.width, p.height)
        kill(p)
    for i in range(41, 50):
        kill(sh[i])

    # ---------- 母版左上角 [Copyright <Year>]
    for m in prs.slide_master.shapes:
        if m.has_text_frame and m.text_frame.text.strip() in ("‹#›", "|"):
            m.left = -Cm(30)          # 页码/竖线移出画布，不留白痕
    for m in prs.slide_master.shapes:
        if m.has_text_frame and "[Copyright" in m.text_frame.text:
            for p in m.text_frame.paragraphs:
                for r in p.runs:
                    r.text = ""

    # ---------- 顶部
    title = ("声堤：声反馈抑制与稳定裕度提升" if cn
             else "HUSH: Acoustic Feedback Suppression with Enhanced Stability Margin")
    sh[2].fill.background()
    fill(sh[2], [title], size=19 if cn else 17, bold=True, name=CN if cn else None)

    sh[22].top = Cm(0.62)
    sh[22].height = Cm(0.62)
    fill(sh[22], ["刘北辰   王浩宇   陈致远" if cn else "B. Liu    H. Wang    Z. Chen"],
         size=11 if cn else 10, bold=True, name=CN if cn else None)
    sh[24].left = Cm(18.4)
    sh[24].top = Cm(1.34)
    sh[24].width = Cm(7.0)
    sh[24].height = Cm(0.7)
    fill(sh[24], ["华中科技大学" if cn else "Huazhong University of Science and Technology"],
         size=10, name=CN if cn else None)
    fill(sh[23], ["基于 AMD Zynq-7020 的实时测试" if cn else "Real-time test on AMD Zynq-7020"],
         size=9, name=CN if cn else None)

    # ---------- 左栏
    fill(sh[1], ["简介" if cn else "INTRODUCTION"], name=CN if cn else None,
         color=RGBColor(0xFF, 0xD1, 0x00))

    sh[0].height = Cm(8.6)
    if cn:
        body = [
            "声反馈是正反馈：只要某个频点的环路增益超过 1，几百毫秒内就会自激啸叫。"
            "它不会逐渐变差，事后任何处理都无法把信号恢复回来。",
            "在位置固定的扩声场景里，声学路径是稳定的、可以被辨识的。真正的难点在于抵消器"
            "本身就在环路里——它的延迟会先吃掉稳定裕度，然后才谈得上收益。所以延迟是能否"
            "工作的前提，不是性能优化。",
            "声堤用实际播放的信号估计回传路径，预测会传回来的那一份，并且只从麦克风信号里"
            "减掉它。直达语音从一开始就不在估计里，所以也不会被减掉。",
            "针对三个关键问题：环路内的延迟；音响或麦克风移动后的现场重辨识；"
            "区分抵消与音量——把声音调小不等于抑制。",
        ]
    else:
        body = [
            "Acoustic feedback is positive feedback: once the loop gain passes unity at any single "
            "frequency, howling builds up within a few hundred milliseconds. Nothing degrades gradually, "
            "and no downstream processing can recover the signal.",
            "In a fixed layout the acoustic path is stable enough to be identified. What is hard is that "
            "the canceller sits inside the loop: its own latency is subtracted from the stability margin "
            "before any benefit is counted, so delay is a precondition, not an optimisation.",
            "HUSH estimates the feedback path from the signal actually played, predicts the component "
            "that will return, and subtracts only that component. The direct speech is never in the "
            "estimate, so it is never in what gets removed.",
            "Three issues addressed: latency inside the loop; on-site re-identification after the "
            "loudspeaker or the microphone moves; and distinguishing cancellation from attenuation.",
        ]
    fill(sh[0], body, size=10, name=CN if cn else None, space_after=5, line_spacing=1.08)

    kill(sh[4])

    # ---------- 中栏
    fill(sh[36], ["系统架构" if cn else "System Architecture"], name=CN if cn else None)
    if cn:
        pl = ["PL 侧（可编程逻辑）：",
              "1. 512 抽头 FIR，每拍一次乘加；",
              "2. 宽残差，饱和在数字增益之后；",
              "3. 每帧 2048 拍预算中占 3N+3 = 1539 拍；",
              "4. 预测流按 lag_first = 1 对齐。"]
        ps = ["PS 侧（处理器）：",
              "1. 回读实际硬件身份，不把请求值当回读；",
              "2. 下发系数与增益，写模型 bundle；",
              "3. 记录运行与原始捕获，保留原件；",
              "4. 判定输入满幅停声。"]
    else:
        pl = ["PL side (programmable logic):",
              "1. 512-tap FIR, one MAC per sample;",
              "2. Wide residual, saturation after digital gain;",
              "3. 3N+3 = 1539 of the 2048-frame budget;",
              "4. Prediction stream aligned to lag_first = 1."]
        ps = ["PS side (processor):",
              "1. Reads back the actual hardware identity;",
              "2. Loads coefficients and gain, stages the model bundle;",
              "3. Logs the run and keeps the original captures;",
              "4. Decides the input-overload stop."]
    fill(sh[39], pl, size=10, name=CN if cn else None, space_after=3, line_spacing=1.1)
    fill(sh[38], ps, size=10, name=CN if cn else None, space_after=3, line_spacing=1.1)

    # ---------- 右栏
    if cn:
        res = [
            "两种夹具（箱体、房间）固定位置上测得。",
            "322 Hz 三臂（纯音、单摆位、数字增益 −8 dB）：无环路 45.44 dB，环路闭合未抵消 49.19 dB，"
            "环路闭合已抵消 44.43 dB；环路提升 +3.75 dB，声学差 +4.76 dB。",
            "房间夹具、512 抽头、逐段时域残差：150 Hz–10 kHz −11.24 dB；8.2–8.6 kHz −23.4 dB；"
            "300 Hz–1 kHz −4.0 dB。",
            "XC7Z020：BRAM 80 %，DSP 3，LUT 3 588，FF 5 018，WNS +0.287 ns。",
            "口径：不宣称稳定增益提升（ASG）。这里报告的是留出数据上的预测抑制，不是听感结论；"
            "保护停声与抵消收益是两个机制，分开陈述。",
        ]
    else:
        res = [
            "Measured on two fixtures (enclosure, room) at fixed layouts.",
            "322 Hz three-arm test (single tone, single layout, digital gain −8 dB): open loop 45.44 dB, "
            "loop closed without cancellation 49.19 dB, loop closed cancelling 44.43 dB → loop boost "
            "+3.75 dB, acoustic difference +4.76 dB.",
            "Room fixture, 512 taps, per-segment time-domain residual: 150 Hz–10 kHz −11.24 dB; "
            "8.2–8.6 kHz −23.4 dB; 300 Hz–1 kHz −4.0 dB.",
            "XC7Z020: BRAM 80 %, DSP 3, LUT 3 588, FF 5 018, WNS +0.287 ns.",
            "Scope: no gain-before-feedback figure is claimed. What is reported is prediction suppression "
            "on held-out captures, not a listening result. Protection stop and cancellation benefit are "
            "separate mechanisms, reported separately.",
        ]
    sh[34].left = Cm(24.6)
    sh[34].top = Cm(10.2)
    sh[34].width = Cm(9.0)
    sh[34].height = Cm(6.9)
    fill(sh[34], res, size=10, name=CN if cn else None, space_after=6, line_spacing=1.1)

    # ---------- 五张图换成占位框
    def ph(idx, label, note):
        l, t, w, h = pics[idx]
        add_placeholder(s, l, t, w, h, label, note)

    ph(33, "校徽", "待提供")
    ph(32, "测试平台示意图", "待插入")
    ph(40, "作品实物照片", "待插入")
    ph(37, "系统框图", "待绘制")
    # 左栏原示例图位置改到底部，避免打断正文
    add_placeholder(s, Cm(0.7), Cm(13.9), Cm(9.9), Cm(3.5), "应用场景配图", "待插入")

    out = OUT / f"poster-hush-{lang}.pptx"
    OUT.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print("saved", out.name, out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    build("en")
    build("cn")
