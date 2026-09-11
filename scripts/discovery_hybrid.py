#!/usr/bin/env python3
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'discovery-hybrid.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def _valid_date(value):
    return bool(DATE_RE.fullmatch(str(value or '').strip()))


def load_hybrid_config():
    cfg = json.loads(CONFIG.read_text('utf-8'))
    if int(cfg.get('version', 0)) < 1:
        raise ValueError('hybrid discovery config version must be >=1')
    effective = str(cfg.get('effective_date', '')).strip()
    if not _valid_date(effective):
        raise ValueError('hybrid discovery effective_date must be YYYY-MM-DD')

    low = cfg.get('low_volume_release') or {}
    normal = int(low.get('normal_floor', 0) or 0)
    fallback = int(low.get('fallback_floor', 0) or 0)
    maximum = int(low.get('maximum', 0) or 0)
    if not (0 < fallback < normal <= maximum):
        raise ValueError('hybrid low-volume floors must satisfy 0 < fallback < normal <= maximum')

    learning = cfg.get('preference_learning') or {}
    if learning:
        if not _valid_date(learning.get('effective_date')):
            raise ValueError('hybrid preference_learning.effective_date must be YYYY-MM-DD')
        samples = learning.get('positive_samples') or []
        if not isinstance(samples, list) or not samples:
            raise ValueError('hybrid preference_learning.positive_samples must be a non-empty list')
        seen_ids, seen_urls = set(), set()
        for sample in samples:
            if not isinstance(sample, dict):
                raise ValueError('hybrid positive sample entries must be objects')
            sid = str(sample.get('id', '')).strip()
            url = str(sample.get('url', '')).strip()
            affinity = sample.get('affinity') or []
            if not sid or sid in seen_ids:
                raise ValueError('hybrid positive sample ids must be unique and non-empty')
            if not url.startswith('https://') or url in seen_urls:
                raise ValueError('hybrid positive sample urls must be unique https URLs')
            if not isinstance(affinity, list) or not affinity or not all(str(x).strip() for x in affinity):
                raise ValueError(f'hybrid positive sample {sid} requires non-empty affinity[]')
            seen_ids.add(sid)
            seen_urls.add(url)
        use_for = learning.get('use_for') or []
        if not isinstance(use_for, list) or not {'discovery-query-expansion', 'user-interest-fit-ranking'} <= set(use_for):
            raise ValueError('hybrid preference_learning.use_for must include discovery-query-expansion and user-interest-fit-ranking')
        if not str(learning.get('ranking_policy', '')).strip():
            raise ValueError('hybrid preference_learning.ranking_policy is required')

    sources = cfg.get('priority_sources') or []
    seen_source_ids = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError('hybrid priority_sources entries must be objects')
        sid = str(source.get('id', '')).strip()
        domain = str(source.get('domain', '')).strip().lower()
        if not sid or sid in seen_source_ids:
            raise ValueError('hybrid priority source ids must be unique and non-empty')
        if not domain or '.' not in domain:
            raise ValueError(f'hybrid priority source {sid} requires a domain')
        if source.get('required_check') not in (True, False):
            raise ValueError(f'hybrid priority source {sid}.required_check must be boolean')
        if not str(source.get('mode', '')).strip() or not str(source.get('admission', '')).strip():
            raise ValueError(f'hybrid priority source {sid} requires mode and admission')
        seen_source_ids.add(sid)

    coverage = cfg.get('coverage_audit') or {}
    if coverage.get('require_priority_source_checks') is True:
        if not sources:
            raise ValueError('hybrid priority-source coverage requires priority_sources[]')
        if not _valid_date(coverage.get('priority_source_coverage_effective_date')):
            raise ValueError('hybrid priority_source_coverage_effective_date must be YYYY-MM-DD')

    return cfg


def hybrid_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    value = str(data_or_date.get('date', '') if isinstance(data_or_date, dict) else data_or_date or '').strip()
    return bool(_valid_date(value) and value >= str(cfg['effective_date']))


def preference_learning_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    learning = cfg.get('preference_learning') or {}
    effective = str(learning.get('effective_date', '')).strip()
    value = str(data_or_date.get('date', '') if isinstance(data_or_date, dict) else data_or_date or '').strip()
    return bool(_valid_date(value) and _valid_date(effective) and value >= effective)


def priority_source_coverage_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    coverage = cfg.get('coverage_audit') or {}
    effective = str(coverage.get('priority_source_coverage_effective_date', '')).strip()
    value = str(data_or_date.get('date', '') if isinstance(data_or_date, dict) else data_or_date or '').strip()
    return bool(
        coverage.get('require_priority_source_checks') is True
        and _valid_date(value)
        and _valid_date(effective)
        and value >= effective
    )


def positive_samples(cfg=None):
    cfg = cfg or load_hybrid_config()
    return list((cfg.get('preference_learning') or {}).get('positive_samples') or [])


def priority_sources(cfg=None):
    cfg = cfg or load_hybrid_config()
    return list(cfg.get('priority_sources') or [])


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

    if priority_source_coverage_applies(data, cfg):
        source_audit = audit.get('priority_sources') or {}
        for source in priority_sources(cfg):
            if source.get('required_check') is not True:
                continue
            sid = str(source.get('id', '')).strip()
            rec = source_audit.get(sid)
            if not isinstance(rec, dict):
                errors.append(f'discovery coverage: missing priority source check {sid}')
                continue
            if str(rec.get('status', '')).strip() != 'checked':
                errors.append(f'discovery coverage: priority source {sid} must have status=checked')
            found = rec.get('candidates_found')
            if isinstance(found, bool) or not isinstance(found, int) or found < 0:
                errors.append(f'discovery coverage: priority source {sid} candidates_found must be integer >=0')

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
