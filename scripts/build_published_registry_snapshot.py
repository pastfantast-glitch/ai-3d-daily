#!/usr/bin/env python3
"""Materialize the verified Published Intelligence Registry for early Collector dedupe.

This is a read-only derived private artifact. Identity rules are NOT reimplemented
here: source precedence and URL normalization delegate to normalize_registry_identity.
Only dates with state=DONE are included. The canonical pre-ready normalizer remains
authoritative and revalidates every candidate before .ready.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import normalize_registry_identity as registry  # noqa: E402

OUT = ROOT / "data" / "candidates" / "published-registry-snapshot.json"


def build(through: str | None = None) -> dict:
    by_source = {}
    by_id = {}
    done_dates = []
    for path in sorted((ROOT / "data" / "daily").glob("20??-??-??.json")):
        date = path.stem
        if through and date > through:
            continue
        if not registry.is_verified_published(date):
            continue
        done_dates.append(date)
        data = json.loads(path.read_text("utf-8"))
        published_surface = registry.published_source_by_id(date)
        for item in data.get("items") or []:
            stable_id = str(item.get("id") or "").strip()
            if not stable_id:
                continue
            source = published_surface.get(stable_id) or registry.norm_url(item.get("source_url"))
            source = registry.norm_url(source)
            if source and source not in by_source:
                by_source[source] = {"source_url": source, "date": date, "id": stable_id}
            by_id.setdefault(stable_id, {"id": stable_id, "date": date, "source_url": source})

    return {
        "schema_version": 1,
        "state": "DERIVED_FROM_VERIFIED_DONE",
        "generated_through": max(done_dates) if done_dates else None,
        "identity_policy": "normalize_registry_identity.py:published-daily-html-card-then-canonical-json",
        "url_identity": "scripts/url_identity.py",
        "source_count": len(by_source),
        "id_count": len(by_id),
        "published_sources": [by_source[k] for k in sorted(by_source)],
        "published_ids": [by_id[k] for k in sorted(by_id)],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--through", default=None)
    args = ap.parse_args()
    payload = build(args.through)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(
        f"PUBLISHED REGISTRY SNAPSHOT: through={payload['generated_through']} "
        f"sources={payload['source_count']} ids={payload['id_count']}"
    )


if __name__ == "__main__":
    main()
