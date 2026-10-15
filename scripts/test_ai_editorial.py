"""No network: verify AI decisions cannot bypass evidence, QA or bounded retries."""
import copy
import os
from unittest.mock import patch
import unittest

import ai_editorial as ai
import run_daily_collector as collector


DRAFT = {'title': '布料工具：以筆刷調整衣褶輪廓',
         'summary': '這套布料工具示範在網格上以筆刷建立衣褶並調整輪廓，適合檢視衣物形狀與局部折線的變化。',
         'evidence_refs': ['p001'], 'full_analysis': [
             {'label': '技術變更', 'text': '工具在既有網格上提供衣褶筆刷，示範者調整筆刷大小和強度後沿衣物表面畫出折線，再觀察模型形狀。', 'evidence_refs': ['p001']},
             {'label': '製作用途', 'text': '教學直接展示筆刷編輯前後的網格，因此美術可以從畫面比較局部衣褶的方向與輪廓，理解修改的作用。', 'evidence_refs': ['p002']},
             {'label': '適用限制', 'text': '原文示範的是單件衣物網格的局部調整，沒有提供批次處理的數據，也沒有說明遊戲引擎內的運算成本。', 'evidence_refs': ['p002']} ]}
APPROVAL = {'approved': True, 'issues': [], 'unsupported_claims': [], 'evidence_refs': ['p001', 'p002'],
            'checks': {key: True for key in ai.REVIEW_SCHEMA['properties']['checks']['properties']}}


def candidate():
    return {'candidate_id': 'fixture-ai', 'source_url': 'https://example.com/cloth',
            'category': '3d-production', 'subcategory': 'character-production',
            'meta': {'title': 'Cloth brush', 'published': '2026-10-15', 'article_evidence': {
                'status': 'extracted', 'truncated': False, 'sha256': 'fixture', 'blocks': [
                    {'id': 'p001', 'text': 'A cloth brush edits folds on the mesh; size and strength control the strokes.'},
                    {'id': 'p002', 'text': 'The single garment example shows before and after shapes. No batch or engine benchmarks are given.'}]}},
            'reader_copy': {'id': 'fixture-ai', 'title': 'Bad', 'summary': 'Bad', 'full_analysis': []}}


class Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret',
            'AI_EDITOR_MODEL': 'editor-fixture', 'AI_REVIEW_MODEL': 'review-fixture'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def editor(self, outputs):
        self.calls = []
        def transport(model, instructions, payload, schema):
            self.calls.append((model, instructions, payload))
            return copy.deepcopy(outputs.pop(0))
        return ai.Editor(transport=transport)

    def test_separate_reviewer_and_evidence_bound_approval(self):
        editor = self.editor([DRAFT, APPROVAL])
        c = candidate()
        reader, errors = editor.repair(c, '2026-10-15', ['bad copy'], lambda r: [])
        self.assertFalse(errors)
        self.assertEqual(reader['title'], DRAFT['title'])
        self.assertEqual(c['ai_editorial']['status'], 'approved')
        self.assertEqual([c[0] for c in self.calls], ['editor-fixture', 'review-fixture'])
        self.assertNotIn('previous_draft', self.calls[1][2])
        self.assertNotIn('test-secret', str(self.calls))
        self.assertNotIn('evidence_refs', reader['full_analysis'][0])

    def test_reviewer_false_checks_overrule_approved(self):
        bad = copy.deepcopy(APPROVAL)
        bad['checks']['faithful_to_source'] = False
        editor = self.editor([DRAFT, bad, DRAFT, bad])
        c = candidate()
        self.assertIsNone(editor.repair(c, '2026-10-15', [], lambda r: [])[0])
        self.assertEqual(c['ai_editorial']['attempts'], 2)
        self.assertEqual(len(self.calls), 4)
        editor.repair(c, '2026-10-15', [], lambda r: [])
        self.assertEqual(len(self.calls), 4)

    def test_rewrite_receives_specific_rejection(self):
        reject = {**APPROVAL, 'approved': False, 'unsupported_claims': ['No supported speed claim']}
        editor = self.editor([DRAFT, reject, DRAFT, APPROVAL])
        self.assertIsNotNone(editor.repair(candidate(), '2026-10-15', [], lambda r: [])[0])
        self.assertIn('No supported speed claim', self.calls[2][2]['feedback'])

    def test_deterministic_gate_rejects_before_review(self):
        editor = self.editor([DRAFT, DRAFT])
        self.assertIsNone(editor.repair(candidate(), '2026-10-15', [], lambda r: ['historical label missing'])[0])
        self.assertEqual([c[0] for c in self.calls], ['editor-fixture'] * 2)

    def test_fake_evidence_refs_rejected(self):
        bad = {**DRAFT, 'evidence_refs': ['p999']}
        editor = self.editor([bad, bad])
        self.assertIsNone(editor.repair(candidate(), '2026-10-15', [], lambda r: [])[0])
        self.assertEqual(len(self.calls), 2)

    def test_malformed_draft_and_review_are_rejected(self):
        for outputs in ([None], [{**DRAFT, 'full_analysis': [None]}], [DRAFT, None]):
            editor = self.editor(list(outputs))
            self.assertIsNone(editor.repair(candidate(), '2026-10-15', [], lambda r: [])[0])

    def test_missing_key_or_truncated_evidence_never_calls_api(self):
        editor = self.editor([])
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            self.assertIn('configuration missing', editor.repair(candidate(), '2026-10-15', [], lambda r: [])[1][0])
        c = candidate()
        c['meta']['article_evidence']['truncated'] = True
        self.assertIn('complete extracted', editor.repair(c, '2026-10-15', [], lambda r: [])[1][0])
        self.assertFalse(self.calls)

    def test_wall_time_and_article_budget_stop_calls(self):
        editor = self.editor([])
        editor.started -= 1000
        self.assertIn('budget exhausted', editor.repair(candidate(), '2026-10-15', [], lambda r: [])[1][0])
        editor = self.editor([])
        editor.articles = editor.config['max_articles_per_run']
        self.assertIn('budget exhausted', editor.repair(candidate(), '2026-10-15', [], lambda r: [])[1][0])
        self.assertFalse(self.calls)

    def test_api_contract_refusal_http_error_and_call_budget(self):
        editor = ai.Editor()
        with patch.object(ai.requests, 'post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}
            with self.assertRaises(ai.EditorialError):
                editor.request('fixture', ai.EDITOR, {}, ai.DRAFT_SCHEMA)
            body = post.call_args.kwargs['json']
            self.assertFalse(body['store'])
            self.assertEqual(body['text']['format']['type'], 'json_schema')
            post.return_value.status_code = 429
            with self.assertRaisesRegex(ai.EditorialError, 'HTTP 429'):
                editor.request('fixture', ai.EDITOR, {}, ai.DRAFT_SCHEMA)
            editor.calls = editor.config['max_calls_per_run']
            with self.assertRaisesRegex(ai.EditorialError, 'budget exhausted'):
                editor.request('fixture', ai.EDITOR, {}, ai.DRAFT_SCHEMA)
            self.assertEqual(post.call_count, 2)

    def test_collector_only_accepts_independently_approved_repair(self):
        c = candidate()
        editor = self.editor([DRAFT, APPROVAL])
        with patch.dict(os.environ, {'AI_EDITORIAL_ENABLED': 'true'}), patch.object(ai, '_active_editor', editor):
            accepted, rejected = collector.readable_candidates([c], '2026-10-15')
        self.assertEqual(len(accepted), 1, rejected)
        self.assertFalse(rejected)
        self.assertEqual(c['reader_copy']['source_url'], c['source_url'])
        self.assertEqual(c['ai_editorial']['status'], 'approved')

    def test_collector_repair_cannot_bypass_batch_duplicate_gate(self):
        c = candidate()
        other = candidate()
        other['candidate_id'] = 'other'
        other['source_url'] = 'https://example.com/other'
        other['reader_copy'] = {**copy.deepcopy(DRAFT), 'id': 'other'}
        editor = self.editor([DRAFT, DRAFT])
        with patch.dict(os.environ, {'AI_EDITORIAL_ENABLED': 'true'}), patch.object(ai, '_active_editor', editor):
            accepted, rejected = collector.readable_candidates([other, c], '2026-10-15')
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertTrue(any('duplicate' in e for e in rejected[0][1]))
        self.assertEqual(len(self.calls), 2)  # reviewer is never asked to override QA


if __name__ == '__main__':
    unittest.main()
