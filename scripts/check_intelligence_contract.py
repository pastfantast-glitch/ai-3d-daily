#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
errors=[]

def norm(s):
    return re.sub(r'\s+',' ',s).strip()

def canonical_text(record):
    return norm(' '.join(f"{b['label']} {b['text']}" for b in record['full_analysis']))

dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
for date in dates:
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    recs={x['id']:x for x in data['items']}
    views=[('daily',ROOT/date/'index.html')]
    if date==dates[-1]:
        views.insert(0,('home',ROOT/'index.html'))

    seen={}
    for name,path in views:
        soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
        seen[name]={}
        for card in soup.select('[data-intel-id]'):
            rid=card.get('data-intel-id')
            if rid not in recs:
                continue
            details=card.find('details')
            if not details:
                errors.append(f'{date} {name}: {rid} missing Full Analysis details')
                continue
            body=details.find('div',class_='detail-body')
            if not body:
                errors.append(f'{date} {name}: {rid} missing detail-body')
                continue

            blocks=recs[rid].get('full_analysis',[])
            headings=body.find_all('h4',recursive=False)
            paragraphs=body.find_all('p',recursive=False)
            if len(headings)!=len(blocks) or len(paragraphs)!=len(blocks):
                errors.append(f'{date} {name}: {rid} semantic block count mismatch')
            else:
                for i,block in enumerate(blocks):
                    if norm(headings[i].get_text(' ',strip=True))!=norm(block['label']):
                        errors.append(f'{date} {name}: {rid} heading mismatch at block {i+1}')
                    if norm(paragraphs[i].get_text(' ',strip=True))!=norm(block['text']):
                        errors.append(f'{date} {name}: {rid} paragraph mismatch at block {i+1}')

            rendered=norm(' '.join(x.get_text(' ',strip=True) for pair in zip(headings,paragraphs) for x in pair))
            expected=canonical_text(recs[rid])
            if rendered!=expected:
                errors.append(f'{date} {name}: {rid} rendered Full Analysis differs from canonical data')
            seen[name][rid]=rendered

        missing=set(recs)-set(seen[name])
        if missing:
            errors.append(f'{date} {name}: missing canonical IDs: {sorted(missing)}')

    if len(views)==2:
        for rid in recs:
            if seen.get('home',{}).get(rid)!=seen.get('daily',{}).get(rid):
                errors.append(f'{date}: Full Analysis drift for {rid}')

    for rid,record in recs.items():
        if len(record.get('full_analysis',[]))<3:
            errors.append(f'{date}: {rid} full_analysis must have >=3 structured blocks')
        for i,block in enumerate(record.get('full_analysis',[]),1):
            if not block.get('label','').strip() or not block.get('text','').strip():
                errors.append(f'{date}: {rid} block {i} requires non-empty label and text')

if errors:
    print('INTELLIGENCE CONTRACT FAILED')
    print('\n'.join('- '+e for e in errors))
    sys.exit(1)
print('INTELLIGENCE CONTRACT PASS')
