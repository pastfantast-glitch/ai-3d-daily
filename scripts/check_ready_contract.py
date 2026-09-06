#!/usr/bin/env python3
"""Fail closed unless .ready proves the canonical dataset passed pre-ready preparation.

The canonical publisher calls this before any canonical mutation. This prevents a
hand-written/stale .ready marker from entering the writer and guarantees Registry
normalization happened before publication was triggered.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str) -> None:
    print(f'READY CONTRACT FAILED: {msg}')
    raise SystemExit(1)


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else ''
    if not DATE_RE.fullmatch(date):
        fail('usage: check_ready_contract.py YYYY-MM-DD')

    data_path = ROOT / 'data' / 'daily' / f'{date}.json'
    ready_path = ROOT / 'data' / 'publish' / f'{date}.ready'
    if not data_path.exists():
        fail(f'missing canonical dataset {data_path.relative_to(ROOT)}')
    if not ready_path.exists():
        fail(f'missing ready marker {ready_path.relative_to(ROOT)}')

    try:
        marker = json.loads(ready_path.read_text('utf-8'))
    except Exception as exc:
        fail(f'ready marker must be JSON produced by pre-ready gate: {exc}')

    if str(marker.get('state', '')).strip().upper() != 'READY':
        fail('ready marker state must be READY')
    if marker.get('date') != date:
        fail(f"ready marker date mismatch: {marker.get('date')} != {date}")
    if marker.get('prepared_by') != 'scripts/prepare_release_candidate.py':
        fail('ready marker was not produced by scripts/prepare_release_candidate.py')
    if marker.get('registry_normalized_before_ready') is not True:
        fail('ready marker does not attest registry normalization before ready')
    if marker.get('preflight_passed_before_ready') is not True:
        fail('ready marker does not attest preflight before ready')

    actual_sha = sha256_file(data_path)
    expected_sha = str(marker.get('canonical_sha256', '')).strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha):
        fail('ready marker canonical_sha256 must be a 64-character lowercase SHA-256')
    if actual_sha != expected_sha:
        fail(f'canonical changed after pre-ready gate: ready={expected_sha} current={actual_sha}')

    try:
        data = json.loads(data_path.read_text('utf-8'))
    except Exception as exc:
        fail(f'invalid canonical JSON: {exc}')
    item_count = len(data.get('items') or [])
    if marker.get('item_count') != item_count:
        fail(f"item_count drift: ready={marker.get('item_count')} current={item_count}")

    print(f'READY CONTRACT PASS: {date} items={item_count} sha256={actual_sha}')


if __name__ == '__main__':
    main()
