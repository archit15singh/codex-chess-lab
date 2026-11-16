#!/usr/bin/env python3
"""Render a local, self-contained dark research report with a contrast explorer.

Inputs are a Markdown manuscript, local figure aliases and precomputed contrast
rows. The page performs formatting/filtering only, never statistical analysis.
"""
import argparse,base64,csv,io,json,re,os,struct
from html import escape
from pathlib import Path

def list_item(value):
    item=re.match(r'^([-*]|[0-9]+\.)\s+(.+)$',value)
    return None if item is None else (item[1] if item[1][0].isdigit() else '-')+' '+item[2]

def inline(value):
    value=escape(value)
    value=re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
    value=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)
    value=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<em>\1</em>',value)
    return re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',r'<a href="\2" rel="noreferrer">\1</a>',value)

def numeric(value,scale=1):return 'Unavailable' if value is None else f'{value*scale:.2f}'
def table_rows(rows,scale):
    body=[]
    for r in rows:
        label=r['contrast'].replace('_',' ')
        values=[label,numeric(r['estimate'],scale),numeric(r['bootstrap95_low'],scale)+' to '+numeric(r['bootstrap95_high'],scale),str(r['common_items']),str(r['common_families']),numeric(r['leave_one_family_out_min'],scale)+' to '+numeric(r['leave_one_family_out_max'],scale),'Unavailable' if r['sign_flip_reference_two_sided_p'] is None else f"{r['sign_flip_reference_two_sided_p']:.5f}"]
        body.append('<tr>'+''.join('<th scope="row">'+escape(v)+'</th>' if i==0 else '<td>'+escape(v)+'</td>' for i,v in enumerate(values))+'</tr>')
    return ''.join(body)

def render_markdown(text,root,aliases):
    parts=[];toc=[];paragraph=[];seen=set();i=0;lines=text.splitlines();skip_title=False
    def flush():
        if paragraph:parts.append('<p>'+inline(' '.join(paragraph))+'</p>');paragraph.clear()
    while i<len(lines):
        line=lines[i].strip()
        if not line:flush();i+=1;continue
        if line in ['<!-- contents -->','<!-- pagebreak -->']:flush();i+=1;continue
        if line=='<!-- contrast-explorer -->':flush();parts.append('__EXPLORER__');i+=1;continue
        if line.startswith('```'):
            flush();i+=1;code=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):code.append(lines[i]);i+=1
            if i==len(lines):raise ValueError('unclosed code fence')
            parts.append('<pre tabindex="0"><code>'+escape('\n'.join(code))+'</code></pre>');i+=1;continue
        image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if image:
            flush();caption,name=image.groups();path=(root/aliases.get(name,name)).resolve(strict=True)
            if not path.is_relative_to(root):raise ValueError('figure escapes asset root')
            raw=path.read_bytes()
            dimensions=''
            if raw.startswith(b'\x89PNG\r\n\x1a\n'):
                if len(raw)<24 or raw[12:16]!=b'IHDR':raise ValueError('invalid PNG dimensions')
                width,height=struct.unpack('>II',raw[16:24])
                if not width or not height:raise ValueError('empty PNG dimensions')
                mime='image/png';dimensions=f' width="{width}" height="{height}"'
            elif raw.startswith(b'\xff\xd8'):mime='image/jpeg'
            else:raise ValueError('only local PNG/JPEG figures supported')
            data=base64.b64encode(raw).decode('ascii')
            parts.append('<figure><img loading="lazy"'+dimensions+' alt="'+escape(caption,quote=True)+'" src="data:'+mime+';base64,'+data+'"><figcaption>'+inline(caption)+'</figcaption></figure>');i+=1;continue
        if line.startswith('|'):
            flush();rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells):rows.append(cells)
                i+=1
            if not rows or any(len(r)!=len(rows[0]) for r in rows):raise ValueError('inconsistent table columns')
            table='<div class="table-scroll" tabindex="0" role="region" aria-label="Research table"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'
            table+=''.join('<tr>'+''.join('<th scope="row">'+inline(c)+'</th>' if n==0 else '<td>'+inline(c)+'</td>' for n,c in enumerate(row))+'</tr>' for row in rows[1:])
            parts.append(table+'</tbody></table></div>');continue
        heading=re.match(r'^(#{1,6})\s+(.+)$',line)
        if heading:
            flush();depth=len(heading[1]);name=heading[2]
            if depth==1 and not skip_title:skip_title=True;i+=1;continue
            base=re.sub('[^a-z0-9]+','-',name.lower()).strip('-') or 'section';slug=base;suffix=2
            while slug in seen:slug=base+'-'+str(suffix);suffix+=1
            seen.add(slug);level=min(4,max(2,depth));parts.append(f'<h{level} id="{slug}">'+inline(name)+f'</h{level}>')
            if level<=3:toc.append((level,slug,name))
            i+=1;continue
        item=list_item(line)
        if item:flush();parts.append('<p class="list-item">'+inline(item)+'</p>');i+=1;continue
        paragraph.append(line);i+=1
    flush();return '\n'.join(parts),toc

CSS='''
:root{color-scheme:dark;--bg:#101821;--panel:#162331;--ink:#e6edf4;--soft:#b6c6d5;--line:#344352;--link:#8fc7ee;--focus:#edb46d}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.72 Georgia,serif}a{color:var(--link);text-underline-offset:3px}a:hover{color:#c4e4fc}a:focus-visible,button:focus-visible,select:focus-visible,[tabindex]:focus-visible,summary:focus-visible{outline:3px solid var(--focus);outline-offset:4px}.skip{position:absolute;left:12px;top:-80px;background:var(--panel);padding:10px;z-index:10}.skip:focus{top:10px}.layout{display:grid;grid-template-columns:245px minmax(0,1030px);gap:52px;max-width:1400px;margin:0 auto;padding:40px 35px 90px}aside{font:13px/1.6 system-ui,sans-serif;position:sticky;top:28px;height:calc(100vh - 60px);overflow:auto;padding-right:15px}aside p{color:var(--soft)}nav ol{list-style:none;margin:0;padding:0}nav li{margin:8px 0}nav li.sub{padding-left:13px;font-size:12px}nav a{color:var(--soft);text-decoration:none}nav a:hover{text-decoration:underline;color:var(--ink)}summary{cursor:pointer;font-weight:700;color:var(--ink)}main{min-width:0}header{border-bottom:1px solid var(--line);padding-bottom:30px;margin-bottom:35px}.eyebrow{font:12px/1.5 system-ui,sans-serif;letter-spacing:.13em;text-transform:uppercase;color:var(--soft);margin:0 0 13px}h1{font-size:clamp(34px,4.6vw,58px);line-height:1.08;letter-spacing:-.035em;margin:0 0 22px;max-width:16ch}.subtitle{font:20px/1.5 system-ui,sans-serif;max-width:45ch;color:var(--soft)}.meta{font:12px/1.6 system-ui,sans-serif;color:var(--soft)}h2{font-size:30px;line-height:1.25;padding-top:25px;margin:50px 0 20px;border-top:1px solid var(--line);scroll-margin-top:20px}h3{font-size:23px;line-height:1.35;margin:30px 0 13px}h4{font-size:20px;line-height:1.4}p{max-width:76ch;margin:0 0 18px}strong{font-weight:700}code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}code{font-size:.82em;background:#1b2d3b;padding:2px 4px;border-radius:3px}pre{background:#0b1219;border:1px solid var(--line);padding:18px;overflow:auto;font-size:13px;line-height:1.6}pre code{background:none;padding:0;font-size:inherit}figure{margin:35px 0}figure img{width:100%;height:auto;display:block;background:var(--bg)}figcaption{font:13px/1.65 system-ui,sans-serif;color:var(--soft);margin:12px 0}.table-scroll{overflow:auto;margin:24px 0;border:1px solid var(--line);border-radius:4px}table{border-collapse:collapse;width:100%;font:13px/1.55 system-ui,sans-serif;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top}thead th{background:#22394b;color:var(--ink);font-weight:600}tbody th{font-weight:500;min-width:120px}tbody tr:nth-child(even){background:var(--panel)}.list-item{padding-left:18px;border-left:2px solid var(--line)}.explorer{background:#12212e;padding:24px;border:1px solid #385267;border-radius:6px;margin:35px 0;font-family:system-ui,sans-serif}.explorer h3{font-family:Georgia,serif;margin-top:0}.controls{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0}.controls label{font-size:12px;display:grid;gap:7px;color:var(--soft)}select,button{font:14px system-ui,sans-serif;color:var(--ink);background:#20384a;border:1px solid #5b778b;border-radius:4px;padding:10px 12px;min-height:43px}button{cursor:pointer}button:hover{background:#2a4b62}.explorer p{font-size:13px;line-height:1.6;color:var(--soft)}.explorer table{min-width:800px}.explorer td{white-space:nowrap}.source-note{font:12px/1.7 system-ui,sans-serif;color:var(--soft);margin-top:50px;padding-top:20px;border-top:1px solid var(--line)}@media(max-width:1050px){.layout{grid-template-columns:190px minmax(0,1fr);gap:28px;padding:30px 22px}}@media(max-width:780px){.layout{display:block;padding:22px 18px 60px}aside{position:relative;height:auto;max-height:260px;overflow:auto;margin-bottom:30px;padding:0 0 20px;border-bottom:1px solid var(--line)}body{font-size:17px}h2{font-size:27px}.explorer{padding:16px}.controls{display:grid;grid-template-columns:1fr}figure{margin:25px 0}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{body{background:#101821;color:#e6edf4;print-color-adjust:exact}aside,.skip,.controls{display:none}.layout{display:block;padding:0}h2{break-after:avoid}figure,table{break-inside:avoid}a{color:#8fc7ee}main{width:100%}}
'''
JS=r'''
(()=>{'use strict';const db=JSON.parse(document.getElementById('contrast-data').textContent);const endpoint=document.getElementById('endpoint');const cohort=document.getElementById('cohort');const body=document.getElementById('contrast-rows');const note=document.getElementById('contrast-note');let shown=[];
const fmt=(v,s)=>Number.isFinite(v)?(v*s).toFixed(2):'Unavailable';
function update(){const key=endpoint.value;const cp=key==='quality_cp_loss_raw';const scale=cp?1:100;shown=db[key].filter(r=>r.cohort===cohort.value||r.contrast==='factorial_interaction_D-B-C+A');body.replaceChildren();for(const r of shown){const tr=document.createElement('tr');const vals=[r.contrast.replaceAll('_',' '),fmt(r.estimate,scale),fmt(r.bootstrap95_low,scale)+' to '+fmt(r.bootstrap95_high,scale),r.common_items,r.common_families,fmt(r.leave_one_family_out_min,scale)+' to '+fmt(r.leave_one_family_out_max,scale),(Number.isFinite(r.sign_flip_reference_two_sided_p)?r.sign_flip_reference_two_sided_p.toFixed(5):'Unavailable')];vals.forEach((v,i)=>{const c=document.createElement(i===0?'th':'td');if(i===0)c.scope='row';c.textContent=String(v);tr.append(c)});body.append(tr)}note.textContent=(cp?'Raw finite CP difference; negative favors treatment. Numeric quality is conditional on score coverage. ':'Percentage-point difference; positive favors treatment. ')+(cohort.value==='pairwise_common'?'Each contrast uses its pairwise-common cohort. ':'Contrasts use the same all-nine-arm available cohort. ')+'The interaction always uses its four-arm common cohort. Intervals are exploratory family bootstraps; sign-flip p is a small-cluster reference, without multiplicity adjustment. A zero-width observed interval does not prove equivalence.';}
endpoint.addEventListener('change',update);cohort.addEventListener('change',update);document.getElementById('download-contrasts').addEventListener('click',()=>{const fields=['contrast','cohort','estimate','bootstrap95_low','bootstrap95_high','common_items','common_families','leave_one_family_out_min','leave_one_family_out_max','sign_flip_reference_two_sided_p'];const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';const cp=endpoint.value==='quality_cp_loss_raw';const unit=cp?'cp':'percentage_points';const scale=cp?1:100;const scaled=new Set(['estimate','bootstrap95_low','bootstrap95_high','leave_one_family_out_min','leave_one_family_out_max']);const csv=[['endpoint','unit',...fields].map(quote).join(','),...shown.map(r=>[endpoint.value,unit,...fields.map(k=>r[k]!==null&&scaled.has(k)?r[k]*scale:r[k])].map(quote).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='chess-contrasts-'+endpoint.value+'-'+cohort.value+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});update();})();
'''

def render(manuscript,output,*,root,aliases,contrasts,title,subtitle,date,replace_derived=False,protected_inputs=()):
    root=root.resolve(strict=True);manuscript=manuscript.resolve(strict=True);output=output.absolute()
    text=manuscript.read_text();inputs={manuscript,*[Path(p).resolve(strict=True) for p in protected_inputs]}
    for line in text.splitlines():
        match=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line.strip())
        if match:inputs.add((root/aliases.get(match[2],match[2])).resolve(strict=True))
    if output.is_symlink() or output.resolve() in inputs:raise ValueError('output cannot replace manuscript/config/figure input or symlink')
    if output.exists() and not replace_derived:raise FileExistsError('derived output exists; explicit replacement required')
    temporary=output.with_suffix(output.suffix+'.part')
    if temporary.exists() or temporary.is_symlink():raise FileExistsError('partial output exists; preserve and diagnose it')
    body,toc=render_markdown(text,root,aliases)
    data={k:contrasts[k] for k in ['response_success','quality_cp_loss_raw','final_ontime_exact_board']}
    initial=[r for r in data['response_success'] if r['cohort'] in ('pairwise_common','four_arm_common')]
    explorer='''<section class="explorer" aria-labelledby="explorer-heading"><h3 id="explorer-heading">Inspect the static comparisons</h3><p>All declared contrasts and the factorial interaction are retained. These controls change the displayed endpoint and cohort; they do not run a new analysis.</p><div class="controls"><label for="endpoint">Endpoint<select id="endpoint"><option value="response_success">On-time legal final</option><option value="quality_cp_loss_raw">Conditional raw CP difference</option><option value="final_ontime_exact_board">On-time exact final board</option></select></label><label for="cohort">Available cohort<select id="cohort"><option value="pairwise_common">Pairwise common</option><option value="all_arm_common_sensitivity">All nine arms common</option></select></label><button type="button" id="download-contrasts">Download displayed rows</button></div><p id="contrast-note" aria-live="polite">Percentage-point differences; positive favors treatment. Exploratory source-family bootstrap intervals, not confirmatory or rating evidence. Full numeric tables remain available without JavaScript.</p><noscript><p>The default table is shown without JavaScript. Complete endpoint tables are included in the report and package; switching or downloading requires JavaScript.</p></noscript><div class="table-scroll" tabindex="0" role="region" aria-label="Declared static contrasts"><table><thead><tr><th scope="col">Contrast</th><th scope="col">Difference</th><th scope="col">95% interval</th><th scope="col">Items</th><th scope="col">Families</th><th scope="col">Leave-one-family-out range</th><th scope="col">Sign-flip p</th></tr></thead><tbody id="contrast-rows">'''+table_rows(initial,100)+'''</tbody></table></div></section>'''
    if '__EXPLORER__' not in body:raise ValueError('manuscript must place <!-- contrast-explorer --> explicitly')
    body=body.replace('__EXPLORER__',explorer)
    navigation='<ol>'+''.join('<li'+(' class="sub"' if depth==3 else '')+'><a href="#'+slug+'">'+escape(name)+'</a></li>' for depth,slug,name in toc)+'</ol>'
    payload=json.dumps(data,allow_nan=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark"><title>'''+escape(title)+'''</title><style>'''+CSS+'''</style></head><body><a class="skip" href="#main">Skip to report</a><div class="layout"><aside><p class="eyebrow">Codex Chess Lab</p><p>Local research report<br>'''+escape(date)+'''</p><nav aria-label="Report contents"><details open><summary>Contents</summary>'''+navigation+'''</details></nav><p>Saved evidence, explicit failures and conditional comparisons. No external publication is implied.</p></aside><main id="main"><header><p class="eyebrow">Empirical agent research</p><h1>'''+escape(title)+'''</h1><p class="subtitle">'''+escape(subtitle)+'''</p><p class="meta">'''+escape(date)+''' | Automated collection and authorship disclosed | Prepared for researcher review</p></header>'''+body+'''<p class="source-note">This self-contained report uses embedded local figures and precomputed data. The explorer formats supplied results only. Saved analyses and the reproducibility package define the quantitative record; model weights, calibrated human strength and billing are not independently measured.</p></main></div><script type="application/json" id="contrast-data">'''+payload+'''</script><script>'''+JS+'''</script></body></html>'''
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.is_symlink():raise ValueError('output cannot replace a symlink')
    with temporary.open('x') as stream:stream.write(html)
    if output.exists() and not replace_derived:raise FileExistsError('derived output appeared; preserve partial and diagnose')
    os.replace(temporary,output)
    return {'output':str(output),'bytes':output.stat().st_size,'headings':len(toc),'embedded_figures':body.count('data:image/'),'contrast_endpoints':len(data)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manuscript',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--aliases',type=Path,required=True);p.add_argument('--contrasts',type=Path,required=True);p.add_argument('--title',required=True);p.add_argument('--subtitle',required=True);p.add_argument('--date',required=True);p.add_argument('--replace-derived',action='store_true');a=p.parse_args()
    print(json.dumps(render(a.manuscript,a.output,root=a.asset_root,aliases=json.loads(a.aliases.read_text()),contrasts=json.loads(a.contrasts.read_text()),title=a.title,subtitle=a.subtitle,date=a.date,replace_derived=a.replace_derived,protected_inputs=[a.aliases,a.contrasts])))
if __name__=='__main__':main()
