#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def norm(s):
    return ' '.join((s or '').split())


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: check_archive_backfill.py YYYY-MM-DD')
    date = sys.argv[1]
    data_path = ROOT/'data'/'daily'/f'{date}.json'
    page_path = ROOT/date/'index.html'
    manifest_path = ROOT/'assets'/'visual'/date/'manifest.json'
    errors=[]
    if not data_path.exists(): errors.append('canonical JSON missing')
    if not page_path.exists(): errors.append('archive page missing')
    if errors:
        print('ARCHIVE BACKFILL CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); return 1
    data=json.loads(data_path.read_text('utf-8'))
    soup=BeautifulSoup(page_path.read_text('utf-8'),'html.parser')
    if data.get('date') != date: errors.append('canonical date mismatch')
    items=data.get('items',[]); recs={x['id']:x for x in items}
    top=[x for x in items if x.get('slot')=='top']
    if len(top)!=5: errors.append(f'canonical TOP must be 5, got {len(top)}')
    if len(recs)!=len(items): errors.append('canonical IDs must be unique')
    cards=soup.select('[data-intel-role="card"][data-intel-id]')
    seen=set()
    for card in cards:
        rid=card.get('data-intel-id')
        if rid not in recs: errors.append(f'page contains non-canonical ID {rid}'); continue
        seen.add(rid)
        details=card.find('details'); body=details.find('div',class_='detail-body') if details else None
        if not body: errors.append(f'{rid}: missing Full Analysis detail-body'); continue
        hs=body.find_all('h4',recursive=False); ps=body.find_all('p',recursive=False); blocks=recs[rid].get('full_analysis',[])
        if len(blocks)<3: errors.append(f'{rid}: canonical full_analysis <3 blocks')
        if len(hs)!=len(blocks) or len(ps)!=len(blocks): errors.append(f'{rid}: rendered semantic block count mismatch'); continue
        for i,b in enumerate(blocks):
            if norm(hs[i].get_text(' ',strip=True))!=norm(b.get('label')): errors.append(f'{rid}: heading mismatch {i+1}')
            if norm(ps[i].get_text(' ',strip=True))!=norm(b.get('text')): errors.append(f'{rid}: paragraph mismatch {i+1}')
    missing=set(recs)-seen
    if missing: errors.append(f'canonical IDs missing from archive: {sorted(missing)}')

    enabled={k:v for k,v in (data.get('visual_evidence') or {}).items() if v.get('enabled',True) is not False}
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text('utf-8'))
        if manifest.get('date')!=date: errors.append('visual manifest date mismatch')
        entries={x['id']:x for x in manifest.get('entries',[])}
        missing_attempt=set(enabled)-set(entries)
        if missing_attempt: errors.append(f'visual IDs not attempted: {sorted(missing_attempt)}')
        for rid,rec in entries.items():
            if rid not in enabled: errors.append(f'visual manifest orphan ID: {rid}'); continue
            if rec.get('page_url')!=enabled[rid].get('source_url'): errors.append(f'{rid}: visual source drift')
            if rec.get('status')=='ok':
                asset=ROOT/rec.get('asset_path','')
                if not asset.exists(): errors.append(f'{rid}: local visual asset missing')
                matches=soup.select(f'[data-intel-role="card"][data-intel-id="{rid}"]')
                for card in matches:
                    fig=card.find('figure',class_='case-preview')
                    if not fig: errors.append(f'{rid}: successful visual not injected into archive'); break
                    img=fig.find('img'); expected='../'+rec['asset_path']
                    if not img or img.get('src')!=expected: errors.append(f'{rid}: archive visual path mismatch'); break
            elif not rec.get('error'):
                errors.append(f'{rid}: missing visual needs diagnostic reason')
    elif enabled:
        errors.append('date-scoped visual manifest missing')

    if errors:
        print('ARCHIVE BACKFILL CONTRACT FAILED')
        print('\n'.join('- '+e for e in errors)); return 1
    ok_count=0
    if manifest_path.exists():
        ok_count=sum(x.get('status')=='ok' for x in json.loads(manifest_path.read_text('utf-8')).get('entries',[]))
    print(f'ARCHIVE BACKFILL CONTRACT PASS {date}: {len(recs)} intelligence IDs, visuals={ok_count}/{len(enabled)}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
