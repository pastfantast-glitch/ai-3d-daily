"""Crash/resume and fail-closed progress tests; no network or model calls."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import editorial_progress as progress
from test_editorial_review import article, record, DATE, SHA


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = article()
        self.packet = {'date': DATE, 'source_run_id': 123, 'source_head_sha': SHA, 'articles': [self.a]}
        self.run = {'id': 123, 'head_sha': SHA, 'head_branch': 'main',
                    'created_at': DATE + 'T00:00:00Z', 'name': 'Autonomous daily Collector',
                    'status': 'completed', 'conclusion': 'failure'}
        self.session = progress.initialize(self.root, self.packet, self.run)
        self.approved = record(self.a)
        self.draft = copy.deepcopy(self.approved)
        self.draft['review']['approved'] = False
        self.draft['reviewed_on'] = None

    def draft_then_approve(self):
        progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)
        return progress.change(self.session, 1, 'approve', cid='fixture', record=self.approved)

    def test_download_is_not_completion_and_zero_approvals_cannot_export(self):
        state = progress.summary(progress.load(self.session)[0])
        self.assertEqual(state['state'], 'REVIEW_INCOMPLETE')
        self.assertEqual(state['next_article_id'], 'fixture')
        self.assertFalse(state['publication_verified'])
        with self.assertRaises(progress.ReviewError):
            progress.export_review(self.session, 'release')

    def test_resume_keeps_draft_and_selects_second_pass(self):
        progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)
        restarted = progress.initialize(self.root, self.packet, self.run)
        state = progress.load(restarted)[0]
        self.assertEqual(state['items']['fixture']['record'], self.draft)
        self.assertEqual(state['revision'], 1)
        self.assertIn('second pass', progress.summary(state)['next_step'])
        with self.assertRaises(progress.ReviewError):
            progress.export_review(restarted, 'reserve')

    def test_approval_requires_separate_unchanged_draft(self):
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 0, 'approve', cid='fixture', record=self.approved)
        progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)
        changed = copy.deepcopy(self.approved)
        changed['summary'] += 'changed'
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 1, 'approve', cid='fixture', record=changed)
        changed = copy.deepcopy(self.approved)
        changed['review']['checks']['faithful_to_source'] = False
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 1, 'approve', cid='fixture', record=changed)

    def test_actual_validator_and_approved_only_export(self):
        self.draft_then_approve()
        result = progress.export_review(self.session, 'release')
        self.assertEqual(result['items'], {'fixture': self.approved})
        self.assertNotIn('blocks', json.dumps(result))
        self.assertNotIn('packet_sha256', result)
        self.assertEqual(progress.summary(progress.load(self.session)[0])['state'], 'REVIEWED_UNSUBMITTED')

    def test_changed_evidence_or_run_cannot_resume(self):
        changed = copy.deepcopy(self.packet)
        changed['articles'][0]['evidence']['blocks'][0]['text'] = 'different'
        with self.assertRaises(progress.ReviewError):
            progress.initialize(self.root, changed, self.run)
        progress.atomic_write(self.session / 'packet.json', changed)
        with self.assertRaises(progress.ReviewError):
            progress.load(self.session)

    def test_stale_revision_and_exclusive_lock_preserve_existing_draft(self):
        progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 0, 'exclude', cid='fixture', reason='stale')
        (self.session / '.lock').touch()
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 1, 'exclude', cid='fixture', reason='concurrent')
        self.assertTrue((self.session / '.lock').exists())
        self.assertEqual(progress.load(self.session)[0]['items']['fixture']['state'], 'draft')

    def test_interrupted_atomic_save_leaves_original_checkpoint(self):
        before = (self.session / 'progress.json').read_bytes()
        with patch.object(progress.os, 'replace', side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)
        self.assertEqual((self.session / 'progress.json').read_bytes(), before)
        self.assertFalse((self.session / '.lock').exists())
        self.assertEqual(list(self.session.glob('.pending-*')), [])

    def test_two_round_limit_and_exclusion_reason(self):
        progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)
        progress.change(self.session, 1, 'draft', cid='fixture', record=self.draft)
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 2, 'draft', cid='fixture', record=self.draft)
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 2, 'exclude', cid='fixture', reason='')
        state = progress.change(self.session, 2, 'exclude', cid='fixture', reason='insufficient support')
        self.assertEqual(state['state'], 'NO_APPROVED_CONTENT')

    def test_blocker_and_submission_are_not_publication_success(self):
        self.draft_then_approve()
        result = progress.change(self.session, 2, 'block', reason='GitHub unavailable; inspect existing PR before retry')
        self.assertEqual(result['state'], 'BLOCKED')
        with self.assertRaises(progress.ReviewError):
            progress.export_review(self.session, 'release')
        progress.change(self.session, 3, 'resume')
        url = 'https://github.com/pastfantast-glitch/ai-3d-daily/pull/123'
        result = progress.change(self.session, 4, 'submission', url=url)
        self.assertEqual(result['state'], 'SUBMITTED_UNVERIFIED')
        self.assertFalse(result['publication_verified'])
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 5, 'submission', url=url + '4')

    def test_extra_source_body_field_cannot_be_saved(self):
        self.draft['evidence'] = self.a['evidence']
        with self.assertRaises(progress.ReviewError):
            progress.change(self.session, 0, 'draft', cid='fixture', record=self.draft)

    def test_work_limit_keeps_remaining_articles_pending(self):
        packet = copy.deepcopy(self.packet)
        packet['source_run_id'] = 124
        packet['articles'] = [{**self.a, 'id': str(n)} for n in range(41)]
        run = {**self.run, 'id': 124}
        session = progress.initialize(self.root, packet, run)
        for n in range(40):
            progress.change(session, n, 'exclude', cid=str(n), reason='duplicate fixture')
        with self.assertRaises(progress.ReviewError):
            progress.change(session, 40, 'exclude', cid='40', reason='beyond limit')
        self.assertEqual(progress.summary(progress.load(session)[0])['counts']['pending'], 1)


if __name__ == '__main__':
    unittest.main()
