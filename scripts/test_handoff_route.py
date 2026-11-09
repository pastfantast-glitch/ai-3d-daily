"""Exact-run routing, stale-session isolation and marker provenance regressions."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from handoff_route import collector_target, pending_session, route_receipt, verify_route


class HandoffRouteTests(unittest.TestCase):
    def test_exact_preflight_date_for_delayed_schedule_and_manual_dispatch(self):
        run = dict(id=17, head_sha='a'*40, head_branch='main', status='completed',
                   conclusion='success', event='schedule', created_at='2026-11-08T21:30:00Z')
        receipt = dict(schema_version=1, source_run_id=17, head_sha='a'*40,
                       date='2026-11-10', policy_republish=False)
        self.assertEqual(collector_target(run, receipt), ('2026-11-10', False))
        self.assertEqual(collector_target({**run, 'event':'workflow_dispatch'}, receipt),
                         ('2026-11-10', False))
        for invalid in ({'id':18}, {'head_sha':'b'*40}, {'head_branch':'feature'},
                        {'status':'in_progress'}, {'conclusion':'failure'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                collector_target({**run, **invalid}, receipt)
        with self.assertRaises(ValueError):
            collector_target(run, {**receipt, 'policy_republish': True})

    def test_noop_does_not_replay_unrelated_old_session_or_completed_day(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sessions = root/'data/candidates/collection-session'; sessions.mkdir(parents=True)
            pub = root/'data/publish'; pub.mkdir(parents=True)
            (sessions/'2026-11-04.json').write_text('{}')
            self.assertFalse(pending_session(root, '2026-11-09'))
            (sessions/'2026-11-09.json').write_text('{}')
            self.assertTrue(pending_session(root, '2026-11-09'))
            for suffix in ('done.json', 'request', 'ready', 'collector'):
                marker = pub/f'2026-11-09.{suffix}'; marker.write_text('{}')
                self.assertFalse(pending_session(root, '2026-11-09'))
                marker.unlink()
            self.assertFalse(pending_session(root, '../../other'))

    def test_receipt_requires_exact_upstream_run_and_committed_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True,
                                               stderr=subprocess.DEVNULL).strip()
            git('init', '-b', 'main'); git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            marker = root/'data/publish/2026-11-09.collector'; marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps(dict(date='2026-11-09', state='COLLECTOR_PERSISTED',
                                             writer_idle_confirmed_externally=True)))
            git('add', '.'); git('commit', '-m', 'Fixture marker')
            receipt = route_receipt(root, '2026-11-09', git('rev-parse', 'HEAD'), 37)
            self.assertEqual(verify_route(root, receipt, 37), '2026-11-09')
            with self.assertRaises(ValueError): verify_route(root, receipt, 38)
            marker.write_text('{}')
            with self.assertRaises(ValueError): verify_route(root, receipt, 37)


if __name__ == '__main__':
    unittest.main()
