#!/usr/bin/env python3
"""Verify that GitHub Pages serves the just-published canonical release.

Read-only post-publish verification. Schema-v3/V2 verifies the intentionally
split public surfaces: homepage + daily contain TOP5+next10 only, while each of
the six date-scoped category pages contains its canonical pool. Analysis depth
is tier-aware from config/full-analysis-depth.json: FULL and BRIEF are verified
against their own block contracts; REJECT is never publishable.
Legacy schemas retain their original all-items home/daily verification.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset, load_config, homepage_groups, category_items

ROOT = Path(__file__).resolve().parents[1]
STABILITY = ROOT / 'config' / 'stability-contract.json'
DEPTH = ROOT / 'config' / 'full-analysis-depth.json'


def load_stability() -> dict:
    return json.loads(STABILITY.read_text('utf-8'))


def load_depth() -> dict:
    if not DEPTH.exists():
        return {}
    return json.loads(DEPTH.read_text('utf-8'))


def load_canonical(date: str) -> dict:
    path = ROOT / "data" / "daily" / f"{date}.json"
    if not path.exists():
        raise SystemExit(f"missing canonical dataset: {path}")
    return json.loads(path.read_text("utf-8"))


def get(url: str, timeout: int) -> requests.Response:
    headers = {
        "User-Agent": "ai-3d-daily-release-verifier/1.2",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


def tiered_for_date(date: str, depth: dict) -> bool:
    effective = str(depth.get('tiered_effective_date') or '').strip()
    return bool(effective and date >= effective)


def analysis_policy(date: str, item: dict, depth: dict, legacy_min_blocks: int):
    if not tiered_for_date(date, depth):
        return 'FULL', legacy_min_blocks, None, None

    level = str(item.get('analysis_level') or depth.get('default_analysis_level') or 'FULL').upper()
    if level == 'REJECT':
        return level, 0, 0, 'REJECT item reached public Pages surface'
    if level not in ('FULL', 'BRIEF'):
        return level, 0, 0, f'unknown analysis_level={level}'

    rule = depth.get(level.lower()) or {}
    minimum = int(rule.get('min_blocks', 0) or 0)
    maximum = int(rule.get('max_blocks', 0) or 0)
    if minimum <= 0 or maximum < minimum:
        return level, minimum, maximum, f'invalid {level} depth policy min={minimum} max={maximum}'
    return level, minimum, maximum, None


def analysis_errors(
    card,
    rid: str,
    *,
    expected_level: str,
    min_blocks: int,
    max_blocks: int | None,
    require_level_attr: bool,
) -> list[str]:
    errors: list[str] = []
    details = card.find("details")
    body_el = details.find("div", class_="detail-body") if details else None
    if not details or not body_el:
        return [f"{rid}: missing analysis details/detail-body"]

    rendered_level = str(details.get('data-analysis-level') or '').upper()
    if require_level_attr and expected_level in ('FULL', 'BRIEF') and not rendered_level:
        errors.append(f"{rid}: rendered analysis level missing; expected {expected_level}")
    elif rendered_level and expected_level in ('FULL', 'BRIEF') and rendered_level != expected_level:
        errors.append(f"{rid}: rendered analysis level={rendered_level}, expected {expected_level}")

    headings = body_el.find_all("h4", recursive=False)
    paragraphs = body_el.find_all("p", recursive=False)
    if len(headings) < min_blocks:
        errors.append(f"{rid}: {expected_level} expected >={min_blocks} analysis headings, got {len(headings)}")
    if len(paragraphs) < min_blocks:
        errors.append(f"{rid}: {expected_level} expected >={min_blocks} analysis paragraphs, got {len(paragraphs)}")
    if max_blocks is not None and max_blocks > 0:
        if len(headings) > max_blocks:
            errors.append(f"{rid}: {expected_level} expected <={max_blocks} analysis headings, got {len(headings)}")
        if len(paragraphs) > max_blocks:
            errors.append(f"{rid}: {expected_level} expected <={max_blocks} analysis paragraphs, got {len(paragraphs)}")
    return errors


def structural_errors(
    html: str,
    date: str,
    expected_items: list[dict],
    *,
    surface: str,
    depth: dict,
    legacy_min_blocks: int,
) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    errors: list[str] = []
    body = soup.body
    report_date = body.get("data-report-date", "") if body else ""
    text = soup.get_text(" ", strip=True)
    if report_date and report_date != date:
        errors.append(f"data-report-date={report_date}, expected {date}")
    if date not in text:
        errors.append(f"visible date {date} missing")

    if surface == "home":
        cards = soup.select('.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]')
    elif surface == "daily":
        cards = soup.select('#top .news[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]')
    elif surface == "category":
        cards = soup.select('.category-card[data-intel-role="card"][data-intel-id]')
    else:
        raise ValueError(f"unknown surface: {surface}")

    expected_ids = [str(item.get('id') or '') for item in expected_items]
    ids = [c.get("data-intel-id") for c in cards]
    if ids != expected_ids:
        errors.append(f"stable ID order mismatch: got={ids} expected={expected_ids}")

    item_by_id = {str(item.get('id') or ''): item for item in expected_items}
    require_level_attr = tiered_for_date(date, depth)
    for card in cards:
        rid = str(card.get('data-intel-id') or '?')
        item = item_by_id.get(rid)
        if item is None:
            errors.append(f"{rid}: rendered card is not in expected canonical surface")
            continue
        level, minimum, maximum, policy_error = analysis_policy(date, item, depth, legacy_min_blocks)
        if policy_error:
            errors.append(f"{rid}: {policy_error}")
            continue
        errors.extend(analysis_errors(
            card,
            rid,
            expected_level=level,
            min_blocks=minimum,
            max_blocks=maximum,
            require_level_attr=require_level_attr,
        ))
    return errors


def visual_errors(base_url: str, date: str, timeout: int) -> list[str]:
    url = urljoin(base_url, f"assets/visual/{date}/manifest.json")
    try:
        manifest = get(url, timeout).json()
    except Exception as exc:
        return [f"visual manifest unavailable: {exc}"]
    errors: list[str] = []
    if manifest.get("date") != date:
        errors.append(f"visual manifest date={manifest.get('date')} expected={date}")
    entries = manifest.get("entries") or []
    if not entries:
        errors.append("visual manifest has no entries")
    for entry in entries:
        if entry.get("status") == "ok" and not (entry.get("asset_path") or ""):
            errors.append(f"{entry.get('id')}: status=ok but asset_path missing")
    return errors


def verify_once(base_url: str, date: str, data: dict, timeout: int) -> list[str]:
    base_url = base_url.rstrip("/") + "/"
    errors: list[str] = []
    v2 = is_v2_dataset(data)
    cfg = load_config() if v2 else None
    depth = load_depth() if v2 else {}
    legacy_min_blocks = int((cfg or {}).get("full_analysis", {}).get("min_blocks", 3))

    if v2:
        top, next10 = homepage_groups(data)
        public_items = top + next10
    else:
        public_items = list(data.get("items", []))

    surfaces = [
        ("home", base_url, public_items),
        ("daily", urljoin(base_url, f"{date}/"), public_items),
    ]
    if v2:
        for category in cfg["categories"]:
            cid = category["id"]
            expected = category_items(data, cid)
            surfaces.append((f"category:{cid}", urljoin(base_url, f"{date}/{cid}/"), expected))

    for name, url, expected in surfaces:
        try:
            html = get(url, timeout).text
            surface = "category" if name.startswith("category:") else name
            errors.extend(
                f"{name}: {e}"
                for e in structural_errors(
                    html,
                    date,
                    expected,
                    surface=surface,
                    depth=depth,
                    legacy_min_blocks=legacy_min_blocks,
                )
            )
        except Exception as exc:
            errors.append(f"{name} request failed: {exc}")

    errors.extend(visual_errors(base_url, date, timeout))
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--base-url", default=os.environ.get("SITE_URL", ""))
    ap.add_argument("--attempts", type=int, default=8)
    ap.add_argument("--delay", type=int, default=15)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()
    if not args.base_url:
        raise SystemExit("SITE_URL / --base-url is required")

    stability = load_stability()
    page_policy = stability.get('pages_verify') or {}
    minimum_attempts = int(page_policy.get('minimum_attempts', 8))
    minimum_delay = int(page_policy.get('minimum_delay_seconds', 15))
    configured_timeout = int(page_policy.get('timeout_seconds', 20))
    # Workflow CLI values may request more resilience, but never less than the
    # repository stability contract. This keeps the source of truth in repo config.
    args.attempts = max(args.attempts, minimum_attempts)
    args.delay = max(args.delay, minimum_delay)
    args.timeout = max(args.timeout, configured_timeout)
    print(f"PAGES VERIFY POLICY: attempts={args.attempts} delay={args.delay}s timeout={args.timeout}s")

    data = load_canonical(args.date)
    if not data.get("items"):
        raise SystemExit("canonical dataset contains no items")

    last: list[str] = []
    for attempt in range(1, args.attempts + 1):
        last = verify_once(args.base_url, args.date, data, args.timeout)
        if not last:
            print(f"PAGES VERIFY PASS: {args.date} {args.base_url.rstrip('/')}/")
            return 0
        print(f"PAGES VERIFY attempt {attempt}/{args.attempts} not ready:")
        for err in last:
            print(" -", err)
        if attempt < args.attempts:
            time.sleep(args.delay)

    print("PAGES VERIFY FAILED")
    for err in last:
        print(" -", err)
    return 1


if __name__ == "__main__":
    sys.exit(main())
