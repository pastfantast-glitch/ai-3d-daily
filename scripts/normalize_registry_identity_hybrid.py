#!/usr/bin/env python3
from pathlib import Path
import json
import sys

import normalize_registry_identity as core
from discovery_hybrid import (
    candidate_decision_ledger_applies,
    candidate_decision_ledger_path,
    load_hybrid_config,
    low_volume_release_allowed,
)

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_GATE = core.daily_gate


def hybrid_gate(cfg, items):
    gate = ORIGINAL_GATE(cfg, items)
    target = sys.argv[1] if len(sys.argv) > 1 else ''
    data_path = ROOT / 'data' / 'daily' / f'{target}.json'
    if not data_path.exists():
        return gate
    data = json.loads(data_path.read_text('utf-8'))
    data['items'] = list(items)

    # Registry normalization can deterministically remove historical duplicates or
    # rewrite a surviving item to its historical stable id. The low-volume gate
    # validates the candidate decision ledger, so synchronize that private ledger
    # against the normalized survivor set before evaluating LOW_VOLUME_COMPLETE.
    # This prevents a stale pre-normalization ledger from forcing an unnecessary
    # refill-only pass.
    sync_candidate_decision_ledger(target, data['items'])

    category_ids = [c['id'] for c in cfg.get('categories') or []]
    if gate['have'] < gate['min'] and low_volume_release_allowed(data, category_ids):
        hybrid = load_hybrid_config()
        fallback = int(hybrid['low_volume_release']['fallback_floor'])
        normal_min = gate['min']
        gate['normal_min'] = normal_min
        gate['min'] = fallback
        gate['release_ready'] = True
        gate['release_mode'] = str(hybrid['low_volume_release'].get('release_mode', 'LOW_VOLUME_COMPLETE'))
        gate['low_volume_authorized'] = True
    else:
        gate['release_mode'] = 'NORMAL' if gate['release_ready'] else 'BLOCKED'
        gate['low_volume_authorized'] = False
    return gate


def sync_candidate_decision_ledger(target, canonical_items=None):
    """Keep the private candidate ledger aligned with Registry normalization.

    The Collector records its terminal decision before the deterministic Published
    Intelligence Registry pass. The Registry is allowed to drop an item as a
    historical duplicate or rewrite an UPDATE to the historical stable id. From
    2026-09-16 onward the ledger is a release invariant, so those deterministic
    Registry outcomes must be reflected in the ledger before check_release_input.

    This function never creates missing ledger rows and never invents discovery
    evidence. It only converts an already-published Collector row to `duplicate`
    when Registry removed it, or rewrites its canonical_id when the surviving item
    with the same canonical source received a historical stable id.
    """
    if not candidate_decision_ledger_applies(target):
        return

    data_path = ROOT / 'data' / 'daily' / f'{target}.json'
    ledger_path = candidate_decision_ledger_path(target)
    if not ledger_path.exists():
        return

    if canonical_items is None:
        if not data_path.exists():
            return
        data = json.loads(data_path.read_text('utf-8'))
        canonical_items = data.get('items') or []

    ledger = json.loads(ledger_path.read_text('utf-8'))
    if not isinstance(ledger, dict) or not isinstance(ledger.get('items'), list):
        return

    canonical_items = [x for x in canonical_items if isinstance(x, dict)]
    canonical_ids = {
        str(x.get('id', '')).strip()
        for x in canonical_items
        if str(x.get('id', '')).strip()
    }
    source_to_ids = {}
    for item in canonical_items:
        rid = str(item.get('id', '')).strip()
        src = core.norm_url(item.get('source_url'))
        if rid and src:
            source_to_ids.setdefault(src, []).append(rid)

    duplicate_count = 0
    rewrite_count = 0
    for row in ledger['items']:
        if not isinstance(row, dict) or str(row.get('decision', '')).strip() != 'published':
            continue
        canonical_id = str(row.get('canonical_id', '')).strip()
        if canonical_id in canonical_ids:
            continue

        src = core.norm_url(row.get('source_url'))
        matches = source_to_ids.get(src, []) if src else []
        if len(matches) == 1:
            row['canonical_id'] = matches[0]
            rewrite_count += 1
            continue

        row['decision'] = 'duplicate'
        row.pop('canonical_id', None)
        row['reason_code'] = 'registry-normalized-duplicate'
        duplicate_count += 1

    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(
        'CANDIDATE LEDGER REGISTRY SYNC: '
        f'duplicate={duplicate_count} stable_id_rewrite={rewrite_count} '
        f'path={ledger_path.relative_to(ROOT)}'
    )


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else ''
    exit_code = 0
    try:
        core.main()
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 1

    # Synchronize once more against the final canonical file in case Registry also
    # performed a stable-id rewrite while writing the normalized dataset.
    if exit_code in (0, 2):
        sync_candidate_decision_ledger(target)

    if exit_code:
        raise SystemExit(exit_code)


core.daily_gate = hybrid_gate
main()
