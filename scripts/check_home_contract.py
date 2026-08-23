#!/usr/bin/env python3
from pathlib import Path
import re
import sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
FOUNDATION = ROOT / 'home.css'
UI = ROOT / 'home-content.css'
COMPONENTS = ROOT / 'home-components.css'
JS = ROOT / 'home.js'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
errors = []

def fail(msg):
    errors.append(msg)

def archive_dates():
    return sorted(
        p.name for p in ROOT.iterdir()
        if p.is_dir() and DATE_RE.fullmatch(p.name) and (p / 'index.html').exists()
    )

if not INDEX.exists():
    fail('index.html missing')
else:
    html = INDEX.read_text('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    for asset in ('home.css?v=', 'home-content.css?v=', 'home-components.css?v=', 'home.js?v='):
        if asset not in html:
            fail(f'index.html missing cache-busted asset: {asset}')
    if 'home-layout-fixes.css' in html:
        fail('legacy emergency stylesheet is still referenced')

    # Design lock: the homepage reading order is part of the product contract.
    sections = soup.select('main.home-main > section.home-section')
    expected_section_classes = ['today-section', 'more-section', 'test-section', 'history-section']
    actual_section_classes = []
    for section in sections:
        classes = set(section.get('class', []))
        matched = [name for name in expected_section_classes if name in classes]
        actual_section_classes.append(matched[0] if len(matched) == 1 else '?')
    if actual_section_classes != expected_section_classes:
        fail(f'homepage section order drift: {actual_section_classes} != {expected_section_classes}')

    top_items = soup.select('.top-item')
    if len(top_items) != 5:
        fail(f'homepage must contain exactly 5 TOP 5 cards, got {len(top_items)}')

    more_cards = soup.select('.more-card')
    if not 6 <= len(more_cards) <= 12:
        fail(f'Supplemental cards must be 6-12, got {len(more_cards)}')

    if soup.select('[data-supplemental-id]'):
        fail('workflow-managed stale supplemental cards must not exist on homepage')

    test_sections = soup.select('section.test-section')
    if len(test_sections) != 1:
        fail(f'homepage must contain one test-section, got {len(test_sections)}')

    history_lists = soup.select('.history-list')
    if len(history_lists) != 1:
        fail(f'homepage must contain one history-list, got {len(history_lists)}')
    else:
        expected_archives = list(reversed(archive_dates()))
        actual_archives = []
        for a in history_lists[0].select('a[href]'):
            m = re.fullmatch(r'(20\d{2}-\d{2}-\d{2})/?', a.get('href', ''))
            if m:
                actual_archives.append(m.group(1))
        if actual_archives != expected_archives:
            fail(f'history-list must exactly match real archives newest-first: {actual_archives} != {expected_archives}')

    # Every current intelligence card must keep the same semantic component stack.
    for label, cards in [('TOP', top_items), ('Supplemental', more_cards)]:
        for card in cards:
            rid = card.get('data-intel-id', '?')
            if card.get('data-intel-role') != 'card':
                fail(f'{label} {rid}: missing data-intel-role="card"')
            details = card.select_one('details.home-full-analysis')
            body = card.select_one('details.home-full-analysis .detail-body.home-analysis-body')
            impact = card.select_one('.quick-impact')
            source = card.select_one('a.source[href]')
            if not details:
                fail(f'{label} {rid}: missing home-full-analysis')
            if not body:
                fail(f'{label} {rid}: missing home-analysis-body')
            if not impact:
                fail(f'{label} {rid}: missing quick-impact')
            if not source:
                fail(f'{label} {rid}: missing source link')

            # Preview is optional, but if present it must sit before impact/details and share identity.
            preview = card.select_one('figure.case-preview')
            descendants = list(card.descendants)
            def pos(node):
                try:
                    return descendants.index(node)
                except ValueError:
                    return -1
            if preview:
                if preview.get('data-intel-role') != 'visual' or preview.get('data-intel-id') != rid:
                    fail(f'{label} {rid}: visual identity/role mismatch')
                if impact and pos(preview) > pos(impact):
                    fail(f'{label} {rid}: visual preview must appear before quick-impact')
            if impact and details and pos(impact) > pos(details):
                fail(f'{label} {rid}: quick-impact must appear before Full Analysis')
            if details and source and pos(details) > pos(source):
                fail(f'{label} {rid}: Full Analysis must appear before source link')

    if '\n' not in html or len(html.splitlines()) < 40:
        fail('index.html must remain readable non-minified HTML')

    for a in soup.select('a[target="_blank"]'):
        rel = set(a.get('rel') or [])
        if 'noopener' not in rel or 'noreferrer' not in rel:
            fail(f'external target=_blank link missing noopener noreferrer: {str(a)[:120]}')

for path in (FOUNDATION, UI, COMPONENTS, JS):
    if not path.exists():
        fail(f'missing required frontend asset: {path.name}')

css = ''
for path in (FOUNDATION, UI, COMPONENTS):
    if path.exists():
        css += '\n' + path.read_text('utf-8')

required = (
    '.top-list', '.top-item', '.more-grid', '.more-card',
    '.today-section', '.more-section', '.test-section', '.history-list',
    '.preference-vote', '.home-full-analysis', '.quick-impact', '.case-preview'
)
for selector in required:
    if selector not in css:
        fail(f'missing required selector: {selector}')

for forbidden in (
    '.test-strip', '.archive-item', '.archive-list', '.more-group', '.more-feed',
    '.history-search', '.search-box', '.empty-state', '.category-list',
    '.week-summary', '.week-topic'
):
    if forbidden in css:
        fail(f'legacy selector returned: {forbidden}')

if JS.exists():
    js = JS.read_text('utf-8')
    if 'ai3d-preferences-v1' not in js:
        fail('preference localStorage key missing')
    if '#news-search' in js or "querySelectorAll('.filter')" in js:
        fail('removed homepage search/filter code has returned')
    if '.top-item, .more-card' not in js:
        fail('card interaction selector missing')

# Newly published daily page must never expose placeholder navigation.
daily_dirs = sorted(
    p for p in ROOT.iterdir()
    if p.is_dir() and DATE_RE.fullmatch(p.name) and (p / 'index.html').exists()
)
if daily_dirs:
    latest = daily_dirs[-1] / 'index.html'
    latest_html = latest.read_text('utf-8')
    if 'null' in latest_html:
        fail(f'latest daily page contains null placeholder: {latest.relative_to(ROOT)}')

if errors:
    print('Homepage contract QA FAILED:')
    for e in errors:
        print(' -', e)
    sys.exit(1)

print('Homepage contract QA passed: layout order + card structure + archive parity locked')
