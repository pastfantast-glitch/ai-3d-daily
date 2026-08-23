#!/usr/bin/env python3
"""Apply deterministic cache tokens to the current Homepage/Daily shell assets.

Token = YYYYMMDD-r<render_revision>. Re-running the same canonical revision is
idempotent; a new day or render revision gets a new URL without random churn.
"""
from pathlib import Path
import json, re, sys

ROOT=Path(__file__).resolve().parents[1]

def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def replace_asset(text, asset, token):
    pattern=rf'({re.escape(asset)})\?v=[^"\']+'
    return re.sub(pattern, rf'\1?v={token}', text)

def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    rev=int(data.get('render_revision',1))
    token=f"{date.replace('-','')}-r{rev}"
    targets=[
        (ROOT/'index.html', ['styles.css','home.css','home-content.css','home-components.css','home.js']),
        (ROOT/date/'index.html', ['../styles.css','../daily.css','../daily.js']),
    ]
    for path,assets in targets:
        if not path.exists(): raise SystemExit(f'missing page for cache bust: {path}')
        text=path.read_text('utf-8'); old=text
        for asset in assets: text=replace_asset(text,asset,token)
        if text!=old: path.write_text(text,'utf-8')
        print(path.relative_to(ROOT), token)

if __name__=='__main__': main()
