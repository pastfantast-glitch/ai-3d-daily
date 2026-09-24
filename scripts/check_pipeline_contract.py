#!/usr/bin/env python3
"""Guard publishing topology, runtime integrity and V2 information architecture."""
from pathlib import Path
import json, re, sys, tempfile
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; WF=ROOT/'.github'/'workflows'; MAIN=WF/'intelligence-build.yml'; COLLECTOR_GATE=WF/'collector-handoff.yml'; LOCK=ROOT/'requirements-pipeline.txt'; errors=[]
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
        "- 'data/publish/*.collector'", "- 'data/publish/*.request'", "- 'data/publish/*.ready'",
        'workflow_run:', "workflows: ['Collector handoff gate']", "needs.route.outputs.mode == 'collector_handoff'", 'COLLECTOR_HANDOFF_DATE',
        'group: canonical-intelligence-publish','cancel-in-progress: false','pip install -r requirements-pipeline.txt',
        'finalize_collector_trigger.py','Collector refill required','Collector correction required','prepare_release_candidate.py','PRE-READY HANDOFF COMPLETE','check_ready_contract.py','check_release_input.py','check_registry_contract.py',
        'render_daily_navigation.py','render_home_archive_links.py','render_information_architecture.py','build_intelligence.py',
        'extract_visual_assets.py','inject_visual_previews.py','apply_cache_bust.py','check_intelligence_contract.py','check_visual_contract.py','check_home_contract.py',
        'check_daily_contract.py','check_information_architecture.py','check_historical_regression.py --days 4','verify_pages_publish.py','write_publish_receipt.py','build_published_registry_snapshot.py','restore_publish_snapshot.py',
        "find \"${{ steps.date.outputs.value }}\" -mindepth 2 -maxdepth 2 -name index.html",'Publish canonical intelligence','Record verified publish','recovery_sha','ref: main']
    for token in required:
        if token not in main: fail(f'intelligence-build missing required stage/token: {token}')
    publish_section=main.split('\n  publish:',1)[1].split('\n  recovery:',1)[0] if '\n  publish:' in main else ''
    if 'normalize_registry_identity.py' in publish_section or 'normalize_registry_identity_hybrid.py' in publish_section:
        fail('registry normalization must happen before .ready, never inside canonical publish job')
    if "needs.route.outputs.mode == 'request'" not in main: fail('same canonical workflow must route .request to pre-ready preparation')
    if "needs.route.outputs.mode == 'ready'" not in main: fail('same canonical workflow must route generated .ready to publish')
    if "needs: [route, prepare, handoff]" not in main or "needs.prepare.result == 'success'" not in main:
        fail('request/collector prepare must continue into publish in the same workflow run; do not rely on GITHUB_TOKEN push retrigger')
    if "needs: [route, handoff]" not in main or "needs.handoff.result == 'success'" not in main:
        fail('collector handoff must gate prepare inside the single canonical workflow')
    if "needs.handoff.outputs.outcome == 'request'" not in main:
        fail('collector prepare/publish must require handoff outcome=request')
    if "needs.handoff.outputs.outcome == 'refill_required'" not in main:
        fail('collector Registry refill must be represented as controlled workflow state before prepare')
    if "needs.handoff.outputs.outcome == 'fix_required'" not in main:
        fail('collector content correction must be represented as controlled workflow state before prepare')
    if 'git push origin HEAD:main' not in main: fail('canonical workflow must persist pre-ready/publish results through its sole writer path')
    if main.count('ref: main')<3: fail('route, canonical writer and recovery checkouts must refresh to latest main')
    if 'cancel-in-progress: true' in main: fail('canonical writer must never cancel an active prepare/publish')
    if "- 'data/publish/**'" in main: fail('receipt metadata must not retrigger canonical workflow')
    if "- 'data/daily/**'" in main: fail('canonical workflow must not trigger on data/daily/** before request/ready')
    if 'contents: write' not in main: fail('canonical publisher requires contents: write')
    if re.search(r'^\s{2}issues:\s*$', main, re.M) or 'rerun-canonical:' in main:
        fail('issue-based canonical publish trigger is forbidden; automated handoff must use .collector/.request/.ready only')
    if 'data/candidates/published-registry-snapshot.json' not in main:
        fail('verified publish receipt commit must persist the derived Published Intelligence Registry snapshot')

# The Collector gate is allowed to write exactly one non-canonical marker:
# data/publish/YYYY-MM-DD.collector. It must never mutate canonical/public data,
# create request/ready/DONE, or perform publish work. Canonical publication remains
# owned exclusively by intelligence-build.yml.
if not COLLECTOR_GATE.exists():
    fail('collector-handoff.yml missing')
else:
    gate=COLLECTOR_GATE.read_text('utf-8')
    for token in (
        'contents: write',
        'actions: read',
        'group: collector-handoff-gate',
        "'data/candidates/collection-session/*.json'",
        'python scripts/create_collector_trigger.py "$DATE" --writer-idle-confirmed',
        'status=queued',
        'status=in_progress',
        'git add "$trigger"',
        'staged="$(git diff --cached --name-only)"',
        'test "$staged" = "$trigger"',
        'git commit -m "Collector handoff $DATE"',
        'git push origin HEAD:main',
    ):
        if token not in gate:
            fail(f'collector handoff gate missing restricted-writer token: {token}')
    if gate.count('git add ') != 1 or gate.count('git commit ') != 1 or gate.count('git push ') != 1:
        fail('collector handoff gate must have exactly one add/commit/push path')
    for forbidden in ('index.html', 'assets/visual', '.request', '.ready', '.done.json', 'write_publish_receipt.py', 'prepare_release_candidate.py'):
        if forbidden in gate:
            fail(f'collector handoff gate crossed canonical/public boundary: {forbidden}')

registry_snapshot_builder=ROOT/'scripts'/'build_published_registry_snapshot.py'
if not registry_snapshot_builder.exists():
    fail('published Registry snapshot builder missing')
else:
    snapshot_builder=registry_snapshot_builder.read_text('utf-8')
    for token in ('import normalize_registry_identity as registry','registry.is_verified_published','registry.published_source_by_id','registry.norm_url'):
        if token not in snapshot_builder:
            fail(f'published Registry snapshot builder must delegate authoritative identity logic: {token}')

# Collection-stage identity mutation and .ready creation must be a single fail-closed
# pre-ready operation; the publisher only verifies the resulting canonical hash.
for path in (
    ROOT/'scripts'/'prepare_release_candidate.py', ROOT/'scripts'/'check_ready_contract.py',
    ROOT/'scripts'/'normalize_registry_identity.py', ROOT/'scripts'/'normalize_registry_identity_hybrid.py',
    ROOT/'scripts'/'check_quick_impact_contract.py', ROOT/'config'/'quick-impact-contract.json'
):
    if not path.exists(): fail(f'pre-ready pipeline module missing: {path.relative_to(ROOT)}')
if (ROOT/'scripts'/'prepare_release_candidate.py').exists():
    prep=(ROOT/'scripts'/'prepare_release_candidate.py').read_text('utf-8')
    for token in ('check_pipeline_contract.py','check_collection_contract.py','check_quick_impact_contract.py','normalize_registry_identity_hybrid.py','enrich_full_analysis_v3.py','normalize_release_seed.py','check_release_input.py','check_registry_contract.py','canonical_sha256','registry_normalized_before_ready','preflight_passed_before_ready'):
        if token not in prep: fail(f'pre-ready preparation missing required stage/token: {token}')
    if "run('normalize_registry_identity.py'" in prep:
        fail('prepare must use the hybrid registry wrapper so LOW_VOLUME_COMPLETE remains contract-driven')
    if "ready_path.write_text" not in prep: fail('pre-ready preparation must be the code path that writes .ready')
registry_hybrid=ROOT/'scripts'/'normalize_registry_identity_hybrid.py'
if registry_hybrid.exists():
    registry_wrapper=registry_hybrid.read_text('utf-8')
    if 'import normalize_registry_identity as core' not in registry_wrapper:
        fail('registry hybrid wrapper must delegate canonical identity/tier logic to normalize_registry_identity.py')
    if 'core.main()' not in registry_wrapper:
        fail('registry hybrid wrapper must execute canonical normalizer main()')
    if 'assign_homepage_tiers' in registry_wrapper:
        fail('registry hybrid wrapper must not duplicate homepage tier assignment')
if (ROOT/'scripts'/'check_ready_contract.py').exists():
    ready_check=(ROOT/'scripts'/'check_ready_contract.py').read_text('utf-8')
    for token in ('canonical_sha256','prepared_by','registry_normalized_before_ready','preflight_passed_before_ready','sha256_file'):
        if token not in ready_check: fail(f'ready contract missing required attestation/token: {token}')

# Collector bridge must use the same authoritative Registry and evidence-depth
# implementations before .request, and must treat Registry deficit as controlled
# refill rather than a publisher failure.
bridge_path=ROOT/'scripts'/'finalize_collector_trigger.py'
if not bridge_path.exists():
    fail('collector bridge missing')
else:
    bridge_text=bridge_path.read_text('utf-8')
    for token in (
        'normalize_registry_identity_hybrid.py',
        'enrich_full_analysis_v3.py',
        'validation_only_finalizer(date)',
        'registry.returncode == 2',
        'persist_followup(',
        'controlled_collector_validation_failure',
        'write_output(date, "refill_required"',
        'write_output(date, "fix_required"',
        'write_output(date, "request"',
        'COLLECTOR_HANDOFF_DATE',
    ):
        if token not in bridge_text:
            fail(f'collector bridge pre-request preflight missing: {token}')
    if bridge_text.find('normalize_registry_identity_hybrid.py') > bridge_text.find('write_request(date)'):
        fail('collector Registry normalization must happen before request creation')
    if bridge_text.find('enrich_full_analysis_v3.py') > bridge_text.find('write_request(date)'):
        fail('collector evidence-depth validation must happen before request creation')

# A semantic no-op during Collector finalization must preserve the exact JSON bytes.
# Otherwise minified Collector artifacts become pretty-printed and the bridge
# falsely interprets that formatting-only rewrite as unpersisted Collector state.
finalizer_path=ROOT/'scripts'/'finalize_collection_handoff.py'
if not finalizer_path.exists():
    fail('collector finalizer missing')
else:
    finalizer_text=finalizer_path.read_text('utf-8')
    for token in ('write_json_if_changed(data_path, data)','write_json_if_changed(ledger_path, ledger)'):
        if token not in finalizer_text: fail(f'collector finalizer semantic no-op guard missing: {token}')
    try:
        scripts_dir=str(ROOT/'scripts')
        if scripts_dir not in sys.path: sys.path.insert(0,scripts_dir)
        from finalize_collection_handoff import write_json_if_changed
        with tempfile.TemporaryDirectory() as td:
            probe=Path(td)/'probe.json'
            original='{"schema_version":1,"items":[]}\n'
            probe.write_text(original,'utf-8')
            if write_json_if_changed(probe, {'schema_version':1,'items':[]}):
                fail('collector finalizer semantic no-op incorrectly reported a mutation')
            if probe.read_text('utf-8') != original:
                fail('collector finalizer semantic no-op rewrote JSON bytes')
            if not write_json_if_changed(probe, {'schema_version':1,'items':[{'id':'changed'}]}):
                fail('collector finalizer failed to persist a real semantic mutation')
    except Exception as exc:
        fail(f'collector finalizer semantic no-op self-test crashed: {type(exc).__name__}: {exc}')

# Quick-impact canonical data is rating-only; presentation derives one compact
# label from the canonical subtype. Every configured subtype must have a label.
qcfg_path=ROOT/'config'/'quick-impact-contract.json'
if qcfg_path.exists():
    try:
        qcfg=json.loads(qcfg_path.read_text('utf-8'))
        required_q={
            'format':'stars_only','presentation':'label_plus_rating','label_source':'subcategory','label_language':'zh-Hant'
        }
        for key,expected in required_q.items():
            if qcfg.get(key)!=expected: fail(f'quick-impact contract {key} must be {expected!r}')
        labels=qcfg.get('subtype_labels') or {}
        if not isinstance(labels,dict) or not labels: fail('quick-impact subtype_labels must be a non-empty mapping')
    except Exception as exc: fail(f'quick-impact contract unreadable/inconsistent: {exc}')

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
        if qcfg_path.exists():
            qcfg=json.loads(qcfg_path.read_text('utf-8')); labels=qcfg.get('subtype_labels') or {}
            configured_subtypes={sub for cat in categories for sub in (cat.get('subtypes') or [])}
            missing=sorted(configured_subtypes-set(labels))
            stale=sorted(set(labels)-configured_subtypes)
            if missing: fail('quick-impact labels missing configured subtypes: '+', '.join(missing))
            if stale: fail('quick-impact labels contain stale/unconfigured subtypes: '+', '.join(stale))
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
    if 'quick-impact-label' not in text or 'subtype_labels' not in text:
        fail('cache/presentation normalization must render subtype label beside quick-impact stars')

for path in sorted(WF.glob('*.yml')):
    text=path.read_text('utf-8')
    for m in re.finditer(r'actions/checkout@v(\d+)',text):
        if int(m.group(1))<5: fail(f'old checkout action returned: {path.name}')
    for m in re.finditer(r'actions/setup-python@v(\d+)',text):
        if int(m.group(1))<6: fail(f'old setup-python action returned: {path.name}')
    if path==MAIN or path==COLLECTOR_GATE: continue
    if re.search(r'contents:\s*write',text): fail(f'second canonical writer permission found: {path.name}')
    if re.search(r'\bgit\s+(commit|push)\b',text): fail(f'second canonical writer command found: {path.name}')
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
print('PIPELINE CONTRACT PASS: one canonical publisher + marker-only Collector gate + workflow-run bridge + Collector pre-request Registry/evidence validation + controlled refill/correction states + same-run request-to-ready-to-publish handoff + registry hybrid wrapper delegates canonical identity/tier logic + registry normalization/hash attestation before publish + config-driven daily release gate IA + quick-impact label contract + latest-main checkout + semantic visual compatibility + cache/category coverage + fail-closed infrastructure QA')
