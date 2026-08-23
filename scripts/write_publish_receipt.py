#!/usr/bin/env python3
"""Write success-only release metadata after repository + Pages verification.

The canonical content publication remains one atomic commit. This script writes a
small, separate operational receipt commit only after that publication is pushed
and the public GitHub Pages result has been verified.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime as dt
import json

ROOT = Path(__file__).resolve().parents[1]


def visual_summary(date: str) -> dict:
    path = ROOT / "assets" / "visual" / date / "manifest.json"
    if not path.exists():
        return {"ok": 0, "total": 0, "soft_failures": []}
    data = json.loads(path.read_text("utf-8"))
    entries = data.get("entries") or []
    ok = [e for e in entries if e.get("status") == "ok"]
    soft = [
        {"id": e.get("id"), "status": e.get("status"), "reason": e.get("error") or e.get("reason") or ""}
        for e in entries if e.get("status") != "ok"
    ]
    return {"ok": len(ok), "total": len(entries), "soft_failures": soft}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--publish-sha", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--site-url", required=True)
    args = ap.parse_args()

    canonical = json.loads((ROOT / "data" / "daily" / f"{args.date}.json").read_text("utf-8"))
    receipt = {
        "schema": 2,
        "date": args.date,
        "state": "DONE",
        "publish_commit_sha": args.publish_sha,
        "workflow_run_id": str(args.run_id),
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
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
        "schema": 2,
        "date": args.date,
        "publish_commit_sha": args.publish_sha,
        "receipt": f"data/publish/{args.date}.done.json",
        "site_url": receipt["site_url"],
        "verified_at": receipt["verified_at"],
    }
    (out_dir / "latest-success.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"PUBLISH RECEIPT WRITTEN: {args.date} -> {args.publish_sha}")


if __name__ == "__main__":
    main()
