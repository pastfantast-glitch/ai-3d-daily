#!/usr/bin/env python3
"""Guard publishing topology, runtime integrity and V2 information architecture."""
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
        "- 'data/publish/*.request'", "- 'data/publish/*.ready'",
        'group: canonical-intelligence-publish','cancel-in-progress: false','pip install -r requirements-pipeline.txt',
        'prepare_release_candidate.py','PRE-READY HANDOFF COMPLETE','check_ready_contract.py','check_release_input.py','check_registry_contract.py',
        'render_daily_navigation.py','render_home_archive_links.py','render_information_architecture.py','build_intelligence.py',
        'extract_visual_assets.py','inject_visual_previews.py','apply_cache_bust.py','check_intelligence_contract.py','check_visual_contract.py','check_home_contract.py',
        'check_daily_contract.py','check_information_architecture.py','check_historical_regression.py --days 4','verify_pages_publish.py','write_publish_receipt.py','restore_publish_snapshot.py',
        "find \"${{ steps.date.outputs.value }}\" -mindepth 2 -maxdepth 2 -name index.html",'Publish canonical intelligence','Record verified publish','recovery_sha','ref: main']
    for token in required:
        if token not in main: fail(f'intelligence-build missing required stage/token: {token}')
    publish_section=main.split('\n  publish:',1)[1].split('\n  recovery:',1)[0] if '\n  publish:' in main else ''
    if 'normalize_registry_identity.py' in publish_section: fail('registry normalization must happen before .ready, never inside canonical publish job')
    if "needs.route.outputs.mode == 'request'" not in main: fail('same canonical workflow must route .request to pre-ready preparation')
    if "needs.route.outputs.mode == 'ready'" not in main: fail('same canonical workflow must route generated .ready to publish')
    if 'git push origin HEAD:main' not in main: fail('canonical workflow must persist pre-ready/publish results through its sole writer path')
    if main.count('ref: main')<3: fail('route, canonical writer and recovery checkouts must refresh to latest main')
    if 'cancel-in-progress: true' in main: fail('canonical writer must never cancel an active prepare/publish')
    if "- 'data/publish/**'" in main: fail('receipt metadata must not retrigger canonical workflow')
    if "- 'data/daily/**'" in main: fail('canonical workflow must not trigger on data/daily/** before request/ready')
    if 'contents: write' not in main: fail('canonical publisher requires contents: write')

# Collection-stage identity mutation and .ready creation must be a single fail-closed
# pre-ready operation; the publisher only verifies the resulting canonical hash.
for path in (
    ROOT/'scripts'/'prepare_release_candidate.py', ROOT/'scripts'/'check_ready_contract.py',
    ROOT/'scripts'/'normalize_registry_identity.py'
):
    if not path.exists(): fail(f'pre-ready pipeline module missing: {path.relative_to(ROOT)}')
if (ROOT/'scripts'/'prepare_release_candidate.py').exists():
    prep=(ROOT/'scripts'/'prepare_release_candidate.py').read_text('utf-8')
    for token in ('normalize_registry_identity.py','enrich_full_analysis_v3.py','normalize_release_seed.py','check_release_input.py','check_registry_contract.py','canonical_sha256','registry_normalized_before_ready','preflight_passed_before_ready'):
        if token not in prep: fail(f'pre-ready preparation missing required stage/token: {token}')
    if "ready_path.write_text" not in prep: fail('pre-ready preparation must be the code path that writes .ready')
if (ROOT/'scripts'/'check_ready_contract.py').exists():
    ready_check=(ROOT/'scripts'/'check_ready_contract.py').read_text('utf-8')
    for token in ('canonical_sha256','prepared_by','registry_normalized_before_ready','preflight_passed_before_ready','sha256_file'):
        if token not in ready_check: fail(f'ready contract missing required attestation/token: {token}')

# V2 contract values live in config. Python validates consistency rather than
# repeating target/date/count literals that can drift during contract changes.
for path in (
    ROOT/'config'/'intelligence-v2.json', ROOT/'scripts'/'intelligence_v2.py',
    ROOT/'scripts'/'check_collection_contract.py', ROOT/'scripts'/'render_information_architecture.py',
    ROOT/'scripts'/'check_information_architecture.py', ROOT/'category.css'
):
    if not path.exists(): fail(f'V2 module missing: {path.relative_to(ROOT)}')
if (ROOT/'config'/'intelligence-v2.json').exists() and (ROOT/'scripts'/'intelligence_v2.py').exists():
    try:
        scripts_dir=str(ROOT/'scripts')
        if scripts_dir not in sys.path: sys.path.insert(0,scripts_dir)
        from intelligence_v2 import load_config
        cfg=load_config(); categories=cfg.get('categories') or []; collection=cfg.get('collection') or {}
        soft_target=int(cfg['category_pool_target_items']); daily_target=int(collection.get('daily_target_items',0) or 0)
        if int(collection.get('completeness_trigger_total_items',0))!=daily_target:
            fail(f'V2 completeness trigger must equal configured daily target {daily_target}')
        candidate_target=int(collection.get('candidate_pool_target_per_category',0) or 0)
        candidate_stretch=int(collection.get('candidate_pool_stretch_per_category',0) or 0)
        if candidate_target<soft_target: fail('V2 discovery candidate target must be >= category balancing target')
        if candidate_stretch<candidate_target: fail('V2 discovery candidate stretch must be >= candidate target')
    except Exception as exc: fail(f'V2 config contract unreadable/inconsistent: {exc}')

history_wf=WF/'historical-regression.yml'
if not history_wf.exists():
    fail('historical-regression.yml missing')
elif 'check_collection_contract.py' not in history_wf.read_text('utf-8'):
    fail('historical regression must run config-driven collection contract dry run')

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
print('PIPELINE CONTRACT PASS: one canonical writer workflow + request-to-ready preflight handoff + registry normalization/hash attestation before publish + config-driven daily 20-30 release-gate IA + latest-main checkout + semantic visual compatibility + cache/category coverage + fail-closed QA')
