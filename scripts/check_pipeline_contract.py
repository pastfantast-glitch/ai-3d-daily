#!/usr/bin/env python3
"""Guard the publishing topology and runtime integrity contracts.

Only intelligence-build.yml may write repository contents. Legacy QA workflows
must remain read-only. The canonical publisher must keep release-ready gating,
preflight, registry QA, archive navigation rendering, atomic publish, and a
global concurrency lock. Runtime modules must inherit the shell cache token and
must never guess stable IDs for new dates.
"""
from pathlib import Path
import re, sys

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/'.github'/'workflows'
MAIN=WF/'intelligence-build.yml'
errors=[]

def fail(msg): errors.append(msg)

if not MAIN.exists():
    fail('intelligence-build.yml missing')
    main=''
else:
    main=MAIN.read_text('utf-8')
    required=[
        "- 'data/publish/**'",
        'group: canonical-intelligence-publish',
        'check_release_input.py',
        'check_registry_contract.py',
        'render_daily_navigation.py',
        'build_intelligence.py',
        'extract_visual_assets.py',
        'inject_visual_previews.py',
        'apply_cache_bust.py',
        'check_intelligence_contract.py',
        'check_visual_contract.py',
        'check_home_contract.py',
        'check_daily_contract.py',
        'find . -maxdepth 2 -mindepth 2',
        'Publish canonical intelligence',
    ]
    for token in required:
        if token not in main: fail(f'intelligence-build missing required stage/token: {token}')
    if "- 'data/daily/**'" in main:
        fail('canonical publish must not trigger on data/daily/** before release is ready')
    if 'contents: write' not in main:
        fail('canonical publisher requires contents: write')

for path in sorted(WF.glob('*.yml')):
    if path == MAIN: continue
    text=path.read_text('utf-8')
    if re.search(r'contents:\s*write', text):
        fail(f'second writer permission found: {path.name}')
    if re.search(r'\bgit\s+(commit|push)\b', text):
        fail(f'second writer command found: {path.name}')

for retired in ('visual-assets.yml','today-more.yml'):
    if (WF/retired).exists(): fail(f'retired writer workflow returned: {retired}')

# Runtime cache token must be inherited from the cache-busted shell asset so a
# same-day render_revision change invalidates canonical-client.js as well.
for name in ('home.js','daily.js'):
    path=ROOT/name
    if not path.exists():
        fail(f'missing runtime shell: {name}')
        continue
    text=path.read_text('utf-8')
    if "searchParams.get('v')" not in text:
        fail(f'{name}: canonical runtime must inherit shell cache token')
    if "moduleUrl.searchParams.set('v',token)" not in text:
        fail(f'{name}: canonical-client module token wiring missing')
    if re.search(r'canonical-client\.js\?v=2026\d+', text):
        fail(f'{name}: hard-coded dated canonical-client token returned')

client=ROOT/'canonical-client.js'
if not client.exists():
    fail('canonical-client.js missing')
else:
    text=client.read_text('utf-8')
    if "if(!id&&date==='2026-08-23')" not in text:
        fail('legacy identity fallback must be scoped only to 2026-08-23')
    if 'LEGACY_20260823_RULES' not in text:
        fail('legacy 2026-08-23 compatibility rules missing explicit namespace')

if errors:
    print('PIPELINE CONTRACT FAILED')
    print('\n'.join('- '+e for e in errors))
    sys.exit(1)
print('PIPELINE CONTRACT PASS: one atomic writer + release-ready gate + archive navigation + runtime integrity')
