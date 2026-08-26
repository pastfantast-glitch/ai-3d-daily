#!/usr/bin/env python3
import json, sys
from pathlib import Path
from bs4 import BeautifulSoup
from normalize_archive_presentation import main as normalize_archive_presentation

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'assets'/'visual'/'manifest.json'


def latest_date():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]


def asset_src(rec,prefix):
    return f"{prefix}{rec['asset_path']}"


def make_preview(soup,rec,prefix,is_archive=False):
    classes='case-preview daily-visual' if is_archive else 'case-preview'
    fig=soup.new_tag('figure',attrs={'class':classes,'data-visual-id':rec['id'],'data-intel-id':rec['id'],'data-intel-role':'visual'})
    a=soup.new_tag('a',href=rec['page_url'],target='_blank',rel='noopener noreferrer',title='開啟原始案例')
    img=soup.new_tag('img',src=asset_src(rec,prefix),alt=f"{rec.get('label','SOURCE PREVIEW')} preview",loading='lazy',decoding='async')
    img['onerror']="this.closest('.case-preview').style.display='none'"
    a.append(img); fig.append(a)
    cap=soup.new_tag('figcaption'); badge=soup.new_tag('span'); badge.string=rec.get('label','SOURCE PREVIEW')
    cap.append(badge); cap.append(' · Local visual evidence · 點圖開啟原始來源')
    fig.append(cap); return fig


def inject(path,prefix,records,is_archive=False):
    soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); changed=False
    cards=soup.select('[data-intel-role="card"][data-intel-id]')
    for card in cards:
        intel_id=card.get('data-intel-id'); rec=records.get(intel_id)

        # Canonicalize preview DOM by removing every pre-existing preview first.
        # This avoids stale/duplicate template previews and guarantees that the
        # single injected visual is placed immediately before quick-impact.
        existing_previews=list(card.select('figure.case-preview'))
        if existing_previews:
            for preview in existing_previews:
                preview.decompose()
            changed=True

        if not rec:
            continue

        preview=make_preview(soup,rec,prefix,is_archive=is_archive)
        # quick-impact is a semantic class, not a fixed HTML tag. Homepage uses
        # <p class="quick-impact"> while archive templates may use other tags.
        impact=card.select_one('.quick-impact')
        if impact:
            impact.insert_before(preview)
        else:
            details=card.find('details')
            if details:
                details.insert_before(preview)
            else:
                card.append(preview)
        changed=True

    if changed: path.write_text(soup.prettify(),'utf-8')
    return changed


def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    if not MANIFEST.exists(): raise SystemExit('visual manifest missing; run extract_visual_assets.py first')
    manifest=json.loads(MANIFEST.read_text('utf-8'))
    if manifest.get('date')!=date: raise SystemExit(f"visual manifest date mismatch: {manifest.get('date')} != {date}")
    if manifest.get('asset_versioning')!='daily-snapshot': raise SystemExit('visual manifest must use daily-snapshot asset versioning')
    records={x['id']:x for x in manifest.get('entries',[]) if x.get('status')=='ok'}
    changed=[]
    if inject(ROOT/'index.html','',records,is_archive=False): changed.append('index.html')
    daily=ROOT/date/'index.html'
    if daily.exists() and inject(daily,'../',records,is_archive=True): changed.append(str(daily.relative_to(ROOT)))

    # Visual injection is the last stage that may create new archive DOM nodes.
    # Re-normalize presentation afterwards so future new figures cannot bypass the
    # shared Daily Presentation Contract.
    normalize_archive_presentation()
    print('visual preview injection:',', '.join(changed) if changed else 'no markup changes',f'({len(records)} canonical visuals)')

if __name__=='__main__': main()
