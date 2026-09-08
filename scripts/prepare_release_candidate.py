#!/usr/bin/env python3
"""Prepare one canonical intelligence date and create .ready only after all pre-ready gates pass.

Hybrid discovery extends the canonical prepare sequence without publishing derived
homepage/daily surfaces. Public presentation files are generated temporarily for
preflight, then restored before the prepare commit so a failed publish can never
leak a half-prepared homepage to GitHub Pages.
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


def snapshot(path: Path):
    if path.exists():
        return True, path.read_bytes()
    return False, b''


def restore(path: Path, state) -> None:
    existed, payload = state
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    else:
        path.unlink(missing_ok=True)


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

    ready_path.unlink(missing_ok=True)

    # normalize_release_seed.py writes these derived public surfaces for preflight.
    # Snapshot and restore them so prepare never publishes a half-ready site.
    public_paths = [ROOT / 'index.html', ROOT / date / 'index.html']
    public_snapshots = {path: snapshot(path) for path in public_paths}

    try:
        run('check_release_architecture.py')
        run('check_pipeline_contract.py')
        run('check_collection_contract.py')
        run('check_discovery_hybrid_contract.py')
        run('check_stability_contract.py')
        run('check_quick_impact_contract.py', date)

        # Contract stage token: normalize_registry_identity.py
        # The hybrid wrapper delegates normal Registry identity handling to that core gate.
        run('normalize_registry_identity_hybrid.py', date)
        run('apply_analysis_overrides.py', date)
        run('enrich_full_analysis_v3.py', date)
        run('normalize_release_seed.py', date)
        # Contract stage token: check_release_input.py
        # The hybrid wrapper delegates normal release-input validation to that core gate.
        run('check_release_input_hybrid.py', date)
        run('check_registry_contract.py', date)
    except SystemExit as exc:
        ready_path.unlink(missing_ok=True)
        code = int(exc.code) if isinstance(exc.code, int) else 1
        if code == 2:
            print('PRE-READY REFILL REQUIRED: canonical was normalized; continue discovery/fill ladder and rerun this gate. No .ready created.')
        else:
            print('PRE-READY FAILED: no .ready created.')
        raise
    finally:
        for path, state in public_snapshots.items():
            restore(path, state)
        print('PRE-READY PUBLIC SURFACES RESTORED: prepare did not publish homepage/daily HTML.')

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
        'public_surfaces_committed_before_publish': False,
    }
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(
        f"PRE-READY PASS: {date} items={len(items)} sha256={marker['canonical_sha256']} "
        f"ready={ready_path.relative_to(ROOT)}"
    )


if __name__ == '__main__':
    main()
