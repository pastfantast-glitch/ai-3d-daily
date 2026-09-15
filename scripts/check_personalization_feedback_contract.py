#!/usr/bin/env python3
"""Regression guard for bounded Supabase thumbs-up/down personalization."""
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

if cfg.get('effective_date') != '2026-09-16':
    fail('effective_date must remain 2026-09-16 for the rollout contract')
if ((cfg.get('signals') or {}).get('bookmark')) != 0.0:
    fail('bookmark signal must remain zero')
if ((cfg.get('ranking') or {}).get('max_rank_multiplier')) != 0.20:
    fail('dynamic ranking influence must remain capped at 20%')
if ((cfg.get('discovery') or {}).get('max_query_expansion_fraction')) != 0.20:
    fail('dynamic discovery query expansion must remain capped at 20%')

votes = {
    'liked-meshy': {
        'vote': 1,
        'updatedAt': '2026-09-15T00:00:00Z',
        'features': {
            'category': ['ai-generation'],
            'tools': ['Meshy'],
            'topics': ['Image-to-3D'],
            'tags': ['multi-view'],
        },
    },
    'disliked-generic': {
        'vote': -1,
        'updatedAt': '2026-09-15T00:00:00Z',
        'features': {
            'category': ['emerging-case'],
            'tools': [],
            'topics': ['generic-hype'],
            'tags': ['marketing'],
        },
    },
}
weights = derive_weights(votes, as_of='2026-09-16T00:00:00Z', cfg=cfg)
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
if hi > 96.0 or lo < 64.0:
    fail(f'20% rank bound violated: base={base} low={lo} high={hi}')

fingerprint = profile_fingerprint(weights)
legacy = {'date': '2026-09-15', 'metadata': {}}
if audit_errors(legacy, cfg):
    fail('historical 2026-09-15 must not require personalization metadata')
missing = {'date': '2026-09-16', 'metadata': {}}
if not audit_errors(missing, cfg):
    fail('2026-09-16 must require personalization audit metadata')
valid = {
    'date': '2026-09-16',
    'metadata': {
        'personalization': {
            'contract': cfg['mode'],
            'status': 'applied',
            'vote_count': 2,
            'profile_fingerprint': fingerprint,
            'max_rank_multiplier': 0.20,
            'max_query_expansion_fraction': 0.20,
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
    date = sys.argv[1].strip()
    path = ROOT / 'data' / 'daily' / f'{date}.json'
    if not path.exists():
        fail(f'missing canonical dataset for personalization check: {path.relative_to(ROOT)}')
    else:
        data = json.loads(path.read_text('utf-8'))
        for err in audit_errors(data, cfg):
            fail(f'{date}: {err}')

if errors:
    print('PERSONALIZATION CONTRACT FAILED')
    print('\n'.join('- ' + e for e in errors))
    raise SystemExit(1)

print('PERSONALIZATION CONTRACT PASS: Supabase thumbs-up/down feeds semantic-only discovery/ranking with 20% caps; bookmarks and source/domain identity remain zero-weight; historical dates stay unchanged')
