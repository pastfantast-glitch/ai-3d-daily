import base64
import json
import unittest
from collector_watchdog import execute, trigger_input, REPO, TRIGGER, GitHub, MUTATION
from unittest.mock import patch

SHA = 'a' * 40
DAY = '2026-11-24'

class Fake:
    def __init__(self):
        self.files = {}
        self.events = []
        self.writes = []
        self.head = SHA
        self.calls = 0
        self.change_at = None
        self.fail_write = False
    def main(self):
        self.calls += 1
        if self.change_at == self.calls:
            self.head = 'b' * 40
        return self.head
    def file(self, path, sha):
        return self.files.get(path)
    def runs(self, query):
        return [r for r in self.events if r['status'] == query.get('status')] if 'status' in query else self.events
    def commit_trigger(self, sha, date, reason):
        self.writes.append(trigger_input(sha, date, reason))
        if self.fail_write:
            raise RuntimeError('write rejected')
        return {'oid': 'c' * 40}

class WatchdogTests(unittest.TestCase):
    def test_graphql_uses_fixed_mutation_not_rest_wrapper(self):
        c = GitHub('test-not-a-credential')
        with patch.object(c, 'request', return_value={'data': {'createCommitOnBranch': {'commit': {'oid': SHA}}}}) as request:
            c.commit_trigger(SHA, DAY, 'verified')
            path, payload = request.call_args.args
            self.assertEqual(path, '/graphql')
            self.assertEqual(payload['query'], MUTATION)
            self.assertEqual(payload['variables']['input']['expectedHeadOid'], SHA)
        with self.assertRaises(ValueError): c.get('/graphql')

    def test_read_only_and_single_scoped_cas_write(self):
        c = Fake()
        self.assertEqual(execute(c, DAY)['state'], 'NOT_STARTED')
        self.assertFalse(c.writes)
        self.assertEqual(execute(c, DAY, True)['state'], 'WATCHDOG_TRIGGERED')
        self.assertEqual(len(c.writes), 1)
        v = c.writes[0]
        self.assertEqual(v['expectedHeadOid'], SHA)
        self.assertEqual(v['branch'], {'repositoryNameWithOwner': REPO, 'branchName': 'main'})
        self.assertEqual([a['path'] for a in v['fileChanges']['additions']], [TRIGGER])
        payload = json.loads(base64.b64decode(v['fileChanges']['additions'][0]['contents']))
        self.assertEqual(payload['date'], DAY)
        self.assertTrue(payload['writer_idle_confirmed_externally'])
    def test_receipt_session_canonical_and_same_day_marker_block_write(self):
        for path in [f'data/publish/{DAY}.done.json', f'data/candidates/collection-session/{DAY}.json', f'data/daily/{DAY}.json', TRIGGER]:
            with self.subTest(path=path):
                c = Fake(); c.files[path] = {'date': DAY}
                execute(c, DAY, True)
                self.assertFalse(c.writes)
    def test_all_active_states_and_completed_failure_block(self):
        for status in ['queued', 'in_progress', 'waiting', 'pending', 'requested', 'completed']:
            c = Fake(); c.events = [{'name':'Autonomous daily Collector','status':status,'conclusion':'failure' if status=='completed' else None,'html_url':'run'}]
            execute(c, DAY, True)
            self.assertFalse(c.writes)
    def test_skipped_run_does_not_block(self):
        c = Fake(); c.events = [{'name':'Autonomous daily Collector','status':'completed','conclusion':'skipped','html_url':'run'}]
        self.assertEqual(execute(c, DAY, True)['state'], 'WATCHDOG_TRIGGERED')
    def test_main_changed_between_checks_no_write(self):
        c = Fake(); c.change_at = 3
        self.assertIn('write_skipped', execute(c, DAY, True))
        self.assertFalse(c.writes)
    def test_failed_write_verifies_main_and_never_retries(self):
        c = Fake(); c.fail_write = True
        with self.assertRaisesRegex(RuntimeError, 'main after failed write: '+SHA):
            execute(c, DAY, True)
        self.assertEqual(len(c.writes), 1)
        self.assertEqual(c.calls, 5)

if __name__ == '__main__': unittest.main()
