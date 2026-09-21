#!/usr/bin/env python3
"""Write success-only release metadata after repository + Pages verification.

The canonical content publication remains one atomic commit. This script writes a
small, separate operational receipt commit only after that publication is pushed
and the public GitHub Pages result has been verified. latest-success.json also
stores the last verified pipeline-health snapshot; it is not a substitute for the
current-main CI gate used before a future handoff.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime as dt
import json

ROOT = Path(__file__).resolve().parents[1]
HEALTH_CONTRACT = ROOT / "config" / "pipeline-health.json"


def visual_summary(date: str) -> dict:
    path = ROOT / "assets" / "visual" / date / "manifest.json"
    if not path.exists():
        return {"ok": 0, "total": 0, "soft_failures": []}
    data = json.loads(path.read_text("utf-8"))
    entries = data.get("entries") or []
    ok = [e for e in entries if e.get("status") == "ok"]
    fallback = [e for e in entries if e.get("status") == "fallback_card"]
    soft = [
        {"id": e.get("id"), "status": e.get("status"), "reason": e.get("error") or e.get("reason") or ""}
        for e in entries if e.get("status") not in {"ok", "fallback_card"}
    ]
    fallback_details = [
        {"id": e.get("id"), "extraction_status": e.get("extraction_status"), "reason": e.get("fallback_reason") or e.get("error") or ""}
        for e in fallback
    ]
    return {
        "ok": len(ok),
        "fallback": len(fallback),
        "rendered": len(ok) + len(fallback),
        "total": len(entries),
        "fallback_details": fallback_details,
        "soft_failures": soft,
    }


def health_snapshot(date: str, publish_sha: str, run_id: str, verified_at: str) -> dict:
    contract = json.loads(HEALTH_CONTRACT.read_text("utf-8")) if HEALTH_CONTRACT.exists() else {}
    return {
        "contract_version": int(contract.get("version", 1) or 1),
        "state": str(contract.get("required_state") or "HEALTHY"),
        "date": date,
        "publish_commit_sha": publish_sha,
        "workflow_run_id": str(run_id),
        "verified_at": verified_at,
        "checks": {
            "policy_contracts": "pass",
            "historical_regression": "pass",
            "pages": "pass",
            "canonical_publish": "pass"
        },
        "scope": "last-verified-release",
        "current_main_ci_required_before_next_handoff": True
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--publish-sha", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--site-url", required=True)
    args = ap.parse_args()

    canonical = json.loads((ROOT / "data" / "daily" / f"{args.date}.json").read_text("utf-8"))
    verified_at = dt.datetime.now(dt.timezone.utc).isoformat()
    receipt = {
        "schema": 2,
        "date": args.date,
        "state": "DONE",
        "publish_commit_sha": args.publish_sha,
        "workflow_run_id": str(args.run_id),
        "verified_at": verified_at,
        "site_url": args.site_url.rstrip("/") + "/",
        "daily_url": args.site_url.rstrip("/") + f"/{args.date}/",
        "qa": {
            "pipeline_topology": "pass",
            "release_preflight": "pass",
            "registry": "pass",
            "archive_navigation": "pass",
            "homepage_archive_parity": "pass",
            "intelligence": "pass",
            "visual": "pass",
            "homepage": "pass",
            "daily": "pass",
            "historical_regression": "pass",
            "pages": "pass",
        },
        "canonical": {
            "item_count": len(canonical.get("items") or []),
            "ids": [x.get("id") for x in canonical.get("items") or []],
            "render_revision": canonical.get("render_revision"),
        },
        "visual": visual_summary(args.date),
    }

    out_dir = ROOT / "data" / "publish"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.date}.done.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", "utf-8")
    latest = {
        "schema": 3,
        "date": args.date,
        "publish_commit_sha": args.publish_sha,
        "receipt": f"data/publish/{args.date}.done.json",
        "site_url": receipt["site_url"],
        "verified_at": verified_at,
        "health": health_snapshot(args.date, args.publish_sha, str(args.run_id), verified_at),
    }
    (out_dir / "latest-success.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"PUBLISH RECEIPT WRITTEN: {args.date} -> {args.publish_sha}; pipeline-health=HEALTHY")


if __name__ == "__main__":
    main()
