#!/usr/bin/env python3
"""Fail-closed Collector finalizer for canonical intelligence handoff.

The Collector owns discovery evidence. This helper never fabricates source probes,
coverage counts, exhaustion, candidate decisions, personalization, or public
surfaces. It consumes one explicit private collection-session JSON, copies only the
contracted audit fields into the canonical dataset, writes the private decision
ledger, validates collector-side current-main contracts, and optionally creates the
`.request` marker after the caller explicitly confirms that the canonical writer is
idle.

Expected private session path:
  data/candidates/collection-session/YYYY-MM-DD.json

The authoritative structure is config/collection-session.schema.json. Raw votes,
full profiles, e-mail addresses, user ids, source/domain preference weights,
bookmarks, and public presentation data are rejected from this input.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from discovery_hybrid import coverage_audit_errors  # noqa: E402
from intelligence_v2 import load_config as load_intelligence_config, validate_v2_dataset  # noqa: E402

DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
FORBIDDEN_SESSION_KEYS = {
    "votes",
    "raw_votes",
    "raw_profile",
    "profile",
    "email",
    "user_id",
    "userId",
    "bookmarks",
    "domain_weights",
    "source_weights",
    "site_weights",
    "publisher_weights",
}


def fail(message: str) -> None:
    raise SystemExit(f"COLLECTOR HANDOFF FAILED: {message}")


def read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        fail(f"missing {path.relative_to(ROOT)}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")


def reject_forbidden_session_data(value, trail="session") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_SESSION_KEYS:
                fail(f"forbidden private/preference field in collection session: {trail}.{key}")
            reject_forbidden_session_data(child, f"{trail}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_forbidden_session_data(child, f"{trail}[{index}]")


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"COLLECTOR HANDOFF STAGE: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode:
        raise SystemExit(proc.returncode)


def done_is_verified(path: Path) -> bool:
    if not path.exists():
        return False
    receipt = read_json(path)
    return str((receipt or {}).get("state", "")).strip().upper() == "DONE"


def parse_args(argv):
    if len(argv) < 2 or not DATE_RE.fullmatch(str(argv[1])):
        fail("usage: finalize_collection_handoff.py YYYY-MM-DD [--write-request --writer-idle-confirmed]")
    date = str(argv[1])
    flags = set(argv[2:])
    allowed = {"--write-request", "--writer-idle-confirmed"}
    unknown = flags - allowed
    if unknown:
        fail(f"unknown flags: {sorted(unknown)}")
    if "--write-request" in flags and "--writer-idle-confirmed" not in flags:
        fail("--write-request requires an external queued/in_progress writer check and --writer-idle-confirmed")
    return date, flags


def collector_data_errors(data):
    """Validate only collector-owned invariants; never require rendered public HTML."""
    errors = list(validate_v2_dataset(data, strict_pool=True))
    cfg = load_intelligence_config()
    category_ids = [str(x.get("id", "")).strip() for x in (cfg.get("categories") or [])]
    for error in coverage_audit_errors(data, category_ids):
        if error not in errors:
            errors.append(error)
    return errors


def main() -> None:
    date, flags = parse_args(sys.argv)
    data_path = ROOT / "data" / "daily" / f"{date}.json"
    session_path = ROOT / "data" / "candidates" / "collection-session" / f"{date}.json"
    ledger_path = ROOT / "data" / "candidates" / "decision-ledger" / f"{date}.json"
    request_path = ROOT / "data" / "publish" / f"{date}.request"
    ready_path = ROOT / "data" / "publish" / f"{date}.ready"
    done_path = ROOT / "data" / "publish" / f"{date}.done.json"

    if done_is_verified(done_path):
        fail(f"{date} already has state=DONE")
    if ready_path.exists():
        fail(f"refusing Collector mutation after ready exists: {ready_path.relative_to(ROOT)}")

    if "--write-request" in flags:
        run("check_main_ci.py")

    data = read_json(data_path)
    session = read_json(session_path)
    if not isinstance(data, dict) or str(data.get("date", "")).strip() != date:
        fail("canonical dataset date mismatch")
    if not isinstance(session, dict):
        fail("collection session must be a JSON object")
    if int(session.get("schema_version", 0) or 0) != 1:
        fail("collection session schema_version must be 1")
    if str(session.get("date", "")).strip() != date:
        fail("collection session date mismatch")

    reject_forbidden_session_data(session)
    # One shared session validator owns candidate traceability and schema semantics.
    # The finalizer keeps its private-data check as a defense-in-depth boundary.
    run("check_collection_session_contract.py", date)

    coverage = session.get("discovery_coverage")
    decisions = session.get("candidate_decisions")
    personalization = session.get("personalization")
    if not isinstance(coverage, dict):
        fail("collection session requires discovery_coverage object")
    if not isinstance(decisions, list):
        fail("collection session requires candidate_decisions list")
    if not isinstance(personalization, dict):
        fail("collection session requires non-sensitive personalization audit object")

    metadata = data.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        fail("canonical metadata must be an object")
    metadata["discovery_coverage"] = coverage
    metadata["personalization"] = personalization

    ledger = {
        "schema_version": 1,
        "date": date,
        "items": decisions,
    }
    write_json(data_path, data)
    write_json(ledger_path, ledger)

    # Fail closed against current-main Collector contracts without generating or
    # requiring public homepage/daily surfaces. Public-surface parity remains a
    # prepare/publish responsibility of the single canonical writer.
    run("check_collection_contract.py")
    run("check_discovery_hybrid_contract.py")
    run("check_personalization_feedback_contract.py", date)
    run("check_quick_impact_contract.py", date)
    errors = collector_data_errors(data)
    if errors:
        fail("collector canonical validation failed: " + "; ".join(errors))

    if "--write-request" not in flags:
        print(
            f"COLLECTOR HANDOFF PASS: {date} canonical+audit+ledger validated; "
            "request not written (validation-only mode)."
        )
        return

    if request_path.exists():
        existing = read_json(request_path)
        if str((existing or {}).get("date", "")).strip() != date:
            fail("existing request has wrong date")
        print(f"COLLECTOR HANDOFF IDEMPOTENT: {request_path.relative_to(ROOT)} already exists")
        return

    request = {
        "state": "REQUESTED",
        "date": date,
        "intent": "canonical-publish",
        "requested_by": "scripts/finalize_collection_handoff.py",
        "collector_contracts_passed": True,
        "writer_idle_confirmed_externally": True,
        "public_surfaces_committed": False,
    }
    write_json(request_path, request)
    print(
        f"COLLECTOR HANDOFF REQUESTED: {date} -> {request_path.relative_to(ROOT)}; "
        "only .github/workflows/intelligence-build.yml may prepare/ready/publish."
    )


if __name__ == "__main__":
    main()
