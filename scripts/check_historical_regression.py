#!/usr/bin/env python3
"""Read-only historical regression matrix with schema-v3 V2 compatibility."""
from __future__ import annotations
import argparse,json,re,shutil,subprocess,sys,tempfile
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$'); errors=[]; rows=[]
def fail(date,message): errors.append(f'{date}: {message}')
def archive_dirs(root): return sorted(p for p in root.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
def canonical_dates(): return sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))

def validate_archive_snapshot(d,all_dirs):
    date=d.name; text=(d/'index.html').read_text('utf-8'); soup=BeautifulSoup(text,'html.parser'); body=soup.body
    if body is None: fail(date,'missing body'); rows.append((date,'snapshot','FAIL')); return
    if 'null' in text.lower(): fail(date,'literal null present')
    if 'archive-page' not in body.get('class',[]): fail(date,'missing archive-page class')
    if body.get('data-report-date')!=date: fail(date,'data-report-date mismatch')
    if not soup.find('link',href=re.compile(r'\.\./styles\.css\?v=')): fail(date,'missing cache-busted styles.css')
    if not soup.find('link',href=re.compile(r'\.\./daily\.css\?v=')): fail(date,'missing cache-busted daily.css')
    if not soup.find('script',src=re.compile(r'\.\./daily\.js\?v=')): fail(date,'missing cache-busted daily.js')
    if soup.find('script',src=re.compile(r'accordion\.js')): fail(date,'legacy accordion.js referenced')
    if len(soup.select('#top .news'))!=5: fail(date,f'TOP card count must be 5, got {len(soup.select("#top .news"))}')
    if not soup.find('details'): fail(date,'no expandable Full Analysis/details content')
    for a in soup.find_all('a',target='_blank'):
        if not {'noopener','noreferrer'}<=set(a.get('rel',[])): fail(date,'unsafe target=_blank link'); break
    idx=all_dirs.index(d); expected_prev=all_dirs[idx-1].name if idx else ''; expected_next=all_dirs[idx+1].name if idx+1<len(all_dirs) else ''
    if body.get('data-previous','')!=expected_prev: fail(date,f'previous mismatch: expected {expected_prev!r}')
    if body.get('data-next','')!=expected_next: fail(date,f'next mismatch: expected {expected_next!r}')
    manifest=ROOT/'assets'/'visual'/date/'manifest.json'
    if manifest.exists():
        data=json.loads(manifest.read_text('utf-8'))
        if data.get('date')!=date: fail(date,'date-scoped visual manifest date mismatch')
        for entry in data.get('entries',[]):
            if entry.get('status')=='ok':
                asset=entry.get('asset_path')
                if not asset or not (ROOT/asset.lstrip('/')).exists(): fail(date,f'visual asset missing: {asset}')
    rows.append((date,'snapshot','PASS' if not any(e.startswith(date+':') for e in errors) else 'FAIL'))

def validate_home_archive_links(all_dirs,root=ROOT):
    soup=BeautifulSoup((root/'index.html').read_text('utf-8'),'html.parser')
    marker=soup.select_one('.week-asof'); current=marker.get_text(' ',strip=True) if marker else ''
    known={d.name for d in all_dirs}
    if current not in known: current=all_dirs[-1].name if all_dirs else ''
    expected=[d.name for d in reversed(all_dirs) if d.name!=current]; actual=[]
    for a in soup.select('.history-list a[href]'):
        m=re.fullmatch(r'(20\d{2}-\d{2}-\d{2})/?',a.get('href',''))
        if m: actual.append(m.group(1))
    if actual!=expected: fail('home',f'history archive list mismatch: expected prior archives {expected}, got {actual}')
    entry=soup.select_one('.current-report-entry')
    if current and (not entry or entry.get('data-current-report-date')!=current or not entry.select_one(f'a.current-report-link[href="{current}/"]')):
        fail('home',f'current report entry missing or mismatched for {current}')

def selected_ids(data):
    if int(data.get('schema_version',0))>=3:
        ordered=sorted(data.get('items',[]),key=lambda x:int(x.get('rank_global',10**9)))
        return [x['id'] for x in ordered if x.get('homepage_tier') in {'top5','next10'}]
    return [x['id'] for x in data.get('items',[])]

def validate_canonical_archive_parity(date):
    canonical=ROOT/'data'/'daily'/f'{date}.json'; archive=ROOT/date/'index.html'
    if not canonical.exists() or not archive.exists(): return
    data=json.loads(canonical.read_text('utf-8')); expected=selected_ids(data); soup=BeautifulSoup(archive.read_text('utf-8'),'html.parser')
    cards=soup.select('#top [data-intel-role="card"][data-intel-id], #more [data-intel-role="card"][data-intel-id]')
    actual=[c.get('data-intel-id') for c in cards if c.get('data-intel-id') in expected]
    if actual!=expected: fail(date,f'archive/canonical selected ID order mismatch: expected {expected}, got {actual}'); rows.append((date,'canonical-parity','FAIL')); return
    rows.append((date,'canonical-parity','PASS'))

def run(work,*cmd):
    proc=subprocess.run(cmd,cwd=work,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT); print(f"$ {' '.join(cmd)}"); print(proc.stdout,end='' if proc.stdout.endswith('\n') else '\n')
    if proc.returncode: raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")

def canonical_rebuild_simulation(date):
    cds=canonical_dates()
    if date not in cds: rows.append((date,'canonical-rebuild','SKIP (legacy snapshot: no canonical JSON)')); return
    if date!=cds[-1]: validate_canonical_archive_parity(date); rows.append((date,'canonical-rebuild','SKIP (older canonical date; archive parity used)')); return
    with tempfile.TemporaryDirectory(prefix=f'ai3d-regression-{date}-') as td:
        work=Path(td)/'repo'; shutil.copytree(ROOT,work,ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache'))
        try:
            if date=='2026-08-23': run(work,sys.executable,'scripts/bootstrap_intelligence_ids.py')
            run(work,sys.executable,'scripts/check_release_input.py',date)
            run(work,sys.executable,'scripts/render_daily_navigation.py')
            run(work,sys.executable,'scripts/render_home_archive_links.py')
            run(work,sys.executable,'scripts/render_information_architecture.py',date)
            run(work,sys.executable,'scripts/build_intelligence.py',date)
            run(work,sys.executable,'scripts/inject_visual_previews.py',date)
            run(work,sys.executable,'scripts/apply_cache_bust.py',date)
            run(work,sys.executable,'scripts/check_intelligence_contract.py')
            run(work,sys.executable,'scripts/check_visual_contract.py',date)
            run(work,sys.executable,'scripts/check_home_contract.py')
            run(work,sys.executable,'scripts/check_daily_contract.py')
            run(work,sys.executable,'scripts/check_information_architecture.py',date)
            before=len(errors)
            validate_home_archive_links(archive_dirs(work),root=work)
            if len(errors)!=before: raise RuntimeError('rebuilt homepage archive contract failed')
        except Exception as exc:
            fail(date,f'canonical rebuild simulation failed: {exc}'); rows.append((date,'canonical-rebuild','FAIL'))
        else: rows.append((date,'canonical-rebuild','PASS'))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--days',type=int,default=4); args=ap.parse_args(); all_dirs=archive_dirs(ROOT)
    if not all_dirs: print('HISTORICAL REGRESSION FAILED: no archive directories'); return 1
    selected=all_dirs[-max(1,args.days):]; print('Historical regression archives:',', '.join(d.name for d in selected))
    for d in selected: validate_archive_snapshot(d,all_dirs)
    for d in selected: canonical_rebuild_simulation(d.name)
    print('\nHISTORICAL REGRESSION MATRIX')
    for date,mode,status in rows: print(f'- {date:<10} | {mode:<17} | {status}')
    if errors:
        print('\nHISTORICAL REGRESSION FAILED'); [print('-',e) for e in errors]; return 1
    print('\nHISTORICAL REGRESSION PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
