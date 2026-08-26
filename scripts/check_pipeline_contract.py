#!/usr/bin/env python3
"""Guard publishing topology, runtime integrity, presentation triggers, and operational reliability."""
from pathlib import Path
import re, sys, tempfile
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; WF=ROOT/'.github'/'workflows'; MAIN=WF/'intelligence-build.yml'; LOCK=ROOT/'requirements-pipeline.txt'; errors=[]
def fail(msg): errors.append(msg)

if not LOCK.exists(): fail('requirements-pipeline.txt missing')
else:
    locked=LOCK.read_text('utf-8')
    for package in ('beautifulsoup4==','requests==','Pillow=='):
        if package not in locked: fail(f'pipeline dependency not exactly pinned: {package[:-2]}')

if not MAIN.exists(): fail('intelligence-build.yml missing'); main=''
else:
    main=MAIN.read_text('utf-8')
    required=[
        "- 'data/publish/*.ready'","- 'styles.css'","- 'home.css'","- 'home-content.css'","- 'home-components.css'","- 'daily.css'","- 'scripts/normalize_archive_presentation.py'",
        'group: canonical-intelligence-publish','cancel-in-progress: false','pip install -r requirements-pipeline.txt','check_release_input.py','check_registry_contract.py','render_daily_navigation.py','render_home_archive_links.py','build_intelligence.py','extract_visual_assets.py','inject_visual_previews.py','apply_cache_bust.py','check_intelligence_contract.py','check_visual_contract.py','check_home_contract.py','check_daily_contract.py','check_historical_regression.py --days 4','verify_pages_publish.py','write_publish_receipt.py','restore_publish_snapshot.py','find . -maxdepth 2 -mindepth 2','Publish canonical intelligence','Record verified publish','recovery_sha']
    for token in required:
        if token not in main: fail(f'intelligence-build missing required stage/token: {token}')
    if 'cancel-in-progress: true' in main: fail('canonical writer must queue overlapping triggers, never cancel an active publish')
    if "- 'data/publish/**'" in main: fail('receipt metadata must not retrigger canonical publish; use *.ready only')
    if "- 'data/daily/**'" in main: fail('canonical publish must not trigger on data/daily/** before release is ready')
    if 'contents: write' not in main: fail('canonical publisher requires contents: write')
    if re.search(r'pip install\s+beautifulsoup4\b', main): fail('canonical publisher bypasses dependency lock')

normalizer=ROOT/'scripts'/'normalize_archive_presentation.py'; nav_renderer=ROOT/'scripts'/'render_daily_navigation.py'
if not normalizer.exists(): fail('archive presentation normalizer missing')
if not nav_renderer.exists(): fail('render_daily_navigation.py missing')
else:
    nav_text=nav_renderer.read_text('utf-8')
    if 'normalize_archive_presentation' not in nav_text or 'normalize_presentation()' not in nav_text: fail('archive navigation renderer no longer invokes shared presentation normalizer')

# Fail-fast compatibility guard for the visual injector. The component contract is
# semantic-class based: quick-impact may be a <p>, <div>, <span>, etc. This test
# runs in the very first pipeline stage, before any network visual extraction.
injector=ROOT/'scripts'/'inject_visual_previews.py'
if not injector.exists():
    fail('inject_visual_previews.py missing')
else:
    injector_text=injector.read_text('utf-8')
    if "select_one('.quick-impact')" not in injector_text:
        fail('visual injector must locate quick-impact by semantic class, not fixed HTML tag')
    if re.search(r"find\(['\"](?:div|p|span)['\"],\s*class_=['\"]quick-impact['\"]", injector_text):
        fail('visual injector regressed to tag-bound quick-impact lookup')
    try:
        scripts_dir=str(ROOT/'scripts')
        if scripts_dir not in sys.path: sys.path.insert(0,scripts_dir)
        from inject_visual_previews import inject
        record={'id':'contract-fixture','asset_path':'assets/visual/contract.webp','page_url':'https://example.com/source','label':'SOURCE PREVIEW'}
        for tag in ('p','div','span'):
            fixture=f'''<!doctype html><html><body><article data-intel-role="card" data-intel-id="contract-fixture"><h3>Fixture</h3><figure class="case-preview"><img src="stale.webp"></figure><{tag} class="quick-impact">Quick Impact｜fixture</{tag}><details class="home-full-analysis"><summary>Full Analysis</summary></details><a class="source" href="https://example.com/source">Source</a></article></body></html>'''
            with tempfile.TemporaryDirectory() as td:
                path=Path(td)/'index.html'; path.write_text(fixture,'utf-8')
                inject(path,'',{'contract-fixture':record},is_archive=False)
                soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
                card=soup.select_one('[data-intel-role="card"]'); previews=card.select('figure.case-preview'); impact=card.select_one('.quick-impact')
                if len(previews)!=1: fail(f'visual injector fixture {tag}: expected exactly one preview, got {len(previews)}'); continue
                preview=previews[0]
                nodes=list(card.descendants)
                if nodes.index(preview)>nodes.index(impact): fail(f'visual injector fixture {tag}: preview must precede quick-impact')
                if preview.get('data-intel-id')!='contract-fixture' or preview.get('data-intel-role')!='visual': fail(f'visual injector fixture {tag}: identity/role mismatch')
        fallback='''<!doctype html><html><body><article data-intel-role="card" data-intel-id="contract-fixture"><h3>Fixture</h3><details class="home-full-analysis"><summary>Full Analysis</summary></details></article></body></html>'''
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'index.html'; path.write_text(fallback,'utf-8')
            inject(path,'',{'contract-fixture':record},is_archive=False)
            soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); card=soup.select_one('[data-intel-role="card"]'); preview=card.select_one('figure.case-preview'); details=card.select_one('details')
            nodes=list(card.descendants)
            if not preview or nodes.index(preview)>nodes.index(details): fail('visual injector fallback: preview must precede Full Analysis when quick-impact is absent')
    except Exception as exc:
        fail(f'visual injector compatibility self-test crashed: {type(exc).__name__}: {exc}')

cache=ROOT/'scripts'/'apply_cache_bust.py'
if not cache.exists(): fail('apply_cache_bust.py missing')
else:
    cache_text=cache.read_text('utf-8')
    if "(?:\\?v=[^\"\\']+)?" not in cache_text: fail('cache bust must support both unversioned and already-versioned asset references')
    if 'cache bust verification failed' not in cache_text: fail('cache bust must verify every expected shell asset received the current token')

for path in sorted(WF.glob('*.yml')):
    text=path.read_text('utf-8')
    for match in re.finditer(r'actions/checkout@v(\d+)', text):
        if int(match.group(1))<5: fail(f'Node 20 checkout action returned: {path.name} uses {match.group(0)}')
    for match in re.finditer(r'actions/setup-python@v(\d+)', text):
        if int(match.group(1))<6: fail(f'Node 20 setup-python action returned: {path.name} uses {match.group(0)}')
    if path==MAIN: continue
    if re.search(r'contents:\s*write', text): fail(f'second writer permission found: {path.name}')
    if re.search(r'\bgit\s+(commit|push)\b', text): fail(f'second writer command found: {path.name}')

for retired in ('visual-assets.yml','today-more.yml','historical-backfill-once.yml'):
    if (WF/retired).exists(): fail(f'retired writer workflow returned: {retired}')

for name in ('home.js','daily.js'):
    path=ROOT/name
    if not path.exists(): fail(f'missing runtime shell: {name}'); continue
    text=path.read_text('utf-8')
    if "searchParams.get('v')" not in text: fail(f'{name}: canonical runtime must inherit shell cache token')
    if "moduleUrl.searchParams.set('v',token)" not in text: fail(f'{name}: canonical-client module token wiring missing')
    if re.search(r'canonical-client\.js\?v=2026\d+', text): fail(f'{name}: hard-coded dated canonical-client token returned')

client=ROOT/'canonical-client.js'
if not client.exists(): fail('canonical-client.js missing')
else:
    text=client.read_text('utf-8')
    if "if(!id&&date==='2026-08-23')" not in text: fail('legacy identity fallback must be scoped only to 2026-08-23')
    if 'LEGACY_20260823_RULES' not in text: fail('legacy 2026-08-23 compatibility rules missing explicit namespace')

if errors:
    print('PIPELINE CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
print('PIPELINE CONTRACT PASS: one atomic writer + fail-fast semantic visual injection compatibility + complete shell-trigger coverage + non-cancelling concurrency + cache verification + shared Daily presentation + ready gate + historical regression + locked deps + Pages receipt + recovery + Node 24')
