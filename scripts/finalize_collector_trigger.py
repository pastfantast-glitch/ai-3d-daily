#!/usr/bin/env python3
"""Bridge persisted Collector artifacts into the existing single canonical writer.

This script is invoked only by .github/workflows/intelligence-build.yml after a
Collector has persisted today's canonical/private artifacts and a .collector trigger.
It does not perform discovery or fabricate evidence. It waits for the authoritative
current-main CI gate, validates/synchronizes Collector-owned artifacts, runs the same
authoritative Registry normalization used by prepare, and only creates .request when
that preflight is clean.

Registry refill is expected control flow, not a broken publisher: normalized
canonical/private state is persisted, the .collector trigger is consumed, and the
bridge returns outcome=refill_required without creating .request/.ready. Deterministic
schema/evidence/CI violations remain fail-closed errors.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


def run(*args: str, check: bool = True, capture: bool = False):
    return subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        check=check,
        capture_output=capture,
    )


def print_proc(proc) -> None:
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)


def event_date() -> str:
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    if not event_path.is_file():
        raise SystemExit("COLLECTOR BRIDGE FAILED: GITHUB_EVENT_PATH missing")
    event = json.loads(event_path.read_text("utf-8"))
    message = str(((event.get("head_commit") or {}).get("message") or "")).strip()
    if not message.startswith("Collector handoff "):
        raise SystemExit("COLLECTOR BRIDGE FAILED: push is not an explicit Collector handoff")
    match = DATE_RE.search(message)
    if not match:
        raise SystemExit("COLLECTOR BRIDGE FAILED: Collector handoff commit has no date")
    return match.group(0)


def read_trigger(date: str) -> Path:
    path = ROOT / "data" / "publish" / f"{date}.collector"
    try:
        payload = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"COLLECTOR BRIDGE FAILED: missing {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"COLLECTOR BRIDGE FAILED: invalid trigger JSON: {exc}")
    if str(payload.get("date", "")).strip() != date:
        raise SystemExit("COLLECTOR BRIDGE FAILED: trigger date mismatch")
    if str(payload.get("state", "")).strip().upper() != "COLLECTOR_PERSISTED":
        raise SystemExit("COLLECTOR BRIDGE FAILED: trigger state must be COLLECTOR_PERSISTED")
    if payload.get("writer_idle_confirmed_externally") is not True:
        raise SystemExit("COLLECTOR BRIDGE FAILED: writer idle was not externally confirmed")
    return path


def wait_for_main_ci() -> None:
    script = ROOT / "scripts" / "check_main_ci.py"
    last = ""
    for attempt in range(1, 19):
        proc = run(sys.executable, str(script), check=False, capture=True)
        output = (proc.stdout or "") + (proc.stderr or "")
        print(output, end="")
        if proc.returncode == 0:
            return
        last = output.strip()
        if attempt < 18:
            print(f"COLLECTOR BRIDGE: current-main CI not green yet ({attempt}/18)")
            time.sleep(10)
    raise SystemExit("COLLECTOR BRIDGE FAILED: current-main CI gate did not become green: " + last)


def canonical_paths(date: str) -> set[str]:
    return {
        f"data/daily/{date}.json",
        f"data/candidates/decision-ledger/{date}.json",
    }


def assert_only_expected_changes(date: str, trigger: Path, *, allow_request: bool) -> None:
    allowed = canonical_paths(date) | {trigger.relative_to(ROOT).as_posix()}
    if allow_request:
        allowed.add(f"data/publish/{date}.request")
    proc = run("git", "status", "--porcelain", check=True, capture=True)
    unexpected = []
    for line in (proc.stdout or "").splitlines():
        path = line[3:].strip()
        if path not in allowed:
            unexpected.append(path)
    if unexpected:
        raise SystemExit(
            "COLLECTOR BRIDGE FAILED: preflight changed non-Collector/public artifacts: "
            + ", ".join(unexpected)
        )


def configure_git() -> None:
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")


def stage_canonical_private(date: str) -> None:
    data = ROOT / "data" / "daily" / f"{date}.json"
    ledger = ROOT / "data" / "candidates" / "decision-ledger" / f"{date}.json"
    run("git", "add", data.relative_to(ROOT).as_posix())
    if ledger.exists():
        run("git", "add", ledger.relative_to(ROOT).as_posix())


def persist_refill(date: str, trigger: Path) -> None:
    assert_only_expected_changes(date, trigger, allow_request=False)
    configure_git()
    stage_canonical_private(date)
    run("git", "rm", "-f", trigger.relative_to(ROOT).as_posix())
    run("git", "commit", "-m", f"Collector refill required {date}")
    run("git", "push", "origin", "HEAD:main")
    print(
        f"COLLECTOR REFILL REQUIRED: {date} authoritative Registry normalization "
        "was persisted; no .request/.ready created."
    )


def persist_request(date: str, trigger: Path) -> None:
    request = ROOT / "data" / "publish" / f"{date}.request"
    if not request.is_file():
        raise SystemExit("COLLECTOR BRIDGE FAILED: finalizer did not create request")
    assert_only_expected_changes(date, trigger, allow_request=True)
    configure_git()
    stage_canonical_private(date)
    run("git", "add", request.relative_to(ROOT).as_posix())
    run("git", "rm", "-f", trigger.relative_to(ROOT).as_posix())
    run("git", "commit", "-m", f"Request canonical intelligence publish {date}")
    run("git", "push", "origin", "HEAD:main")
    run("git", "fetch", "origin", "main")
    run("git", "show", f"origin/main:data/publish/{date}.request", capture=True)


def write_output(date: str, outcome: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"date={date}\n")
            fh.write(f"outcome={outcome}\n")


def validation_only_finalizer(date: str) -> None:
    run(
        sys.executable,
        str(ROOT / "scripts" / "finalize_collection_handoff.py"),
        date,
    )


def authoritative_registry_preflight(date: str) -> int:
    proc = run(
        sys.executable,
        str(ROOT / "scripts" / "normalize_registry_identity_hybrid.py"),
        date,
        check=False,
        capture=True,
    )
    print_proc(proc)
    return proc.returncode


def evidence_depth_preflight(date: str) -> None:
    run(
        sys.executable,
        str(ROOT / "scripts" / "enrich_full_analysis_v3.py"),
        date,
    )


def write_request(date: str) -> None:
    run(
        sys.executable,
        str(ROOT / "scripts" / "finalize_collection_handoff.py"),
        date,
        "--write-request",
        "--writer-idle-confirmed",
    )


def main() -> int:
    date = event_date()
    trigger = read_trigger(date)
    wait_for_main_ci()

    # First synchronize session-owned metadata/ledger and catch category/schema
    # mistakes before Registry mutation or request creation.
    validation_only_finalizer(date)

    # Run the exact authoritative Registry/tier/release-gate implementation before
    # .request. A deficit is controlled Collector refill, not publisher failure.
    registry_rc = authoritative_registry_preflight(date)
    if registry_rc == 2:
        persist_refill(date, trigger)
        write_output(date, "refill_required")
        return 0
    if registry_rc != 0:
        raise SystemExit(
            f"COLLECTOR BRIDGE FAILED: authoritative Registry preflight exited {registry_rc}"
        )

    # Catch BRIEF/FULL semantic-depth defects while the artifact is still owned by
    # Collector. Successful enrichment may normalize canonical metadata and is
    # persisted with the request in the same single-writer commit.
    evidence_depth_preflight(date)

    # Re-run the finalizer on the normalized/enriched canonical state; only this
    # invocation is allowed to create the repo-owned request marker.
    write_request(date)
    persist_request(date, trigger)
    write_output(date, "request")
    print(f"COLLECTOR BRIDGE PASS: {date} request persisted; canonical run continues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
