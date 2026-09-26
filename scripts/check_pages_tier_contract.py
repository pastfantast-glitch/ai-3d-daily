#!/usr/bin/env python3
"""Offline guard for tier-aware public surface verification.

Runs the same structural analysis checks used by verify_pages_publish.py against
the newest rendered canonical report without making network requests. This catches
FULL/BRIEF/REJECT verifier drift before the final GitHub Pages verification stage.
It also fail-closes the runtime path that keeps TOP5 and category analyses on the
same canonical full_analysis renderer.
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


def policy_recollect_pending(date: str, data: dict) -> bool:
    receipt_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not receipt_path.exists():
        return False
    try:
        receipt = json.loads(receipt_path.read_text('utf-8'))
    except Exception:
        return False
    if str(receipt.get('state', '')).upper() != 'DONE':
        return False
    if (data.get('metadata') or {}).get('policy_recollect') is not True:
        return False
    current = [str(x.get('id', '')) for x in (data.get('items') or [])]
    published = [str(x) for x in ((receipt.get('canonical') or {}).get('ids') or [])]
    return bool(current) and current != published


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
    errors = []
    if not pending_republish:
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
    state = ' pending-policy-republish' if pending_republish else ''
    print(f'PAGES TIER CONTRACT PASS: {date} FULL={counts.get("FULL", 0)} BRIEF={counts.get("BRIEF", 0)} REJECT={counts.get("REJECT", 0)}{state}')


if __name__ == '__main__':
    main()
