#!/usr/bin/env python3
"""Offline guard for tier-aware public surface verification.

Runs the same structural analysis checks used by verify_pages_publish.py against
the newest rendered canonical report without making network requests. This catches
FULL/BRIEF/REJECT verifier drift before the final GitHub Pages verification stage.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from intelligence_v2 import is_v2_dataset, load_config, homepage_groups, category_items
from verify_pages_publish import structural_errors, load_depth


def newest_rendered_canonical():
    dates = sorted(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))
    for date in reversed(dates):
        daily = ROOT / date / 'index.html'
        if daily.exists():
            return date, json.loads((ROOT / 'data' / 'daily' / f'{date}.json').read_text('utf-8'))
    raise SystemExit('PAGES TIER CONTRACT FAIL: no rendered canonical report')


def check_surface(path: Path, date: str, items: list[dict], surface: str, depth: dict, legacy_min: int):
    if not path.exists():
        return [f'{path.relative_to(ROOT)} missing']
    html = path.read_text('utf-8')
    return structural_errors(
        html,
        date,
        items,
        surface=surface,
        depth=depth,
        legacy_min_blocks=legacy_min,
    )


def main():
    date, data = newest_rendered_canonical()
    if not is_v2_dataset(data):
        print(f'PAGES TIER CONTRACT SKIP: {date} is legacy schema')
        return

    cfg = load_config()
    depth = load_depth()
    legacy_min = int((cfg or {}).get('full_analysis', {}).get('min_blocks', 3))
    top, next10 = homepage_groups(data)
    public_items = top + next10

    errors = []
    errors += [f'home: {e}' for e in check_surface(ROOT / 'index.html', date, public_items, 'home', depth, legacy_min)]
    errors += [f'daily: {e}' for e in check_surface(ROOT / date / 'index.html', date, public_items, 'daily', depth, legacy_min)]

    for category in cfg.get('categories') or []:
        cid = category['id']
        items = category_items(data, cid)
        errors += [
            f'category:{cid}: {e}'
            for e in check_surface(ROOT / date / cid / 'index.html', date, items, 'category', depth, legacy_min)
        ]

    if errors:
        print('PAGES TIER CONTRACT FAIL')
        print('\n'.join('- ' + e for e in errors))
        raise SystemExit(1)

    counts = data.get('metadata', {}).get('analysis_level_counts', {})
    print(f'PAGES TIER CONTRACT PASS: {date} FULL={counts.get("FULL", 0)} BRIEF={counts.get("BRIEF", 0)} REJECT={counts.get("REJECT", 0)}')


if __name__ == '__main__':
    main()
