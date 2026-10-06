#!/usr/bin/env python3
"""Feedback bridge, ranking, discovery and full Collector integration regressions."""
import copy
import json
import unittest
from unittest.mock import Mock, patch
import requests
import run_daily_collector as collector
from collector_personalization import (load_owner_preferences, candidate_features,
    apply_candidate_personalization, positive_expansion_terms, expand_source_links)
from personalization_feedback import load_config, derive_weights, audit_errors

CFG = load_config()
SIGNALS = [
    {'vote': 1, 'updatedAt': '2026-10-01T00:00:00Z', 'features': {'category': [], 'tools': ['Houdini'], 'topics': ['Shader'], 'tags': []}},
    {'vote': -1, 'updatedAt': '2026-10-01T00:00:00Z', 'features': {'category': [], 'tools': ['Blender'], 'topics': [], 'tags': []}},
]
BODY = {'schema_version': 1, 'owner_verified': True, 'vote_count': 2, 'signals': SIGNALS}
ENV = {'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://pipelines.actions.githubusercontent.com/test?api-version=2',
       'ACTIONS_ID_TOKEN_REQUEST_TOKEN': 'private-request-token'}


def response(body, status=200):
    res = requests.Response()
    res.status_code = status
    res._content = json.dumps(body).encode()
    return res


class FeedbackTests(unittest.TestCase):
    def reader(self, body=BODY):
        http = Mock()
        http.get.return_value = response({'value': 'private-oidc-token-12345'})
        http.post.return_value = response(body)
        result = load_owner_preferences(CFG, env=ENV, session=http, as_of='2026-10-06T00:00:00Z')
        return http, result

    def test_verified_owner_and_private_in_memory_only(self):
        http, (weights, audit) = self.reader()
        self.assertEqual((audit['status'], audit['vote_count']), ('applied', 2))
        self.assertGreater(weights['tool']['Houdini'], 0)
        self.assertLess(weights['tool']['Blender'], 0)
        self.assertEqual(audit_errors({'date': '2026-10-07', 'metadata': {'personalization': audit}}, CFG), [])
        self.assertNotIn('signals', audit)
        self.assertNotIn('weights', audit)
        self.assertIn('audience=https%3A', http.get.call_args.args[0])
        self.assertFalse(http.post.call_args.kwargs['allow_redirects'])

    def test_empty_owner_is_distinct_from_unavailable(self):
        _, (_, audit) = self.reader({**BODY, 'signals': [], 'vote_count': 0})
        self.assertEqual(audit['status'], 'empty')
        self.assertIn('profile_fingerprint', audit)

    def test_outages_invalid_owner_and_auth_failures_are_neutral(self):
        for body in ({**BODY, 'owner_verified': False}, {**BODY, 'vote_count': 100},
                     {**BODY, 'bookmarks': {'secret': 1}}, {**BODY, 'signals': [{'vote': True}]}):
            _, (weights, audit) = self.reader(body)
            self.assertEqual(audit['status'], 'unavailable')
            self.assertTrue(all(not values for values in weights.values()))
            self.assertNotIn('profile_fingerprint', audit)
        for failure in (requests.Timeout('private-token'), requests.HTTPError('private-token')):
            http = Mock(); http.get.side_effect = failure
            _, audit = load_owner_preferences(CFG, env=ENV, session=http)
            self.assertEqual(audit['status'], 'unavailable')
            self.assertNotIn('private-token', json.dumps(audit))
        http = Mock()
        _, audit = load_owner_preferences(CFG, env={}, session=http)
        self.assertEqual(audit['status'], 'unavailable'); http.get.assert_not_called()
        for url in ('http://pipelines.actions.githubusercontent.com/test', 'https://actions.githubusercontent.com.evil.invalid/test'):
            http = Mock()
            _, audit = load_owner_preferences(CFG, env={**ENV, 'ACTIONS_ID_TOKEN_REQUEST_URL': url}, session=http)
            self.assertEqual(audit['status'], 'unavailable'); http.get.assert_not_called()

    def test_positive_negative_neutral_ranking_and_no_compounding(self):
        _, (weights, _) = self.reader()
        candidates = [dict(title=title, category='blender-dcc', ranking_score=80, source_url=url)
                      for title, url in [('Houdini Shader', 'https://a.invalid'),
                                         ('Blender workflow', 'https://b.invalid'),
                                         ('Maya animation', 'https://c.invalid')]]
        self.assertEqual(apply_candidate_personalization(candidates, weights, CFG), 2)
        self.assertGreater(candidates[0]['ranking_score'], 80)
        self.assertLess(candidates[1]['ranking_score'], 80)
        self.assertEqual(candidates[2]['ranking_score'], 80)
        scores = [c['ranking_score'] for c in candidates]
        apply_candidate_personalization(candidates, weights, CFG)
        self.assertEqual(scores, [c['ranking_score'] for c in candidates])
        for c in candidates:
            self.assertLessEqual(abs(c['ranking_score'] - 80), 16)

    def test_source_and_bookmarks_cannot_supply_semantics(self):
        _, (weights, _) = self.reader()
        self.assertEqual(candidate_features({'title':'General article', 'source_url':'https://Houdini.invalid', 'source':'Houdini'})['tool'], [])
        altered = copy.deepcopy(BODY)
        altered['signals'][0]['features']['tags'] = ['80 Level', 'cgchannel.com']
        _, (other, _) = self.reader(altered)
        self.assertEqual(weights, other)

    def test_semantic_expansion_supplements_all_base_links_with_bounded_budget(self):
        _, (weights, _) = self.reader()
        terms = positive_expansion_terms(weights, CFG)
        self.assertIn('Houdini', terms); self.assertNotIn('Blender', terms)
        links = [(f'https://example.invalid/{i}', 'General article') for i in range(10)]
        links += [(f'https://example.invalid/extra-{i}', 'Houdini Shader tutorial') for i in range(10)]
        chosen, extra = expand_source_links(links, 10, terms, CFG)
        self.assertEqual(chosen[:10], links[:10]); self.assertEqual(len(extra), 2)
        chosen, extra = expand_source_links(links, 10, [], CFG)
        self.assertEqual(chosen, links[:10]); self.assertEqual(extra, set())

    def test_full_collector_consumes_feedback_before_selection_and_keeps_private_data_out(self):
        _, (weights, audit) = self.reader()
        candidates = []
        for i in range(14):
            title = 'Houdini Shader tutorial' if i == 13 else 'Maya animation tutorial'
            url = f'https://80.lv/articles/feedback-fixture-{i:02}'
            candidates.append({'candidate_id':f'fixture-{i}', 'source_id':'80-level', 'source_url':url,
                'title':title, 'description':'Production tutorial', 'published':'2026-10-07', 'window':'24h',
                'category':'blender-dcc', 'subcategory':'houdini' if i == 13 else 'maya', 'ranking_score':75,
                'brief_reason':'single-source-verified-production-tip',
                'meta':{'title':title,'description':'Production tutorial','url':url}})
        record = {'status':'checked','method':'latest-index','candidates_found':14,
                  'candidate_ids':[c['candidate_id'] for c in candidates], 'refill_links_checked':1}
        outputs = {}
        def capture(path, value): outputs[str(path.relative_to(collector.ROOT))] = value
        with patch.object(collector.sys, 'argv', ['collector', '2026-10-07']), \
             patch.object(collector, 'load_owner_preferences', return_value=(weights, audit)), \
             patch.object(collector, 'registered_source_probe_plan', return_value={'selected':['80-level']}), \
             patch.object(collector, 'registered_source_refill_plan', return_value={'selected':[]}), \
             patch.object(collector, 'source_probe', return_value=(candidates, record)) as probe, \
             patch.object(collector, 'write_json', side_effect=capture):
            self.assertEqual(collector.main(), 0)
        daily = outputs['data/daily/2026-10-07.json']
        self.assertEqual(daily['items'][0]['id'], 'fixture-13')
        self.assertEqual(len(daily['items']), 14)
        self.assertEqual(daily['metadata']['personalization']['status'], 'applied')
        self.assertEqual(daily['metadata']['personalization']['ranking_adjusted_count'], 1)
        self.assertEqual(daily['items'][0]['quick_impact'], collector.stars(75))
        self.assertIn('Houdini', probe.call_args.kwargs['expansion_terms'])
        serialized = json.dumps(outputs)
        for forbidden in ('private-request-token','private-oidc-token','"signals"','"weights"','"bookmarks"'):
            self.assertNotIn(forbidden, serialized)


if __name__ == '__main__':
    unittest.main()
