#!/usr/bin/env python3
"""Fail-closed architecture guard for the canonical intelligence release pipeline.

This guard validates cross-file wiring that is easy to regress when individual
contracts evolve: hybrid discovery, Full Analysis depth, single-writer handoff,
atomic publication, Pages verification, and source-QA coverage.
"""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / '.github' / 'workflows'
MAIN = WF / 'intelligence-build.yml'
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
    'data/candidates/rolling-backlog.json',
    'scripts/discovery_hybrid.py',
    'scripts/check_discovery_hybrid_contract.py',
    'scripts/normalize_registry_identity_hybrid.py',
    'scripts/check_release_input.py',
    'scripts/enrich_full_analysis_v3.py',
    'scripts/check_intelligence_contract.py',
    'scripts/prepare_release_candidate.py',
    'scripts/check_ready_contract.py',
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
            if top5.get('allow_brief') is not False:
                fail('full-analysis-depth top5_policy must keep allow_brief=false')
        else:
            # Legacy FULL-only contract support for older branches/configs.
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

if MAIN.exists():
    main = MAIN.read_text('utf-8')
    for token in (
        'group: canonical-intelligence-publish',
        'cancel-in-progress: false',
        "- 'data/publish/*.request'",
        "- 'data/publish/*.ready'",
        'prepare_release_candidate.py',
        'check_ready_contract.py',
        'enrich_full_analysis_v3.py',
        'check_release_input.py',
        'check_intelligence_contract.py',
        'python scripts/check_release_architecture.py',
        'Atomic publish canonical data, derived assets and views',
        'Verify public GitHub Pages release',
        'Write verified publish receipt',
    ):
        if token not in main:
            fail(f'intelligence-build.yml missing architecture token: {token}')

    # Enforce critical publication ordering, not just token presence.
    order = [
        'Validate pre-ready canonical identity and hash',
        'Enrich canonical V3 Full Analysis depth',
        'Release-ready input preflight',
        'Full publish contract QA',
        'Atomic publish canonical data, derived assets and views',
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

    # Prepare may persist canonical JSON + repo-generated .ready only. Public
    # HTML/assets belong exclusively to Atomic Publish. This prevents a future
    # restore/preflight regression from leaking half-built Pages content.
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
    if 'write_publish_receipt.py' in main and main.find('write_publish_receipt.py') < main.find('verify_pages_publish.py'):
        fail('DONE receipt wiring must occur after Pages verification')

# Daily source QA must actually watch every contract that controls tomorrow's run.
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
        "'scripts/check_release_architecture.py'",
        "'.github/workflows/intelligence-build.yml'",
    ]
    for token in watched:
        if token not in qa:
            fail(f'daily-contract.yml does not watch critical release source: {token}')
    for command in ('python scripts/check_release_architecture.py', 'python scripts/check_discovery_hybrid_contract.py'):
        if command not in qa:
            fail(f'daily-contract.yml missing architecture validation command: {command}')

if errors:
    print('RELEASE ARCHITECTURE CONTRACT FAILED')
    print('\n'.join('- ' + e for e in errors))
    sys.exit(1)
print('RELEASE ARCHITECTURE CONTRACT PASS: hybrid discovery + tiered Full/Brief/Reject depth + strict pre-ready/public boundary + single-writer handoff + ordered QA/atomic/Pages/DONE + daily source-QA coverage')
