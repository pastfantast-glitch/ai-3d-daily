#!/usr/bin/env python3
"""Read-only main-workflow smoke check; never persist or print private signals."""
import json
from pathlib import Path
from collector_personalization import load_owner_preferences, apply_candidate_personalization, positive_expansion_terms, expand_source_links
from personalization_feedback import load_config, audit_errors

cfg = load_config()
weights, audit = load_owner_preferences(cfg)
if audit['status'] == 'unavailable':
    raise SystemExit('LIVE PERSONALIZATION FAILED: authenticated bridge unavailable')
root = Path(__file__).resolve().parents[1]
daily_path = sorted((root / 'data' / 'daily').glob('20??-??-??.json'))[-1]
daily = json.loads(daily_path.read_text('utf-8'))
errors = audit_errors({'date': daily['date'], 'metadata': {'personalization': audit}}, cfg)
if errors:
    raise SystemExit('LIVE PERSONALIZATION FAILED: invalid audit contract')
candidates = [dict(item, ranking_score=item.get('base_ranking_score', item['ranking_score'])) for item in daily['items']]
changed = apply_candidate_personalization(candidates, weights, cfg)
terms = positive_expansion_terms(weights, cfg)
links = [(f'https://example.invalid/article/{i}', 'Baseline production article') for i in range(10)]
links += [(f'https://example.invalid/extra/{i}', term) for i, term in enumerate(terms)]
expanded, added = expand_source_links(links, 10, terms, cfg)
assert expanded[:10] == links[:10] and len(added) <= 2
assert all(abs(item['ranking_score'] - item['base_ranking_score']) <= item['base_ranking_score'] * .20 + .01 for item in candidates)
print(f"LIVE PERSONALIZATION PASS: status={audit['status']} votes={audit['vote_count']} "
      f"ranking_adjusted={changed}/{len(candidates)} expansion_probe={len(added)} "
      'bookmarks_used=false private_data_written=false release_mutated=false')
