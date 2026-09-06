#!/usr/bin/env python3
"""Apply deterministic cache tokens and compact labeled rating presentation."""
from pathlib import Path
import html
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
QUICK_IMPACT_CONFIG=ROOT/'config'/'quick-impact-contract.json'
WORKSPACE_REV='workspace-v6'
STAR_RE=re.compile(r'[★☆]{1,5}')
QUICK_IMPACT_SPAN_RE=re.compile(
    r'<div\b[^>]*class="[^"]*\bquick-impact\b[^"]*"[^>]*>\s*<span\b[^>]*>(.*?)</span>',
    re.S,
)

def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def replace_asset(text, asset, token):
    pattern=rf'({re.escape(asset)})(?:\?v=[^"\']+)?'
    return re.sub(pattern, rf'\1?v={token}', text)

def quick_impact_labels(data):
    cfg=json.loads(QUICK_IMPACT_CONFIG.read_text('utf-8'))
    if cfg.get('presentation')!='label_plus_rating':
        raise SystemExit('quick impact presentation contract must be label_plus_rating')
    labels=cfg.get('subtype_labels') or {}
    out={}
    for item in data.get('items') or []:
        intel_id=str(item.get('id') or '').strip(); subtype=str(item.get('subcategory') or '').strip()
        label=str(labels.get(subtype) or '').strip()
        if not intel_id or not label:
            raise SystemExit(f'quick impact label missing for {intel_id or "<missing-id>"}: subcategory={subtype!r}')
        out[intel_id]=label
    return out

def normalize_quick_impact(text, path, label_by_id):
    """Render each quick impact as one concise subtype label plus star rating."""
    normalized=0
    for intel_id,label in label_by_id.items():
        pattern=re.compile(
            rf'(<article\b(?=[^>]*\bdata-intel-id="{re.escape(intel_id)}")[^>]*>.*?'
            rf'<div\b[^>]*class="[^"]*\bquick-impact\b[^"]*"[^>]*>\s*<span\b[^>]*>)'
            rf'(.*?)(</span>)',
            re.S,
        )
        def repl(match):
            inner_text=re.sub(r'<[^>]+>','',match.group(2))
            stars=STAR_RE.search(html.unescape(inner_text))
            if not stars:
                raise SystemExit(f'quick impact presentation missing star rating for {intel_id} in {path.relative_to(ROOT)}')
            rendered=f'<b class="quick-impact-label">{html.escape(label)}</b> {stars.group(0)}'
            return match.group(1)+rendered+match.group(3)
        text,count=pattern.subn(repl,text,count=1)
        normalized+=count

    if 'quick-impact' in text:
        invalid=[]
        for inner in QUICK_IMPACT_SPAN_RE.findall(text):
            plain=html.unescape(re.sub(r'<[^>]+>','',inner)).strip()
            if not re.fullmatch(r'.+\s+[★☆]{1,5}',plain): invalid.append(plain)
        if invalid:
            raise SystemExit(f'quick impact presentation must be label + stars in {path.relative_to(ROOT)}: {invalid[0]!r}')
    return text,normalized

def apply(path, assets, token, label_by_id):
    if not path.exists(): raise SystemExit(f'missing page for cache bust: {path}')
    text=path.read_text('utf-8'); old=text
    text,normalized=normalize_quick_impact(text,path,label_by_id)
    for asset in assets: text=replace_asset(text,asset,token)
    missing=[asset for asset in assets if f'{asset}?v={token}' not in text]
    if missing: raise SystemExit(f"cache bust verification failed for {path.relative_to(ROOT)}: {', '.join(missing)}")
    if text!=old: path.write_text(text,'utf-8')
    print(path.relative_to(ROOT), token, f'quick-impact-labeled={normalized}')

def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    labels=quick_impact_labels(data)
    rev=int(data.get('render_revision',1)); token=f"{date.replace('-','')}-r{rev}-{WORKSPACE_REV}"
    apply(ROOT/'index.html',['shared-components.css','home.css','home-content.css','home-components.css','home.js'],token,labels)
    apply(ROOT/date/'index.html',['../styles.css','../shared-components.css','../daily.css','../daily.js','../archive-nav-state.js'],token,labels)
    if int(data.get('schema_version',0))>=3:
        for path in sorted((ROOT/date).glob('*/index.html')):
            apply(path,['../../styles.css','../../shared-components.css','../../category.css','../../archive-nav-state.js'],token,labels)

if __name__=='__main__': main()
