#!/usr/bin/env python3
"""Prepare one canonical intelligence date and create .ready only after all pre-ready gates pass.

Hybrid discovery extends the canonical prepare sequence without publishing derived
homepage/daily surfaces. Public presentation files are generated temporarily for
preflight, then restored before the prepare commit so a failed publish can never
leak a half-prepared homepage to GitHub Pages.

Normal collection remains idempotent: a date with state=DONE is refused. The sole
exception is an explicit repository request whose JSON intent is `policy-republish`
and whose date matches the target. That path exists for deterministic contract or
presentation-policy migrations of an already-verified canonical release; it still
runs the complete prepare gate and generates `.ready` here rather than by hand.
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


def explicit_policy_republish_requested(date: str) -> bool:
    request_path = ROOT / 'data' / 'publish' / f'{date}.request'
    if not request_path.exists():
        return False
    try:
        request = json.loads(request_path.read_text('utf-8'))
    except Exception:
        return False
    return (
        str(request.get('intent', '')).strip() == 'policy-republish'
        and str(request.get('date', '')).strip() == date
        and request.get('allow_done_republish') is True
    )


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else ''
    if not DATE_RE.fullmatch(date):
        raise SystemExit('Usage: prepare_release_candidate.py YYYY-MM-DD')

    data_path = ROOT / 'data' / 'daily' / f'{date}.json'
    ready_path = ROOT / 'data' / 'publish' / f'{date}.ready'
    done_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not data_path.exists():
        raise SystemExit(f'Missing canonical dataset: {data_path}')

    controlled_republish = False
    if done_path.exists():
        try:
            receipt = json.loads(done_path.read_text('utf-8'))
        except Exception as exc:
            raise SystemExit(f'Invalid DONE receipt: {done_path}: {exc}')
        if str(receipt.get('state', '')).strip().upper() == 'DONE':
            controlled_republish = explicit_policy_republish_requested(date)
            if not controlled_republish:
                raise SystemExit(f'{date} already has state=DONE; refusing to prepare/re-run')
            print(
                f'CONTROLLED POLICY REPUBLISH: {date} has state=DONE but an explicit '
                'repo request authorizes full pre-ready revalidation.'
            )

    ready_path.unlink(missing_ok=True)

    # normalize_release_seed.py writes these derived public surfaces for preflight.
    # Snapshot and restore them so prepare never publishes a half-ready site.
    public_paths = [ROOT / 'index.html', ROOT / date / 'index.html']
    public_snapshots = {path: snapshot(path) for path in public_paths}

    try:
        run('check_release_architecture.py')
        run('check_tier_assignment_contract.py')
        run('check_analysis_reading_contract.py')
        run('check_pipeline_contract.py')
        run('check_collection_contract.py')
        run('check_discovery_hybrid_contract.py')
        run('check_personalization_feedback_contract.py', date)
        run('check_stability_contract.py')
        run('check_quick_impact_contract.py', date)

        # Registry identity + tier assignment are normalized before any ready marker.
        run('normalize_registry_identity_hybrid.py', date)
        run('apply_analysis_overrides.py', date)
        run('enrich_full_analysis_v3.py', date)
        run('normalize_release_seed.py', date)

        # Canonical release-input validator. Legacy hybrid filename is compatibility-only.
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
        'controlled_policy_republish': controlled_republish,
    }
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(
        f"PRE-READY PASS: {date} items={len(items)} sha256={marker['canonical_sha256']} "
        f"ready={ready_path.relative_to(ROOT)} controlled_republish={controlled_republish}"
    )


if __name__ == '__main__':
    main()
