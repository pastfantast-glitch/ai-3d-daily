import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import daily_release_status as status


class StatusTests(unittest.TestCase):
    def test_old_health_and_noop_success_cannot_mean_today_done(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data/publish').mkdir(parents=True)
            (root / 'data/publish/latest-success.json').write_text(json.dumps({'date':'2026-10-11','health':{'state':'HEALTHY'}}))
            runs = [{'id':1,'head_branch':'main','created_at':'2026-10-12T23:40:00Z','name':'Autonomous daily Collector','status':'completed','conclusion':'failure'},
                    {'id':2,'head_branch':'main','created_at':'2026-10-12T23:43:00Z','name':'Canonical intelligence publish','status':'completed','conclusion':'success'}]
            result = status.release_status('2026-10-13', root, runs)
            self.assertEqual(result['state'], 'COLLECTOR_FAILED')
            runs.append({'id':4,'head_branch':'main','created_at':'2026-10-13T02:00:00Z','name':'Autonomous daily Collector','status':'completed','conclusion':'skipped'})
            self.assertEqual(status.release_status('2026-10-13', root, runs)['state'], 'COLLECTOR_FAILED')
            self.assertEqual(result['last_verified_date'], '2026-10-11')
            shortage = status.release_status('2026-10-13', root, runs, collector_log='COLLECTOR FAILED: verified unpublished survivors=9 below configured fallback floor=12')
            self.assertEqual(shortage['state'], 'CANDIDATES_INSUFFICIENT')
            self.assertEqual(shortage['verified_unpublished'], 9)
            runs[0]['status'] = 'in_progress'
            self.assertEqual(status.release_status('2026-10-13', root, runs)['state'], 'COLLECTING')

    def test_done_requires_matching_canonical_pages_and_existing_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data/publish').mkdir(parents=True)
            (root / 'data/daily').mkdir(parents=True)
            (root / 'data/daily/2026-10-13.json').write_text(json.dumps({'date':'2026-10-13','items':[{'id':'article-a'}]}))
            receipt = {'date':'2026-10-13','state':'DONE','canonical':{'ids':['article-a'],'item_count':1},'qa':{'pages':'pass'},'site_url':'https://example.invalid/','daily_url':'https://example.invalid/2026-10-13/','publish_commit_sha':'a'*40}
            path = root / 'data/publish/2026-10-13.done.json'
            path.write_text(json.dumps(receipt))
            with patch.object(status, 'commit_exists', return_value=True):
                self.assertEqual(status.release_status('2026-10-13', root)['state'], 'DONE')
                receipt['canonical']['ids'] = ['other']
                path.write_text(json.dumps(receipt))
                self.assertEqual(status.release_status('2026-10-13', root)['state'], 'INVALID_RECEIPT')

    def test_exclude_current_reporter_and_publish_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = [{'id':3,'head_branch':'main','created_at':'2026-10-13T01:00:00Z','name':'Canonical intelligence publish','status':'in_progress'}]
            self.assertEqual(status.release_status('2026-10-13',Path(temporary),runs)['state'], 'PUBLISHING')
            self.assertEqual(status.release_status('2026-10-13',Path(temporary),runs,publish_result='failure',exclude_run_id=3)['state'], 'PUBLISH_FAILED')


if __name__ == '__main__':
    unittest.main()
