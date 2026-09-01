#!/usr/bin/env python3
from pathlib import Path
import json,sys
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset, homepage_groups

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'ok','blocked','no_candidate','too_small','not_image','http_error','identity_uncertain'}
def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def assert_preview(errors,view,path,prefix,intel_id,rec):
    if not path.exists(): errors.append(f'{view}: page missing'); return
    soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    card=soup.select_one(f'[data-intel-role="card"][data-intel-id="{intel_id}"]')
    if not card: errors.append(f'{view}: {intel_id} card missing'); return
    fig=card.find('figure',class_='case-preview')
    if not fig: errors.append(f'{view}: {intel_id} extracted visual not rendered'); return
    if fig.get('data-intel-id')!=intel_id or fig.get('data-intel-role')!='visual': errors.append(f'{view}: {intel_id} preview identity/role mismatch')
    img=fig.find('img'); expected=f"{prefix}{rec['asset_path']}"
    if not img or img.get('src')!=expected: errors.append(f'{view}: {intel_id} preview asset mismatch: {img.get("src") if img else None} != {expected}')

def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date(); data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    enabled={k:v for k,v in (data.get('visual_evidence') or {}).items() if v.get('enabled',True) is not False}
    manifest_path=ROOT/'assets'/'visual'/'manifest.json'; snapshot_manifest=ROOT/'assets'/'visual'/date/'manifest.json'; errors=[]
    manifest=json.loads(manifest_path.read_text('utf-8')) if manifest_path.exists() else {'entries':[]}
    if not manifest_path.exists(): errors.append('assets/visual/manifest.json missing')
    if manifest.get('date')!=date: errors.append(f"manifest date mismatch: {manifest.get('date')} != {date}")
    if manifest.get('identity')!='data-intel-id': errors.append('manifest identity must be data-intel-id')
    if manifest.get('asset_versioning')!='daily-snapshot': errors.append('manifest asset_versioning must be daily-snapshot')
    if not snapshot_manifest.exists(): errors.append(f'per-date visual manifest missing: {snapshot_manifest.relative_to(ROOT)}')
    else:
        snap=json.loads(snapshot_manifest.read_text('utf-8'))
        if snap!=manifest: errors.append('per-date visual manifest differs from current manifest')
    entries={x['id']:x for x in manifest.get('entries',[])}
    unknown=set(entries)-set(enabled); missing=set(enabled)-set(entries)
    if unknown: errors.append(f'manifest contains non-canonical visual IDs: {sorted(unknown)}')
    if missing: errors.append(f'enabled visual IDs were not attempted: {sorted(missing)}')
    for intel_id in enabled:
        rec=entries.get(intel_id)
        if not rec: continue
        status=rec.get('status')
        if status not in ALLOWED: errors.append(f'{intel_id}: invalid/unresolved visual status {status!r}')
        if rec.get('page_url')!=enabled[intel_id].get('source_url'): errors.append(f'{intel_id}: source page drift')
        if status!='ok' and not rec.get('error'): errors.append(f'{intel_id}: missing visual must include explicit error reason')
    ok={k:v for k,v in entries.items() if v.get('status')=='ok'}
    for intel_id,rec in ok.items():
        asset_path=Path(rec.get('asset_path','')); asset=ROOT/asset_path
        if not asset.exists(): errors.append(f'{intel_id}: local asset missing: {asset}')
        expected_prefix=Path('assets')/'visual'/date
        try: asset_path.relative_to(expected_prefix)
        except Exception: errors.append(f'{intel_id}: asset must be date-versioned under {expected_prefix}')
    if is_v2_dataset(data):
        records={x['id']:x for x in data['items']}; top,next10=homepage_groups(data); selected={x['id'] for x in top+next10}
        for intel_id,rec in ok.items():
            item=records.get(intel_id)
            if not item: continue
            assert_preview(errors,f'category:{item["category"]}',ROOT/date/item['category']/'index.html','../../',intel_id,rec)
            if intel_id in selected:
                assert_preview(errors,'home',ROOT/'index.html','',intel_id,rec)
                assert_preview(errors,'daily',ROOT/date/'index.html','../',intel_id,rec)
    else:
        for intel_id,rec in ok.items():
            assert_preview(errors,'home',ROOT/'index.html','',intel_id,rec)
            assert_preview(errors,'daily',ROOT/date/'index.html','../',intel_id,rec)
    attempted=len(enabled); success=len(ok)
    print(f'VISUAL COVERAGE {date}: {success}/{attempted} canonical candidates')
    for intel_id in enabled:
        rec=entries.get(intel_id,{})
        print(f" - {intel_id}: {rec.get('status','not_attempted')} candidates={rec.get('candidate_count',0)} reason={rec.get('error','')}")
    if errors:
        print('VISUAL CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
    print('VISUAL CONTRACT PASS')
if __name__=='__main__': main()
