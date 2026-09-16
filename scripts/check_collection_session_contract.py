#!/usr/bin/env python3
"""Validate Collector session structure and cross-record traceability without public rendering."""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from policy_resolver import discovery_policy  # noqa: E402

DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
SCHEMA = ROOT / "config" / "collection-session.schema.json"
SESSION_DIR = ROOT / "data" / "candidates" / "collection-session"
FORBIDDEN_KEYS = {
    "votes", "raw_votes", "raw_profile", "profile", "email", "user_id", "userId",
    "bookmarks", "domain_weights", "source_weights", "site_weights", "publisher_weights",
}


def die(errors: list[str]) -> None:
    print("COLLECTION SESSION CONTRACT FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)


def load(path: Path):
    return json.loads(path.read_text("utf-8"))


def reject_private(value, trail="session", errors=None):
    errors = errors if errors is not None else []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                errors.append(f"forbidden private/preference field: {trail}.{key}")
            reject_private(child, f"{trail}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_private(child, f"{trail}[{index}]", errors)
    return errors


def valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate(date: str, session: dict) -> list[str]:
    errors: list[str] = []
    schema = load(SCHEMA)
    required = schema.get("required") or []
    for key in required:
        if key not in session:
            errors.append(f"missing required field: {key}")

    if int(session.get("schema_version", 0) or 0) != 1:
        errors.append("schema_version must be 1")
    if str(session.get("date", "")) != date:
        errors.append(f"date mismatch: {session.get('date')!r} != {date}")
    errors += reject_private(session)

    coverage = session.get("discovery_coverage")
    if not isinstance(coverage, dict):
        errors.append("discovery_coverage must be an object")
        coverage = {}
    for key in (
        "fill_ladder_exhausted", "backlog_checked", "backlog_remaining_eligible",
        "targeted_refill_performed", "quality_first_confirmed", "windows", "category_candidates",
    ):
        if key not in coverage:
            errors.append(f"discovery_coverage missing {key}")

    decisions = session.get("candidate_decisions")
    if not isinstance(decisions, list):
        errors.append("candidate_decisions must be an array")
        decisions = []

    hybrid = discovery_policy(date)
    ledger_cfg = hybrid.get("candidate_decision_ledger") or {}
    terminal = set(ledger_cfg.get("terminal_decisions") or ["published", "duplicate", "rejected", "ranked-out", "backlog"])
    require_reason = bool(ledger_cfg.get("require_reason_for_non_published", True))

    seen: set[str] = set()
    decision_ids: set[str] = set()
    for index, item in enumerate(decisions):
        prefix = f"candidate_decisions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id:
            errors.append(f"{prefix}.candidate_id missing")
        elif candidate_id in seen:
            errors.append(f"duplicate candidate_id: {candidate_id}")
        else:
            seen.add(candidate_id)
            decision_ids.add(candidate_id)
        source_url = str(item.get("source_url") or "").strip()
        if not valid_http_url(source_url):
            errors.append(f"{prefix}.source_url invalid")
        channels = item.get("discovery_channels")
        if not isinstance(channels, list) or not channels or any(not str(x).strip() for x in channels):
            errors.append(f"{prefix}.discovery_channels must be a non-empty string array")
        decision = str(item.get("decision") or "").strip()
        if decision not in terminal:
            errors.append(f"{prefix}.decision={decision!r} not in terminal decisions")
        if decision == "published":
            if not str(item.get("canonical_id") or "").strip():
                errors.append(f"{prefix}.canonical_id required for published")
        elif require_reason and decision and not str(item.get("reason_code") or "").strip():
            errors.append(f"{prefix}.reason_code required for non-published decision")

    probe = coverage.get("registered_source_probe") if isinstance(coverage, dict) else None
    if isinstance(probe, dict):
        for source_id, source in (probe.get("sources") or {}).items():
            if not isinstance(source, dict):
                errors.append(f"registered_source_probe.sources.{source_id} must be an object")
                continue
            candidate_ids = source.get("candidate_ids") or []
            found = int(source.get("candidates_found", 0) or 0)
            if found != len(candidate_ids):
                errors.append(
                    f"registered_source_probe.sources.{source_id}: candidates_found={found} "
                    f"!= candidate_ids={len(candidate_ids)}"
                )
            for candidate_id in candidate_ids:
                if str(candidate_id) not in decision_ids:
                    errors.append(
                        f"registered source probe candidate missing decision ledger entry: {candidate_id}"
                    )

    personalization = session.get("personalization")
    if not isinstance(personalization, dict):
        errors.append("personalization must be an object")
    else:
        for key in (
            "raw_profile_committed", "bookmarks_used", "domain_weights_used",
            "admission_bypass", "quality_gate_bypass", "source_quota",
        ):
            if personalization.get(key) is not False:
                errors.append(f"personalization.{key} must be false")
        status = str(personalization.get("status") or "")
        if status not in {"applied", "empty", "unavailable"}:
            errors.append(f"personalization.status invalid: {status!r}")
        if status == "unavailable" and not str(personalization.get("reason") or "").strip():
            errors.append("personalization.reason required when unavailable")
        if status in {"applied", "empty"} and not str(personalization.get("profile_fingerprint") or "").strip():
            errors.append("personalization.profile_fingerprint required when profile is available")

    return errors


def resolve_date(argv: list[str]) -> str:
    if len(argv) > 1:
        date = argv[1]
    else:
        dates = sorted(p.stem for p in SESSION_DIR.glob("20??-??-??.json"))
        if not dates:
            raise SystemExit("COLLECTION SESSION CONTRACT FAILED: no collection sessions")
        date = dates[-1]
    if not DATE_RE.fullmatch(date):
        raise SystemExit("usage: check_collection_session_contract.py [YYYY-MM-DD]")
    return date


def main() -> None:
    date = resolve_date(sys.argv)
    path = SESSION_DIR / f"{date}.json"
    if not path.exists():
        raise SystemExit(f"COLLECTION SESSION CONTRACT FAILED: missing {path.relative_to(ROOT)}")
    session = load(path)
    if not isinstance(session, dict):
        raise SystemExit("COLLECTION SESSION CONTRACT FAILED: session root must be an object")
    errors = validate(date, session)
    if errors:
        die(errors)
    print(
        f"COLLECTION SESSION CONTRACT PASS: {date} candidates={len(session.get('candidate_decisions') or [])} "
        "schema=1 private-data=blocked probe-to-ledger=consistent"
    )


if __name__ == "__main__":
    main()
