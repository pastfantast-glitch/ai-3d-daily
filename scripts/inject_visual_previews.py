#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'assets'/'visual'/'manifest.json'


def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]


def make_preview(soup,rec,prefix):
    fig=soup.new_tag('figure',attrs={'class':'case-preview','data-visual-id':rec['id'],'data-intel-id':rec['id']})
    a=soup.new_tag('a',href=rec['page_url'],target='_blank',rel='noopener noreferrer',title='開啟原始案例')
    asset_name=Path(rec['asset_path']).name
    img=soup.new_tag('img',src=f'{prefix}{asset_name}',alt=f"{rec.get('label','SOURCE PREVIEW')} preview",loading='lazy',decoding='async')
    img['onerror']="this.closest('.case-preview').style.display='none'"
    a.append(img); fig.append(a)
    cap=soup.new_tag('figcaption'); badge=soup.new_tag('span'); badge.string=rec.get('label','SOURCE PREVIEW')
    cap.append(badge); cap.append(' · Local visual evidence · 點圖開啟原始來源')
    fig.append(cap); return fig


def inject(path,prefix,records):
    soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); changed=False
    # Remove orphan preview markup from canonical cards; it can be re-added only by exact ID.
    for card in soup.select('[data-intel-id]'):
        intel_id=card.get('data-intel-id'); rec=records.get(intel_id)
        existing=card.find('figure',class_='case-preview',recursive=False) or card.find('figure',class_='case-preview')
        if not rec:
            if existing and existing.get('data-intel-id'):
                existing.decompose(); changed=True
            continue
        expected=f"{prefix}{Path(rec['asset_path']).name}"
        if existing:
            img=existing.find('img'); a=existing.find('a'); existing['data-visual-id']=intel_id; existing['data-intel-id']=intel_id
            if img and img.get('src')!=expected: img['src']=expected; changed=True
            if a and a.get('href')!=rec['page_url']: a['href']=rec['page_url']; changed=True
            continue
        preview=make_preview(soup,rec,prefix)
        impact=card.find('div',class_='quick-impact')
        if impact: impact.insert_before(preview)
        else:
            details=card.find('details')
            if details: details.insert_before(preview)
            else: card.append(preview)
        changed=True
    if changed: path.write_text(soup.prettify(),'utf-8')
    return changed


def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    if not MANIFEST.exists(): raise SystemExit('visual manifest missing; run extract_visual_assets.py first')
    manifest=json.loads(MANIFEST.read_text('utf-8'))
    if manifest.get('date')!=date: raise SystemExit(f"visual manifest date mismatch: {manifest.get('date')} != {date}")
    records={x['id']:x for x in manifest.get('entries',[]) if x.get('status')=='ok'}
    changed=[]
    if inject(ROOT/'index.html','assets/visual/',records): changed.append('index.html')
    daily=ROOT/date/'index.html'
    if daily.exists() and inject(daily,'../assets/visual/',records): changed.append(str(daily.relative_to(ROOT)))
    print('visual preview injection:',', '.join(changed) if changed else 'no markup changes',f'({len(records)} canonical visuals)')

if __name__=='__main__': main()
