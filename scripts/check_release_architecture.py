#!/usr/bin/env python3
"""Fail-closed architecture guard for the canonical intelligence release pipeline.

This guard validates cross-file wiring that is easy to regress when individual
contracts evolve: hybrid discovery, tiered analysis depth, single-writer handoff,
pre-atomic surface QA, atomic publication, Pages verification, and source-QA coverage.
"""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / '.github' / 'workflows'
MAIN = WF / 'intelligence-build.yml'
COLLECTOR_GATE = WF / 'collector-handoff.yml'
AUTONOMOUS_COLLECTOR = WF / 'daily-collector.yml'
DAILY_QA = WF / 'daily-contract.yml'
errors = []


def fail(message):
    errors.append(message)


required_files = [
    'config/intelligence-v2.json',
    'config/discovery-hybrid.json',
    'config/full-analysis-depth.json',
    'config/quick-impact-contract.json',
    'config/stability-contract.json',
    'config/collector-runtime.json',
    'data/candidates/rolling-backlog.json',
    'scripts/discovery_hybrid.py',
    'scripts/check_discovery_hybrid_contract.py',
    'scripts/normalize_registry_identity_hybrid.py',
    'scripts/check_release_input.py',
    'scripts/enrich_full_analysis_v3.py',
    'scripts/check_intelligence_contract.py',
    'scripts/check_preference_contract.py',
    'scripts/check_pages_tier_contract.py',
    'scripts/wait_for_pages_deployment.py',
    'scripts/verify_pages_publish.py',
    'scripts/prepare_release_candidate.py',
    'scripts/check_ready_contract.py',
    'scripts/create_collector_trigger.py',
    'scripts/run_daily_collector.py',
    'scripts/check_collector_runtime_contract.py',
    '.github/workflows/daily-collector.yml',
    '.github/workflows/collector-handoff.yml',
    '.github/workflows/intelligence-build.yml',
    '.github/workflows/daily-contract.yml',
]
for rel in required_files:
    if not (ROOT / rel).exists():
        fail(f'missing release architecture component: {rel}')

# Full Analysis depth contract must remain substantive and fail-closed.
depth_path = ROOT / 'config' / 'full-analysis-depth.json'
if depth_path.exists():
    try:
        depth = json.loads(depth_path.read_text('utf-8'))
        if not depth.get('effective_date'):
            fail('full-analysis-depth effective_date missing')

        tiered = bool(depth.get('tiered_effective_date') or depth.get('analysis_levels'))
        if tiered:
            if not depth.get('tiered_effective_date'):
                fail('full-analysis-depth tiered_effective_date missing')
            levels = depth.get('analysis_levels') or []
            if levels != ['FULL', 'BRIEF', 'REJECT']:
                fail('full-analysis-depth analysis_levels must be FULL/BRIEF/REJECT')
            if str(depth.get('default_analysis_level', '')).upper() != 'FULL':
                fail('full-analysis-depth default_analysis_level must be FULL')

            full = depth.get('full') or {}
            if int(full.get('min_blocks', 0)) < 3:
                fail('full-analysis-depth FULL min_blocks must be >= 3')
            if int(full.get('max_blocks', 0)) < int(full.get('min_blocks', 0)):
                fail('full-analysis-depth FULL max_blocks must be >= min_blocks')
            if int(full.get('min_block_chars', 0)) <= 0 or int(full.get('min_total_text_chars', 0)) <= 0:
                fail('full-analysis-depth FULL substantive text thresholds must be positive')
            full_groups = set(full.get('required_semantic_groups') or [])
            for key in ('workflow_or_technical_change', 'production_impact', 'test_risk_or_limit'):
                if key not in full_groups:
                    fail(f'full-analysis-depth FULL semantic group missing: {key}')

            brief = depth.get('brief') or {}
            if int(brief.get('min_blocks', 0)) < 1:
                fail('full-analysis-depth BRIEF min_blocks must be >= 1')
            if int(brief.get('max_blocks', 0)) < int(brief.get('min_blocks', 0)):
                fail('full-analysis-depth BRIEF max_blocks must be >= min_blocks')
            if int(brief.get('min_block_chars', 0)) <= 0 or int(brief.get('min_total_text_chars', 0)) <= 0:
                fail('full-analysis-depth BRIEF substantive text thresholds must be positive')
            if 'brief_reason' not in (brief.get('required_fields') or []):
                fail('full-analysis-depth BRIEF must require brief_reason')
            if not brief.get('allowed_reasons'):
                fail('full-analysis-depth BRIEF allowed_reasons must be non-empty')

            reject = depth.get('reject') or {}
            if reject.get('publish_allowed') is not False:
                fail('full-analysis-depth REJECT publish_allowed must be false')

            top5 = depth.get('top5_policy') or {}
            selection_mode = str(top5.get('selection_mode') or 'full-only').strip()
            allow_brief = top5.get('allow_brief')
            fallback_only = top5.get('brief_fallback_only', True)
            if selection_mode not in ('full-only', 'full-first-brief-fallback'):
                fail(f'full-analysis-depth unknown top5_policy selection_mode: {selection_mode}')
            elif selection_mode == 'full-only':
                if allow_brief is not False:
                    fail('full-analysis-depth full-only TOP5 mode requires allow_brief=false')
            else:
                if allow_brief is not True:
                    fail('full-analysis-depth full-first-brief-fallback mode requires allow_brief=true')
                if fallback_only is not True:
                    fail('full-analysis-depth BRIEF TOP5 admission must remain fallback-only')
                if top5.get('require_visible_brief_label') is not True:
                    fail('full-analysis-depth BRIEF TOP5 fallback must require visible BRIEF identification')
        else:
            if int(depth.get('min_blocks', 0)) < 3:
                fail('full-analysis-depth min_blocks must be >= 3')
            if int(depth.get('max_blocks', 0)) < int(depth.get('min_blocks', 0)):
                fail('full-analysis-depth max_blocks must be >= min_blocks')
            if int(depth.get('min_block_chars', 0)) <= 0 or int(depth.get('min_total_text_chars', 0)) <= 0:
                fail('full-analysis-depth substantive text thresholds must be positive')

        groups = depth.get('required_semantic_groups') or {}
        for key in ('workflow_or_technical_change', 'production_impact', 'test_risk_or_limit'):
            if not groups.get(key):
                fail(f'full-analysis-depth semantic group vocabulary missing: {key}')
        if depth.get('fail_closed') is not True:
            fail('full-analysis-depth must remain fail_closed=true')
    except Exception as exc:
        fail(f'full-analysis-depth contract unreadable: {exc}')

enrich = ROOT / 'scripts' / 'enrich_full_analysis_v3.py'
if enrich.exists():
    text = enrich.read_text('utf-8')
    for token in ('DEPTH_PATH', 'depth_issues', 'effective_date', 'full_analysis_depth_contract'):
        if token not in text:
            fail(f'enrich_full_analysis_v3.py missing depth enforcement token: {token}')

release_input = ROOT / 'scripts' / 'check_release_input.py'
if release_input.exists():
    text = release_input.read_text('utf-8')
    for token in ('low_volume_release_allowed', 'validate_with_hybrid', 'V2 daily release minimum is '):
        if token not in text:
            fail(f'check_release_input.py missing hybrid-aware release token: {token}')

pages_verify = ROOT / 'scripts' / 'verify_pages_publish.py'
if pages_verify.exists():
    text = pages_verify.read_text('utf-8')
    for token in ('full-analysis-depth.json', 'analysis_level', "('FULL', 'BRIEF')", 'REJECT item reached public Pages surface'):
        if token not in text:
            fail(f'verify_pages_publish.py missing tier-aware Pages token: {token}')
    if 'get("full_analysis", {}).get("min_blocks", 3)' in text and 'analysis_policy(' not in text:
        fail('Pages verifier regressed to one global Full Analysis minimum')

preference_check = ROOT / 'scripts' / 'check_preference_contract.py'
if preference_check.exists():
    text = preference_check.read_text('utf-8')
    for token in ('latest_surface_date', 'newest_canonical', "ROOT / newest_canonical / 'index.html'"):
        if token not in text:
            fail(f'check_preference_contract.py missing pre-ready rendered-surface fallback token: {token}')

if MAIN.exists():
    main = MAIN.read_text('utf-8')
    for token in (
        'group: canonical-intelligence-publish',
        'cancel-in-progress: false',
        "- 'data/publish/*.collector'",
        "- 'data/publish/*.request'",
        "- 'data/publish/*.ready'",
        'workflow_run:',
        "workflows: ['Collector handoff gate']",
        "needs.route.outputs.mode == 'collector_handoff'",
        'COLLECTOR_HANDOFF_DATE',
        'finalize_collector_trigger.py',
        'prepare_release_candidate.py',
        'check_ready_contract.py',
        'enrich_full_analysis_v3.py',
        'check_release_input.py',
        'check_intelligence_contract.py',
        'check_preference_contract.py',
        'check_pages_tier_contract.py',
        'python scripts/check_release_architecture.py',
        'python scripts/check_collector_runtime_contract.py',
        'Atomic publish canonical data, derived assets and views',
        'Wait for Pages deployment of publish commit',
        'wait_for_pages_deployment.py',
        'Verify public GitHub Pages release',
        'Write verified publish receipt',
    ):
        if token not in main:
            fail(f'intelligence-build.yml missing architecture token: {token}')

    order = [
        'Validate pre-ready canonical identity and hash',
        'Enrich canonical V3 Full Analysis depth',
        'Release-ready input preflight',
        'Full publish contract QA',
        'Atomic publish canonical data, derived assets and views',
        'Wait for Pages deployment of publish commit',
        'Verify public GitHub Pages release',
        'Write verified publish receipt',
        'Commit operational receipt metadata',
    ]
    positions = []
    for token in order:
        pos = main.find(token)
        if pos < 0:
            fail(f'intelligence-build.yml missing ordered stage: {token}')
        positions.append(pos)
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        fail('canonical publish stage order regressed: ready/depth/preflight/QA/atomic/Pages/DONE must remain ordered')

    prepare_section = main.split('\n  prepare:', 1)[1].split('\n  publish:', 1)[0] if '\n  prepare:' in main and '\n  publish:' in main else ''
    publish_section = main.split('\n  publish:', 1)[1].split('\n  recovery:', 1)[0] if '\n  publish:' in main else ''

    prepare_git_add_lines = [line.strip() for line in prepare_section.splitlines() if line.strip().startswith('git add ')]
    for line in prepare_git_add_lines:
        if 'index.html' in line or 'assets/visual' in line or '$DATE/' in line:
            fail(f'prepare stages public publication surface: {line}')
    if 'git add "data/daily/$DATE.json" "data/publish/$DATE.ready"' not in prepare_section:
        fail('prepare must stage canonical JSON + repo-generated .ready on successful handoff')

    if 'normalize_registry_identity.py' in publish_section:
        fail('Registry normalization must remain pre-ready, not inside publish')
    if 'python scripts/check_release_architecture.py' not in publish_section:
        fail('publish must re-run release architecture guard, including direct .ready/workflow_dispatch paths')
    if main.find('python scripts/check_pages_tier_contract.py') > main.find('Atomic publish canonical data, derived assets and views'):
        fail('tier-aware public-surface contract must run before Atomic Publish')
    if main.find('python scripts/check_preference_contract.py') > main.find('Atomic publish canonical data, derived assets and views'):
        fail('preference surface contract must run before Atomic Publish')
    if 'write_publish_receipt.py' in main and main.find('write_publish_receipt.py') < main.find('verify_pages_publish.py'):
        fail('DONE receipt wiring must occur after Pages verification')

if AUTONOMOUS_COLLECTOR.exists():
    autonomous = AUTONOMOUS_COLLECTOR.read_text('utf-8')
    for token in (
        'name: Autonomous daily Collector',
        "cron: '30 23 * * *'",
        'group: autonomous-daily-collector',
        'cancel-in-progress: false',
        'contents: write',
        'actions: read',
        'python scripts/run_daily_collector.py "$DATE"',
        'python scripts/check_collection_session_contract.py "$DATE"',
        'python scripts/finalize_collection_handoff.py "$DATE"',
        'commit_subject="Collect production intelligence $DATE"',
        'commit_subject="Recollect production intelligence $DATE"',
        'git commit -m "$commit_subject"',
    ):
        if token not in autonomous:
            fail(f'daily-collector.yml missing autonomous Collector token: {token}')
    for forbidden in ('index.html', 'assets/visual', '.request', '.ready'):
        if forbidden in autonomous:
            fail(f'daily-collector.yml crossed Collector/public boundary: {forbidden}')

if COLLECTOR_GATE.exists():
    collector = COLLECTOR_GATE.read_text('utf-8')
    for token in (
        'group: collector-handoff-gate',
        'cancel-in-progress: false',
        "'data/candidates/collection-session/*.json'",
        'actions: read',
        'status=queued',
        'status=in_progress',
        'python scripts/create_collector_trigger.py "$DATE" --writer-idle-confirmed',
        'git commit -m "Collector handoff $DATE"',
    ):
        if token not in collector:
            fail(f'collector-handoff.yml missing runner handoff token: {token}')
    if 'finalize_collection_handoff.py' in collector:
        fail('collector-handoff.yml must not create .request; canonical bridge owns finalizer execution')
    if re.search(r'git\\s+(?:add|rm)[^\\n]*(?:\\.request|\\.ready)', collector):
        fail('collector-handoff.yml must not stage request/ready markers')

collector_trigger = ROOT / 'scripts' / 'create_collector_trigger.py'
if collector_trigger.exists():
    text = collector_trigger.read_text('utf-8')
    for token in (
        'COLLECTOR_PERSISTED',
        '--writer-idle-confirmed',
        'finalize_collection_handoff.py',
        'working tree must be clean before persisted-artifact validation',
        'validation-only finalizer detected unpersisted Collector mutations',
        'public_surfaces_committed',
    ):
        if token not in text:
            fail(f'create_collector_trigger.py missing fail-closed token: {token}')
    if text.count('write_text(') != 1 or 'trigger_path.write_text(' not in text:
        fail('create_collector_trigger.py must write only the .collector marker')

if DAILY_QA.exists():
    qa = DAILY_QA.read_text('utf-8')
    watched = [
        "'config/intelligence-v2.json'",
        "'config/discovery-hybrid.json'",
        "'config/full-analysis-depth.json'",
        "'config/quick-impact-contract.json'",
        "'config/stability-contract.json'",
        "'data/candidates/rolling-backlog.json'",
        "'scripts/discovery_hybrid.py'",
        "'scripts/check_discovery_hybrid_contract.py'",
        "'scripts/enrich_full_analysis_v3.py'",
        "'scripts/check_release_input.py'",
        "'scripts/check_intelligence_contract.py'",
        "'scripts/check_preference_contract.py'",
        "'scripts/check_pages_tier_contract.py'",
        "'scripts/wait_for_pages_deployment.py'",
        "'scripts/verify_pages_publish.py'",
        "'scripts/check_release_architecture.py'",
        "'scripts/create_collector_trigger.py'",
        "'scripts/run_daily_collector.py'",
        "'scripts/check_collector_runtime_contract.py'",
        "'config/collector-runtime.json'",
        "'.github/workflows/daily-collector.yml'",
        "'.github/workflows/collector-handoff.yml'",
        "'.github/workflows/intelligence-build.yml'",
    ]
    for token in watched:
        if token not in qa:
            fail(f'daily-contract.yml does not watch critical release source: {token}')
    for command in (
        'python scripts/check_release_architecture.py',
        'python scripts/check_discovery_hybrid_contract.py',
        'python scripts/check_preference_contract.py',
        'python scripts/check_pages_tier_contract.py',
    ):
        if command not in qa:
            fail(f'daily-contract.yml missing architecture validation command: {command}')

if errors:
    print('RELEASE ARCHITECTURE CONTRACT FAILED')
    print('\n'.join('- ' + e for e in errors))
    sys.exit(1)
print('RELEASE ARCHITECTURE CONTRACT PASS: hybrid discovery + tiered Full/Brief/Reject depth + runner-owned Collector handoff gate + strict pre-ready/public boundary + single canonical writer + ordered QA/atomic/Pages/DONE + daily source-QA coverage')
