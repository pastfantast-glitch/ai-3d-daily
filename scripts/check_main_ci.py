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
    source_sha = git("log", "-1", "--format=%H", head, "--", *paths)
    if not source_sha:
        raise ValueError("cannot resolve latest source QA commit")
    checks = [require_success(fetch_runs(w, sha), w, sha) for w, sha in
              ((SOURCE_WORKFLOW, source_sha), (HISTORY_WORKFLOW, head))]
    if get_json("/branches/main")["commit"]["sha"] != head:
        raise ValueError("main moved during CI verification; refresh and recheck")
    return {"state": "PASS", "main_sha": head, "checks": checks}


def main():
    try:
        print(json.dumps(check(), indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"MAIN CI GATE FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
