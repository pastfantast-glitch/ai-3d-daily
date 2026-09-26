#!/usr/bin/env python3
"""Contract guard for the autonomous GitHub-hosted Collector."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "config" / "collector-runtime.json"
HYBRID = ROOT / "config" / "discovery-hybrid.json"
WORKFLOW = ROOT / ".github" / "workflows" / "daily-collector.yml"
HANDOFF = ROOT / ".github" / "workflows" / "collector-handoff.yml"
SCRIPT = ROOT / "scripts" / "run_daily_collector.py"
MAIN_CI = ROOT / "scripts" / "check_main_ci.py"

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


for path in (RUNTIME, HYBRID, WORKFLOW, HANDOFF, SCRIPT, MAIN_CI):
    if not path.exists():
        fail(f"missing autonomous Collector component: {path.relative_to(ROOT)}")

if RUNTIME.exists() and HYBRID.exists():
    try:
        runtime = json.loads(RUNTIME.read_text("utf-8"))
        hybrid = json.loads(HYBRID.read_text("utf-8"))
        if int(runtime.get("version", 0) or 0) != 1:
            fail("collector-runtime version must be 1")
        if runtime.get("timezone") != "Asia/Taipei" or runtime.get("schedule_local") != "07:30":
            fail("autonomous Collector must run at 07:30 Asia/Taipei before the 07:45 monitor")
        http = runtime.get("http") or {}
        if not (5 <= int(http.get("timeout_seconds", 0) or 0) <= 30):
            fail("collector HTTP timeout must be bounded to 5..30 seconds")
        if not (1 <= int(http.get("max_workers", 0) or 0) <= 16):
            fail("collector max_workers must be bounded to 1..16")
        discovery = runtime.get("discovery") or {}
        for key in ("max_links_per_endpoint", "max_pages_per_source", "refill_pages_per_source"):
            if int(discovery.get(key, 0) or 0) <= 0:
                fail(f"collector discovery.{key} must be positive")
        if "entire public web" not in str(discovery.get("exhaustion_semantics", "")):
            fail("collector exhaustion semantics must explicitly avoid claiming whole-web exhaustion")
        security = runtime.get("security") or {}
        for key in ("public_surfaces_written", "publish_markers_written", "raw_personalization_data_written"):
            if security.get(key) is not False:
                fail(f"collector security.{key} must be false")
        expected_mutations = {
            "data/daily/{date}.json",
            "data/candidates/collection-session/{date}.json",
            "data/candidates/decision-ledger/{date}.json",
            "data/candidates/rolling-backlog.json",
        }
        if set(security.get("allowed_repo_mutations") or []) != expected_mutations:
            fail("collector allowed_repo_mutations drifted from canonical/private Collector boundary")

        enabled = {
            str(x.get("id")): str(x.get("domain"))
            for x in ((hybrid.get("discovery_source_pool") or {}).get("sources") or [])
            if x.get("enabled") is True
        }
        endpoints = runtime.get("source_endpoints") or {}
        unknown = set(endpoints) - set(enabled)
        if unknown:
            fail(f"collector source_endpoints contain unknown/unregistered sources: {sorted(unknown)}")
        for sid, urls in endpoints.items():
            if not isinstance(urls, list) or not urls:
                fail(f"collector source {sid} requires non-empty endpoint list")
                continue
            domain = enabled[sid]
            for url in urls:
                parsed = urlparse(str(url))
                host = (parsed.hostname or "").lower()
                if parsed.scheme != "https" or not host:
                    fail(f"collector endpoint must be https: {sid} {url}")
                elif not (host == domain or host.endswith("." + domain)):
                    fail(f"collector endpoint escapes registered domain: {sid} {url}")
    except Exception as exc:
        fail(f"collector runtime config unreadable: {exc}")

if SCRIPT.exists():
    content = SCRIPT.read_text("utf-8")
    for token in (
        "registered_source_probe_plan",
        "canonicalize_url",
        "from content_quality import",
        "content_admission",
        "classify_content",
        "production_summary",
        "published-registry-snapshot.json",
        "rolling-backlog.json",
        "targeted_refill_performed",
        "quality_first_confirmed",
        "analysis_level",
        '"BRIEF"',
        "Autonomous GitHub Collector has no authoritative active-app-owner identity",
    ):
        if token not in content:
            fail(f"run_daily_collector.py missing contract token: {token}")
    for forbidden in ("index.html", "assets/visual", ".collector", ".request", ".ready", "write_publish_receipt"):
        if forbidden in content:
            fail(f"run_daily_collector.py crossed Collector/public boundary: {forbidden}")

if WORKFLOW.exists():
    content = WORKFLOW.read_text("utf-8")
    required = (
        "name: Autonomous daily Collector",
        "cron: '30 23 * * *'",
        "workflow_dispatch:",
        "group: autonomous-daily-collector",
        "cancel-in-progress: false",
        "contents: write",
        "actions: read",
        "fetch-depth: 0",
        'python scripts/run_daily_collector.py "$DATE"',
        'python scripts/check_collection_session_contract.py "$DATE"',
        'python scripts/finalize_collection_handoff.py "$DATE"',
        'git commit -m "Collect production intelligence $DATE"',
        "git push origin HEAD:main",
        "data/daily/$DATE.json",
        "data/candidates/collection-session/$DATE.json",
        "data/candidates/decision-ledger/$DATE.json",
        "data/candidates/rolling-backlog.json",
    )
    for token in required:
        if token not in content:
            fail(f"daily-collector.yml missing restricted-writer token: {token}")
    if "index.html" in content or "assets/visual" in content or ".request" in content or ".ready" in content:
        fail("daily-collector.yml must not stage public surfaces/request/ready")
    if content.count("git commit ") != 1 or content.count("git push ") != 1:
        fail("daily-collector.yml must have exactly one Collector artifact commit/push path")

if HANDOFF.exists():
    content = HANDOFF.read_text("utf-8")
    for token in (
        "workflow_run:",
        "workflows: ['Autonomous daily Collector']",
        "WORKFLOW_RUN_CONCLUSION",
        "Collect production intelligence ",
        "proceed=true",
    ):
        if token not in content:
            fail(f"collector-handoff workflow_run bridge missing token: {token}")

if MAIN_CI.exists():
    content = MAIN_CI.read_text("utf-8")
    if r'^Collect production intelligence 20\d{2}-\d{2}-\d{2}$' not in content:
        fail("check_main_ci.py must allowlist only exact bot-generated Collector commit subjects")
    match = re.search(r"MAX_WRITER_COMMITS_TO_SKIP\s*=\s*(\d+)", content)
    if not match or int(match.group(1)) < 128:
        fail("check_main_ci.py writer-chain bound is too short for sustained autonomous daily publishing")

if errors:
    print("AUTONOMOUS COLLECTOR CONTRACT FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("AUTONOMOUS COLLECTOR CONTRACT PASS: bounded source-grounded GitHub Collector + private-only mutation + GITHUB_TOKEN workflow_run bridge + trusted bot-chain CI semantics")
