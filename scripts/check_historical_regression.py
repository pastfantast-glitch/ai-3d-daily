#!/usr/bin/env python3
"""Read-only historical regression matrix.

Legacy archive snapshots are validated structurally. Dates that also have canonical
JSON receive a full rebuild simulation inside a temporary copy of the repository.
Nothing in the working repository is modified or pushed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
errors: list[str] = []
rows: list[tuple[str, str, str]] = []


def fail(date: str, message: str) -> None:
    errors.append(f"{date}: {message}")


def archive_dirs(root: Path) -> list[Path]:
    return sorted(
        p for p in root.iterdir()
        if p.is_dir() and DATE_RE.fullmatch(p.name) and (p / "index.html").exists()
    )


def validate_archive_snapshot(d: Path, all_dirs: list[Path]) -> None:
    date = d.name
    text = (d / "index.html").read_text("utf-8")
    soup = BeautifulSoup(text, "html.parser")
    body = soup.body
    if body is None:
        fail(date, "missing body")
        rows.append((date, "snapshot", "FAIL"))
        return

    if "null" in text.lower():
        fail(date, "literal null present")
    if "archive-page" not in body.get("class", []):
        fail(date, "missing archive-page class")
    if body.get("data-report-date") != date:
        fail(date, "data-report-date mismatch")
    if not soup.find("link", href=re.compile(r"\.\./styles\.css\?v=")):
        fail(date, "missing cache-busted styles.css")
    if not soup.find("link", href=re.compile(r"\.\./daily\.css\?v=")):
        fail(date, "missing cache-busted daily.css")
    if not soup.find("script", src=re.compile(r"\.\./daily\.js\?v=")):
        fail(date, "missing cache-busted daily.js")
    if soup.find("script", src=re.compile(r"accordion\.js")):
        fail(date, "legacy accordion.js referenced")

    top_cards = soup.select("#top .news")
    if len(top_cards) != 5:
        fail(date, f"TOP card count must be 5, got {len(top_cards)}")
    if not soup.find("details"):
        fail(date, "no expandable Full Analysis/details content")

    for a in soup.find_all("a", target="_blank"):
        rel = set(a.get("rel", []))
        if not {"noopener", "noreferrer"} <= rel:
            fail(date, "unsafe target=_blank link")
            break

    index = all_dirs.index(d)
    expected_prev = all_dirs[index - 1].name if index else ""
    expected_next = all_dirs[index + 1].name if index + 1 < len(all_dirs) else ""
    if body.get("data-previous", "") != expected_prev:
        fail(date, f"previous mismatch: expected {expected_prev!r}, got {body.get('data-previous','')!r}")
    if body.get("data-next", "") != expected_next:
        fail(date, f"next mismatch: expected {expected_next!r}, got {body.get('data-next','')!r}")

    manifest = ROOT / "assets" / "visual" / date / "manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text("utf-8"))
        if data.get("date") != date:
            fail(date, "date-scoped visual manifest date mismatch")
        for entry in data.get("entries", []):
            if entry.get("status") == "ok":
                asset = entry.get("local_path") or entry.get("asset")
                if asset:
                    candidate = ROOT / asset.lstrip("/")
                    if not candidate.exists():
                        fail(date, f"visual asset missing: {asset}")

    rows.append((date, "snapshot", "PASS" if not any(e.startswith(date + ":") for e in errors) else "FAIL"))


def validate_home_archive_links(all_dirs: list[Path]) -> None:
    home = ROOT / "index.html"
    if not home.exists():
        fail("home", "index.html missing")
        return
    soup = BeautifulSoup(home.read_text("utf-8"), "html.parser")
    existing = {d.name for d in all_dirs}
    for a in soup.select(".history-list a[href]"):
        href = a.get("href", "")
        m = re.fullmatch(r"(20\d{2}-\d{2}-\d{2})/?", href)
        if m and m.group(1) not in existing:
            fail("home", f"dangling history archive link: {href}")


def run(work: Path, *cmd: str) -> None:
    proc = subprocess.run(cmd, cwd=work, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(f"$ {' '.join(cmd)}")
    print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def canonical_rebuild_simulation(date: str) -> None:
    canonical = ROOT / "data" / "daily" / f"{date}.json"
    if not canonical.exists():
        rows.append((date, "canonical-rebuild", "SKIP (legacy snapshot: no canonical JSON)"))
        return

    with tempfile.TemporaryDirectory(prefix=f"ai3d-regression-{date}-") as td:
        work = Path(td) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        try:
            if date == "2026-08-23":
                run(work, sys.executable, "scripts/bootstrap_intelligence_ids.py")
            run(work, sys.executable, "scripts/check_release_input.py", date)
            run(work, sys.executable, "scripts/render_daily_navigation.py")
            run(work, sys.executable, "scripts/build_intelligence.py", date)
            # Historical dry runs reuse the persisted date-scoped visual snapshot;
            # they deliberately do not hit third-party websites again.
            run(work, sys.executable, "scripts/inject_visual_previews.py", date)
            run(work, sys.executable, "scripts/apply_cache_bust.py", date)
            run(work, sys.executable, "scripts/check_intelligence_contract.py")
            run(work, sys.executable, "scripts/check_visual_contract.py", date)
            run(work, sys.executable, "scripts/check_home_contract.py")
            run(work, sys.executable, "scripts/check_daily_contract.py")
        except Exception as exc:
            fail(date, f"canonical rebuild simulation failed: {exc}")
            rows.append((date, "canonical-rebuild", "FAIL"))
        else:
            rows.append((date, "canonical-rebuild", "PASS"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4, help="latest archive snapshots to include")
    args = ap.parse_args()

    all_dirs = archive_dirs(ROOT)
    if not all_dirs:
        print("HISTORICAL REGRESSION FAILED: no archive directories")
        return 1
    selected = all_dirs[-max(1, args.days):]

    print("Historical regression archives:", ", ".join(d.name for d in selected))
    validate_home_archive_links(all_dirs)
    for d in selected:
        validate_archive_snapshot(d, all_dirs)
    for d in selected:
        canonical_rebuild_simulation(d.name)

    print("\nHISTORICAL REGRESSION MATRIX")
    for date, mode, status in rows:
        print(f"- {date:<10} | {mode:<17} | {status}")

    if errors:
        print("\nHISTORICAL REGRESSION FAILED")
        for e in errors:
            print("-", e)
        return 1
    print("\nHISTORICAL REGRESSION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
