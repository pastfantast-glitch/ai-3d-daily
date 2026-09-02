#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'index.html'; FOUNDATION=ROOT/'home.css'; UI=ROOT/'home-content.css'; COMPONENTS=ROOT/'home-components.css'; SHARED=ROOT/'shared-components.css'; JS=ROOT/'home.js'
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$'); errors=[]
def fail(msg): errors.append(msg)
def archive_dates(): return sorted(p.name for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())

def latest_data():
    paths=sorted((ROOT/'data'/'daily').glob('20??-??-??.json'))
    return json.loads(paths[-1].read_text('utf-8')) if paths else {}

if not INDEX.exists(): fail('index.html missing')
else:
    html=INDEX.read_text('utf-8'); soup=BeautifulSoup(html,'html.parser'); data=latest_data(); v2=is_v2_dataset(data)
    for asset in ('shared-components.css?v=','home.css?v=','home-content.css?v=','home-components.css?v=','home.js?v='):
        if asset not in html: fail(f'index.html missing cache-busted asset: {asset}')
    sections=soup.select('main.home-main > section.home-section')
    expected=['today-section','more-section','category-section','history-section'] if v2 else ['today-section','more-section','test-section','history-section']
    actual=[]
    for section in sections:
        classes=set(section.get('class',[])); matched=[x for x in expected if x in classes]; actual.append(matched[0] if len(matched)==1 else '?')
    if actual!=expected: fail(f'homepage section order drift: {actual} != {expected}')
    top=soup.select('.top-item'); more=soup.select('.more-card')
    if len(top)!=5: fail(f'homepage must contain exactly 5 TOP cards, got {len(top)}')
    if v2:
        if len(more)!=10: fail(f'V2 homepage must contain exactly 10 next items, got {len(more)}')
        if len(soup.select('.category-nav-card[href]'))!=6: fail('V2 homepage must expose exactly six category navigation cards')
        if soup.select('.week-counts,.week-summary,.week-topic'): fail('V2 homepage must not contain weekly overview UI')
    elif not 6<=len(more)<=12: fail(f'legacy Supplemental cards must be 6-12, got {len(more)}')
    if soup.select('[data-supplemental-id]'): fail('stale supplemental cards must not exist')
    histories=soup.select('.history-list')
    if len(histories)!=1: fail(f'homepage must contain one history-list, got {len(histories)}')
    else:
        expected_archives=list(reversed(archive_dates())); actual_archives=[]
        for a in histories[0].select('a[href]'):
            m=re.fullmatch(r'(20\d{2}-\d{2}-\d{2})/?',a.get('href',''))
            if m: actual_archives.append(m.group(1))
        if actual_archives!=expected_archives: fail('history-list must exactly match real archives newest-first')
        if len(soup.select('.history-controls'))!=1: fail('history library must expose exactly one control panel')
        if len(soup.select('.history-search[type="search"]'))!=1: fail('history library search missing')
        if not soup.select('.archive-year .archive-month .history-entry'): fail('history library must use year/month accordion entries')
        category_filters=soup.select('[data-history-category]')
        if v2 and len(category_filters)!=7: fail(f'V2 history library must expose all + six category filters, got {len(category_filters)}')
        if len(soup.select('[data-history-range]'))!=3: fail('history library must expose 7/30/all date range filters')
    for label,cards in [('TOP',top),('Next10' if v2 else 'Supplemental',more)]:
        for card in cards:
            rid=card.get('data-intel-id','?')
            if card.get('data-intel-role')!='card': fail(f'{label} {rid}: missing role=card')
            details=card.select_one('details.home-full-analysis'); body=card.select_one('details.home-full-analysis .detail-body.home-analysis-body')
            impact=card.select_one('.quick-impact'); source=card.select_one('a.source[href]')
            if not details: fail(f'{label} {rid}: missing home-full-analysis')
            if not body: fail(f'{label} {rid}: missing home-analysis-body')
            if not impact: fail(f'{label} {rid}: missing quick-impact')
            if not source: fail(f'{label} {rid}: missing source')
            descendants=list(card.descendants)
            def pos(node):
                try: return descendants.index(node)
                except ValueError: return -1
            preview=card.select_one('figure.case-preview')
            if preview:
                if preview.get('data-intel-role')!='visual' or preview.get('data-intel-id')!=rid: fail(f'{label} {rid}: visual identity mismatch')
                if impact and pos(preview)>pos(impact): fail(f'{label} {rid}: preview must precede quick-impact')
            if impact and details and pos(impact)>pos(details): fail(f'{label} {rid}: quick-impact must precede Full Analysis')
            if details and source and pos(details)>pos(source): fail(f'{label} {rid}: Full Analysis must precede source')
    if len(html.splitlines())<40: fail('index.html must remain readable non-minified HTML')
    for a in soup.select('a[target="_blank"]'):
        rel=set(a.get('rel') or [])
        if 'noopener' not in rel or 'noreferrer' not in rel: fail('external target=_blank link missing noopener noreferrer')

for path in (FOUNDATION,UI,COMPONENTS,SHARED,JS):
    if not path.exists(): fail(f'missing required frontend asset: {path.name}')
css='\n'.join(p.read_text('utf-8') for p in (FOUNDATION,UI,COMPONENTS,SHARED) if p.exists())
for selector in ('.top-list','.top-item','.more-grid','.more-card','.history-list','.history-controls','.archive-year','.archive-month','.history-entry','.preference-vote','.detail-body','details > summary','.quick-impact','.case-preview'):
    if selector not in css: fail(f'missing required selector: {selector}')
if is_v2_dataset(latest_data()):
    for selector in ('.category-nav-grid','.category-nav-card'):
        if selector not in css: fail(f'missing V2 selector: {selector}')
if JS.exists():
    js=JS.read_text('utf-8')
    if 'ai3d-preferences-v1' not in js: fail('preference localStorage key missing')
    if '.top-item, .more-card' not in js: fail('card interaction selector missing')
    for token in ('history-search','data-history-category','data-history-range'):
        if token not in js: fail(f'history interaction missing: {token}')
if errors:
    print('Homepage contract QA FAILED:'); print('\n'.join(' - '+e for e in errors)); sys.exit(1)
print('Homepage contract QA passed: V2-aware layout + shared components + searchable grouped history library + archive parity locked')
