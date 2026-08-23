#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; errors=[]
def norm(s): return re.sub(r'\s+',' ',s).strip()
dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
for date in dates:
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8')); recs={x['id']:x for x in data['items']}
    if date==dates[-1]:
        views=[('home',ROOT/'index.html'),('daily',ROOT/date/'index.html')]
    else: views=[('daily',ROOT/date/'index.html')]
    seen={}
    for name,path in views:
        soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); seen[name]={}
        for card in soup.select('[data-intel-id]'):
            rid=card.get('data-intel-id'); details=card.find('details');
            if rid in recs and details: seen[name][rid]=norm(details.get_text(' ',strip=True).replace('完整分析','',1))
        missing=set(recs)-set(seen[name]);
        if missing: errors.append(f'{date} {name}: missing canonical IDs: {sorted(missing)}')
    if len(views)==2:
        for rid in recs:
            if seen['home'].get(rid)!=seen['daily'].get(rid): errors.append(f'{date}: Full Analysis drift for {rid}')
    for rid,r in recs.items():
        if len(r.get('full_analysis',[]))<3: errors.append(f'{date}: {rid} full_analysis must have >=3 structured blocks')
if errors:
    print('INTELLIGENCE CONTRACT FAILED');print('\n'.join('- '+e for e in errors));sys.exit(1)
print('INTELLIGENCE CONTRACT PASS')
