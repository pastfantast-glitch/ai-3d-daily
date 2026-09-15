#!/usr/bin/env python3
from pathlib import Path
import json, re, subprocess, sys
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset, homepage_groups

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'index.html'; HISTORY=ROOT/'history'/'index.html'
FOUNDATION=ROOT/'home.css'; UI=ROOT/'home-content.css'; COMPONENTS=ROOT/'home-components.css'; SHARED=ROOT/'shared-components.css'
JS=ROOT/'home.js'; HISTORY_JS=ROOT/'history.js'; PREF=ROOT/'preference.js'
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$'); errors=[]
def fail(msg): errors.append(msg)
def archive_dates(): return sorted(p.name for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())

def latest_data():
    paths=sorted((ROOT/'data'/'daily').glob('20??-??-??.json'))
    return json.loads(paths[-1].read_text('utf-8')) if paths else {}

# Design System ownership is part of the homepage contract: page CSS may control
# layout, but shared visual properties and Full Analysis styling stay centralized.
design_guard=ROOT/'scripts'/'check_design_system_contract.py'
if not design_guard.exists():
    fail('Design System ownership guard missing')
else:
    result=subprocess.run([sys.executable,str(design_guard)],cwd=ROOT,text=True,capture_output=True)
    if result.returncode:
        fail('Design System ownership guard failed:\n'+(result.stdout or result.stderr).strip())

current_data=latest_data(); v2=is_v2_dataset(current_data); current_date=str(current_data.get('date','')).strip()

if not INDEX.exists(): fail('index.html missing')
else:
    html=INDEX.read_text('utf-8'); soup=BeautifulSoup(html,'html.parser')
    for asset in ('shared-components.css?v=','home.css?v=','home-content.css?v=','home-components.css?v=','home.js?v='):
        if asset not in html: fail(f'index.html missing cache-busted asset: {asset}')
    sections=soup.select('main.home-main > section.home-section')
    expected=['today-section','more-section','category-section'] if v2 else ['today-section','more-section','test-section']
    actual=[]
    for section in sections:
        classes=set(section.get('class',[])); matched=[x for x in expected if x in classes]; actual.append(matched[0] if len(matched)==1 else '?')
    if actual!=expected: fail(f'homepage section order drift: {actual} != {expected}')
    if soup.select('.history-section,.history-list,.history-controls,.current-report-entry'):
        fail('homepage must be Today-first and must not embed History/archive UI')

    top=soup.select('.top-item'); more=soup.select('.more-card')
    if v2:
        canonical_top, canonical_next = homepage_groups(current_data)
        if len(top)!=len(canonical_top): fail(f'V2 homepage TOP card count must match available canonical TOP5, got {len(top)} != {len(canonical_top)}')
        if len(more)!=len(canonical_next): fail(f'V2 homepage next10 card count must match available canonical ranks 6-15, got {len(more)} != {len(canonical_next)}')
        if len(soup.select('.category-nav-grid .category-nav-card[href]'))!=6: fail('V2 homepage must expose exactly six category navigation cards')
        if soup.select('.week-counts,.week-summary,.week-topic'): fail('V2 homepage must not contain weekly overview UI')
    else:
        if len(top)!=5: fail(f'legacy homepage must contain exactly 5 TOP cards, got {len(top)}')
        if not 6<=len(more)<=12: fail(f'legacy Supplemental cards must be 6-12, got {len(more)}')
    if soup.select('[data-supplemental-id]'): fail('stale supplemental cards must not exist')

    history_nav=soup.select('nav.global-category-nav a.global-history-link[data-global-view="history"][href="history/"]')
    if len(history_nav)!=1: fail('homepage global nav must expose exactly one standalone History link')
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

if not HISTORY.exists():
    fail('history/index.html missing')
else:
    history_html=HISTORY.read_text('utf-8'); hsoup=BeautifulSoup(history_html,'html.parser')
    if not hsoup.body or 'history-page' not in (hsoup.body.get('class') or []): fail('History portal body identity missing')
    for asset in ('../styles.css?v=','../shared-components.css?v=','../home.css?v=','../home-content.css?v=','../home-components.css?v=','../history.js?v=','../preference.js?v='):
        if asset not in history_html: fail(f'History portal missing cache-busted asset: {asset}')
    if len(hsoup.select('section.history-section#history'))!=1: fail('History portal must contain exactly one history section')
    if len(hsoup.select('.history-list'))!=1: fail('History portal must contain exactly one history-list')
    if len(hsoup.select('.history-controls'))!=1: fail('History portal must expose exactly one control panel')
    if len(hsoup.select('.history-search[type="search"]'))!=1: fail('History portal search missing')
    if not hsoup.select('.archive-year .archive-month .history-entry'): fail('History portal must use year/month accordion entries')
    category_filters=hsoup.select('[data-history-category]')
    if v2 and len(category_filters)!=7: fail(f'V2 History portal must expose all + six category filters, got {len(category_filters)}')
    if len(hsoup.select('[data-history-range]'))!=3: fail('History portal must expose 7/30/all date range filters')
    active_history=hsoup.select('nav.global-category-nav a.global-history-link.is-active[data-global-view="history"]')
    if len(active_history)!=1: fail('History portal global nav must mark 歷史日報 active exactly once')

    current_entries=hsoup.select('.current-report-entry')
    if current_date:
        if len(current_entries)!=1: fail(f'History portal must expose exactly one current report entry, got {len(current_entries)}')
        else:
            entry=current_entries[0]
            if entry.get('data-current-report-date')!=current_date: fail('History current report entry date differs from canonical current date')
            if not entry.select_one(f'a.current-report-link[href="../{current_date}/"]'): fail('History current report entry must link to current daily page')
            if '查看今日完整日報' not in entry.get_text(' ',strip=True): fail('History current report entry label drift')

    expected_archives=list(reversed([d for d in archive_dates() if d!=current_date])); actual_archives=[]
    for a in hsoup.select('.history-list a.history-entry[href]'):
        m=re.fullmatch(r'\.\./(20\d{2}-\d{2}-\d{2})/?',a.get('href',''))
        if m: actual_archives.append(m.group(1))
    if actual_archives!=expected_archives: fail('History portal must contain only prior real archives newest-first')
    if current_date and current_date in actual_archives: fail('current report date must not appear inside History archive list')

for path in (FOUNDATION,UI,COMPONENTS,SHARED,JS,HISTORY_JS,PREF):
    if not path.exists(): fail(f'missing required frontend asset: {path.name}')
css='\n'.join(p.read_text('utf-8') for p in (FOUNDATION,UI,COMPONENTS,SHARED) if p.exists())
for selector in ('.top-list','.top-item','.more-grid','.more-card','.current-report-entry','.current-report-link','.history-list','.history-controls','.archive-year','.archive-month','.history-entry','.preference-vote','.detail-body','details > summary','.quick-impact','.case-preview'):
    if selector not in css: fail(f'missing required selector: {selector}')
if v2:
    for selector in ('.category-nav-grid','.category-nav-card'):
        if selector not in css: fail(f'missing V2 selector: {selector}')
if JS.exists():
    js=JS.read_text('utf-8')
    if '.top-item, .more-card' not in js: fail('card interaction selector missing')
    if '.global-history-link' not in js: fail('homepage workspace must explicitly exclude standalone History navigation')
    for token in ('history-search','data-history-category','data-history-range'):
        if token in js: fail(f'homepage JS must not own History interaction anymore: {token}')
if HISTORY_JS.exists():
    hjs=HISTORY_JS.read_text('utf-8')
    for token in ('history-search','data-history-category','data-history-range'):
        if token not in hjs: fail(f'History portal interaction missing: {token}')
if PREF.exists():
    pref=PREF.read_text('utf-8')
    if 'ai3d-preferences-v2' not in pref: fail('shared preference v2 localStorage key missing')
    if 'ai3d-preferences-v1' not in pref: fail('shared preference legacy migration key missing')
    if '[data-intel-role="card"][data-intel-id]' not in pref: fail('shared stable-ID card preference selector missing')
if errors:
    print('Homepage/History contract QA FAILED:'); print('\n'.join(' - '+e for e in errors)); sys.exit(1)
print('Homepage/History contract QA passed: Today-first homepage + standalone searchable History portal + shared navigation + shared preference + Design System ownership locked')
