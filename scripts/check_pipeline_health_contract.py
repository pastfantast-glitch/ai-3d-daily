#!/usr/bin/env python3
"""Validate the last-verified-release health snapshot contract."""
from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "pipeline-health.json"
LATEST = ROOT / "data" / "publish" / "latest-success.json"
WRITER = ROOT / "scripts" / "write_publish_receipt.py"


def fail(message: str) -> None:
    raise SystemExit("PIPELINE HEALTH CONTRACT FAILED: " + message)


def main() -> None:
    cfg = json.loads(CFG.read_text("utf-8"))
    if cfg.get("version") != 1:
        fail("contract version must be 1")
    if cfg.get("storage") != "data/publish/latest-success.json#health":
        fail("health storage must remain inside latest-success writer-owned metadata")
    if cfg.get("writer") != "scripts/write_publish_receipt.py":
        fail("health writer must remain write_publish_receipt.py")
    if cfg.get("fail_closed") is not True:
        fail("health contract must remain fail_closed=true")

    writer = WRITER.read_text("utf-8")
    for token in ("health_snapshot", '"state"', '"policy_contracts"', '"historical_regression"', '"pages"', '"canonical_publish"'):
        if token not in writer:
            fail(f"write_publish_receipt.py missing health token: {token}")

    if not LATEST.exists():
        fail("latest-success.json missing")
    latest = json.loads(LATEST.read_text("utf-8"))
    latest_date = str(latest.get("date") or "")
    effective = str(cfg.get("effective_date") or "")
    if latest_date and effective and latest_date < effective:
        print(
            f"PIPELINE HEALTH CONTRACT PASS: latest verified release {latest_date} predates health snapshot effective date {effective}; writer wiring ready"
        )
        return

    health = latest.get("health")
    if not isinstance(health, dict):
        fail("latest-success.health missing after effective date")
    if health.get("state") != cfg.get("required_state"):
        fail(f"health.state={health.get('state')!r} expected={cfg.get('required_state')!r}")
    if health.get("scope") != "last-verified-release":
        fail("health.scope must be last-verified-release")
    if health.get("current_main_ci_required_before_next_handoff") is not True:
        fail("health snapshot must not claim to replace current-main pre-handoff CI")
    checks = health.get("checks") or {}
    for key in cfg.get("required_checks") or []:
        if checks.get(key) != "pass":
            fail(f"health check {key} must be pass")
    if health.get("publish_commit_sha") != latest.get("publish_commit_sha"):
        fail("health publish SHA differs from latest-success")
    if health.get("date") != latest_date:
        fail("health date differs from latest-success")

    receipt_path = ROOT / str(latest.get("receipt") or "")
    if not receipt_path.exists():
        fail("referenced DONE receipt missing")
    receipt = json.loads(receipt_path.read_text("utf-8"))
    if str(receipt.get("state") or "").upper() != "DONE":
        fail("referenced receipt is not DONE")
    if (receipt.get("qa") or {}).get("pages") != "pass":
        fail("referenced receipt Pages QA is not pass")

    print(
        f"PIPELINE HEALTH CONTRACT PASS: {latest_date} last-verified-release=HEALTHY; current-main CI remains independently required"
    )


if __name__ == "__main__":
    main()
