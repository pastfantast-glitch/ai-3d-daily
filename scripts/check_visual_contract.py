#!/usr/bin/env python3
from pathlib import Path
import json,sys
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]

def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    enabled={k:v for k,v in (data.get('visual_evidence') or {}).items() if v.get('enabled',True) is not False}
    manifest_path=ROOT/'assets'/'visual'/'manifest.json'
    errors=[]
    if not manifest_path.exists():
        errors.append('assets/visual/manifest.json missing')
        manifest={'entries':[]}
    else:
        manifest=json.loads(manifest_path.read_text('utf-8'))
    if manifest.get('date')!=date:
        errors.append(f"manifest date mismatch: {manifest.get('date')} != {date}")
    entries={x['id']:x for x in manifest.get('entries',[])}
    unknown=set(entries)-set(enabled)
    if unknown: errors.append(f'manifest contains non-canonical visual IDs: {sorted(unknown)}')

    ok={k:v for k,v in entries.items() if v.get('status')=='ok'}
    for intel_id,rec in ok.items():
        asset=ROOT/rec.get('asset_path','')
        if not asset.exists(): errors.append(f'{intel_id}: local asset missing: {asset}')
        cfg=enabled[intel_id]
        if rec.get('page_url')!=cfg.get('source_url'): errors.append(f'{intel_id}: source page drift')

    for view,path in [('home',ROOT/'index.html'),('daily',ROOT/date/'index.html')]:
        if not path.exists(): errors.append(f'{view}: page missing'); continue
        soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
        for intel_id in ok:
            card=soup.select_one(f'[data-intel-id="{intel_id}"]')
            if not card: errors.append(f'{view}: {intel_id} card missing'); continue
            fig=card.find('figure',class_='case-preview')
            if not fig: errors.append(f'{view}: {intel_id} extracted visual not rendered'); continue
            if fig.get('data-intel-id')!=intel_id: errors.append(f'{view}: {intel_id} preview identity mismatch')
            img=fig.find('img')
            if not img or Path(img.get('src','')).name!=Path(ok[intel_id]['asset_path']).name:
                errors.append(f'{view}: {intel_id} preview asset mismatch')

    attempted=len(enabled); success=len(ok)
    print(f'VISUAL COVERAGE {date}: {success}/{attempted} canonical candidates')
    for intel_id,cfg in enabled.items():
        rec=entries.get(intel_id,{})
        if rec.get('status')!='ok': print(f' - missing: {intel_id} ({rec.get("error","not extracted")})')
    if errors:
        print('VISUAL CONTRACT FAILED')
        print('\n'.join('- '+e for e in errors)); sys.exit(1)
    print('VISUAL CONTRACT PASS')

if __name__=='__main__': main()
