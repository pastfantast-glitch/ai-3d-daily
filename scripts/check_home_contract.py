#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
LAYOUT = ROOT / 'home-layout.css'
UI = ROOT / 'home-ui.css'
JS = ROOT / 'home.js'

errors = []

def fail(msg):
    errors.append(msg)

if not INDEX.exists():
    fail('index.html missing')
else:
    html = INDEX.read_text('utf-8')
    if 'home-layout.css?v=' not in html:
        fail('index.html must reference home-layout.css with cache-bust')
    if 'home-ui.css?v=' not in html:
        fail('index.html must reference home-ui.css with cache-bust')
    for legacy in ('home.css', 'home-content.css', 'home-layout-fixes.css'):
        if legacy in html:
            fail(f'legacy stylesheet still referenced: {legacy}')
    if html.count('class="top-item') != 5:
        fail('homepage must contain exactly 5 TOP 5 cards')
    more_count = html.count('class="more-card')
    if not 6 <= more_count <= 12:
        fail(f'Supplemental cards must be 6-12, got {more_count}')
    if html.count('class="test-section') != 1:
        fail('homepage must contain one test-section')
    if html.count('class="history-list') != 1:
        fail('homepage must contain one history-list')
    for tag in re.findall(r'<a\b[^>]*target="_blank"[^>]*>', html):
        rel = re.search(r'rel="([^"]*)"', tag)
        if not rel or 'noopener' not in rel.group(1) or 'noreferrer' not in rel.group(1):
            fail(f'external target=_blank link missing noopener noreferrer: {tag[:120]}')

for path in (LAYOUT, UI, JS):
    if not path.exists():
        fail(f'missing required frontend asset: {path.name}')

css = ''
for path in (LAYOUT, UI):
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

if errors:
    print('Homepage contract QA FAILED:')
    for e in errors:
        print(' -', e)
    sys.exit(1)

print('Homepage contract QA passed')
