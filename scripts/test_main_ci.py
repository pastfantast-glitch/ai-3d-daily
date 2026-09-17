"""Regression cases for the September 17 false CI-missing incident."""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from check_main_ci import SOURCE_WORKFLOW, fetch_runs, require_success, source_paths
import check_main_ci as ci


def run_record(**overrides):
    return {"id": 100, "head_sha": "abc", "head_branch": "main", "event": "push",
            "path": SOURCE_WORKFLOW, "status": "completed", "conclusion": "success",
            **overrides}


class MainCITests(unittest.TestCase):
    def test_push_run_is_accepted(self):
        self.assertEqual(require_success([run_record()], SOURCE_WORKFLOW, "abc")["run_id"], 100)

    def test_pr_other_sha_branch_or_workflow_cannot_satisfy_gate(self):
        for change in ({"event": "pull_request"}, {"head_sha": "old"},
                       {"head_branch": "feature"}, {"path": "other.yml"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "MISSING"):
                require_success([run_record(**change)], SOURCE_WORKFLOW, "abc")

    def test_latest_failure_or_pending_run_overrides_older_success(self):
        for change in ({"conclusion": "failure"}, {"conclusion": "cancelled"},
                       {"status": "in_progress", "conclusion": None}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "NOT_SUCCESS"):
                require_success([run_record(), run_record(id=101, **change)], SOURCE_WORKFLOW, "abc")

    def test_latest_attempt_overrides_previous_success(self):
        with self.assertRaisesRegex(ValueError, "NOT_SUCCESS"):
            require_success([run_record(), run_record(run_attempt=2, conclusion="failure")],
                            SOURCE_WORKFLOW, "abc")

    def test_empty_evidence_fails(self):
        with self.assertRaisesRegex(ValueError, "MISSING"):
            require_success([], SOURCE_WORKFLOW, "abc")

    def test_pagination_and_exact_query(self):
        calls = []
        def fetch(path):
            query = parse_qs(urlparse(path).query)
            calls.append(query)
            self.assertEqual(query["event"], ["push"])
            self.assertEqual(query["head_sha"], ["abc"])
            self.assertEqual(query["branch"], ["main"])
            return {"workflow_runs": [run_record()] * (100 if query["page"] == ["1"] else 1)}
        self.assertEqual(len(fetch_runs(SOURCE_WORKFLOW, "abc", fetch)), 101)
        self.assertEqual(len(calls), 2)

    def test_api_error_is_not_treated_as_empty_or_success(self):
        def fetch(path):
            raise OSError("API unavailable")
        with self.assertRaises(OSError):
            fetch_runs(SOURCE_WORKFLOW, "abc", fetch)

    def test_paths_exclude_pr_configuration(self):
        config = "on:\n  push:\n    paths:\n      - '" + SOURCE_WORKFLOW + "'\n      - 'scripts/a.py'\n  pull_request:\n      - 'not-a-path'\n"
        self.assertEqual(source_paths(config), [SOURCE_WORKFLOW, "scripts/a.py"])

    def fake_git(self, *args):
        if args == ("rev-parse", "HEAD"):
            return "current"
        if args == ("rev-parse", "--is-shallow-repository"):
            return "false"
        if args[0] == "show":
            return "  push:\n    paths:\n      - '" + SOURCE_WORKFLOW + "'\n  pull_request:\n"
        if args[0] == "status":
            return ""
        if args[0] == "log":
            return "source"
        raise AssertionError(args)

    def test_path_filtered_source_and_current_history_use_separate_shas(self):
        def runs(workflow, sha):
            return [run_record(path=workflow, head_sha=sha)]
        with patch.object(ci, "git", side_effect=self.fake_git), \
             patch.object(ci, "get_json", return_value={"commit": {"sha": "current"}}), \
             patch.object(ci, "fetch_runs", side_effect=runs) as fetch:
            result = ci.check()
            self.assertEqual(result["state"], "PASS")
            self.assertEqual(fetch.call_args_list[0].args, (SOURCE_WORKFLOW, "source"))
            self.assertEqual(fetch.call_args_list[1].args, (ci.HISTORY_WORKFLOW, "current"))

    def test_stale_checkout_and_moving_main_fail(self):
        for shas in (("new",), ("current", "new")):
            with self.subTest(shas=shas), \
                 patch.object(ci, "git", side_effect=self.fake_git), \
                 patch.object(ci, "get_json", side_effect=[{"commit": {"sha": s}} for s in shas]), \
                 patch.object(ci, "fetch_runs", side_effect=lambda w, s: [run_record(path=w, head_sha=s)]), \
                 self.assertRaises(ValueError):
                ci.check()

    def test_shallow_history_and_dirty_sources_fail(self):
        for kind in ("shallow", "dirty"):
            def local_git(*args):
                if kind == "shallow" and args == ("rev-parse", "--is-shallow-repository"):
                    return "true"
                if kind == "dirty" and args[0] == "status":
                    return " M scripts/check_main_ci.py"
                return self.fake_git(*args)
            with self.subTest(kind=kind), patch.object(ci, "git", side_effect=local_git), \
                 patch.object(ci, "get_json", return_value={"commit": {"sha": "current"}}), \
                 self.assertRaises(ValueError):
                ci.check()


if __name__ == "__main__":
    unittest.main()
