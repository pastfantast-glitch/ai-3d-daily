#!/usr/bin/env python3
"""Guard publishing topology, runtime integrity, and operational reliability.

Only intelligence-build.yml may write repository contents. Legacy QA workflows
must remain read-only. The canonical publisher must keep a release-ready gate,
preflight, registry QA, archive navigation + homepage archive-list rendering,
historical regression, atomic content publish, public Pages verification,
success receipt, recovery path, and one global concurrency lock. Runtime modules
must inherit the shell cache token and never guess stable IDs for new dates.
GitHub-hosted JavaScript actions must stay on Node.js 24-capable majors and Python
dependencies must be installed from the validated lock file.
"""
from pathlib import Path
import re, sys

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/'.github'/'workflows'
MAIN=WF/'intelligence-build.yml'
LOCK=ROOT/'requirements-pipeline.txt'
errors=[]

def fail(msg): errors.append(msg)

if not LOCK.exists():
    fail('requirements-pipeline.txt missing')
else:
    locked=LOCK.read_text('utf-8')
    for package in ('beautifulsoup4==','requests==','Pillow=='):
        if package not in locked: fail(f'pipeline dependency not exactly pinned: {package[:-2]}')

if not MAIN.exists():
    fail('intelligence-build.yml missing')
    main=''
else:
    main=MAIN.read_text('utf-8')
    required=[
        "- 'data/publish/*.ready'",
        'group: canonical-intelligence-publish',
        'pip install -r requirements-pipeline.txt',
        'check_release_input.py',
        'check_registry_contract.py',
        'render_daily_navigation.py',
        'render_home_archive_links.py',
        'build_intelligence.py',
        'extract_visual_assets.py',
        'inject_visual_previews.py',
        'apply_cache_bust.py',
        'check_intelligence_contract.py',
        'check_visual_contract.py',
        'check_home_contract.py',
        'check_daily_contract.py',
        'check_historical_regression.py --days 4',
        'verify_pages_publish.py',
        'write_publish_receipt.py',
        'restore_publish_snapshot.py',
        'find . -maxdepth 2 -mindepth 2',
        'Publish canonical intelligence',
        'Record verified publish',
        'recovery_sha',
    ]
    for token in required:
        if token not in main: fail(f'intelligence-build missing required stage/token: {token}')
    if "- 'data/publish/**'" in main:
        fail('receipt metadata must not retrigger canonical publish; use *.ready only')
    if "- 'data/daily/**'" in main:
        fail('canonical publish must not trigger on data/daily/** before release is ready')
    if 'contents: write' not in main:
        fail('canonical publisher requires contents: write')
    if re.search(r'pip install\s+beautifulsoup4\b', main):
        fail('canonical publisher bypasses dependency lock')

for path in sorted(WF.glob('*.yml')):
    text=path.read_text('utf-8')

    for match in re.finditer(r'actions/checkout@v(\d+)', text):
        if int(match.group(1)) < 5:
            fail(f'Node 20 checkout action returned: {path.name} uses {match.group(0)}')
    for match in re.finditer(r'actions/setup-python@v(\d+)', text):
        if int(match.group(1)) < 6:
            fail(f'Node 20 setup-python action returned: {path.name} uses {match.group(0)}')

    if path == MAIN:
        continue
    if re.search(r'contents:\s*write', text):
        fail(f'second writer permission found: {path.name}')
    if re.search(r'\bgit\s+(commit|push)\b', text):
        fail(f'second writer command found: {path.name}')

for retired in ('visual-assets.yml','today-more.yml','historical-backfill-once.yml'):
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
print('PIPELINE CONTRACT PASS: one atomic writer + ready gate + archive parity + historical regression + locked deps + Pages receipt + recovery + Node 24')
