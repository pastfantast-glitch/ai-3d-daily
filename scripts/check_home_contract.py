#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
FOUNDATION = ROOT / 'home.css'
UI = ROOT / 'home-content.css'
COMPONENTS = ROOT / 'home-components.css'
JS = ROOT / 'home.js'

errors = []

def fail(msg):
    errors.append(msg)

if not INDEX.exists():
    fail('index.html missing')
else:
    html = INDEX.read_text('utf-8')
    for asset in ('home.css?v=', 'home-content.css?v=', 'home-components.css?v=', 'home.js?v='):
        if asset not in html:
            fail(f'index.html missing cache-busted asset: {asset}')
    if 'home-layout-fixes.css' in html:
        fail('legacy emergency stylesheet is still referenced')
    if html.count('class="top-item') != 5:
        fail('homepage must contain exactly 5 TOP 5 cards')
    more_count = html.count('class="more-card')
    if not 6 <= more_count <= 12:
        fail(f'Supplemental cards must be 6-12, got {more_count}')
    if 'data-supplemental-id=' in html:
        fail('workflow-managed stale supplemental cards must not exist on homepage')
    if html.count('class="test-section') != 1:
        fail('homepage must contain one test-section')
    if html.count('class="history-list') != 1:
        fail('homepage must contain one history-list')
    if '\n' not in html or len(html.splitlines()) < 40:
        fail('index.html must remain readable non-minified HTML')
    for tag in re.findall(r'<a\b[^>]*target="_blank"[^>]*>', html):
        rel = re.search(r'rel="([^"]*)"', tag)
        if not rel or 'noopener' not in rel.group(1) or 'noreferrer' not in rel.group(1):
            fail(f'external target=_blank link missing noopener noreferrer: {tag[:120]}')

for path in (FOUNDATION, UI, COMPONENTS, JS):
    if not path.exists():
        fail(f'missing required frontend asset: {path.name}')

css = ''
for path in (FOUNDATION, UI, COMPONENTS):
    if path.exists():
        css += '\n' + path.read_text('utf-8')

required = (
    '.top-list', '.top-item', '.more-grid', '.more-card',
    '.test-section', '.history-list', '.preference-vote',
    '.home-full-analysis', '.quick-impact'
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
    if p.is_dir() and re.fullmatch(r'20\d{2}-\d{2}-\d{2}', p.name) and (p / 'index.html').exists()
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

print('Homepage contract QA passed')
