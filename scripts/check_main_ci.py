#!/usr/bin/env python3
"""Read-only, fail-closed CI gate for the Collector's current-main checkout."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "pastfantast-glitch/ai-3d-daily"
API = f"https://api.github.com/repos/{REPOSITORY}"
SOURCE_WORKFLOW = ".github/workflows/daily-contract.yml"
HISTORY_WORKFLOW = ".github/workflows/historical-regression.yml"
GITHUB_ACTIONS_BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
WRITER_COMMIT_PATTERNS = tuple(re.compile(x) for x in (
    r"^Prepare canonical intelligence 20\d{2}-\d{2}-\d{2}$",
    r"^Normalize intelligence candidate 20\d{2}-\d{2}-\d{2}; refill required$",
    r"^Publish canonical intelligence 20\d{2}-\d{2}-\d{2}$",
    r"^Record verified publish 20\d{2}-\d{2}-\d{2}$",
    r"^Recover canonical publication from [0-9a-f]{7,40}$",
    r"^Collect production intelligence 20\d{2}-\d{2}-\d{2}$",
    r"^Collector handoff 20\d{2}-\d{2}-\d{2}$",
))
MAX_WRITER_COMMITS_TO_SKIP = 512


def git(*args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT, text=True, encoding="utf-8",
    ).strip()


def get_json(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai3d-collector-ci"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(API + path, headers=headers), timeout=30) as response:
        return json.load(response)


def source_paths(workflow):
    # Scope parsing to push.paths; do not accidentally collect branch names or steps.
    push = workflow.split("  push:\n", 1)[1].split("  pull_request:", 1)[0]
    paths = re.findall(r"^      - '([^']+)'$", push, re.M)
    if not paths or SOURCE_WORKFLOW not in paths:
        raise ValueError("cannot resolve source QA push paths")
    return paths


def fetch_runs(workflow, sha, fetch=get_json):
    runs = []
    for page in range(1, 101):
        query = urlencode({"head_sha": sha, "branch": "main", "event": "push",
                           "per_page": 100, "page": page})
        data = fetch(f"/actions/workflows/{Path(workflow).name}/runs?{query}")
        batch = data["workflow_runs"]
        if not isinstance(batch, list):
            raise ValueError("malformed workflow_runs response")
        runs.extend(batch)
        if len(batch) < 100:
            return runs
    raise ValueError("CI run pagination limit reached; evidence incomplete")


def require_success(runs, workflow, sha):
    matching = [r for r in runs if r.get("head_sha") == sha
                and r.get("head_branch") == "main" and r.get("event") == "push"
                and r.get("path") == workflow]
    if not matching:
        raise ValueError(f"MISSING: {workflow} main/push at {sha}")
    latest = max(matching, key=lambda r: (int(r["id"]), int(r.get("run_attempt", 1))))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise ValueError(f"NOT_SUCCESS: {workflow} run {latest['id']} "
                         f"{latest.get('status')}/{latest.get('conclusion')}")
    return {"workflow": workflow, "head_sha": sha, "run_id": latest["id"],
            "url": latest.get("html_url"), "conclusion": "success"}


def writer_generated_commit(sha):
    """Return whether sha is a trusted pipeline GITHUB_TOKEN commit and its parent.\n\n    GitHub intentionally does not emit new push workflow runs for commits pushed\n    with the repository GITHUB_TOKEN. Only the exact GitHub Actions bot identity\n    plus an allowlisted generated commit-message contract may be skipped. This\n    includes the autonomous GitHub Collector commit (which runs its own Collector\n    validation before push) and the marker-only Collector handoff commit. Unknown\n    bot subjects and all non-bot commits still require their own main/push evidence.\n    """
    raw = git("show", "-s", "--format=%H%x00%P%x00%ce%x00%s", sha)
    parts = raw.split("\x00", 3)
    if len(parts) != 4 or parts[0] != sha:
        raise ValueError(f"cannot inspect commit identity for historical CI: {sha}")
    _commit, parents, committer_email, subject = parts
    trusted = (committer_email == GITHUB_ACTIONS_BOT_EMAIL
               and any(pattern.fullmatch(subject) for pattern in WRITER_COMMIT_PATTERNS))
    if not trusted:
        return False, None, subject
    parent_list = parents.split()
    if len(parent_list) != 1:
        raise ValueError(f"canonical writer commit must have exactly one parent: {sha}")
    return True, parent_list[0], subject


COLLECTOR_SUBJECT_RE = re.compile(r"^Collect production intelligence (20\\d{2}-\\d{2}-\\d{2})$")


def changed_paths(sha):
    raw = git("diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    return {line.strip() for line in raw.splitlines() if line.strip()}


def source_evidence_sha(head, paths):
    """Resolve source-QA evidence while safely skipping private-only Collector bot commits.

    Autonomous Collector commits use GITHUB_TOKEN, so GitHub intentionally does not
    emit another push-triggered source-QA run for those commits. We may skip such a
    commit only when both identity and mutation scope are proven: exact Actions bot
    identity + exact Collector subject + only that date's three Collector JSON files
    and rolling backlog. Any extra path fails closed instead of inheriting parent CI.
    """
    start = head
    skipped = []
    for _ in range(MAX_WRITER_COMMITS_TO_SKIP + 1):
        sha = git("log", "-1", "--format=%H", start, "--", *paths)
        if not sha:
            raise ValueError("cannot resolve latest source QA commit")
        trusted, parent, subject = writer_generated_commit(sha)
        match = COLLECTOR_SUBJECT_RE.fullmatch(subject or "") if trusted else None
        if not match:
            return sha, skipped

        report_date = match.group(1)
        required = {
            f"data/daily/{report_date}.json",
            f"data/candidates/collection-session/{report_date}.json",
            f"data/candidates/decision-ledger/{report_date}.json",
        }
        allowed = required | {"data/candidates/rolling-backlog.json"}
        changed = changed_paths(sha)
        unexpected = changed - allowed
        missing = required - changed
        if unexpected or missing:
            details = []
            if unexpected:
                details.append("unexpected=" + ",".join(sorted(unexpected)))
            if missing:
                details.append("missing=" + ",".join(sorted(missing)))
            raise ValueError(
                "autonomous Collector source-QA inheritance scope invalid at "
                + sha + ": " + "; ".join(details)
            )

        skipped.append({"sha": sha, "subject": subject})
        if len(skipped) > MAX_WRITER_COMMITS_TO_SKIP:
            raise ValueError("too many consecutive Collector source commits; source QA evidence ambiguous")
        start = parent
    raise ValueError("cannot resolve source QA evidence commit")


def history_evidence_sha(head):
    """Resolve the newest commit for which a main/push regression run must exist."""
    sha = head
    skipped = []
    for _ in range(MAX_WRITER_COMMITS_TO_SKIP + 1):
        trusted, parent, subject = writer_generated_commit(sha)
        if not trusted:
            return sha, skipped
        skipped.append({"sha": sha, "subject": subject})
        if len(skipped) > MAX_WRITER_COMMITS_TO_SKIP:
            raise ValueError("too many consecutive canonical writer commits; history evidence ambiguous")
        sha = parent
    raise ValueError("cannot resolve historical regression evidence commit")


def check():
    head = git("rev-parse", "HEAD")
    if get_json("/branches/main")["commit"]["sha"] != head:
        raise ValueError("checkout is not current remote main; refresh before handoff")
    if git("rev-parse", "--is-shallow-repository") != "false":
        raise ValueError("full git history required to resolve source QA commit")
    workflow = git("show", f"{head}:{SOURCE_WORKFLOW}")
    paths = source_paths(workflow)
    if git("status", "--porcelain", "--", *paths):
        raise ValueError("uncommitted source QA inputs; remote CI does not cover local changes")
    source_sha, skipped_source_commits = source_evidence_sha(head, paths)

    history_sha, skipped_writer_commits = history_evidence_sha(head)
    checks = [require_success(fetch_runs(w, sha), w, sha) for w, sha in
              ((SOURCE_WORKFLOW, source_sha), (HISTORY_WORKFLOW, history_sha))]
    if get_json("/branches/main")["commit"]["sha"] != head:
        raise ValueError("main moved during CI verification; refresh and recheck")
    return {
        "state": "PASS",
        "main_sha": head,
        "source_evidence_sha": source_sha,
        "skipped_source_commits": skipped_source_commits,
        "history_evidence_sha": history_sha,
        "skipped_writer_commits": skipped_writer_commits,
        "checks": checks,
    }


def main():
    try:
        print(json.dumps(check(), indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"MAIN CI GATE FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
