"""Review handoff regressions; no external model, credentials or network."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import editorial_review as review
import run_daily_collector as collector

DATE = '2026-10-15'
SHA = 'a' * 40
DRAFT = {'title': '布料工具：以筆刷調整衣褶輪廓',
         'summary': '這套布料工具示範在網格上以筆刷建立衣褶並調整輪廓，適合檢視衣物形狀與局部折線的變化。',
         'evidence_refs': ['p001'], 'full_analysis': [
             {'label': '技術變更', 'text': '工具在既有網格上提供衣褶筆刷，示範者調整筆刷大小和強度後沿衣物表面畫出折線，再觀察模型形狀。', 'evidence_refs': ['p001']},
             {'label': '製作用途', 'text': '教學直接展示筆刷編輯前後的網格，因此美術可以從畫面比較局部衣褶的方向與輪廓，理解修改的作用。', 'evidence_refs': ['p002']},
             {'label': '適用限制', 'text': '原文示範的是單件衣物網格的局部調整，沒有提供批次處理的數據，也沒有說明遊戲引擎內的運算成本。', 'evidence_refs': ['p002']} ]}


def article():
    evidence = {'status': 'extracted', 'truncated': False, 'blocks': [
        {'id': 'p001', 'text': 'A cloth brush edits folds on the mesh; size and strength control the strokes.'},
        {'id': 'p002', 'text': 'The single garment example shows before and after shapes. No batch or engine benchmarks are given.'}]}
    evidence['sha256'] = review.evidence_hash(evidence)
    return {'id': 'fixture', 'source_url': 'https://example.com/cloth', 'source_published_at': DATE,
            'evidence': evidence}


def record(a):
    return {**copy.deepcopy(DRAFT), 'source_url': a['source_url'],
        'source_published_at': a['source_published_at'], 'source_evidence_sha256': a['evidence']['sha256'],
        'reviewed_on': DATE, 'review': {'approved': True, 'method': 'second-pass-source-check',
        'checks': dict.fromkeys(review.CHECKS, True), 'issues': [], 'unsupported_claims': [], 'evidence_refs': ['p001', 'p002']}}


def envelope(a):
    return {'schema_version': 1, 'date': DATE, 'reviewer': 'chatgpt-scheduled-task',
            'source_run_id': 123, 'source_head_sha': SHA, 'items': {a['id']: record(a)}}


def candidate(a):
    return {'candidate_id': a['id'], 'source_url': a['source_url'],
        'category': '3d-production', 'subcategory': 'character-production',
        'meta': {'published': DATE, 'article_evidence': a['evidence'], 'title': 'Cloth brush'},
        'reader_copy': {'id': a['id'], 'title': 'Bad', 'summary': 'Bad', 'full_analysis': []}}


class Tests(unittest.TestCase):
    def test_scheduled_helper_keeps_drafts_unapproved(self):
        from prepare_editorial_review import scheduled_drafts
        a = article()
        result = scheduled_drafts({'date': DATE, 'articles': [a]}, 123, SHA)
        row = result['items'][a['id']]
        self.assertIs(row['review']['approved'], False)
        self.assertIsNone(row['reviewed_on'])
        self.assertNotIn('source_reviewed', row)
        self.assertEqual(result['source_run_id'], 123)

    def test_approved_record_preserves_identity_and_strips_internal_fields(self):
        a = article()
        result = review.validate_record(record(a), a, DATE)
        self.assertEqual(result['id'], a['id'])
        self.assertEqual(result['source_url'], a['source_url'])
        self.assertEqual(set(result['full_analysis'][0]), {'label', 'text'})
        self.assertNotIn('source_reviewed', result)

    def test_identity_date_hash_and_refs_cannot_drift(self):
        a = article()
        for key, bad in [('source_url', 'https://example.com/other'), ('source_published_at', '2020-01-01'),
                         ('source_evidence_sha256', '0' * 64), ('reviewed_on', '2026-10-14'), ('evidence_refs', ['p999'])]:
            r = record(a)
            r[key] = bad
            with self.assertRaises(review.ReviewError, msg=key):
                review.validate_record(r, a, DATE)

    def test_unapproved_or_failed_checks_are_rejected(self):
        a = article()
        for key, value in [('approved', False), ('issues', ['unsupported']), ('unsupported_claims', ['fake speed'])]:
            r = record(a)
            r['review'][key] = value
            with self.assertRaises(review.ReviewError):
                review.validate_record(r, a, DATE)
        r = record(a)
        r['review']['checks']['faithful_to_source'] = False
        with self.assertRaises(review.ReviewError):
            review.validate_record(r, a, DATE)

    def test_truncated_tampered_or_missing_body_rejected(self):
        for change in ('truncated', 'tampered', 'missing'):
            a = article()
            r = record(a)
            if change == 'truncated': a['evidence']['truncated'] = True
            if change == 'tampered': a['evidence']['blocks'][0]['text'] = 'changed'
            if change == 'missing': a['evidence'] = {}
            with self.assertRaises(review.ReviewError):
                review.validate_record(r, a, DATE)

    def test_three_supported_angles_required(self):
        a = article()
        for blocks in ([], [None], DRAFT['full_analysis'][:2]):
            r = record(a)
            r['full_analysis'] = blocks
            with self.assertRaises(review.ReviewError):
                review.validate_record(r, a, DATE)

    def test_packet_binds_run_commit_date_ids_and_real_editorial_gate(self):
        a = article()
        packet = {'date': DATE, 'source_run_id': 123, 'source_head_sha': SHA, 'articles': [a]}
        data = envelope(a)
        self.assertEqual(len(review.validate_packet(data, packet, DATE)), 1)
        for key, value in [('date', '2026-10-14'), ('source_run_id', 124), ('source_head_sha', 'b' * 40), ('articles', [])]:
            with self.assertRaises(review.ReviewError):
                review.validate_packet(data, {**packet, key: value}, DATE)
        data['items']['fixture']['title'] = 'No Chinese'
        with self.assertRaisesRegex(review.ReviewError, 'title'):
            review.validate_packet(data, packet, DATE)

    def test_only_failed_main_collector_from_same_date_can_supply_evidence(self):
        data = envelope(article())
        run = {'id': 123, 'head_sha': SHA, 'head_branch': 'main', 'created_at': '2026-10-14T23:41:00Z',
            'name': 'Autonomous daily Collector', 'status': 'completed', 'conclusion': 'failure'}
        review.validate_run(data, run, DATE)
        for key, value in [('head_branch', 'untrusted'), ('status', 'in_progress'), ('conclusion', 'success'),
                           ('head_sha', 'b' * 40), ('created_at', '2026-10-13T23:00:00Z')]:
            with self.assertRaises(review.ReviewError):
                review.validate_run(data, {**run, key: value}, DATE)

    def test_review_reader_schema_and_collector_adoption(self):
        a = article()
        c = candidate(a)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'data/editorial-reviews' / f'{DATE}.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(envelope(a)))
            with patch.object(collector, 'ROOT', root):
                good, bad = collector.readable_candidates([c], DATE)
            self.assertEqual(len(good), 1, bad)
            self.assertEqual(c['scheduled_review']['status'], 'approved')
            data = envelope(a)
            data['date'] = '2026-10-14'
            path.write_text(json.dumps(data))
            with self.assertRaises(review.ReviewError):
                review.read_review(DATE, root)

    def test_unmatched_and_duplicate_copy_never_bypasses_batch_gate(self):
        a = article()
        c = candidate(a)
        other = candidate(a)
        other.update(candidate_id='other', source_url='https://example.com/other', reader_copy=copy.deepcopy(DRAFT))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'data/editorial-reviews' / f'{DATE}.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(envelope(a)))
            self.assertEqual(review.candidate_copy(other, DATE, root), (None, []))
            with patch.object(collector, 'ROOT', root):
                good, bad = collector.readable_candidates([other, c], DATE)
            self.assertEqual(len(good), 1)
            self.assertEqual(len(bad), 1)
            self.assertTrue(any('duplicate' in e for e in bad[0][1]))


if __name__ == '__main__':
    unittest.main()
