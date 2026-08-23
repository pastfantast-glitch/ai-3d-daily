#!/usr/bin/env python3
"""Treat canonical daily history as the Published Intelligence Registry.

No third registry file is maintained. Reusing a stable ID on a later date means
an UPDATE and requires a non-empty delta. Reusing the same source URL under a
new ID is identity drift and fails publication.
"""
from pathlib import Path
import json, re, sys
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
errors=[]
history={}
source_owner={}

def norm_url(url):
    return (url or '').strip().rstrip('/')

for data_path in sorted((ROOT/'data'/'daily').glob('20??-??-??.json')):
    date=data_path.stem
    data=json.loads(data_path.read_text('utf-8'))
    daily_path=ROOT/date/'index.html'
    source_by_id={}
    if daily_path.exists():
        soup=BeautifulSoup(daily_path.read_text('utf-8'),'html.parser')
        for card in soup.select('[data-intel-role="card"][data-intel-id]'):
            a=card.select_one('a.source[href]')
            if a: source_by_id[card.get('data-intel-id')]=norm_url(a.get('href'))

    for item in data.get('items',[]):
        rid=str(item.get('id','')).strip()
        if not rid: continue
        prior=history.get(rid,[])
        if prior:
            status=str(item.get('status','')).strip().upper()
            delta=str(item.get('delta','')).strip()
            if status!='UPDATE':
                errors.append(f'{date}: repeated stable ID {rid} must declare status=UPDATE')
            if not delta:
                errors.append(f'{date}: repeated stable ID {rid} requires non-empty delta')
        history.setdefault(rid,[]).append(date)

        source=source_by_id.get(rid) or norm_url(item.get('source_url'))
        if source:
            owner=source_owner.get(source)
            if owner and owner!=rid:
                errors.append(f'{date}: source identity drift: {source} was {owner}, now {rid}')
            else:
                source_owner[source]=rid

if errors:
    print('PUBLISHED REGISTRY CONTRACT FAILED')
    print('\n'.join('- '+e for e in errors))
    sys.exit(1)
print(f'PUBLISHED REGISTRY CONTRACT PASS: {len(history)} stable IDs / {len(source_owner)} sources')
