#!/usr/bin/env python3
"""Guard publishing topology, runtime integrity and V2 information architecture."""
from pathlib import Path
import re, sys, tempfile, json
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
        "paths:\n      - 'data/publish/*.ready'\n  workflow_dispatch:",
        'group: canonical-intelligence-publish','cancel-in-progress: false','pip install -r requirements-pipeline.txt',
        'check_release_input.py','check_registry_contract.py','render_daily_navigation.py','render_home_archive_links.py','render_information_architecture.py','build_intelligence.py',
        'extract_visual_assets.py','inject_visual_previews.py','apply_cache_bust.py','check_intelligence_contract.py','check_visual_contract.py','check_home_contract.py',
        'check_daily_contract.py','check_information_architecture.py','check_historical_regression.py --days 4','verify_pages_publish.py','write_publish_receipt.py','restore_publish_snapshot.py',
        "find \"${{ steps.date.outputs.value }}\" -mindepth 2 -maxdepth 2 -name index.html",'Publish canonical intelligence','Record verified publish','recovery_sha','ref: main']
    for token in required:
        if token not in main: fail(f'intelligence-build missing required stage/token: {token}')
    if main.count('ref: main')<2: fail('canonical publish and recovery checkouts must both refresh to latest main')
    if 'cancel-in-progress: true' in main: fail('canonical writer must never cancel an active publish')
    if "- 'data/publish/**'" in main: fail('receipt metadata must not retrigger canonical publish')
    if "- 'data/daily/**'" in main: fail('canonical publish must not trigger on data/daily/** before ready')
    if 'contents: write' not in main: fail('canonical publisher requires contents: write')

# V2 modular contract must exist independently from renderer/presentation.
for path in (ROOT/'config'/'intelligence-v2.json',ROOT/'scripts'/'intelligence_v2.py',ROOT/'scripts'/'render_information_architecture.py',ROOT/'scripts'/'check_information_architecture.py',ROOT/'category.css'):
    if not path.exists(): fail(f'V2 module missing: {path.relative_to(ROOT)}')
if (ROOT/'config'/'intelligence-v2.json').exists():
    try:
        cfg=json.loads((ROOT/'config'/'intelligence-v2.json').read_text('utf-8'))
        if len(cfg.get('categories') or [])!=6: fail('V2 config must define exactly six categories')
        if cfg.get('category_pool_max_items')!=10: fail('V2 category pool maximum must be 10')
        if cfg.get('category_pool_min_items')!=0: fail('V2 category pool minimum must be 0')
        if cfg.get('category_fill_policy')!='quality_first_no_padding': fail('V2 category fill policy must forbid padding')
        if cfg.get('homepage',{}).get('top5')!=5 or cfg.get('homepage',{}).get('next10')!=10: fail('V2 homepage selection limits must be TOP5 + next10')
    except Exception as exc: fail(f'V2 config unreadable: {exc}')

normalizer=ROOT/'scripts'/'normalize_archive_presentation.py'; nav_renderer=ROOT/'scripts'/'render_daily_navigation.py'
if not normalizer.exists(): fail('archive presentation normalizer missing')
if not nav_renderer.exists(): fail('render_daily_navigation.py missing')
else:
    text=nav_renderer.read_text('utf-8')
    if 'normalize_archive_presentation' not in text or 'normalize_presentation()' not in text: fail('archive navigation renderer no longer invokes shared presentation normalizer')

injector=ROOT/'scripts'/'inject_visual_previews.py'
if not injector.exists(): fail('inject_visual_previews.py missing')
else:
    text=injector.read_text('utf-8')
    if "select_one('.quick-impact')" not in text: fail('visual injector must locate quick-impact by semantic class')
    if re.search(r"find\(['\"](?:div|p|span)['\"],\s*class_=['\"]quick-impact['\"]",text): fail('visual injector regressed to tag-bound quick-impact lookup')
    try:
        scripts_dir=str(ROOT/'scripts')
        if scripts_dir not in sys.path: sys.path.insert(0,scripts_dir)
        from inject_visual_previews import inject
        record={'id':'contract-fixture','asset_path':'assets/visual/contract.webp','page_url':'https://example.com/source','label':'SOURCE PREVIEW'}
        for tag in ('p','div','span'):
            fixture=f'''<!doctype html><html><body><article data-intel-role="card" data-intel-id="contract-fixture"><h3>Fixture</h3><figure class="case-preview"><img src="stale.webp"></figure><{tag} class="quick-impact">Quick Impact</{tag}><details class="home-full-analysis"><summary>Full Analysis</summary></details><a class="source" href="https://example.com/source">Source</a></article></body></html>'''
            with tempfile.TemporaryDirectory() as td:
                path=Path(td)/'index.html'; path.write_text(fixture,'utf-8'); inject(path,'',{'contract-fixture':record},False)
                soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); card=soup.select_one('[data-intel-role="card"]'); previews=card.select('figure.case-preview'); impact=card.select_one('.quick-impact')
                if len(previews)!=1: fail(f'visual injector fixture {tag}: expected exactly one preview'); continue
                nodes=list(card.descendants); preview=previews[0]
                if nodes.index(preview)>nodes.index(impact): fail(f'visual injector fixture {tag}: preview must precede quick-impact')
                if preview.get('data-intel-id')!='contract-fixture' or preview.get('data-intel-role')!='visual': fail(f'visual injector fixture {tag}: identity/role mismatch')
        fallback='''<!doctype html><html><body><article data-intel-role="card" data-intel-id="contract-fixture"><h3>Fixture</h3><details class="home-full-analysis"><summary>Full Analysis</summary></details></article></body></html>'''
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'index.html'; path.write_text(fallback,'utf-8'); inject(path,'',{'contract-fixture':record},False)
            soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); card=soup.select_one('[data-intel-role="card"]'); preview=card.select_one('figure.case-preview'); details=card.select_one('details'); nodes=list(card.descendants)
            if not preview or nodes.index(preview)>nodes.index(details): fail('visual injector fallback must precede Full Analysis')
    except Exception as exc: fail(f'visual injector compatibility self-test crashed: {type(exc).__name__}: {exc}')

cache=ROOT/'scripts'/'apply_cache_bust.py'
if not cache.exists(): fail('apply_cache_bust.py missing')
else:
    text=cache.read_text('utf-8')
    if "(?:\\?v=[^\"\\']+)?" not in text: fail('cache bust must support unversioned and already-versioned refs')
    if 'cache bust verification failed' not in text: fail('cache bust must verify current token')
    if 'category.css' not in text: fail('cache bust must cover V2 category pages')

for path in sorted(WF.glob('*.yml')):
    text=path.read_text('utf-8')
    for m in re.finditer(r'actions/checkout@v(\d+)',text):
        if int(m.group(1))<5: fail(f'old checkout action returned: {path.name}')
    for m in re.finditer(r'actions/setup-python@v(\d+)',text):
        if int(m.group(1))<6: fail(f'old setup-python action returned: {path.name}')
    if path==MAIN: continue
    if re.search(r'contents:\s*write',text): fail(f'second writer permission found: {path.name}')
    if re.search(r'\bgit\s+(commit|push)\b',text): fail(f'second writer command found: {path.name}')
for retired in ('visual-assets.yml','today-more.yml','historical-backfill-once.yml'):
    if (WF/retired).exists(): fail(f'retired writer workflow returned: {retired}')
for name in ('home.js','daily.js'):
    path=ROOT/name
    if not path.exists(): fail(f'missing runtime shell: {name}'); continue
    text=path.read_text('utf-8')
    if "searchParams.get('v')" not in text or "moduleUrl.searchParams.set('v',token)" not in text: fail(f'{name}: canonical runtime token wiring missing')
client=ROOT/'canonical-client.js'
if not client.exists(): fail('canonical-client.js missing')
else:
    text=client.read_text('utf-8')
    if "if(!id&&date==='2026-08-23')" not in text or 'LEGACY_20260823_RULES' not in text: fail('legacy identity fallback scope changed')
if errors:
    print('PIPELINE CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
print('PIPELINE CONTRACT PASS: one writer + ready-only push trigger + V2 max-10 quality-first IA + latest-main checkout + semantic visual compatibility + cache/category coverage + fail-closed QA')
