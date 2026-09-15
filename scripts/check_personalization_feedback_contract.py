#!/usr/bin/env python3
"""Regression guard for bounded Supabase thumbs-up/down personalization.

Rollout dates and policy values come from config/personalization-feedback.json so
this checker validates behavior without becoming a second source of truth.
"""
from datetime import date as date_cls, timedelta
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from personalization_feedback import (  # noqa: E402
    audit_errors,
    derive_weights,
    load_config,
    personalized_score,
    profile_fingerprint,
    semantic_fit,
)

errors = []


def fail(message):
    errors.append(message)


try:
    cfg = load_config()
except Exception as exc:
    print(f'PERSONALIZATION CONTRACT FAILED\n- config invalid: {exc}')
    raise SystemExit(1)

effective = str(cfg.get('effective_date') or '').strip()
effective_day = date_cls.fromisoformat(effective)
legacy_day = (effective_day - timedelta(days=1)).isoformat()
rank_cap = float((cfg.get('ranking') or {}).get('max_rank_multiplier', 0.0))
query_cap = float((cfg.get('discovery') or {}).get('max_query_expansion_fraction', 0.0))

if ((cfg.get('signals') or {}).get('bookmark')) != 0.0:
    fail('bookmark signal must remain zero')
if rank_cap <= 0:
    fail('dynamic ranking influence cap must be positive')
if query_cap < 0:
    fail('dynamic discovery query expansion cap must be non-negative')

fixture_time = f'{legacy_day}T00:00:00Z'
votes = {
    'liked-meshy': {
        'vote': 1,
        'updatedAt': fixture_time,
        'features': {
            'category': ['ai-generation'],
            'tools': ['Meshy'],
            'topics': ['Image-to-3D'],
            'tags': ['multi-view'],
        },
    },
    'disliked-generic': {
        'vote': -1,
        'updatedAt': fixture_time,
        'features': {
            'category': ['emerging-case'],
            'tools': [],
            'topics': ['generic-hype'],
            'tags': ['marketing'],
        },
    },
}
weights = derive_weights(votes, as_of=f'{effective}T00:00:00Z', cfg=cfg)
if weights.get('tool', {}).get('Meshy', 0) <= 0:
    fail('like fixture did not produce positive Meshy weight')
if weights.get('topic', {}).get('generic-hype', 0) >= 0:
    fail('dislike fixture did not produce negative topic weight')

positive_fit = semantic_fit(weights, {
    'category': ['ai-generation'], 'tool': ['Meshy'], 'topic': ['Image-to-3D'], 'tag': ['multi-view']
}, cfg=cfg)
negative_fit = semantic_fit(weights, {
    'category': ['emerging-case'], 'topic': ['generic-hype'], 'tag': ['marketing']
}, cfg=cfg)
neutral_fit = semantic_fit(weights, {'category': ['3d-production'], 'topic': ['UV']}, cfg=cfg)
if not (positive_fit > neutral_fit >= negative_fit):
    fail(f'semantic fit ordering invalid: positive={positive_fit} neutral={neutral_fit} negative={negative_fit}')

base = 80.0
hi = personalized_score(base, 1.0, cfg=cfg)
lo = personalized_score(base, -1.0, cfg=cfg)
expected_hi = round(min(100.0, base * (1.0 + rank_cap)), 2)
expected_lo = round(max(0.0, base * (1.0 - rank_cap)), 2)
if abs(hi - expected_hi) > 1e-9 or abs(lo - expected_lo) > 1e-9:
    fail(
        'configured rank bound not honored: '
        f'base={base} cap={rank_cap} low={lo}/{expected_lo} high={hi}/{expected_hi}'
    )

fingerprint = profile_fingerprint(weights)
legacy = {'date': legacy_day, 'metadata': {}}
if audit_errors(legacy, cfg):
    fail(f'historical date before configured rollout ({legacy_day}) must not require personalization metadata')
missing = {'date': effective, 'metadata': {}}
if not audit_errors(missing, cfg):
    fail(f'configured effective date ({effective}) must require personalization audit metadata')
valid = {
    'date': effective,
    'metadata': {
        'personalization': {
            'contract': cfg['mode'],
            'status': 'applied',
            'vote_count': 2,
            'profile_fingerprint': fingerprint,
            'max_rank_multiplier': rank_cap,
            'max_query_expansion_fraction': query_cap,
            'raw_profile_committed': False,
            'bookmarks_used': False,
            'domain_weights_used': False,
            'admission_bypass': False,
            'quality_gate_bypass': False,
            'source_quota': False,
        }
    },
}
valid_errors = audit_errors(valid, cfg)
if valid_errors:
    fail('valid applied fixture rejected: ' + '; '.join(valid_errors))

if len(sys.argv) > 1:
    target_date = sys.argv[1].strip()
    path = ROOT / 'data' / 'daily' / f'{target_date}.json'
    if not path.exists():
        fail(f'missing canonical dataset for personalization check: {path.relative_to(ROOT)}')
    else:
        data = json.loads(path.read_text('utf-8'))
        for err in audit_errors(data, cfg):
            fail(f'{target_date}: {err}')

if errors:
    print('PERSONALIZATION CONTRACT FAILED')
    print('\n'.join('- ' + e for e in errors))
    raise SystemExit(1)

print(
    'PERSONALIZATION CONTRACT PASS: config-driven rollout + semantic-only thumbs-up/down '
    f'discovery/ranking bounds (rank={rank_cap:.3f}, query={query_cap:.3f}); bookmarks and '
    'source/domain identity remain zero-weight; pre-effective historical dates stay unchanged'
)
