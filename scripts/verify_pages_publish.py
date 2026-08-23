#!/usr/bin/env python3
"""Verify that GitHub Pages serves the just-published canonical release.

This is deliberately read-only and runs after the repository push. It retries to
absorb GitHub Pages/CDN propagation delay, then validates the public homepage and
archive against the local canonical dataset by stable intelligence ID.
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

ROOT = Path(__file__).resolve().parents[1]


def load_canonical(date: str) -> dict:
    path = ROOT / "data" / "daily" / f"{date}.json"
    if not path.exists():
        raise SystemExit(f"missing canonical dataset: {path}")
    return json.loads(path.read_text("utf-8"))


def get(url: str, timeout: int) -> requests.Response:
    headers = {
        "User-Agent": "ai-3d-daily-release-verifier/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


def structural_errors(html: str, date: str, expected_ids: list[str], *, home: bool) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    errors: list[str] = []
    body = soup.body
    report_date = body.get("data-report-date", "") if body else ""
    text = soup.get_text(" ", strip=True)
    if report_date and report_date != date:
        errors.append(f"data-report-date={report_date}, expected {date}")
    if date not in text:
        errors.append(f"visible date {date} missing")

    if home:
        cards = soup.select('.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]')
    else:
        cards = soup.select('#top .news[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]')

    ids = [c.get("data-intel-id") for c in cards]
    if ids != expected_ids:
        errors.append(f"stable ID order mismatch: got={ids} expected={expected_ids}")

    for card in cards:
        rid = card.get("data-intel-id")
        details = card.find("details")
        body_el = details.find("div", class_="detail-body") if details else None
        if not details or not body_el:
            errors.append(f"{rid}: missing Full Analysis details/detail-body")
            continue
        if len(body_el.find_all("h4", recursive=False)) < 3:
            errors.append(f"{rid}: expected >=3 Full Analysis headings")
        if len(body_el.find_all("p", recursive=False)) < 3:
            errors.append(f"{rid}: expected >=3 Full Analysis paragraphs")
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
        if entry.get("status") == "ok":
            asset = entry.get("asset_path") or ""
            if not asset:
                errors.append(f"{entry.get('id')}: status=ok but asset_path missing")
    return errors


def verify_once(base_url: str, date: str, expected_ids: list[str], timeout: int) -> list[str]:
    base_url = base_url.rstrip("/") + "/"
    home_url = base_url
    daily_url = urljoin(base_url, f"{date}/")
    errors: list[str] = []
    try:
        home = get(home_url, timeout).text
        errors.extend(f"home: {e}" for e in structural_errors(home, date, expected_ids, home=True))
    except Exception as exc:
        errors.append(f"home request failed: {exc}")
    try:
        daily = get(daily_url, timeout).text
        errors.extend(f"daily: {e}" for e in structural_errors(daily, date, expected_ids, home=False))
    except Exception as exc:
        errors.append(f"daily request failed: {exc}")
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

    data = load_canonical(args.date)
    expected_ids = [x["id"] for x in data.get("items", [])]
    if not expected_ids:
        raise SystemExit("canonical dataset contains no items")

    last: list[str] = []
    for attempt in range(1, args.attempts + 1):
        last = verify_once(args.base_url, args.date, expected_ids, args.timeout)
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
