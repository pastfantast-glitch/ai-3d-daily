#!/usr/bin/env python3
"""Wait for the GitHub Pages deployment corresponding to an atomic publish commit.

Deployment queue latency and public-content propagation are deliberately separate:
this script waits only for the GitHub-owned Pages Actions run to complete. The
existing verify_pages_publish.py then validates the actual public content.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "stability-contract.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_policy() -> dict:
    cfg = json.loads(CONFIG.read_text("utf-8"))
    policy = ((cfg.get("pages_verify") or {}).get("deployment_wait") or {})
    name = str(policy.get("workflow_name", "")).strip()
    attempts = int(policy.get("maximum_attempts", 0) or 0)
    delay = int(policy.get("delay_seconds", 0) or 0)
    timeout = int(policy.get("api_timeout_seconds", 0) or 0)
    if not name or attempts < 1 or delay < 1 or timeout < 1:
        raise ValueError("invalid pages_verify.deployment_wait contract")
    return {
        "workflow_name": name,
        "maximum_attempts": attempts,
        "delay_seconds": delay,
        "api_timeout_seconds": timeout,
    }


def github_json(repository: str, path: str, timeout: int) -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai3d-pages-deployment-wait",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{repository}{path}"
    with urlopen(Request(url, headers=headers), timeout=timeout) as response:
        return json.load(response)


def latest_pages_run(repository: str, publish_sha: str, workflow_name: str, timeout: int):
    query = urlencode({"head_sha": publish_sha, "per_page": 100})
    data = github_json(repository, f"/actions/runs?{query}", timeout)
    runs = data.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("malformed workflow_runs response")
    matches = [
        run for run in runs
        if str(run.get("head_sha", "")).strip() == publish_sha
        and str(run.get("name", "")).strip() == workflow_name
    ]
    if not matches:
        return None
    return max(matches, key=lambda run: (int(run.get("id", 0) or 0), int(run.get("run_attempt", 1) or 1)))


def main() -> int:
    if len(sys.argv) != 2:
        print("PAGES DEPLOYMENT WAIT FAILED: usage: wait_for_pages_deployment.py PUBLISH_SHA", file=sys.stderr)
        return 2
    publish_sha = str(sys.argv[1]).strip().lower()
    if not SHA_RE.fullmatch(publish_sha):
        print(f"PAGES DEPLOYMENT WAIT FAILED: invalid publish SHA {publish_sha!r}", file=sys.stderr)
        return 2

    repository = str(os.environ.get("GITHUB_REPOSITORY", "")).strip()
    if not repository or "/" not in repository:
        print("PAGES DEPLOYMENT WAIT FAILED: GITHUB_REPOSITORY unavailable", file=sys.stderr)
        return 2

    try:
        policy = load_policy()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"PAGES DEPLOYMENT WAIT FAILED: {exc}", file=sys.stderr)
        return 2

    last = "no matching Pages run observed"
    for attempt in range(1, policy["maximum_attempts"] + 1):
        try:
            run = latest_pages_run(
                repository,
                publish_sha,
                policy["workflow_name"],
                policy["api_timeout_seconds"],
            )
            if run is None:
                last = "matching Pages run not created yet"
            else:
                status = str(run.get("status", "")).strip()
                conclusion = run.get("conclusion")
                run_id = run.get("id")
                url = run.get("html_url")
                last = f"run={run_id} status={status} conclusion={conclusion} url={url}"
                if status == "completed":
                    if conclusion == "success":
                        print(
                            "PAGES DEPLOYMENT WAIT PASS: "
                            f"publish_sha={publish_sha} {last}"
                        )
                        return 0
                    print(
                        "PAGES DEPLOYMENT WAIT FAILED: deployment completed without success: " + last,
                        file=sys.stderr,
                    )
                    return 1
        except Exception as exc:
            last = f"GitHub Actions query failed: {type(exc).__name__}: {exc}"

        print(
            f"PAGES DEPLOYMENT WAIT: attempt {attempt}/{policy['maximum_attempts']} "
            f"publish_sha={publish_sha} {last}",
            flush=True,
        )
        if attempt < policy["maximum_attempts"]:
            time.sleep(policy["delay_seconds"])

    print(
        "PAGES DEPLOYMENT WAIT FAILED: deployment did not reach completed/success within "
        f"{policy['maximum_attempts']} attempts: {last}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
