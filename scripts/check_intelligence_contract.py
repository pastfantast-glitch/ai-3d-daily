#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset, homepage_groups, category_items, load_config

ROOT=Path(__file__).resolve().parents[1]; errors=[]
def norm(s): return re.sub(r'\s+',' ',s).strip()
def canonical_text(record): return norm(' '.join(f"{b['label']} {b['text']}" for b in record['full_analysis']))

def inspect_cards(date,name,path,selector,recs,expected_ids):
    seen={}
    if not path.exists(): errors.append(f'{date} {name}: page missing'); return seen
    soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    for card in soup.select(selector):
        rid=card.get('data-intel-id')
        if rid not in recs: continue
        details=card.find('details'); body=details.find('div',class_='detail-body') if details else None
        if not details: errors.append(f'{date} {name}: {rid} missing Full Analysis details'); continue
        if not body: errors.append(f'{date} {name}: {rid} missing detail-body'); continue
        blocks=recs[rid].get('full_analysis',[]); headings=body.find_all('h4',recursive=False); paragraphs=body.find_all('p',recursive=False)
        if len(headings)!=len(blocks) or len(paragraphs)!=len(blocks): errors.append(f'{date} {name}: {rid} semantic block count mismatch')
        else:
            for i,block in enumerate(blocks):
                if norm(headings[i].get_text(' ',strip=True))!=norm(block['label']): errors.append(f'{date} {name}: {rid} heading mismatch at block {i+1}')
                if norm(paragraphs[i].get_text(' ',strip=True))!=norm(block['text']): errors.append(f'{date} {name}: {rid} paragraph mismatch at block {i+1}')
        rendered=norm(' '.join(x.get_text(' ',strip=True) for pair in zip(headings,paragraphs) for x in pair))
        if rendered!=canonical_text(recs[rid]): errors.append(f'{date} {name}: {rid} rendered Full Analysis differs from canonical data')
        seen[rid]=rendered
    missing=set(expected_ids)-set(seen)
    if missing: errors.append(f'{date} {name}: missing expected IDs: {sorted(missing)}')
    extra=set(seen)-set(expected_ids)
    if extra: errors.append(f'{date} {name}: unexpected IDs: {sorted(extra)}')
    return seen

dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
for date in dates:
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8')); recs={x['id']:x for x in data['items']}
    if is_v2_dataset(data):
        top,next10=homepage_groups(data); selected=[x['id'] for x in top+next10]
        daily=inspect_cards(date,'daily',ROOT/date/'index.html','#top .news[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]',recs,selected)
        if date==dates[-1]:
            home=inspect_cards(date,'home',ROOT/'index.html','.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]',recs,selected)
            for rid in selected:
                if home.get(rid)!=daily.get(rid): errors.append(f'{date}: home/daily Full Analysis drift for {rid}')
        for cat in load_config()['categories']:
            expected=[x['id'] for x in category_items(data,cat['id'])]
            inspect_cards(date,f'category:{cat["id"]}',ROOT/date/cat['id']/'index.html','.category-card[data-intel-role="card"][data-intel-id]',recs,expected)
    else:
        expected=list(recs)
        daily=inspect_cards(date,'daily',ROOT/date/'index.html','#top .news[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]',recs,expected)
        if date==dates[-1]:
            home=inspect_cards(date,'home',ROOT/'index.html','.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]',recs,expected)
            for rid in recs:
                if home.get(rid)!=daily.get(rid): errors.append(f'{date}: Full Analysis drift for {rid}')
    for rid,record in recs.items():
        if len(record.get('full_analysis',[]))<3: errors.append(f'{date}: {rid} full_analysis must have >=3 structured blocks')
        for i,block in enumerate(record.get('full_analysis',[]),1):
            if not block.get('label','').strip() or not block.get('text','').strip(): errors.append(f'{date}: {rid} block {i} requires non-empty label and text')
if errors:
    print('INTELLIGENCE CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
print('INTELLIGENCE CONTRACT PASS')
