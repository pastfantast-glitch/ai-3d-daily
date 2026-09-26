"""Regression cases for Collector main-CI evidence selection."""
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

    @staticmethod
    def commit_line(sha, parent, email, subject):
        return "\x00".join((sha, parent, email, subject))

    def test_writer_receipt_publish_prepare_chain_resolves_to_request(self):
        chain = {
            "current": ("publish", ci.GITHUB_ACTIONS_BOT_EMAIL, "Record verified publish 2026-09-17"),
            "publish": ("prepare", ci.GITHUB_ACTIONS_BOT_EMAIL, "Publish canonical intelligence 2026-09-17"),
            "prepare": ("request", ci.GITHUB_ACTIONS_BOT_EMAIL, "Prepare canonical intelligence 2026-09-17"),
            "request": ("older", "owner@example.com", "Request AI 3D daily publish for 2026-09-17"),
        }
        def fake_git(*args):
            sha = args[-1]
            parent, email, subject = chain[sha]
            return self.commit_line(sha, parent, email, subject)
        with patch.object(ci, "git", side_effect=fake_git):
            sha, skipped = ci.history_evidence_sha("current")
        self.assertEqual(sha, "request")
        self.assertEqual([x["sha"] for x in skipped], ["current", "publish", "prepare"])

    def test_collector_handoff_bot_commit_resolves_to_parent_evidence(self):
        chain = {
            "current": ("parent", ci.GITHUB_ACTIONS_BOT_EMAIL, "Collector handoff 2026-09-24"),
            "parent": ("older", "owner@example.com", "Persist Collector session 2026-09-24"),
        }
        def fake_git(*args):
            sha = args[-1]
            parent, email, subject = chain[sha]
            return self.commit_line(sha, parent, email, subject)
        with patch.object(ci, "git", side_effect=fake_git):
            sha, skipped = ci.history_evidence_sha("current")
        self.assertEqual(sha, "parent")
        self.assertEqual([x["sha"] for x in skipped], ["current"])

    def test_autonomous_collector_bot_commit_resolves_to_parent_evidence(self):
        chain = {
            "current": ("parent", ci.GITHUB_ACTIONS_BOT_EMAIL, "Collect production intelligence 2026-09-26"),
            "parent": ("older", "owner@example.com", "Enable autonomous Collector"),
        }
        def fake_git(*args):
            sha = args[-1]
            parent, email, subject = chain[sha]
            return self.commit_line(sha, parent, email, subject)
        with patch.object(ci, "git", side_effect=fake_git):
            sha, skipped = ci.history_evidence_sha("current")
        self.assertEqual(sha, "parent")
        self.assertEqual([x["sha"] for x in skipped], ["current"])

    def test_source_evidence_skips_private_only_autonomous_collector_commit(self):
        paths = [SOURCE_WORKFLOW, "data/candidates/rolling-backlog.json"]
        collector = "collector"
        parent = "parent"
        source = "source"
        required = "\n".join([
            "data/daily/2026-09-26.json",
            "data/candidates/collection-session/2026-09-26.json",
            "data/candidates/decision-ledger/2026-09-26.json",
            "data/candidates/rolling-backlog.json",
        ])

        def fake_git(*args):
            if args[0] == "log":
                start = args[3]
                return collector if start == "current" else source
            if args[0] == "show" and args[1] == "-s":
                sha = args[-1]
                if sha == collector:
                    return self.commit_line(
                        collector, parent, ci.GITHUB_ACTIONS_BOT_EMAIL,
                        "Collect production intelligence 2026-09-26"
                    )
                if sha == source:
                    return self.commit_line(source, "older", "owner@example.com", "Collector architecture source change")
            if args[0] == "diff-tree" and args[-1] == collector:
                return required
            raise AssertionError(args)

        with patch.object(ci, "git", side_effect=fake_git):
            sha, skipped = ci.source_evidence_sha("current", paths)
        self.assertEqual(sha, source)
        self.assertEqual([x["sha"] for x in skipped], [collector])

    def test_source_evidence_refuses_collector_commit_with_extra_source_path(self):
        paths = [SOURCE_WORKFLOW, "data/candidates/rolling-backlog.json"]
        def fake_git(*args):
            if args[0] == "log":
                return "collector"
            if args[0] == "show" and args[1] == "-s":
                return self.commit_line(
                    "collector", "parent", ci.GITHUB_ACTIONS_BOT_EMAIL,
                    "Collect production intelligence 2026-09-26"
                )
            if args[0] == "diff-tree":
                return "\n".join([
                    "data/daily/2026-09-26.json",
                    "data/candidates/collection-session/2026-09-26.json",
                    "data/candidates/decision-ledger/2026-09-26.json",
                    "data/candidates/rolling-backlog.json",
                    "scripts/check_main_ci.py",
                ])
            raise AssertionError(args)

        with patch.object(ci, "git", side_effect=fake_git), \
             self.assertRaisesRegex(ValueError, "scope invalid"):
            ci.source_evidence_sha("current", paths)

    def test_policy_recollect_subject_inherits_parent_source_qa_when_actions_bot_scoped(self):
        paths = [SOURCE_WORKFLOW, "data/candidates/rolling-backlog.json"]
        collector = "collector"
        parent = "parent"
        source = "source"
        required = "\n".join([
            "data/daily/2026-09-26.json",
            "data/candidates/collection-session/2026-09-26.json",
            "data/candidates/decision-ledger/2026-09-26.json",
            "data/candidates/rolling-backlog.json",
        ])

        def fake_git(*args):
            if args[0] == "log":
                start = args[3]
                return collector if start == "current" else source
            if args[0] == "show" and args[1] == "-s":
                sha = args[-1]
                if sha == collector:
                    return self.commit_line(
                        collector, parent, ci.GITHUB_ACTIONS_BOT_EMAIL,
                        "Recollect production intelligence 2026-09-26"
                    )
                if sha == source:
                    return self.commit_line(source, "older", "owner@example.com", "Harden source contract")
            if args[0] == "diff-tree" and args[-1] == collector:
                return required
            raise AssertionError(args)

        with patch.object(ci, "git", side_effect=fake_git):
            source_sha, skipped = ci.source_evidence_sha("current", paths)
        self.assertEqual(source_sha, source)
        self.assertEqual([x["sha"] for x in skipped], [collector])

    def test_autonomous_collector_subject_requires_actions_bot_identity(self):
        def fake_git(*args):
            return self.commit_line(
                "current", "parent", "owner@example.com", "Collect production intelligence 2026-09-26"
            )
        with patch.object(ci, "git", side_effect=fake_git):
            sha, skipped = ci.history_evidence_sha("current")
        self.assertEqual(sha, "current")
        self.assertEqual(skipped, [])

    def test_collector_handoff_subject_requires_actions_bot_identity(self):
        def fake_git(*args):
            return self.commit_line(
                "current", "parent", "owner@example.com", "Collector handoff 2026-09-24"
            )
        with patch.object(ci, "git", side_effect=fake_git):
            sha, skipped = ci.history_evidence_sha("current")
        self.assertEqual(sha, "current")
        self.assertEqual(skipped, [])

    def test_unknown_bot_or_forged_writer_subject_is_not_skipped(self):
        cases = [
            (ci.GITHUB_ACTIONS_BOT_EMAIL, "Change pipeline code"),
            ("owner@example.com", "Record verified publish 2026-09-17"),
        ]
        for email, subject in cases:
            with self.subTest(email=email, subject=subject):
                def fake_git(*args):
                    return self.commit_line("current", "parent", email, subject)
                with patch.object(ci, "git", side_effect=fake_git):
                    sha, skipped = ci.history_evidence_sha("current")
                self.assertEqual(sha, "current")
                self.assertEqual(skipped, [])

    def test_writer_merge_commit_fails_closed(self):
        def fake_git(*args):
            return self.commit_line("current", "p1 p2", ci.GITHUB_ACTIONS_BOT_EMAIL,
                                    "Record verified publish 2026-09-17")
        with patch.object(ci, "git", side_effect=fake_git), self.assertRaisesRegex(ValueError, "one parent"):
            ci.history_evidence_sha("current")

    def fake_git(self, *args):
        if args == ("rev-parse", "HEAD"):
            return "current"
        if args == ("rev-parse", "--is-shallow-repository"):
            return "false"
        if args[0] == "show" and len(args) >= 2 and args[1] == "-s":
            sha = args[-1]
            return self.commit_line(sha, "parent", "owner@example.com", "External main change")
        if args[0] == "show":
            return "  push:\n    paths:\n      - '" + SOURCE_WORKFLOW + "'\n  pull_request:\n"
        if args[0] == "status":
            return ""
        if args[0] == "log":
            return "source"
        if args[0] == "diff-tree":
            return ""
        raise AssertionError(args)

    def test_path_filtered_source_and_history_evidence_use_separate_shas(self):
        def runs(workflow, sha):
            return [run_record(path=workflow, head_sha=sha)]
        with patch.object(ci, "git", side_effect=self.fake_git), \
             patch.object(ci, "get_json", return_value={"commit": {"sha": "current"}}), \
             patch.object(ci, "fetch_runs", side_effect=runs) as fetch:
            result = ci.check()
            self.assertEqual(result["state"], "PASS")
            self.assertEqual(result["history_evidence_sha"], "current")
            self.assertEqual(fetch.call_args_list[0].args, (SOURCE_WORKFLOW, "source"))
            self.assertEqual(fetch.call_args_list[1].args, (ci.HISTORY_WORKFLOW, "current"))

    def test_check_uses_request_regression_after_writer_bookkeeping(self):
        chain = {
            "current": ("publish", ci.GITHUB_ACTIONS_BOT_EMAIL, "Record verified publish 2026-09-17"),
            "publish": ("prepare", ci.GITHUB_ACTIONS_BOT_EMAIL, "Publish canonical intelligence 2026-09-17"),
            "prepare": ("request", ci.GITHUB_ACTIONS_BOT_EMAIL, "Prepare canonical intelligence 2026-09-17"),
            "request": ("older", "owner@example.com", "Request AI 3D daily publish for 2026-09-17"),
        }
        def fake_git(*args):
            if args == ("rev-parse", "HEAD"): return "current"
            if args == ("rev-parse", "--is-shallow-repository"): return "false"
            if args[0] == "show" and len(args) >= 2 and args[1] == "-s":
                sha = args[-1]
                if sha == "source":
                    return self.commit_line("source", "older", "owner@example.com", "Source QA change")
                parent, email, subject = chain[sha]
                return self.commit_line(sha, parent, email, subject)
            if args[0] == "show":
                return "  push:\n    paths:\n      - '" + SOURCE_WORKFLOW + "'\n  pull_request:\n"
            if args[0] == "status": return ""
            if args[0] == "log": return "source"
            raise AssertionError(args)
        def runs(workflow, sha):
            return [run_record(path=workflow, head_sha=sha)]
        with patch.object(ci, "git", side_effect=fake_git), \
             patch.object(ci, "get_json", return_value={"commit": {"sha": "current"}}), \
             patch.object(ci, "fetch_runs", side_effect=runs) as fetch:
            result = ci.check()
        self.assertEqual(result["history_evidence_sha"], "request")
        self.assertEqual(fetch.call_args_list[1].args, (ci.HISTORY_WORKFLOW, "request"))

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
