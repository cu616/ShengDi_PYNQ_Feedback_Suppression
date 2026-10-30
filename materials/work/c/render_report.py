"""Render the editable report to PDF; template pending, no claims added by layout."""
from pathlib import Path
from html import escape
import argparse
import json
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

class Diagram(Flowable):
    def __init__(self,kind,data=None):
        super().__init__(); self.kind=kind; self.data=data; self.width=475; self.height=158 if kind=='architecture' else 158
    def draw(self):
        c=self.canv; c.setFont('CJK',10)
        navy=colors.HexColor('#173b54'); teal=colors.HexColor('#087f8c')
        if self.kind=='architecture':
            for x,label in [(0,'麦克风 / ADC'),(155,'PL FIR / 宽残差'),(310,'增益 / 混合 / DAC')]:
                c.setFillColor(colors.HexColor('#eaf2f6')); c.setStrokeColor(navy)
                c.roundRect(x,95,145,37,5,fill=1); c.setFillColor(navy); c.drawCentredString(x+72.5,109,label)
            for x in [145,300]:
                c.line(x,113,x+10,113); c.line(x+6,117,x+10,113); c.line(x+6,109,x+10,113)
            c.setStrokeColor(teal); c.line(382,95,382,68); c.line(382,68,227,68); c.line(227,68,227,95)
            c.setFillColor(teal); c.drawString(246,74,'实际播放参考反馈到预测核')
            c.setFillColor(colors.HexColor('#eef5ee')); c.roundRect(40,10,375,35,5,fill=1)
            c.setFillColor(navy); c.drawCentredString(227,23,'PS：配置 / 身份校验 / 状态记录 / 停声恢复')
            c.setStrokeColor(navy); c.line(227,45,227,58)
        else:
            lv=self.data['views']['common_source_active']['levels_peak_dbfs']
            left=120; span=290
            c.setFillColor(navy); c.drawString(0,143,'共同含源窗：麦端322 Hz峰值等效电平（dBFS）')
            for tick in [-30,-20,-10,0]:
                x=left+(tick+30)/30*span
                c.setStrokeColor(colors.HexColor('#d8e0e4')); c.line(x,28,x,128)
                c.setFillColor(navy); c.drawCentredString(x,10,str(tick))
            for arm,label,y,col in [('open','开环（增益0）',109,'#8297a4'),('bypass','旁路（同增益）',76,'#bd6a40'),('cancel','抵消（同增益）',43,'#087f8c')]:
                value=lv[arm]['microphone']; c.setFillColor(navy); c.drawString(0,y+2,label)
                c.setFillColor(colors.HexColor(col)); c.rect(left,y,max(0,(value+30)/30*span),17,fill=1,stroke=0)
                c.setFillColor(navy); c.drawString(left+(value+30)/30*span+5,y+3,f'{value:.2f}')

def inline(text):
    text=text.replace('—','-').replace('–','-').replace('\u2011','-')
    text=re.sub(r'`([^`]+)`',r'\1',text)
    text=escape(text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    return text

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=ROOT/'materials/final/shengdi-report.pdf')
    p.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/simsun.ttc')); a=p.parse_args()
    if not a.font.exists(): raise SystemExit('Pass --font with a Chinese TrueType font.')
    pdfmetrics.registerFont(TTFont('CJK',str(a.font),subfontIndex=0))
    pdfmetrics.registerFontFamily('CJK',normal='CJK',bold='CJK',italic='CJK',boldItalic='CJK')
    body=ParagraphStyle('body',fontName='CJK',fontSize=10.1,leading=16.2,spaceAfter=7,wordWrap='CJK',textColor=colors.HexColor('#233744'),splitLongWords=True)
    styles={'body':body,'h1':ParagraphStyle('h1',parent=body,fontSize=30,leading=40,spaceAfter=19,textColor=colors.HexColor('#087f8c')),
        'h2':ParagraphStyle('h2',parent=body,fontSize=17,leading=25,spaceBefore=7,spaceAfter=15,keepWithNext=True),
        'h3':ParagraphStyle('h3',parent=body,fontSize=12,leading=20,spaceBefore=10,spaceAfter=8,keepWithNext=True),
        'cell':ParagraphStyle('cell',parent=body,fontSize=9.2,leading=14,spaceAfter=0),
        'small':ParagraphStyle('small',parent=body,fontSize=8.7,leading=13)}
    lines=(HERE/'technical-report.md').read_text(encoding='utf-8').splitlines(); story=[]; i=0
    while i<len(lines):
        line=lines[i].strip(); i+=1
        if not line: continue
        if line=='{{pagebreak}}': story.append(PageBreak()); continue
        if line=='{{architecture}}': story.append(Diagram('architecture')); story.append(Spacer(1,9)); continue
        if line=='{{tonechart}}':
            story.append(Diagram('tone',json.loads((HERE/'tone-return.json').read_bytes()))); story.append(Spacer(1,9)); continue
        if line.startswith('|'):
            table_lines=[line]
            while i<len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip()); i+=1
            rows=[]
            for t in table_lines:
                cells=[s.strip() for s in t.strip('|').split('|')]
                if all(re.fullmatch(r'[-: ]+',s) for s in cells): continue
                rows.append([Paragraph(inline(s),styles['cell']) for s in cells])
            cols=len(rows[0]); widths=[190,285] if cols==2 else [475/cols]*cols
            t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5eff4')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8fa')]),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),
                ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),
                ('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#86aab8'))]))
            story.extend([t,Spacer(1,9)]); continue
        level=len(line)-len(line.lstrip('#'))
        if level and line[level:level+1]==' ':
            story.append(Paragraph(inline(line[level+1:]),styles['h'+str(min(level,3))])); continue
        story.append(Paragraph(inline(line),styles['small'] if line.startswith('[') else body))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(a.output),pagesize=A4,rightMargin=60,leftMargin=60,topMargin=56,bottomMargin=52,
        title='声堤技术报告审阅初稿',author='ShengDi',subject='Fixed-layout feedback suppression; draft pending template and A/B fragments')
    def page(canvas,doc):
        canvas.setFont('CJK',8); canvas.setFillColor(colors.HexColor('#617d8d'))
        canvas.drawString(60,817,'SHENGDI  /  技术报告审阅初稿')
        canvas.drawRightString(A4[0]-60,817,'2026-10-30')
        canvas.setStrokeColor(colors.HexColor('#cfdee5')); canvas.line(60,805,A4[0]-60,805)
        canvas.drawString(60,30,'待官方模板与A/B片段校订 · 数字按证据范围引用')
        canvas.drawRightString(A4[0]-60,30,str(doc.page))
    doc.build(story,onFirstPage=page,onLaterPages=page)
    print(a.output)

if __name__=='__main__': main()
