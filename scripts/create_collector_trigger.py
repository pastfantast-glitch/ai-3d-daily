#!/usr/bin/env python3
"""Create the sole Collector handoff trigger after persisted-artifact validation.

This helper is intentionally narrow:
- it never performs discovery or invents evidence;
- it never writes .request/.ready/DONE or public surfaces;
- it only creates data/publish/YYYY-MM-DD.collector after the caller has
  externally confirmed that Canonical intelligence publish has no queued or
  in-progress writer;
- it reuses the current-main Collector finalizer in validation-only mode so
  Collector policy remains owned by repository code rather than workflow YAML.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"COLLECTOR TRIGGER FAILED: {message}")


def read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        fail(f"missing persisted artifact: {path.relative_to(ROOT)}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")


def run(*args: str) -> None:
    proc = subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode:
        raise SystemExit(proc.returncode)


def git_status_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        check=True,
        capture_output=True,
    )
    return [line[3:].strip() for line in proc.stdout.splitlines() if line.strip()]


def require_persisted_consistency(date: str) -> None:
    data_path = ROOT / "data" / "daily" / f"{date}.json"
    session_path = ROOT / "data" / "candidates" / "collection-session" / f"{date}.json"
    ledger_path = ROOT / "data" / "candidates" / "decision-ledger" / f"{date}.json"
    backlog_path = ROOT / "data" / "candidates" / "rolling-backlog.json"

    data = read_json(data_path)
    session = read_json(session_path)
    ledger = read_json(ledger_path)
    backlog = read_json(backlog_path)

    if str((data or {}).get("date", "")).strip() != date:
        fail("canonical dataset date mismatch")
    if str((session or {}).get("date", "")).strip() != date:
        fail("collection-session date mismatch")
    if str((ledger or {}).get("date", "")).strip() != date:
        fail("decision-ledger date mismatch")
    if int((ledger or {}).get("schema_version", 0) or 0) != 1:
        fail("decision-ledger schema_version must be 1")
    if int((backlog or {}).get("schema_version", 0) or 0) != 1 or not isinstance((backlog or {}).get("items"), list):
        fail("rolling backlog must be schema_version=1 with items[]")

    metadata = (data or {}).get("metadata")
    if not isinstance(metadata, dict):
        fail("canonical metadata must be an object")
    if metadata.get("discovery_coverage") != (session or {}).get("discovery_coverage"):
        fail("canonical discovery_coverage is not synchronized with persisted collection-session")
    if metadata.get("personalization") != (session or {}).get("personalization"):
        fail("canonical personalization audit is not synchronized with persisted collection-session")
    if (ledger or {}).get("items") != (session or {}).get("candidate_decisions"):
        fail("decision-ledger items are not synchronized with persisted collection-session")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--writer-idle-confirmed", action="store_true")
    args = parser.parse_args()

    date = str(args.date)
    import re
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date):
        fail("date must be YYYY-MM-DD")
    if not args.writer_idle_confirmed:
        fail("--writer-idle-confirmed is required; workflow must check queued/in_progress canonical runs first")

    done_path = ROOT / "data" / "publish" / f"{date}.done.json"
    request_path = ROOT / "data" / "publish" / f"{date}.request"
    ready_path = ROOT / "data" / "publish" / f"{date}.ready"
    trigger_path = ROOT / "data" / "publish" / f"{date}.collector"

    if done_path.exists():
        receipt = read_json(done_path)
        if str((receipt or {}).get("state", "")).strip().upper() == "DONE":
            fail(f"{date} already has state=DONE")
        fail(f"unexpected non-DONE receipt exists: {done_path.relative_to(ROOT)}")
    for path in (request_path, ready_path, trigger_path):
        if path.exists():
            fail(f"refusing duplicate handoff while {path.relative_to(ROOT)} exists")

    if git_status_paths():
        fail("working tree must be clean before persisted-artifact validation")

    require_persisted_consistency(date)

    # Delegate Collector-side semantic validation to current-main code. The
    # validation-only finalizer must be a semantic no-op because Collector-owned
    # artifacts were already persisted and synchronized before this gate.
    run(sys.executable, "scripts/check_release_architecture.py")
    run(sys.executable, "scripts/check_collection_session_contract.py", date)
    run(sys.executable, "scripts/finalize_collection_handoff.py", date)

    changed = git_status_paths()
    if changed:
        fail(
            "validation-only finalizer detected unpersisted Collector mutations: "
            + ", ".join(changed)
        )

    trigger = {
        "state": "COLLECTOR_PERSISTED",
        "date": date,
        "writer_idle_confirmed_externally": True,
        "generated_by": "scripts/create_collector_trigger.py",
        "public_surfaces_committed": False,
    }
    trigger_path.write_text(
        json.dumps(trigger, ensure_ascii=False, indent=2) + "\n",
        "utf-8",
    )

    changed = git_status_paths()
    expected = trigger_path.relative_to(ROOT).as_posix()
    if set(changed) != {expected}:
        fail("trigger creation changed unexpected paths: " + ", ".join(changed))

    print(f"COLLECTOR TRIGGER READY: {date} -> {expected}")


if __name__ == "__main__":
    main()
