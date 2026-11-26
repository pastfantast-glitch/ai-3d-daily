"""Regression tests for actual premerge blockers, reserve drift and recovery bounds."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from test_editorial_review import article, envelope, candidate, DATE
import editorial_review as review
from editorial_reserve import approved_reserve, reserve_seeds
from reader_quality import reader_errors
from check_editorial_submission import packet_from_zip, readiness_errors
from handoff_diagnostics import save_failure, recovery_error
import daily_release_status as status


class SupplyTests(unittest.TestCase):
    def test_supplemental_reserve_keeps_release_and_revalidates_next_day(self):
        from check_editorial_submission import immutable_submission
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'data/editorial-reviews';folder.mkdir(parents=True)
            a=article();release=envelope(a)
            (folder/f'{DATE}.json').write_text(json.dumps(release),encoding='utf-8')
            extra=copy.deepcopy(a);extra.update(id='extra',source_url='https://example.com/extra')
            reserve=envelope(extra);reserve.update(purpose='reserve',source_run_id=456)
            path=folder/f'{DATE}-456.json';path.write_text(json.dumps(reserve),encoding='utf-8')
            self.assertEqual(review.read_review(DATE,root),release)
            self.assertEqual(review.read_review_file(path),reserve)
            c=candidate(extra);reader,errors=review.candidate_copy(c,'2026-10-16',root)
            self.assertFalse(errors);self.assertIsNotNone(reader)
            self.assertEqual(c['scheduled_review']['source_run_id'],456)
            self.assertEqual(c['scheduled_review']['source_head_sha'],reserve['source_head_sha'])
            self.assertEqual(len(reserve_seeds(root,'2026-10-16',[{'id':'example','base_url':'https://example.com'}])),2)
            c['meta']['article_evidence']['blocks'][0]['text']='changed'
            self.assertTrue(review.candidate_copy(c,'2026-10-16',root)[1])
            reserve['purpose']='release';path.write_text(json.dumps(reserve),encoding='utf-8')
            with self.assertRaisesRegex(review.ReviewError,'supplemental'):
                review.read_review_file(path)
            reserve.update(purpose='reserve',source_run_id=999);path.write_text(json.dumps(reserve),encoding='utf-8')
            with self.assertRaisesRegex(review.ReviewError,'filename run'):
                review.read_review_file(path)
        prior=['data/editorial-reviews/'+DATE+'.json']
        with self.assertRaisesRegex(review.ReviewError,'immutable'):
            immutable_submission(prior[0],release,prior,lambda _:release)
        with self.assertRaisesRegex(review.ReviewError,'already submitted'):
            immutable_submission('new.json',release,prior,lambda _:release)
        immutable_submission('new.json',{'source_run_id':456},prior,lambda _:release)

    def test_old_source_cannot_be_reviewed_or_reused_as_reserve(self):
        a=article();a['source_published_at']='2025-10-14';data=envelope(a)
        with self.assertRaisesRegex(review.ReviewError,'12 calendar months'):
            review.validate_packet(data,{'date':DATE,'articles':[a]},DATE)
        # Initially eligible at review time, then expires before reserve use.
        a['source_published_at']='2025-10-15';data=envelope(a)
        review.validate_record(data['items']['fixture'],a,DATE)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'data/editorial-reviews'/f'{DATE}.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(approved_reserve(root,'2026-10-16'),{})

    def test_explicit_angles_allow_specific_headings_but_not_missing_angle(self):
        a=article(); data=envelope(a)
        groups=['workflow_or_technical_change','production_impact','test_risk_or_limit']
        for block,angle,label in zip(data['items']['fixture']['full_analysis'],groups,['局部衣褶','前後對照','未提供的數據']):
            block.update(angle=angle,label=label)
        packet={'date':DATE,'articles':[a]}
        copies=review.validate_packet(data,packet,DATE)
        self.assertEqual(reader_errors(copies,DATE),[])
        data['items']['fixture']['full_analysis'][2]['angle']='production_impact'
        with self.assertRaisesRegex(review.ReviewError,'missing-semantic'):
            review.validate_packet(data,packet,DATE)

    def test_legacy_headings_cannot_pass_review_then_fail_depth(self):
        a=article(); data=envelope(a)
        data['items']['fixture']['full_analysis'][2]['label']='原文資訊'
        with self.assertRaisesRegex(review.ReviewError,'missing-semantic'):
            review.validate_packet(data,{'date':DATE,'articles':[a]},DATE)

    def test_reserve_reuses_only_matching_fresh_evidence_and_original_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); path=root/'data/editorial-reviews'/f'{DATE}.json';path.parent.mkdir(parents=True)
            a=article();path.write_text(json.dumps(envelope(a)),encoding='utf-8')
            c=candidate(a)
            reader,errors=review.candidate_copy(c,'2026-10-16',root)
            self.assertFalse(errors);self.assertIsNotNone(reader)
            self.assertEqual(c['scheduled_review']['reviewed_on'],DATE)
            self.assertEqual(c['scheduled_review']['revalidated_on'],'2026-10-16')
            self.assertEqual(c['scheduled_review']['source_run_id'],123)
            self.assertEqual(len(reserve_seeds(root,'2026-10-16',[{'id':'example','base_url':'https://example.com/'}])),1)
            self.assertEqual(len(reserve_seeds(root,'2026-10-16',[{'id':'example','base_url':'https://www.example.com/'}])),1)
            self.assertEqual(reserve_seeds(root,'2026-10-16',[{'id':'example','base_url':'https://evil-example.com/'}]),[])
            c['meta']['article_evidence']['blocks'][0]['text']='source changed'
            self.assertTrue(review.candidate_copy(c,'2026-10-16',root)[1])
            self.assertEqual(approved_reserve(root,'2027-10-16'),{})

    def test_published_source_is_never_usable_reserve(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=article()
            for folder in ['data/editorial-reviews','data/daily','data/publish']:(root/folder).mkdir(parents=True)
            (root/f'data/editorial-reviews/{DATE}.json').write_text(json.dumps(envelope(a)))
            (root/f'data/daily/{DATE}.json').write_text(json.dumps({'items':[a]}))
            (root/f'data/publish/{DATE}.done.json').write_text('{}')
            self.assertEqual(approved_reserve(root,'2026-10-16'),{})

    def test_unreviewed_readable_body_waits_without_generating_padding(self):
        import run_daily_collector as collector
        a=article();c=candidate(a);c.pop('reader_copy')
        with tempfile.TemporaryDirectory() as td, patch.object(collector,'ROOT',Path(td)), patch.object(collector,'editorial_analysis') as generate:
            accepted,rejected=collector.readable_candidates([c],DATE)
            self.assertFalse(accepted)
            self.assertEqual(rejected[0][1],['awaiting-editorial-review'])
            self.assertEqual(c['scheduled_review']['status'],'awaiting-review')
            generate.assert_not_called()

    def test_zip_only_reads_named_json_no_extraction(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('../evil.py','raise Exception()')
            z.writestr('collector-review.json',json.dumps({'date':DATE}))
        self.assertEqual(packet_from_zip(b.getvalue()),{'date':DATE})
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('other.json','{}')
        with self.assertRaises(review.ReviewError):packet_from_zip(b.getvalue())

    def test_partial_review_is_not_merge_ready(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(any('below fallback floor' in e for e in readiness_errors([article()],DATE,Path(td))))

    def test_bounded_recovery_requires_changed_input_and_stops_after_two_corrections(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/f'data/daily/{DATE}.json';path.parent.mkdir(parents=True);path.write_text('{}')
            save_failure(root,DATE,'pre-request','analysis-depth-invalid','fixture: missing-semantic',123)
            self.assertIn('unchanged',recovery_error(root,DATE))
            path.write_text('{"changed":1}')
            self.assertIsNone(recovery_error(root,DATE))
            save_failure(root,DATE,'pre-request','analysis-depth-invalid','fixture',124)
            path.write_text('{"changed":2}')
            self.assertIsNone(recovery_error(root,DATE))
            save_failure(root,DATE,'pre-request','analysis-depth-invalid','fixture',125)
            path.write_text('{"changed":3}')
            self.assertIn('limit',recovery_error(root,DATE))
            result=status.release_status(DATE,root)
            self.assertEqual(result['state'],'HANDOFF_FAILED')
            self.assertEqual(result['first_blocker'],'analysis-depth-invalid')

    def test_done_rejects_wrong_site_latest_and_commit_content(self):
        data={'date':DATE,'items':[{'id':'a'}]};sha='a'*40
        receipt={'state':'DONE','date':DATE,'canonical':{'ids':['a'],'item_count':1},'qa':{'pages':'pass'},
                 'publish_commit_sha':sha,'site_url':status.SITE_URL,'daily_url':status.SITE_URL+DATE+'/'}
        latest={'date':DATE,'publish_commit_sha':sha,'receipt':f'data/publish/{DATE}.done.json','site_url':status.SITE_URL,
                'health':{'date':DATE,'publish_commit_sha':sha,'state':'HEALTHY','checks':{'pages':'pass'}}}
        with patch.object(status,'committed_dataset',return_value=data):
            self.assertEqual(status.receipt_errors(DATE,Path('.'),receipt,data,latest),[])
            self.assertTrue(status.receipt_errors(DATE,Path('.'),{**receipt,'site_url':'https://wrong.invalid/'},data,latest))
            self.assertTrue(status.receipt_errors(DATE,Path('.'),receipt,data,{**latest,'date':'2026-10-14'}))
            self.assertTrue(status.receipt_errors(DATE,Path('.'),receipt,data,{**latest,'date':'2026-10-16'}))
        with patch.object(status,'committed_dataset',return_value={'items':[]}):
            self.assertTrue(status.receipt_errors(DATE,Path('.'),receipt,data,latest))

if __name__=='__main__':unittest.main()
