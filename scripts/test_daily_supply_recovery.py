"""Cross-day release, bounded recovery, and genuine reserve ingestion regressions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
import check_historical_regression as history
import render_information_architecture as render
import editorial_review as review
import handoff_route as route
import handoff_diagnostics as diagnostics
from check_editorial_submission import readiness_errors
from editorial_reserve import approved_reserve
from article_evidence import extract_article_evidence
from run_daily_collector import page_metadata
from test_editorial_review import article, envelope, DATE, SHA

ROOT = Path(__file__).resolve().parents[1]

class DailySupplyRecoveryTests(unittest.TestCase):
    def test_today_becomes_history_with_full_priority_and_strict_card_parity(self):
        date = '2026-11-20'
        data = json.loads((ROOT / f'data/daily/{date}.json').read_text('utf-8'))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / date).mkdir()
            page = root / date / 'index.html'
            page.write_text((ROOT / date / 'index.html').read_text('utf-8'), 'utf-8')
            (root / 'data/daily').mkdir(parents=True)
            (root / f'data/daily/{date}.json').write_text(json.dumps(data), 'utf-8')
            with patch.object(render, 'ROOT', root):
                render.render_daily(date, data, render.load_config())
            with patch.object(history, 'ROOT', root), patch.object(history, 'errors', []), patch.object(history, 'rows', []):
                history.validate_canonical_archive_parity(date)
                self.assertEqual(history.errors, [])
                # Tomorrow exists: exercise the actual historical branch, not just today's renderer.
                (root / 'data/daily/2026-11-21.json').write_text('{"items":[]}')
                history.canonical_rebuild_simulation(date)
                self.assertEqual(history.errors, [])
                self.assertIn((date, 'canonical-parity', 'PASS'), history.rows)
                original = page.read_text('utf-8')
                soup = BeautifulSoup(original, 'html.parser')
                card = soup.select_one('#top [data-intel-id]')
                for defect in ('foreign', 'duplicate', 'missing', 'wrong-order'):
                    changed = BeautifulSoup(original, 'html.parser')
                    top = changed.select_one('#top [data-intel-id]')
                    if defect == 'foreign': top['data-intel-id'] = 'foreign-id'
                    elif defect == 'duplicate': top.insert_after(copy.copy(top))
                    elif defect == 'missing': top.decompose()
                    else: changed.select_one('#more [data-intel-id]').insert_after(top.extract())
                    page.write_text(str(changed), 'utf-8')
                    history.errors.clear()
                    history.validate_canonical_archive_parity(date)
                    self.assertTrue(history.errors, defect)

    def test_current_regression_fix_allows_one_recovery_not_old_duplicate_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ['data/daily', 'data/publish', 'data/candidates/collection-session', 'scripts']:
                (root / folder).mkdir(parents=True)
            for date in ['2026-11-21', '2026-11-23']:
                (root / f'data/daily/{date}.json').write_text('{}')
                (root / f'data/candidates/collection-session/{date}.json').write_text('{}')
                marker = dict(date=date, state='COLLECTOR_PERSISTED', writer_idle_confirmed_externally=True,
                    generated_by='scripts/create_collector_trigger.py', intent='canonical-publish', resume_attempts=0,
                    input_fingerprint=diagnostics.fingerprint(root, date))
                (root / f'data/publish/{date}.collector').write_text(json.dumps(marker))
            self.assertEqual(route.corrected_pending_session(root), '')
            (root / 'scripts/check_historical_regression.py').write_text('corrected ordering')
            self.assertEqual(route.corrected_pending_session(root), '2026-11-23')
            self.assertFalse(route.pending_session(root, '2026-11-21'))
            path = root / 'data/publish/2026-11-23.collector'
            marker = json.loads(path.read_text()); marker['resume_attempts'] = 2
            path.write_text(json.dumps(marker))
            self.assertEqual(route.corrected_pending_session(root), '')
            marker['resume_attempts'] = 0; path.write_text(json.dumps(marker))
            (root / 'data/publish/2026-11-23.ready').write_text('{}')
            self.assertEqual(route.corrected_pending_session(root), '')

    def test_one_article_successful_run_can_feed_reserve_without_release_threshold_change(self):
        a = article(); data = {**envelope(a), 'purpose': 'reserve'}
        run = dict(id=123, head_sha=SHA, head_branch='main', created_at='2026-10-14T23:41:00Z',
            name='Autonomous daily Collector', status='completed', conclusion='success')
        review.validate_run(data, run, DATE)
        for field, value in [('status', 'in_progress'), ('conclusion', 'skipped'), ('head_branch', 'feature'), ('head_sha', 'b'*40)]:
            with self.assertRaises(review.ReviewError): review.validate_run(data, {**run, field: value}, DATE)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ['data/editorial-reviews', 'data/candidates/collection-session', 'data/publish']:
                (root / folder).mkdir(parents=True)
            (root / f'data/editorial-reviews/{DATE}.json').write_text(json.dumps(data), 'utf-8')
            (root / f'data/candidates/collection-session/{DATE}.json').write_text('{}')
            copies = review.validate_packet(data, {'date': DATE, 'articles': [a]}, DATE)
            self.assertEqual(readiness_errors(copies, DATE, root, purpose='reserve'), [])
            self.assertTrue(readiness_errors(copies, DATE, root))
            self.assertIn(a['source_url'], approved_reserve(root, DATE))
            c = {'candidate_id': a['id'], 'source_url': a['source_url'], 'meta': {'published': DATE, 'article_evidence': a['evidence']}}
            self.assertIsNotNone(review.candidate_copy(c, '2026-10-16', root)[0])
            c['meta']['article_evidence'] = {**a['evidence'], 'truncated': True}
            self.assertIsNone(review.candidate_copy(c, '2026-10-16', root)[0])

    def test_blender_forum_only_first_post_body_and_date_not_replies(self):
        paragraph = 'The animation module discusses joint based armatures and a proposed importer. ' * 3
        html = '<html><h1>Animation module meeting</h1><meta itemprop="datePublished" content="2026-11-22">' + \
            '<div id="post_1"><time datetime="2026-11-12T18:43:00Z"></time><div class="post" itemprop="text"><h2>Proposal</h2>' + \
            '<p>' + paragraph + '</p><p>Known limitations: no implementation or performance benchmark was provided at this meeting.</p></div></div>' + \
            '<div id="post_2"><div class="post" itemprop="text"><p>REPLY INVENTED CLAIM</p></div></div></html>'
        url = 'https://forum.blender.org/t/meeting/123'
        evidence = extract_article_evidence(html, url)
        self.assertEqual(evidence['status'], 'extracted')
        self.assertNotIn('REPLY INVENTED CLAIM', str(evidence))
        meta = page_metadata({'html': html, 'final_url': url})
        self.assertEqual(meta['published'], '2026-11-12')
        missing = html.replace('datetime="2026-11-12T18:43:00Z"', '')
        self.assertIsNone(page_metadata({'html': missing, 'final_url': url})['published'])
        self.assertEqual(extract_article_evidence(html, 'https://other.example/')['status'], 'body-missing')

if __name__ == '__main__': unittest.main()
