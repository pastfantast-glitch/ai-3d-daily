#!/usr/bin/env python3
"""Validate the quick-impact rating contract without rewriting canonical data."""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'quick-impact-contract.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
STAR_PREFIX_RE = re.compile(r'^[★☆]{1,5}')


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else ''
    if not DATE_RE.fullmatch(date):
        print('Usage: check_quick_impact_contract.py YYYY-MM-DD')
        return 1

    try:
        cfg = json.loads(CONFIG.read_text('utf-8'))
    except Exception as exc:
        print(f'QUICK IMPACT CONTRACT FAIL: invalid config: {exc}')
        return 1

    required = {
        'version': 1,
        'field': 'quick_impact',
        'format': 'stars_only',
        'presentation': 'rating_only',
        'legacy_presentation_policy': 'extract_leading_stars',
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            print(f'QUICK IMPACT CONTRACT FAIL: config {key} must be {expected!r}, got {cfg.get(key)!r}')
            return 1

    effective = str(cfg.get('effective_date', ''))
    if not DATE_RE.fullmatch(effective):
        print('QUICK IMPACT CONTRACT FAIL: effective_date must be YYYY-MM-DD')
        return 1
    try:
        allowed = re.compile(str(cfg.get('allowed_pattern', '')))
    except re.error as exc:
        print(f'QUICK IMPACT CONTRACT FAIL: invalid allowed_pattern: {exc}')
        return 1

    data_path = ROOT / 'data' / 'daily' / f'{date}.json'
    if not data_path.exists():
        print(f'QUICK IMPACT CONTRACT FAIL: missing canonical dataset {data_path.relative_to(ROOT)}')
        return 1
    data = json.loads(data_path.read_text('utf-8'))
    errors: list[str] = []
    legacy = date < effective
    for item in data.get('items') or []:
        intel_id = str(item.get('id') or '<missing-id>')
        value = str(item.get('quick_impact') or '').strip()
        if not value:
            errors.append(f'{intel_id}: quick_impact missing')
            continue
        if legacy:
            if not STAR_PREFIX_RE.match(value):
                errors.append(f'{intel_id}: legacy quick_impact must start with 1-5 star glyphs: {value!r}')
        elif not allowed.fullmatch(value):
            errors.append(f'{intel_id}: quick_impact must be stars only after {effective}: {value!r}')

    if errors:
        print('QUICK IMPACT CONTRACT FAIL')
        for error in errors:
            print('-', error)
        return 1

    mode = 'legacy-compatible/display-stars-only' if legacy else 'stars-only'
    print(f'QUICK IMPACT CONTRACT PASS: {date} / mode={mode} / items={len(data.get("items") or [])}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
