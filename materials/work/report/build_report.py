"""Build the anonymous competition review report from the official DOCX.

Use the bundled Python runtime. Only report artifacts are written; no board access.
SVG is editable vector source; matching PNG is embedded for Word compatibility.
"""
from pathlib import Path
from copy import deepcopy
from xml.sax.saxutils import escape
import hashlib
import json
import math
import re
import shutil
import subprocess
import zipfile

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIG = HERE / 'figures'
FINAL = ROOT / 'materials/final'
QA = ROOT / 'tmp/report-20261102'
TEMPLATE = HERE / 'official-template.docx'
ORIGINAL = Path('F:/Dzhuomian/2658aa94-81d0-454c-b2ac-fc040ff2c01a.docx')
OUTPUT = FINAL / 'shengdi-technical-report-review.docx'
for folder in (FIG, FINAL, QA): folder.mkdir(parents=True, exist_ok=True)
if not TEMPLATE.exists(): shutil.copyfile(ORIGINAL, TEMPLATE)
template_sha = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
commit = '87ff28c011806f5e5fcf86b741c8f4caa55c7f5e'  # Reviewed source snapshot, independent of rebuild date.

# Design authority: retained official template, not a generic report theme.
contract = f'''# Official template mapping

Owner: captain report editor. Rebuild when report.md or figure data changes.
Template: official-template.docx (retained copy of the user supplied template).
SHA256: {template_sha}
Source-code review snapshot: {commit}

A4, one section; margins top/bottom 1440 twips, left/right 1800 twips.
Header distance 851 twips; footer 992 twips. Body width 8306 twips.
Preserve the official purple FPGA header image, horizontal rule, all header/footer
parts and relationships, styles, numbering, themes and original media byte-for-byte.
Preserve section geometry and the original PAGE fields. Word exports update page
numbers in the PDF; the original DOCX field definitions remain intact.

Editable slots: title, abstract, five main sections and their original subsections.
Use the template's 18 pt centered title, 14 pt bold main headings, 12 pt body,
Song Chinese type with Times New Roman Latin text and 1.5 body line spacing.
Main headings keep their template wording. Subheading numbers are explicit text
to avoid inheriting the template's instruction-list numbering.
Additional cloned body paragraphs, tables, equations, figures and captions are
allowed inside the original slots. Tables use 10.5 pt text for numeric comparison.
New figures use 9–11 pt equivalent labels at final width and editable SVG sources.

Three real-photo slots are intentionally reserved and explicitly marked in this
review draft because the team has not taken photographs. No illustrative image
is presented as an actual photograph. This draft requires those images before
submission. Refer to README.md for the exact shooting checklist.

Renderer: packaged render_docx.py was attempted; LibreOffice was absent.
Fallback: isolated hidden Microsoft Word COM PDF export, then pypdfium2 page
rendering and visual inspection. Original template is opened read-only.
'''
(HERE / 'artifact.md').write_text(contract, encoding='utf-8')

INK = '#222533'; PURPLE = '#64206e'; TEAL = '#176f78'; MUTED = '#626875'
LINE = '#aeb5bf'; LIGHT = '#f3f5f7'; LAV = '#f2eaf4'; GREEN = '#e8f3f2'

class Canvas:
    """A tiny dual SVG/PIL canvas; text remains real text in the SVG."""
    def __init__(self, name, h, w=1400):
        self.name, self.w, self.h = name, w, h
        self.im = Image.new('RGB', (w*2, h*2), 'white')
        self.d = ImageDraw.Draw(self.im)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">', '<rect width="100%" height="100%" fill="white"/>']
    def text(self, x, y, text, size=29, color=INK, bold=False, anchor='middle'):
        font = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc', size*2)
        for n,line in enumerate(text.split('\n')):
            yy = y + n*size*1.45
            bbox = self.d.textbbox((0,0),line,font=font)
            width = self.d.textlength(line,font=font)
            xx = x*2-(width/2 if anchor=='middle' else width if anchor=='end' else 0)
            self.d.text((xx,yy*2-bbox[1]),line,font=font,fill=color)
            self.svg.append(f'<text x="{x}" y="{yy+size*.88}" font-family="Microsoft YaHei, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{escape(line)}</text>')
    def rect(self,x,y,w,h,fill=LIGHT,stroke=LINE):
        self.d.rectangle((x*2,y*2,(x+w)*2,(y+h)*2),fill=fill,outline=stroke,width=3)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    def line(self,pts,color=INK,width=3,arrow=False,dashed=False):
        pts=[(float(x),float(y)) for x,y in pts]
        self.d.line([(int(x*2),int(y*2)) for x,y in pts],fill=color,width=width*2)
        pp=' '.join(f'{x},{y}' for x,y in pts)
        ds=' stroke-dasharray="10 7"' if dashed else ''
        self.svg.append(f'<polyline points="{pp}" fill="none" stroke="{color}" stroke-width="{width}"{ds}/>')
        if arrow:
            x,y=pts[-1]; x0,y0=pts[-2]; a=math.atan2(y-y0,x-x0)
            p=[(x,y),(x-15*math.cos(a-.45),y-15*math.sin(a-.45)),(x-15*math.cos(a+.45),y-15*math.sin(a+.45))]
            self.d.polygon([(int(a*2),int(b*2)) for a,b in p],fill=color)
            self.svg.append(f'<polygon points="{" ".join(f"{a},{b}" for a,b in p)}" fill="{color}"/>')
    def box(self,x,y,w,h,title,sub='',fill=LIGHT):
        self.rect(x,y,w,h,fill)
        self.text(x+w/2,y+22,title,31,bold=True)
        if sub:self.text(x+w/2,y+70,sub,26,color=MUTED)
    def save(self):
        self.svg.append('</svg>')
        (FIG/f'{self.name}.svg').write_text('\n'.join(self.svg),encoding='utf-8')
        self.im.save(FIG/f'{self.name}.png',dpi=(360,360),optimize=True)

c=Canvas('system',650)
c.text(700,15,'音频主路与场景标定',35,bold=True)
c.box(30,185,210,132,'麦克风','讲话 + 回传声')
c.box(295,185,215,132,'Codec ADC','模拟 → PCM')
c.box(565,185,260,132,'FPGA 实时处理','预测 · 相减 · 增益',fill=LAV)
c.box(880,185,215,132,'Codec DAC','PCM → 模拟')
c.box(1150,185,220,132,'有源音箱','输出到听众')
for x1,x2 in [(240,295),(510,565),(825,880),(1095,1150)]:c.line([(x1,250),(x2,250)],arrow=True)
c.line([(1260,317),(1260,408),(135,408),(135,317)],color=TEAL,arrow=True)
c.text(700,420,'声学反馈 H：音箱播放声重新进入麦克风',28,color=TEAL)
c.box(385,505,630,120,'ARM 处理器与 PYNQ','采集编排 · 模型求解 · 独立验证 · 版本管理',fill=GREEN)
c.line([(695,505),(695,317)],color=PURPLE,arrow=True,dashed=True)
c.text(705,345,'系数 / 控制',25,color=PURPLE,anchor='start')
c.text(700,86,'实际播放字同时作为 FIR 的反馈预测参考',29,color=MUTED)
c.save()

c=Canvas('wiring',420)
c.box(30,115,290,145,'MAX4466 麦克风','模拟前放模块')
c.box(460,100,480,180,'PYNQ-Z2','LINE_IN     ADAU1761     HP+MIC',fill=LAV)
c.box(1080,115,290,145,'有源音箱','独立供电')
c.line([(320,185),(460,185)],color=TEAL,arrow=True)
c.line([(940,185),(1080,185)],color=TEAL,arrow=True)
c.text(390,285,'模拟输入',26,color=TEAL)
c.text(1010,285,'模拟输出',26,color=TEAL)
c.text(700,335,'板载 BTN / SW0 / LED：启动、模式切换与状态提示',29)
c.text(700,28,'连接关系示意  ·  按实际接口标签接线',32,bold=True)
c.save()

c=Canvas('workflow',680)
for x,title,sub in [(30,'按键发起','固定当前布局'),(510,'输入检查','按提示讲话'),(990,'训练采集','已知噪声激励')]:
    c.box(x,45,380,128,title,sub,fill=GREEN if x==30 else LIGHT)
c.line([(410,110),(510,110)],arrow=True)
c.line([(890,110),(990,110)],arrow=True)
c.line([(1180,173),(1180,276)],arrow=True)
for x,title,sub in [(990,'拟合与量化','512 抽头 / Q20'),(510,'独立验证','分离的采集与激励'),(30,'安装与登记','绑定场景和包身份')]:
    c.box(x,276,380,128,title,sub,fill=LAV)
c.line([(990,340),(890,340)],arrow=True)
c.line([(510,340),(410,340)],arrow=True)
c.line([(220,404),(220,514)],arrow=True)
c.box(30,514,380,128,'实时扩声','BTN1 启停 / SW0 对照',fill=GREEN)
c.box(605,514,765,128,'失败分支','保持静音 · 保存原因 · 按提示重试')
c.line([(700,404),(700,514)],color=PURPLE,arrow=True,dashed=True)
c.text(700,208,'每阶段完成后推进；缺少有效数据时给出具体原因',27,color=MUTED)
c.save()

c=Canvas('datapath',640)
c.box(35,80,265,125,'麦克风 m[n]','24 位 PCM')
c.box(440,80,280,125,'相减 / 旁路选择','残差保留 25 位',fill=LAV)
c.box(850,80,230,125,'数字增益','Q4.12',fill=LAV)
c.box(1180,80,190,125,'输出钳位','24 位')
for x1,x2 in [(300,440),(720,850),(1080,1180)]:c.line([(x1,143),(x2,143)],arrow=True)
c.box(290,340,420,143,'512 抽头 FIR','Q20 系数 · 58 位累加',fill=GREEN)
c.line([(500,340),(500,205)],color=TEAL,arrow=True)
c.text(518,252,'预测 p[n]',27,color=TEAL,anchor='start')
c.line([(1275,205),(1275,413),(710,413)],color=TEAL,arrow=True)
c.text(1005,349,'实际播放参考 u[n]',29,color=TEAL)
c.text(700,531,'中间残差 1.0230 × 满幅  →  乘 −8 dB 增益  →  输出 0.4074 × 满幅',29,bold=True)
c.text(700,586,'示例来自语音越界试次的整数复算；帧调度与 I²S 接口在本图中省略',25,color=MUTED)
c.save()

data={'comparison':{'frequency_hz':322,'frame_start':91037,'frame_end':97656,
                   'metric':'microphone_level_relative_to_open_db',
                   'values':{'open':0.0,'bypass':3.7016,'cancel':-1.2486},
                   'source':'report/verification/audio-replay/wide-residual-v3/C-tone-1746930178556850644.json'},
      'timeline':{'gain_q12':5786,'sw0_flip_seconds':9.13,'flip_to_stop_seconds':3.49,
                  'stop_seconds_derived':12.62,
                  'source':'report/verification/audio-replay/demo-protocol-2026-11-02/README.md section 17',
                  'note':'Event timing only. No reconstructed waveform or measured SPL.'}}
(HERE/'figure-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
c=Canvas('comparison',610)
c.text(700,15,'麦克风侧电平（相对开环基准，dB）',34,bold=True)
x0=300; scale=125
for v in [-2,0,2,4,6]:
    x=x0+(v+2)*scale
    c.line([(x,95),(x,430)],color=LINE,width=1)
    c.text(x,448,str(v),25,color=MUTED)
zero=x0+2*scale
for y,label,val,col in [(125,'开环基准',0.0,MUTED),(240,'旁路闭环',3.7016,PURPLE),(355,'抵消闭环',-1.2486,TEAL)]:
    c.text(255,y+12,label,31,anchor='end')
    xx=zero+val*scale
    if val: c.rect(min(zero,xx),y,abs(val)*scale,65,fill=col,stroke=col)
    else:c.line([(zero,y),(zero,y+65)],color=col,width=4)
    c.text(max(zero,xx)+25,y+12,f'{val:+.2f}' if val else '0.00',31,anchor='start',color=col,bold=True)
c.text(700,505,'同一含源窗口：抵消相对旁路降低 4.95 dB',32,bold=True)
c.text(700,560,'历史 v3 · 322 Hz · 6619 帧 · 2026-10-28',25,color=MUTED)
c.save()

c=Canvas('timeline',410)
c.text(700,15,'同一运行内的 SW0 切换事件',34,bold=True)
start,flip,end=75,975,1320
c.rect(start,115,flip-start,95,fill=GREEN,stroke=TEAL)
c.rect(flip,115,end-flip,95,fill=LAV,stroke=PURPLE)
c.text((start+flip)/2,143,'抵消开启',33,color=TEAL,bold=True)
c.text((flip+end)/2,143,'旁路',33,color=PURPLE,bold=True)
c.line([(start,210),(start,247)],width=2)
c.line([(flip,210),(flip,247)],width=2)
c.line([(end,210),(end,247)],width=2)
c.text(start,263,'0 s',27)
c.text(flip,263,'约 9.13 s',27)
c.text(end,263,'约 12.62 s',27)
c.text(655,326,'拨至旁路 → 现场观察到啸叫 → 约 3.49 s 后保护停声',27)
c.text(700,373,'+3.0 dB（q12 = 5786）；事件重绘，不是声压或音频波形',24,color=MUTED)
c.save()

doc=Document(TEMPLATE)
body=doc._element.body
section=deepcopy(body.sectPr)
for child in list(body):
    if child.tag!=qn('w:sectPr'):body.remove(child)

normal=doc.styles['Normal']
# Preserve template styles byte-for-byte; apply direct formatting on new content.
def format_run(r,size=12,bold=False,font='宋体'):
    r.font.size=Pt(size);r.bold=bold;r.font.color.rgb=RGBColor(0,0,0)
    r.font.name='Times New Roman'
    r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),font)
    return r
def para(text='',size=12,bold=False,center=False,before=0,after=6,keep=False):
    p=doc.add_paragraph(style=normal)
    pf=p.paragraph_format;pf.line_spacing=1.5
    pf.space_before=Pt(before);pf.space_after=Pt(after);pf.keep_with_next=keep
    pf.widow_control=True;pf.keep_together=True
    if center:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    format_run(p.add_run(text),size,bold)
    return p
def heading(text,level):
    p=para(text,size=14 if level==2 else 12,bold=True,before=12 if level==2 else 8,after=6,keep=True)
    outline=OxmlElement('w:outlineLvl');outline.set(qn('w:val'),str(level-2));p._p.get_or_add_pPr().append(outline)
    return p
def picture(name,width,caption):
    p=para(after=0,keep=True);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(FIG/f'{name}.png'),width=Inches(width))
    para(caption,size=10.5,center=True,after=8)
def table(rows):
    t=doc.add_table(rows=0,cols=len(rows[0]));t.autofit=False
    widths=[1.14,2.22,2.39] if len(rows[0])==3 else [2.2,3.55]
    for col,w in zip(t.columns,widths):col.width=Inches(w)
    props=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for side in ('top','left','bottom','right','insideH','insideV'):
        b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'B5B9BE');borders.append(b)
    props.append(borders)
    for i,row in enumerate(rows):
        cells=t.add_row().cells
        for cell,txt,w in zip(cells,row,widths):
            cell.width=Inches(w)
            p=cell.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.LEFT;pf=p.paragraph_format;pf.space_after=Pt(4);pf.space_before=Pt(4);pf.line_spacing=1.15
            format_run(p.add_run(txt),10.5,i==0)
            if i==0:
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F0F0F0');cell._tc.get_or_add_tcPr().append(shade)
        trpr=t.rows[-1]._tr.get_or_add_trPr()
        cant=OxmlElement('w:cantSplit');trpr.append(cant)
        if i==0:
            repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
            for cell in cells:cell.paragraphs[0].paragraph_format.keep_with_next=True
    para('',size=2,after=2)
def photo(title,detail):
    p=para(title+'（待补实拍）',size=11,bold=True,center=True,before=10,after=0,keep=True)
    p=para(detail,size=10.5,center=True,before=0,after=10)
    p.paragraph_format.space_before=Pt(30);p.paragraph_format.space_after=Pt(30)
    p.paragraph_format.keep_together=True
    borders=OxmlElement('w:pBdr')
    for side in ('top','left','bottom','right'):
        b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'6');b.set(qn('w:color'),'A0A0A0');b.set(qn('w:space'),'12');borders.append(b)
    p._p.get_or_add_pPr().append(borders)

lines=(HERE/'report.md').read_text(encoding='utf-8').splitlines();i=0; pending_break=False
while i<len(lines):
    s=lines[i].strip();i+=1
    if not s:continue
    if s.startswith('|'):
        rows=[]
        while True:
            if not re.match(r'^\|[\s:|\-]+\|$',s):rows.append([x.strip() for x in s.strip('|').split('|')])
            if i>=len(lines) or not lines[i].startswith('|'):break
            s=lines[i].strip();i+=1
        table(rows)
    elif s.startswith('# '):
        p=para(s[2:],18,True,True,before=8,after=14)
        if 'Title' in doc.styles:p.style=doc.styles['Title']
    elif s.startswith('@subtitle '):para(s[10:],10.5,center=True,after=14)
    elif s=='@break':pending_break=True
    elif s.startswith('## '):
        p=heading(s[3:],2)
        if pending_break:p.paragraph_format.page_break_before=True;pending_break=False
    elif s.startswith('### '):heading(s[4:],3)
    elif s.startswith('#### '):heading(s[5:],4)
    elif s.startswith('@figure '):
        _,name,width,caption=s.split(' ',3);picture(name,float(width),caption)
    elif s.startswith('@equation '):
        p=para(s[10:],11.5,center=True,before=3,after=9,keep=True)
        # Unicode mathematical symbols are rendered by Cambria rather than TNR.
        for r in p.runs:r.font.name='Cambria'
    elif s.startswith('@photo '):
        title,detail=s[7:].split(' 待拍摄：',1);photo(title,'待拍摄：'+detail)
    else:
        p=para(s)
        if not s.startswith(('关键词','[')):p.paragraph_format.first_line_indent=Pt(24)
        if s.startswith('['):p.alignment=WD_ALIGN_PARAGRAPH.LEFT

doc.core_properties.title='声堤：实时声反馈啸叫抑制系统'
doc.core_properties.subject='FPGA 竞赛技术报告审阅稿'
doc.core_properties.author='';doc.core_properties.last_modified_by=''
doc.core_properties.comments=''
raw=QA/'report-generated.docx';doc.save(raw)

# Preserve template parts exactly. Body expansion requires only document.xml,
# added image relationships/media, content types and anonymous core properties.
allowed={'word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml','docProps/core.xml'}
with zipfile.ZipFile(TEMPLATE) as src,zipfile.ZipFile(raw) as new,zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED) as out:
    originals=set(src.namelist());added=[]
    for name in src.namelist():out.writestr(name,new.read(name) if name in allowed else src.read(name))
    for name in new.namelist():
        if name not in originals:out.writestr(name,new.read(name));added.append(name)
with zipfile.ZipFile(TEMPLATE) as a,zipfile.ZipFile(OUTPUT) as b:
    preserved=[n for n in a.namelist() if n not in allowed]
    changed=[n for n in preserved if a.read(n)!=b.read(n)]
assert not changed,changed
assert Document(OUTPUT).sections[0].page_width==Document(TEMPLATE).sections[0].page_width
assert hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()==template_sha
result={'template_sha256':template_sha,'source_snapshot':commit,'docx':OUTPUT.name,
        'preserved_package_parts':len(preserved),'unexpected_changes':changed,
        'new_package_parts':added,'figures':6,'photos_missing':3}
(HERE/'build-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
