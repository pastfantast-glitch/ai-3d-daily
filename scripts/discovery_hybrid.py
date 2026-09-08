#!/usr/bin/env python3
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'discovery-hybrid.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def load_hybrid_config():
    cfg = json.loads(CONFIG.read_text('utf-8'))
    if int(cfg.get('version', 0)) < 1:
        raise ValueError('hybrid discovery config version must be >=1')
    effective = str(cfg.get('effective_date', '')).strip()
    if not DATE_RE.fullmatch(effective):
        raise ValueError('hybrid discovery effective_date must be YYYY-MM-DD')
    low = cfg.get('low_volume_release') or {}
    normal = int(low.get('normal_floor', 0) or 0)
    fallback = int(low.get('fallback_floor', 0) or 0)
    maximum = int(low.get('maximum', 0) or 0)
    if not (0 < fallback < normal <= maximum):
        raise ValueError('hybrid low-volume floors must satisfy 0 < fallback < normal <= maximum')
    return cfg


def hybrid_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    value = str(data_or_date.get('date', '') if isinstance(data_or_date, dict) else data_or_date or '').strip()
    return bool(DATE_RE.fullmatch(value) and value >= str(cfg['effective_date']))


def _category_count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        raw = value.get('candidates_considered', value.get('count'))
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None
        return raw
    return None


def coverage_audit_errors(data, category_ids, cfg=None):
    cfg = cfg or load_hybrid_config()
    if not hybrid_applies(data, cfg):
        return []
    meta = data.get('metadata') or {}
    audit = meta.get('discovery_coverage') or {}
    errors = []
    coverage_cfg = cfg.get('coverage_audit') or {}
    required_windows = coverage_cfg.get('required_windows') or []
    required_categories = coverage_cfg.get('required_categories') or list(category_ids)
    exhaustion_status = str(coverage_cfg.get('exhaustion_status', 'exhausted'))

    if audit.get('fill_ladder_exhausted') is not True:
        errors.append('discovery coverage: fill_ladder_exhausted must be true')
    if audit.get('backlog_checked') is not True:
        errors.append('discovery coverage: backlog_checked must be true')
    if audit.get('targeted_refill_performed') is not True:
        errors.append('discovery coverage: targeted_refill_performed must be true')
    if audit.get('quality_first_confirmed') is not True:
        errors.append('discovery coverage: quality_first_confirmed must be true')
    if int(audit.get('backlog_remaining_eligible', -1)) != 0:
        errors.append('discovery coverage: backlog_remaining_eligible must be 0')

    windows = audit.get('windows') or {}
    for window in required_windows:
        rec = windows.get(window)
        if not isinstance(rec, dict):
            errors.append(f'discovery coverage: missing window {window}')
            continue
        if str(rec.get('status', '')).strip() != exhaustion_status:
            errors.append(f'discovery coverage: window {window} must have status={exhaustion_status}')
        found = rec.get('candidates_found')
        if isinstance(found, bool) or not isinstance(found, int) or found < 0:
            errors.append(f'discovery coverage: window {window} candidates_found must be integer >=0')

    categories = audit.get('category_candidates') or {}
    for cid in required_categories:
        count = _category_count(categories.get(cid))
        if count is None or count < 0:
            errors.append(f'discovery coverage: category {cid} requires candidates_considered >=0')

    unknown = set(categories) - set(required_categories)
    if unknown:
        errors.append(f'discovery coverage: unknown category keys {sorted(unknown)}')
    return errors


def low_volume_release_allowed(data, category_ids, cfg=None):
    cfg = cfg or load_hybrid_config()
    if not hybrid_applies(data, cfg):
        return False
    low = cfg.get('low_volume_release') or {}
    if low.get('enabled') is not True:
        return False
    count = len(data.get('items') or [])
    fallback = int(low['fallback_floor'])
    normal = int(low['normal_floor'])
    maximum = int(low['maximum'])
    if not (fallback <= count < normal <= maximum):
        return False
    return not coverage_audit_errors(data, category_ids, cfg)


def release_mode(data, category_ids, normal_floor, maximum, cfg=None):
    count = len(data.get('items') or [])
    if normal_floor <= count <= maximum:
        return 'NORMAL'
    if low_volume_release_allowed(data, category_ids, cfg):
        return str((cfg or load_hybrid_config())['low_volume_release'].get('release_mode', 'LOW_VOLUME_COMPLETE'))
    return 'BLOCKED'
