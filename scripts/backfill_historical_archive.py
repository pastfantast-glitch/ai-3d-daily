#!/usr/bin/env python3
"""One-time canonical backfill for legacy historical archive pages.

Legacy HTML is source evidence. Existing title/summary/source/analysis are preserved;
identity is deterministic by canonical source URL, not by report date.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
def norm(text): return re.sub(r'\s+',' ',text or '').strip()
def norm_url(url): return (url or '').strip().rstrip('/')
def generated_id(source):
    digest=hashlib.sha1(norm_url(source).encode('utf-8')).hexdigest()[:10]
    host=re.sub(r'[^a-z0-9]+','-',urlparse(source).netloc.lower().replace('www.','')).strip('-')[:24] or 'source'
    return f'hist-{host}-{digest}'
def known_identity():
    source_to_id={}; source_dates={}
    for path in sorted((ROOT/'data'/'daily').glob('20??-??-??.json')):
        data=json.loads(path.read_text('utf-8')); date=path.stem
        for rid,cfg in (data.get('visual_evidence') or {}).items():
            source=norm_url(cfg.get('source_url'))
            if source: source_to_id.setdefault(source,rid); source_dates.setdefault(source,[]).append(date)
    return source_to_id,source_dates
def keywords(title):
    parts=[norm(x) for x in re.split(r'[：:｜|／/、，,。()（）\[\]·\-]+',title)]; out=[]
    for part in parts:
        if len(part)>=2 and part not in out: out.append(part[:40])
    return out[:8]
def extract_blocks(card):
    details=card.find('details'); body=details.find('div',class_='detail-body') if details else None; blocks=[]; current='完整分析'
    if body:
        for child in body.find_all(['h4','p'],recursive=False):
            text=norm(child.get_text(' ',strip=True))
            if not text: continue
            if child.name=='h4': current=text
            else: blocks.append({'label':current,'text':text})
    summary=card.find('p',class_='summary') or card.find('p'); summary_text=norm(summary.get_text(' ',strip=True)) if summary else ''
    impact=card.find('div',class_='quick-impact'); impact_text=norm(impact.get_text(' ',strip=True)) if impact else ''
    meta=card.find(class_='meta') or card.find(class_='item-meta'); meta_text=norm(meta.get_text(' ',strip=True)) if meta else ''
    def prepend(label,text):
        if text and all(norm(b['text'])!=text for b in blocks): blocks.insert(0,{'label':label,'text':text})
    if len(blocks)<3: prepend('摘要脈絡',summary_text)
    if len(blocks)<3: prepend('Production 指標',impact_text)
    if len(blocks)<3: prepend('原始標記',meta_text)
    if len(blocks)<3:
        source=card.find('a',class_='source'); prepend('來源脈絡',norm(f"{source.get_text(' ',strip=True) if source else '原始來源'} {source.get('href','') if source else ''}"))
    if len(blocks)<3: raise RuntimeError('cannot derive >=3 structured Full Analysis blocks from legacy card')
    return blocks
def render_details(soup,blocks):
    details=soup.new_tag('details'); summary=soup.new_tag('summary'); summary.string='完整分析'; details.append(summary); body=soup.new_tag('div'); body['class']=['detail-body']
    for block in blocks:
        h=soup.new_tag('h4'); h.string=block['label']; p=soup.new_tag('p'); p.string=block['text']; body.append(h); body.append(p)
    details.append(body); return details
def main():
    if len(sys.argv)!=2: raise SystemExit('usage: backfill_historical_archive.py YYYY-MM-DD')
    date=sys.argv[1]; page=ROOT/date/'index.html'
    if not page.exists(): raise SystemExit(f'archive missing: {page}')
    soup=BeautifulSoup(page.read_text('utf-8'),'html.parser'); cards=soup.select('article.news')
    if not cards: raise SystemExit(f'no legacy archive cards found for {date}')
    source_to_id,source_dates=known_identity(); records={}; visuals={}; order=[]
    for card in cards:
        heading=card.find(['h3','h4','h2']); source=card.find('a',class_='source')
        if not heading or not source or not source.get('href'): continue
        title=norm(heading.get_text(' ',strip=True)); source_url=norm_url(source.get('href')); rid=source_to_id.get(source_url) or generated_id(source_url); source_to_id[source_url]=rid
        in_top=card.find_parent('section',id='top') is not None; blocks=extract_blocks(card); card['data-intel-id']=rid; card['data-intel-role']='card'; source['rel']='noopener noreferrer'; source['target']='_blank'
        old=card.find('details'); new=render_details(soup,blocks); old.replace_with(new) if old else source.insert_before(new)
        if rid not in records:
            rec={'id':rid,'slot':'top' if in_top else 'more','full_analysis':blocks,'source_url':source_url}; prior=sorted(d for d in source_dates.get(source_url,[]) if d<date)
            if prior: rec['status']='UPDATE'; rec['delta']=f'Historical backfill: same canonical source already appeared on {prior[-1]}; this record preserves the archived {date} snapshot.'
            records[rid]=rec; order.append(rid); visuals[rid]={'enabled':True,'source_url':source_url,'label':'HISTORICAL SOURCE VISUAL','confidence':'medium','keywords':keywords(title)}
        elif in_top: records[rid]['slot']='top'
    top_ids=[]
    for card in soup.select('#top article.news[data-intel-id]'):
        rid=card.get('data-intel-id')
        if rid not in top_ids: top_ids.append(rid)
    if len(top_ids)!=5: raise SystemExit(f'{date}: expected 5 unique TOP cards, got {len(top_ids)}')
    canonical_ids=top_ids+[rid for rid in order if rid not in top_ids]
    visual_scope=set(canonical_ids[:11])
    for rid in canonical_ids:
        if rid not in visual_scope:
            visuals[rid]={'enabled':False,'reason':'Historical backfill limits extraction to TOP 5 + first 6 unique supplemental intelligence items.'}
    data={'date':date,'schema_version':2,'render_revision':1,'identity_provenance':'historical-backfill','backfilled_from':f'{date}/index.html','visual_evidence':{rid:visuals[rid] for rid in canonical_ids},'items':[records[rid] for rid in canonical_ids]}
    out=ROOT/'data'/'daily'/f'{date}.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    token=f"{date.replace('-','')}-r1"; text=soup.prettify()
    for asset in ('../styles.css','../daily.css','../daily.js'): text=re.sub(rf'({re.escape(asset)})\?v=[^\"\']+',rf'\1?v={token}',text)
    page.write_text(text,'utf-8'); print(f'backfilled {date}: {len(canonical_ids)} canonical intelligence IDs; TOP={len(top_ids)}; visual_scope={len(visual_scope)}')
    return 0
if __name__=='__main__': raise SystemExit(main())
