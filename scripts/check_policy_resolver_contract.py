#!/usr/bin/env python3
"""Guard shared policy resolution and legacy consumer parity across date boundaries."""
from __future__ import annotations

from datetime import date as Date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from policy_resolver import (  # noqa: E402
    analysis_depth_policy,
    analysis_policy,
    brief_policy_for_date,
    discovery_policy,
    intelligence_policy,
    personalization_policy,
    release_policy,
    top5_policy,
)
from enrich_full_analysis_v3 import brief_policy_for_date as enrich_brief_policy  # noqa: E402
from verify_pages_publish import analysis_policy as pages_analysis_policy  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit("POLICY RESOLVER CONTRACT FAILED: " + message)


def previous_day(value: str) -> str:
    return (Date.fromisoformat(value) - timedelta(days=1)).isoformat()


def main() -> None:
    depth = analysis_depth_policy()
    effective = str(depth.get("brief_reading_contract_effective_date") or "").strip()
    if not effective:
        fail("brief_reading_contract_effective_date missing")
    before = previous_day(effective)

    legacy = brief_policy_for_date(before)
    current = brief_policy_for_date(effective)
    if int(legacy.get("max_blocks", 0) or 0) >= int(current.get("min_blocks", 0) or 0):
        fail("date boundary does not distinguish legacy and current BRIEF reading policy")

    fixture = {"analysis_level": "BRIEF"}
    for test_date in (before, effective):
        shared = analysis_policy(test_date, fixture, legacy_min_blocks=3)
        pages = pages_analysis_policy(test_date, fixture, depth, 3)
        if tuple(shared) != tuple(pages):
            fail(f"Pages verifier drift on {test_date}: shared={shared} pages={pages}")
        if enrich_brief_policy(test_date) != brief_policy_for_date(test_date):
            fail(f"enrichment BRIEF policy drift on {test_date}")

    cfg_collection = intelligence_policy().get("collection") or {}
    release = release_policy()
    for key in ("daily_min_items", "daily_target_items", "daily_max_items"):
        if int(release.get(key, -1)) != int(cfg_collection.get(key, -2)):
            fail(f"release policy drift for {key}")
    if release.get("discovery_windows") != list(cfg_collection.get("discovery_windows") or []):
        fail("release discovery windows drift")
    if top5_policy() != (depth.get("top5_policy") or {}):
        fail("TOP5 policy drift")

    hybrid_effective = str((discovery_policy(effective) or {}).get("effective_date") or "")
    if not hybrid_effective:
        fail("discovery policy unexpectedly inactive at BRIEF effective date")

    personalization = personalization_policy(effective)
    personalization_effective = str((personalization.get("config") or {}).get("effective_date") or "")
    if personalization_effective and effective >= personalization_effective and personalization.get("active") is not True:
        fail("personalization policy should be active at current boundary")

    print(
        "POLICY RESOLVER CONTRACT PASS: shared date-aware analysis/release/discovery/"
        "personalization policies match current legacy consumers across the effective-date boundary"
    )


if __name__ == "__main__":
    main()
