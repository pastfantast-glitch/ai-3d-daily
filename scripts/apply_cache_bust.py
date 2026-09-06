#!/usr/bin/env python3
"""Apply deterministic cache tokens and compact rating presentation."""
from pathlib import Path
import json, re, sys

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE_REV='workspace-v5'
QUICK_IMPACT_RE=re.compile(
    r'(<div\b[^>]*class="[^"]*\bquick-impact\b[^"]*"[^>]*>\s*<span\b[^>]*>\s*)'
    r'([★☆]{1,5})(?:[^<]*)(\s*</span>)',
    re.S,
)

def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def replace_asset(text, asset, token):
    pattern=rf'({re.escape(asset)})(?:\?v=[^"\']+)?'
    return re.sub(pattern, rf'\1?v={token}', text)

def normalize_quick_impact(text, path):
    """Render quick_impact as rating only, including legacy stars+commentary data."""
    def repl(match):
        return match.group(1)+match.group(2)+match.group(3)
    normalized,count=QUICK_IMPACT_RE.subn(repl,text)
    # Fail closed if a generated quick-impact exists but no leading star rating
    # can be recognized. Legacy prose is allowed only after a valid star prefix.
    if 'quick-impact' in text:
        unmatched=re.findall(
            r'<div\b[^>]*class="[^"]*\bquick-impact\b[^"]*"[^>]*>\s*<span\b[^>]*>(.*?)</span>',
            normalized,
            re.S,
        )
        invalid=[re.sub(r'<[^>]+>','',x).strip() for x in unmatched if not re.fullmatch(r'\s*[★☆]{1,5}\s*',re.sub(r'<[^>]+>','',x))]
        if invalid:
            raise SystemExit(f'quick impact presentation missing stars-only rating in {path.relative_to(ROOT)}: {invalid[0]!r}')
    return normalized,count

def apply(path, assets, token):
    if not path.exists(): raise SystemExit(f'missing page for cache bust: {path}')
    text=path.read_text('utf-8'); old=text
    text,normalized=normalize_quick_impact(text,path)
    for asset in assets: text=replace_asset(text,asset,token)
    missing=[asset for asset in assets if f'{asset}?v={token}' not in text]
    if missing: raise SystemExit(f"cache bust verification failed for {path.relative_to(ROOT)}: {', '.join(missing)}")
    if text!=old: path.write_text(text,'utf-8')
    print(path.relative_to(ROOT), token, f'quick-impact-normalized={normalized}')

def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    rev=int(data.get('render_revision',1)); token=f"{date.replace('-','')}-r{rev}-{WORKSPACE_REV}"
    # Homepage uses the split home design-system stylesheets; do not require the
    # legacy global styles.css when the homepage no longer references it.
    apply(ROOT/'index.html',['shared-components.css','home.css','home-content.css','home-components.css','home.js'],token)
    apply(ROOT/date/'index.html',['../styles.css','../shared-components.css','../daily.css','../daily.js','../archive-nav-state.js'],token)
    if int(data.get('schema_version',0))>=3:
        for path in sorted((ROOT/date).glob('*/index.html')):
            apply(path,['../../styles.css','../../shared-components.css','../../category.css','../../archive-nav-state.js'],token)

if __name__=='__main__': main()
