#!/usr/bin/env python3
"""Guard the publishing topology itself.

Only intelligence-build.yml may write repository contents. Legacy QA workflows
must remain read-only. The canonical publisher must keep release-ready gating,
preflight, registry QA, archive navigation rendering, atomic publish, and a
global concurrency lock.
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

if errors:
    print('PIPELINE CONTRACT FAILED')
    print('\n'.join('- '+e for e in errors))
    sys.exit(1)
print('PIPELINE CONTRACT PASS: one atomic writer + release-ready gate + archive navigation')
