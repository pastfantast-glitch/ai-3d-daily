#!/usr/bin/env python3
"""Apply deterministic cache tokens to Homepage, Daily and V2 category assets."""
from pathlib import Path
import json, re, sys

ROOT=Path(__file__).resolve().parents[1]

def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def replace_asset(text, asset, token):
    pattern=rf'({re.escape(asset)})(?:\?v=[^"\']+)?'
    return re.sub(pattern, rf'\1?v={token}', text)

def apply(path, assets, token):
    if not path.exists(): raise SystemExit(f'missing page for cache bust: {path}')
    text=path.read_text('utf-8'); old=text
    for asset in assets: text=replace_asset(text,asset,token)
    missing=[asset for asset in assets if f'{asset}?v={token}' not in text]
    if missing: raise SystemExit(f"cache bust verification failed for {path.relative_to(ROOT)}: {', '.join(missing)}")
    if text!=old: path.write_text(text,'utf-8')
    print(path.relative_to(ROOT), token)

def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    rev=int(data.get('render_revision',1)); token=f"{date.replace('-','')}-r{rev}"
    # Homepage uses the split home design-system stylesheets; do not require the
    # legacy global styles.css when the homepage no longer references it.
    apply(ROOT/'index.html',['shared-components.css','home.css','home-content.css','home-components.css','home.js'],token)
    apply(ROOT/date/'index.html',['../styles.css','../shared-components.css','../daily.css','../daily.js'],token)
    if int(data.get('schema_version',0))>=3:
        for path in sorted((ROOT/date).glob('*/index.html')):
            apply(path,['../../styles.css','../../shared-components.css','../../category.css'],token)

if __name__=='__main__': main()
