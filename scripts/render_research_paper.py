#!/usr/bin/env python3
"""Render a local Markdown research manuscript with saved figures to PDF.

Supported subset: headings, paragraphs, links, emphasis, fenced code, flat lists,
pipe tables and standalone images. No network, JavaScript or remote images.
ReportLab is an optional reporting dependency, never a player dependency.
"""
import argparse
from html import escape
import os
from pathlib import Path
import re

NORMALIZE=str.maketrans({'\u2010':'-','\u2011':'-','\u2012':'-','\u2013':'-','\u2014':'-','\u2212':'-','\u2018':"'",'\u2019':"'",'\u201c':'"','\u201d':'"','\u2026':'...','\u00d7':'x','\u2264':'<=','\u2265':'>=','\u00b1':'+/-','\u00a0':' '})

def normalized(value):
    result=value.translate(NORMALIZE)
    if any(ord(c)>127 for c in result):raise ValueError('manuscript has unsupported non-ASCII text; normalize explicitly')
    return result

def list_item(value):
    item=re.match(r'^([-*]|[0-9]+\.)\s+(.+)$',value)
    return None if item is None else (item[1] if item[1][0].isdigit() else '-')+' '+item[2]

def inline(value):
    value=escape(normalized(value))
    value=re.sub(r'`([^`]+)`',r'<font name="Courier">\1</font>',value)
    value=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',value)
    value=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<i>\1</i>',value)
    value=re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',r'<link href="\2" color="#235e87">\1</link>',value)
    return value

def render(manuscript, output, *, asset_root, title, subtitle, author, date, footer):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import BaseDocTemplate,Frame,PageTemplate,Paragraph,Spacer,PageBreak,Image,Table,TableStyle,KeepTogether,Preformatted
    from reportlab.platypus.tableofcontents import TableOfContents
    manuscript=manuscript.resolve(strict=True);asset_root=asset_root.resolve(strict=True);output=output.absolute()
    if output==manuscript or output.is_symlink():raise ValueError('output cannot replace manuscript or symlink')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.part')
    if temporary.exists() or temporary.is_symlink():raise FileExistsError('partial output exists; preserve and diagnose it first')
    for line in manuscript.read_text().splitlines():
        image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line.strip())
        if image and (asset_root/image[2]).resolve()==output.resolve():raise ValueError('output cannot replace a figure input')
    width,height=A4;margin=43;content_width=width-2*margin
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='PaperBody',fontName='Times-Roman',fontSize=10.5,leading=14.3,spaceAfter=7.5,allowWidows=0,allowOrphans=0))
    styles.add(ParagraphStyle(name='PaperH1',fontName='Times-Bold',fontSize=15,leading=18,spaceBefore=16,spaceAfter=8,keepWithNext=True))
    styles.add(ParagraphStyle(name='PaperH2',fontName='Times-Bold',fontSize=12,leading=15,spaceBefore=10,spaceAfter=6,keepWithNext=True))
    styles.add(ParagraphStyle(name='PaperH3',fontName='Times-BoldItalic',fontSize=10.8,leading=14,spaceBefore=8,spaceAfter=5,keepWithNext=True))
    styles.add(ParagraphStyle(name='PaperCaption',fontName='Times-Roman',fontSize=9,leading=12,spaceBefore=5,spaceAfter=12))
    styles.add(ParagraphStyle(name='PaperCell',fontName='Times-Roman',fontSize=8.3,leading=11))
    styles.add(ParagraphStyle(name='PaperHeaderCell',fontName='Times-Bold',fontSize=8.3,leading=11,textColor=colors.white))
    styles.add(ParagraphStyle(name='PaperCode',fontName='Courier',fontSize=7.5,leading=10,spaceBefore=4,spaceAfter=8))
    styles.add(ParagraphStyle(name='PaperTitle',fontName='Times-Bold',fontSize=25,leading=29,spaceAfter=12))
    styles.add(ParagraphStyle(name='PaperSubtitle',fontName='Times-Roman',fontSize=15,leading=20,spaceAfter=14))
    styles.add(ParagraphStyle(name='PaperMeta',fontName='Helvetica',fontSize=9,leading=13,spaceAfter=7,textColor=colors.HexColor('#465867')))

    class PaperDocument(BaseDocTemplate):
        def beforeDocument(self):
            self._heading_index=0
        def afterFlowable(self, flowable):
            if isinstance(flowable,Paragraph) and flowable.style.name in ('PaperH1','PaperH2'):
                level=0 if flowable.style.name=='PaperH1' else 1
                text=flowable.getPlainText();self._heading_index+=1;key='section-'+str(self._heading_index)
                self.canv.bookmarkPage(key)
                self.notify('TOCEntry',(level,text,self.page,key))

    def page(canvas,doc):
        canvas.saveState();canvas.setTitle(normalized(title));canvas.setAuthor(normalized(author));canvas.setSubject('Local research report; saved experimental evidence and reproducible analyses')
        canvas.setStrokeColor(colors.HexColor('#cbd5dd'));canvas.setLineWidth(.4);canvas.line(margin,34,width-margin,34)
        canvas.setFont('Helvetica',7.5);canvas.setFillColor(colors.HexColor('#526471'));canvas.drawString(margin,22,normalized(footer));canvas.drawRightString(width-margin,22,str(doc.page));canvas.restoreState()
    document=PaperDocument(str(temporary),pagesize=A4,leftMargin=margin,rightMargin=margin,topMargin=43,bottomMargin=45,allowSplitting=1,title=normalized(title),author=normalized(author))
    document.addPageTemplates(PageTemplate(id='paper',frames=[Frame(margin,45,content_width,height-88,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=page))
    story=[Paragraph(inline(title),styles['PaperTitle']),Paragraph(inline(subtitle),styles['PaperSubtitle']),Paragraph(inline(author+' | '+date),styles['PaperMeta']),Paragraph(inline('Prepared for researcher review. Automated authorship and collection are disclosed; no external publication is implied.'),styles['PaperMeta']),Spacer(1,10)]
    lines=manuscript.read_text().splitlines();i=0;paragraph=[];seen_title=False
    def flush():
        if paragraph:
            story.append(Paragraph(inline(' '.join(paragraph)),styles['PaperBody']));paragraph.clear()
    while i<len(lines):
        line=lines[i].strip()
        if not line:flush();i+=1;continue
        if line=='<!-- contents -->':
            flush();story.append(PageBreak());story.append(Paragraph('Contents',styles['PaperH1']));toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC0',fontName='Times-Roman',fontSize=10.5,leading=15,spaceBefore=5),ParagraphStyle('TOC1',fontName='Times-Roman',fontSize=9.5,leading=13,leftIndent=12)];story.extend([toc,PageBreak()]);i+=1;continue
        if line=='<!-- pagebreak -->':flush();story.append(PageBreak());i+=1;continue
        if line=='<!-- contrast-explorer -->':flush();i+=1;continue
        if line.startswith('```'):
            flush();i+=1;code=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):
                text=normalized(lines[i]);code.extend(text[j:j+105] for j in range(0,len(text),105)) if text else code.append('');i+=1
            if i==len(lines):raise ValueError('unclosed code fence')
            story.append(Preformatted('\n'.join(code),styles['PaperCode']));i+=1;continue
        image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if image:
            flush();caption,relative=image.groups();path=(asset_root/relative).resolve(strict=True)
            if not path.is_relative_to(asset_root) or path.is_symlink():raise ValueError('figure escapes asset root')
            iw,ih=ImageReader(str(path)).getSize();scale=min(content_width/iw,(height-180)/ih)
            figure=Image(str(path),width=iw*scale,height=ih*scale)
            story.append(KeepTogether([figure,Paragraph(inline(caption),styles['PaperCaption'])]));i+=1;continue
        if line.startswith('|'):
            flush();rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells):rows.append(cells)
                i+=1
            if not rows or any(len(r)!=len(rows[0]) for r in rows):raise ValueError('table has inconsistent columns')
            count=len(rows[0]);fractions=[1/count]*count
            if count>=3:fractions=[.32]+[(1-.32)/(count-1)]*(count-1)
            cellrows=[[Paragraph(inline(c),styles['PaperHeaderCell' if n==0 else 'PaperCell']) for c in r] for n,r in enumerate(rows)]
            table=Table(cellrows,colWidths=[content_width*f for f in fractions],repeatRows=1,hAlign='LEFT',splitByRow=1)
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#24485c')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#24485c')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f2f5f7')]),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d8e0e5'))]))
            story.extend([table,Spacer(1,10)]);continue
        heading=re.match(r'^(#{1,6})\s+(.+)$',line)
        if heading:
            flush();depth=len(heading[1]);text=heading[2]
            if depth==1 and not seen_title:seen_title=True;i+=1;continue
            style='PaperH1' if depth<=2 else 'PaperH2' if depth==3 else 'PaperH3';story.append(Paragraph(inline(text),styles[style]));i+=1;continue
        item=list_item(line)
        if item:
            flush();story.append(Paragraph(inline(item),styles['PaperBody']));i+=1;continue
        paragraph.append(line);i+=1
    flush();document.multiBuild(story);os.replace(temporary,output)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manuscript',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--asset-root',type=Path);p.add_argument('--title',required=True);p.add_argument('--subtitle',default='');p.add_argument('--author',default='Research program');p.add_argument('--date',required=True);p.add_argument('--footer',default='Local research report - not externally published');a=p.parse_args()
    result=render(a.manuscript,a.output,asset_root=a.asset_root or a.manuscript.parent,title=a.title,subtitle=a.subtitle,author=a.author,date=a.date,footer=a.footer)
    print(result)
if __name__=='__main__':main()
