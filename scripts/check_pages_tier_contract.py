#!/usr/bin/env python3
"""Offline guard for tier-aware public surface verification.

Runs the same structural analysis checks used by verify_pages_publish.py against
the newest rendered canonical report without making network requests. This catches
FULL/BRIEF/REJECT verifier drift before the final GitHub Pages verification stage.
It also fail-closes the runtime path that keeps TOP5 and category analyses on the
same canonical full_analysis renderer.
"""
from pathlib import Path
import hashlib
import json
import sys
import re
import subprocess

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


def policy_recollect_pending(date: str, data: dict) -> bool:
    """Detect a trusted selection-preserving policy republish before public rerender."""
    receipt_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    collector_path = ROOT / 'data' / 'publish' / f'{date}.collector'
    ready_path = ROOT / 'data' / 'publish' / f'{date}.ready'
    data_path = ROOT / 'data' / 'daily' / f'{date}.json'
    if not receipt_path.exists() or not collector_path.exists() or not data_path.exists():
        return False
    try:
        receipt = json.loads(receipt_path.read_text('utf-8'))
        collector = json.loads(collector_path.read_text('utf-8'))
    except Exception:
        return False
    if str(receipt.get('state', '')).strip().upper() != 'DONE':
        return False
    if str(collector.get('state', '')).strip().upper() != 'COLLECTOR_PERSISTED':
        return False
    if str(collector.get('intent', '')).strip() != 'policy-republish':
        return False
    if collector.get('writer_idle_confirmed_externally') is not True:
        return False
    if (data.get('metadata') or {}).get('policy_recollect') is not True:
        return False

    current_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if not ready_path.exists():
        return True
    try:
        ready = json.loads(ready_path.read_text('utf-8'))
    except Exception:
        return True
    return not (
        ready.get('controlled_policy_republish') is True
        and str(ready.get('canonical_sha256', '')).strip().lower() == current_hash
    )


def pending_verified_historical_editorial_restore(date: str, data: dict) -> bool:
    """Allow private canonical restore to precede public rerender only when an ancestor DONE proves the exact selection."""
    override_path = ROOT / 'data' / 'editorial-overrides' / f'{date}.json'
    current_done_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not override_path.exists() or not current_done_path.exists():
        return False
    try:
        override = json.loads(override_path.read_text('utf-8'))
        current_done = json.loads(current_done_path.read_text('utf-8'))
    except Exception:
        return False
    ref = str(override.get('restore_selection_from_receipt_commit') or '').strip().lower()
    if (
        override.get('preserve_selection') is not True
        or str(override.get('date') or '') != date
        or not re.fullmatch(r'[0-9a-f]{40}', ref)
        or str(current_done.get('state') or '').upper() != 'DONE'
    ):
        return False

    current_items = data.get('items') or []
    current_ids = [str(x.get('id') or '') for x in current_items]
    patches = override.get('items') or {}
    if not isinstance(patches, dict) or set(patches) != set(current_ids) or len(patches) != len(current_ids):
        return False

    ancestor = subprocess.run(
        ['git', 'merge-base', '--is-ancestor', ref, 'HEAD'],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestor.returncode:
        return False

    def git_json(relative_path: str):
        proc = subprocess.run(
            ['git', 'show', f'{ref}:{relative_path}'],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if proc.returncode:
            return None
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None

    historical_done = git_json(f'data/publish/{date}.done.json')
    historical_data = git_json(f'data/daily/{date}.json')
    if not isinstance(historical_done, dict) or not isinstance(historical_data, dict):
        return False
    if str(historical_done.get('state') or '').upper() != 'DONE':
        return False
    historical_ids = [str(x) for x in ((historical_done.get('canonical') or {}).get('ids') or [])]
    if current_ids != historical_ids:
        return False

    def selection_rows(items):
        return [
            (
                str(x.get('id') or ''),
                str(x.get('source_url') or '').rstrip('/'),
                int(x.get('rank_global', 0) or 0),
                str(x.get('category') or ''),
                str(x.get('subcategory') or ''),
            )
            for x in (items or [])
        ]

    if selection_rows(current_items) != selection_rows(historical_data.get('items') or []):
        return False

    current_done_ids = [str(x) for x in ((current_done.get('canonical') or {}).get('ids') or [])]
    return current_done_ids != current_ids


def runtime_surface_errors():
    errors = []
    canonical = (ROOT / 'canonical-client.js').read_text('utf-8')
    archive = (ROOT / 'archive-nav-state.js').read_text('utf-8')
    builder = (ROOT / 'scripts' / 'build_intelligence.py').read_text('utf-8')

    if '.category-card' not in canonical:
        errors.append('canonical-client.js must hydrate category-card surfaces')
    if "summary.textContent='完整分析'" not in canonical:
        errors.append('runtime canonical renderer must expose one 完整分析 entry for every published tier')
    if 'analysis-level-note' not in canonical or '證據深度較有限' not in canonical:
        errors.append('BRIEF must remain visible as evidence depth inside the full-analysis UI')
    if 'async function hydrateCanonical()' not in archive:
        errors.append('archive workspace must expose a canonical hydration helper')
    if 'await hydrateCanonical();' not in archive:
        errors.append('archive tab swaps must hydrate the newly imported main surface')
    init_start = archive.find('function init(){')
    init_end = archive.find("if(document.readyState==='loading')", init_start)
    init_block = archive[init_start:init_end] if init_start >= 0 and init_end > init_start else ''
    if 'hydrateCanonical();' not in init_block:
        errors.append('direct category/archive loads must hydrate canonical full_analysis')
    if "summary.string = '完整分析'" not in builder:
        errors.append('static builder must render BRIEF/FULL under the same 完整分析 entry')
    if "'情報簡析' if level == 'BRIEF'" in builder:
        errors.append('static builder must not fork BRIEF into a separate 情報簡析 UI')
    return errors


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

    pending_republish = policy_recollect_pending(date, data)
    pending_historical_restore = pending_verified_historical_editorial_restore(date, data)
    errors = []
    if not pending_republish and not pending_historical_restore:
        errors += [f'home: {e}' for e in check_surface(ROOT / 'index.html', date, public_items, 'home', depth, legacy_min)]
        errors += [f'daily: {e}' for e in check_surface(ROOT / date / 'index.html', date, public_items, 'daily', depth, legacy_min)]

        for category in cfg.get('categories') or []:
            cid = category['id']
            items = category_items(data, cid)
            errors += [
                f'category:{cid}: {e}'
                for e in check_surface(ROOT / date / cid / 'index.html', date, items, 'category', depth, legacy_min)
            ]

    errors += [f'runtime: {e}' for e in runtime_surface_errors()]

    if errors:
        print('PAGES TIER CONTRACT FAIL')
        print('\n'.join('- ' + e for e in errors))
        raise SystemExit(1)

    counts = data.get('metadata', {}).get('analysis_level_counts', {})
    state = (
        ' pending-policy-republish'
        if pending_republish
        else ' pending-verified-historical-editorial-restore'
        if pending_historical_restore
        else ''
    )
    print(f'PAGES TIER CONTRACT PASS: {date} FULL={counts.get("FULL", 0)} BRIEF={counts.get("BRIEF", 0)} REJECT={counts.get("REJECT", 0)}{state}')


if __name__ == '__main__':
    main()
