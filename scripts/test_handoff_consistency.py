"""Regressions for the Nov 20 mixed-depth handoff and changing candidate IDs."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import editorial_review as review
import finalize_collector_trigger as bridge
import handoff_diagnostics as diagnostics
import intelligence_v2 as intelligence
import check_release_input as release
from normalize_registry_identity import assign_homepage_tiers
from run_daily_collector import stable_id
from test_editorial_review import article, record, envelope, candidate, DATE

ROOT = Path(__file__).resolve().parents[1]
DEPTH = json.loads((ROOT / 'config/full-analysis-depth.json').read_text('utf-8'))


class HandoffConsistencyTests(unittest.TestCase):
    def test_all_tier_gates_accept_full_priority_and_reject_global_top_five(self):
        items = [dict(id=str(i), rank_global=i, analysis_level=level)
                 for i, level in enumerate(['BRIEF', 'FULL', 'FULL', 'BRIEF', 'BRIEF', 'FULL'], 1)]
        assign_homepage_tiers(items, 5, 10, DEPTH['top5_policy'])
        self.assertEqual([x['id'] for x in items if x['homepage_tier'] == 'top5'], ['1','2','3','4','6'])
        data = {'items': items}
        for gate in [intelligence._tier_aware_homepage_errors, release._tier_aware_errors]:
            self.assertEqual(gate(data, DEPTH), [])
            invalid = copy.deepcopy(data)
            for x in invalid['items']:
                x['homepage_tier'] = 'top5' if x['rank_global'] <= 5 else 'next10'
            self.assertTrue(gate(invalid, DEPTH))
        self.assertEqual(items[0]['analysis_level'], 'BRIEF')

    def test_current_session_normalizes_only_in_writer_and_keeps_prose_checks(self):
        from finalize_collection_handoff import collector_data_errors
        data = json.loads((ROOT / 'data/daily/2026-11-20.json').read_text('utf-8'))
        for x in data['items']:
            x['homepage_tier'] = 'top5' if x['rank_global'] <= 5 else 'next10'
        original = copy.deepcopy(data)
        self.assertEqual(collector_data_errors(data, before_normalization=True), [])
        self.assertEqual(data, original)
        self.assertTrue(collector_data_errors(data))
        assign_homepage_tiers(data['items'], 5, 10, DEPTH['top5_policy'])
        self.assertEqual(collector_data_errors(data), [])
        data['items'][0]['summary'] = ''
        self.assertTrue(collector_data_errors(data, before_normalization=True))

    def test_candidate_identity_ignores_discovery_order_title_and_tracking(self):
        urls = ['https://3dnchu.com/archives/alpha/comment-page-1',
                'https://3dnchu.com/archives/bravo/comment-page-1']
        def mapping(order):
            used = set()
            return {u: stable_id('3dnchu', u, 'first title', used) for u in order}
        first = mapping(urls)
        self.assertEqual(first, mapping(list(reversed(urls))))
        self.assertNotEqual(*first.values())
        self.assertEqual(first[urls[0]], stable_id('3dnchu', urls[0]+'?utm_source=x#comment', 'changed title', set()))
        self.assertNotEqual(stable_id('s', 'https://example.com/a?id=1', '', set()),
                            stable_id('s', 'https://example.com/a?id=2', '', set()))

    def test_legacy_id_collision_matches_exact_source_and_still_checks_evidence(self):
        a = article(); c = candidate(a); c['candidate_id'] = 'new-url-id'
        data = envelope(a)
        collision = copy.deepcopy(data['items']['fixture'])
        collision['source_url'] = 'https://example.com/different'
        data['items']['new-url-id'] = collision
        with patch.object(review, 'read_review', return_value=data):
            value, errors = review.candidate_copy(c, DATE)
            self.assertEqual(errors, [])
            self.assertEqual(value['id'], 'new-url-id')
            self.assertEqual(c['scheduled_review']['source_run_id'], data['source_run_id'])
            for field, value in [('published', '2026-10-14'), ('article_evidence', {})]:
                bad = copy.deepcopy(c); bad['meta'][field] = value
                self.assertIsNone(review.candidate_copy(bad, DATE)[0])
            data['items']['duplicate'] = record(a)
            self.assertIn('ambiguous', review.candidate_copy(c, DATE)[1][0])

    def test_last_finalizer_failure_is_persisted_as_controlled_correction(self):
        ok = subprocess.CompletedProcess([], 0, '', '')
        bad = subprocess.CompletedProcess([], 1,
            'COLLECTOR HANDOFF FAILED: collector canonical validation failed: tier mismatch', '')
        with patch.object(bridge, 'event_date', return_value=DATE), \
             patch.object(bridge, 'read_trigger', return_value=Path('marker')), \
             patch.object(bridge, 'trigger_policy_republish', return_value=False), \
             patch.object(bridge, 'wait_for_main_ci'), \
             patch.object(bridge, 'validation_only_finalizer', return_value=ok), \
             patch.object(bridge, 'authoritative_registry_preflight', return_value=ok), \
             patch.object(bridge, 'evidence_depth_preflight', return_value=ok), \
             patch.object(bridge, 'write_request', return_value=bad), \
             patch.object(bridge, 'persist_followup') as followup, \
             patch.object(bridge, 'persist_request') as persist, \
             patch.object(bridge, 'write_output') as output:
            self.assertEqual(bridge.main(), 0)
            persist.assert_not_called()
            self.assertEqual(followup.call_args.kwargs['reason'], 'canonical-content-invalid')
            self.assertIn('tier mismatch', followup.call_args.kwargs['details'])
            output.assert_called_once_with(DATE, 'fix_required', 'canonical-content-invalid')

    def test_existing_marker_resume_is_changed_bounded_and_verified(self):
        marker = dict(date=DATE, state='COLLECTOR_PERSISTED', writer_idle_confirmed_externally=True,
                      generated_by='scripts/create_collector_trigger.py', intent='canonical-publish',
                      input_fingerprint='old', resume_attempts=0)
        with patch.object(diagnostics, 'fingerprint', return_value='new'):
            resumed = diagnostics.resumed_marker(ROOT, DATE, marker)
            self.assertEqual(resumed['resume_attempts'], 1)
            with self.assertRaisesRegex(ValueError, 'unchanged'):
                diagnostics.resumed_marker(ROOT, DATE, resumed)
            with self.assertRaisesRegex(ValueError, 'limit'):
                diagnostics.resumed_marker(ROOT, DATE, {**marker, 'resume_attempts': 2})
            with self.assertRaises(ValueError):
                diagnostics.resumed_marker(ROOT, DATE, {**marker, 'date': 'wrong'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'scripts').mkdir()
            before = diagnostics.fingerprint(root, DATE)
            (root/'scripts/normalize_registry_identity.py').write_text('corrected tiers')
            self.assertNotEqual(before, diagnostics.fingerprint(root, DATE))

    def test_legacy_marker_baseline_is_derived_from_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            git('init', '-b', 'main'); git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            path = root / f'data/publish/{DATE}.collector'; path.parent.mkdir(parents=True)
            marker = dict(date=DATE, state='COLLECTOR_PERSISTED', writer_idle_confirmed_externally=True,
                generated_by='scripts/create_collector_trigger.py', intent='canonical-publish')
            path.write_text(json.dumps(marker))
            git('add', '.'); git('commit', '-m', 'Original marker')
            with self.assertRaisesRegex(ValueError, 'unchanged'):
                diagnostics.resumed_marker(root, DATE, marker)
            (root/'scripts').mkdir()
            (root/'scripts/normalize_registry_identity.py').write_text('corrected FULL-first tiers')
            resumed = diagnostics.resumed_marker(root, DATE, marker)
            self.assertEqual(resumed['resume_attempts'], 1)
            with self.assertRaisesRegex(ValueError, 'unchanged'):
                diagnostics.resumed_marker(root, DATE, resumed)


if __name__ == '__main__':
    unittest.main()
