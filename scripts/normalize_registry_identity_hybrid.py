#!/usr/bin/env python3
from pathlib import Path
import json
import sys

import normalize_registry_identity as core
from discovery_hybrid import load_hybrid_config, low_volume_release_allowed

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


core.daily_gate = hybrid_gate
core.main()
