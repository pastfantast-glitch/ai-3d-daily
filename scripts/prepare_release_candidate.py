#!/usr/bin/env python3
"""Prepare one canonical intelligence date and create .ready only after all pre-ready gates pass.

This is the single collection-stage entry point immediately before publication.
It deliberately performs every canonical mutation that can affect identity, item
count, ranking shell or release seed BEFORE the .ready marker exists.

Exit codes:
- 0: all pre-ready gates passed and data/publish/YYYY-MM-DD.ready was written.
- 2: registry normalization succeeded but discovery/refill is still required;
     no .ready marker is left behind.
- 1: contract/preflight/data error; no .ready marker is left behind.

The script never commits or pushes. The collector owns discovery and commits the
prepared canonical data + release seed + .ready atomically. The canonical publish
workflow is the only repository writer after .ready is pushed.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"PRE-READY STAGE: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode:
        raise SystemExit(proc.returncode)


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else ''
    if not DATE_RE.fullmatch(date):
        raise SystemExit('Usage: prepare_release_candidate.py YYYY-MM-DD')

    data_path = ROOT / 'data' / 'daily' / f'{date}.json'
    ready_path = ROOT / 'data' / 'publish' / f'{date}.ready'
    done_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not data_path.exists():
        raise SystemExit(f'Missing canonical dataset: {data_path}')

    if done_path.exists():
        try:
            receipt = json.loads(done_path.read_text('utf-8'))
        except Exception as exc:
            raise SystemExit(f'Invalid DONE receipt: {done_path}: {exc}')
        if str(receipt.get('state', '')).strip().upper() == 'DONE':
            raise SystemExit(f'{date} already has state=DONE; refusing to prepare/re-run')

    # A stale/hand-authored marker must never survive preparation failures.
    ready_path.unlink(missing_ok=True)

    try:
        # Repository topology/config and cross-pipeline stability controls must be
        # internally consistent before any identity mutation occurs.
        run('check_pipeline_contract.py')
        run('check_collection_contract.py')
        run('check_stability_contract.py')
        # quick_impact is a compact rating field. From the configured effective
        # date onward it must contain star glyphs only; production commentary
        # belongs in summary/full_analysis instead of the rating surface.
        run('check_quick_impact_contract.py', date)

        # Identity normalization is a collection-stage mutation. Exit 2 means the
        # normalized canonical is intentionally kept so discovery can refill it.
        run('normalize_registry_identity.py', date)

        # Canonical analysis/taxonomy and the allowed current-day release seed are
        # normalized before input/registry preflight.
        run('enrich_full_analysis_v3.py', date)
        run('normalize_release_seed.py', date)
        run('check_release_input.py', date)
        run('check_registry_contract.py', date)
    except SystemExit as exc:
        ready_path.unlink(missing_ok=True)
        code = int(exc.code) if isinstance(exc.code, int) else 1
        if code == 2:
            print('PRE-READY REFILL REQUIRED: canonical was normalized; continue discovery/fill ladder and rerun this gate. No .ready created.')
        else:
            print('PRE-READY FAILED: no .ready created.')
        raise

    data = json.loads(data_path.read_text('utf-8'))
    items = data.get('items') or []
    marker = {
        'state': 'READY',
        'date': date,
        'canonical_sha256': sha256_file(data_path),
        'item_count': len(items),
        'prepared_by': 'scripts/prepare_release_candidate.py',
        'registry_normalized_before_ready': True,
        'preflight_passed_before_ready': True,
    }
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(
        f"PRE-READY PASS: {date} items={len(items)} sha256={marker['canonical_sha256']} "
        f"ready={ready_path.relative_to(ROOT)}"
    )


if __name__ == '__main__':
    main()
