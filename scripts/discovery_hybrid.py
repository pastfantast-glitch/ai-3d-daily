#!/usr/bin/env python3
from pathlib import Path
import datetime as dt
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'discovery-hybrid.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def _valid_date(value):
    return bool(DATE_RE.fullmatch(str(value or '').strip()))


def _date_value(data_or_date):
    if isinstance(data_or_date, dict):
        return str(data_or_date.get('date', '')).strip()
    return str(data_or_date or '').strip()


def _effective_feature_applies(data_or_date, feature, enabled_key='enabled'):
    value = _date_value(data_or_date)
    effective = str((feature or {}).get('effective_date', '')).strip()
    enabled = (feature or {}).get(enabled_key) is True
    return bool(enabled and _valid_date(value) and _valid_date(effective) and value >= effective)


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
        if not str(learning.get('sample_source_policy', '')).strip():
            raise ValueError('hybrid preference_learning.sample_source_policy is required')

    neutrality = cfg.get('source_neutrality') or {}
    if neutrality.get('enabled') is not True:
        raise ValueError('hybrid source_neutrality.enabled must be true')
    if neutrality.get('positive_sample_domains_are_provenance_only') is not True:
        raise ValueError('hybrid source_neutrality.positive_sample_domains_are_provenance_only must be true')
    for key in (
        'domain_weight_from_positive_samples',
        'required_site_checks_from_positive_samples',
        'site_specific_refill_from_positive_samples',
        'source_domain_may_increase_user_interest_fit',
    ):
        if neutrality.get(key) is not False:
            raise ValueError(f'hybrid source_neutrality.{key} must be false')
    if not str(neutrality.get('discovery_policy', '')).strip() or not str(neutrality.get('ranking_policy', '')).strip():
        raise ValueError('hybrid source_neutrality requires discovery_policy and ranking_policy')

    source_pool = cfg.get('discovery_source_pool') or {}
    if source_pool:
        if not str(source_pool.get('policy', '')).strip():
            raise ValueError('hybrid discovery_source_pool.policy is required')
        source_items = source_pool.get('sources') or []
        if not isinstance(source_items, list):
            raise ValueError('hybrid discovery_source_pool.sources must be a list')
        seen_source_ids, seen_domains = set(), set()
        for source in source_items:
            if not isinstance(source, dict):
                raise ValueError('hybrid discovery source entries must be objects')
            sid = str(source.get('id', '')).strip()
            domain = str(source.get('domain', '')).strip().lower()
            base_url = str(source.get('base_url', '')).strip()
            if not sid or sid in seen_source_ids:
                raise ValueError('hybrid discovery source ids must be unique and non-empty')
            if not domain or domain in seen_domains:
                raise ValueError('hybrid discovery source domains must be unique and non-empty')
            if not base_url.startswith('https://'):
                raise ValueError(f'hybrid discovery source {sid} requires https base_url')
            if source.get('enabled') is not True:
                raise ValueError(f'hybrid discovery source {sid} must set enabled=true')
            if str(source.get('discovery_mode', '')).strip() != 'active-candidate-source':
                raise ValueError(f'hybrid discovery source {sid} must use discovery_mode=active-candidate-source')
            if float(source.get('ranking_bonus', 0) or 0) != 0:
                raise ValueError(f'hybrid discovery source {sid} must keep ranking_bonus=0')
            if source.get('required_daily_check') is not False:
                raise ValueError(f'hybrid discovery source {sid} must keep required_daily_check=false')
            seen_source_ids.add(sid)
            seen_domains.add(domain)

    probe = cfg.get('registered_source_coverage_probe') or {}
    if probe:
        if not _valid_date(probe.get('effective_date')):
            raise ValueError('hybrid registered_source_coverage_probe.effective_date must be YYYY-MM-DD')
        if probe.get('enabled') is not True:
            raise ValueError('hybrid registered_source_coverage_probe.enabled must be true')
        if str(probe.get('scope', '')).strip() != 'rotating-enabled-discovery-source-pool':
            raise ValueError('hybrid registered source probe scope must be rotating-enabled-discovery-source-pool')
        if probe.get('require_attempt_record_for_every_enabled_source') is not False:
            raise ValueError('hybrid rotating source probe must not require every source to be attempted daily')
        if probe.get('require_audit_record_for_every_enabled_source') is not True:
            raise ValueError('hybrid rotating source probe must keep an audit record for every enabled source')
        if probe.get('require_attempt_record_for_selected_sources') is not True:
            raise ValueError('hybrid rotating source probe must require attempts for the selected daily subset')
        core = [str(x).strip() for x in (probe.get('core_source_ids') or []) if str(x).strip()]
        source_ids = [str(x.get('id')).strip() for x in source_items]
        if not core or len(core) != len(set(core)) or not set(core) <= set(source_ids):
            raise ValueError('hybrid rotating source probe core_source_ids must be unique registered source ids')
        rotating = int(probe.get('rotating_sources_per_day', 0) or 0)
        window = int(probe.get('rolling_window_days', 0) or 0)
        noncore = max(0, len(source_ids) - len(core))
        if rotating <= 0 or window <= 0 or rotating * window < noncore:
            raise ValueError('hybrid rotating source probe budget cannot cover all non-core sources inside rolling_window_days')
        if str(probe.get('selection_policy', '')).strip() != 'deterministic-date-rotation':
            raise ValueError('hybrid rotating source probe must use deterministic-date-rotation')
        if 'not-scheduled' not in set(probe.get('allowed_statuses') or []) or 'rolling-window' not in set(probe.get('allowed_methods') or []):
            raise ValueError('hybrid rotating source probe must declare truthful not-scheduled/rolling-window audit values')
        if probe.get('require_candidate_ids_when_found') is not True:
            raise ValueError('hybrid registered source probe must require candidate ids when candidates are found')
        if probe.get('candidate_only') is not True:
            raise ValueError('hybrid registered source probe must remain candidate-only')
        if float(probe.get('ranking_bonus', 0) or 0) != 0:
            raise ValueError('hybrid registered source probe must keep ranking_bonus=0')
        if probe.get('quota') is not False or probe.get('admission_bypass') is not False:
            raise ValueError('hybrid registered source probe must not create quota or admission bypass')
        methods = probe.get('allowed_methods') or []
        statuses = probe.get('allowed_statuses') or []
        if not isinstance(methods, list) or not methods or not all(str(x).strip() for x in methods):
            raise ValueError('hybrid registered source probe requires allowed_methods[]')
        if not isinstance(statuses, list) or not statuses or not all(str(x).strip() for x in statuses):
            raise ValueError('hybrid registered source probe requires allowed_statuses[]')

    ledger = cfg.get('candidate_decision_ledger') or {}
    if ledger:
        if not _valid_date(ledger.get('effective_date')):
            raise ValueError('hybrid candidate_decision_ledger.effective_date must be YYYY-MM-DD')
        if ledger.get('required') is not True:
            raise ValueError('hybrid candidate_decision_ledger.required must be true')
        if int(ledger.get('schema_version', 0) or 0) < 1:
            raise ValueError('hybrid candidate_decision_ledger.schema_version must be >=1')
        template = str(ledger.get('path_template', '')).strip()
        if '{date}' not in template or not template.startswith('data/candidates/'):
            raise ValueError('hybrid candidate decision ledger path_template must live under data/candidates and contain {date}')
        decisions = ledger.get('terminal_decisions') or []
        if not isinstance(decisions, list) or not decisions or len(decisions) != len(set(decisions)):
            raise ValueError('hybrid candidate decision ledger terminal_decisions must be a non-empty unique list')
        if 'published' not in decisions:
            raise ValueError('hybrid candidate decision ledger terminal_decisions must include published')
        if ledger.get('require_published_canonical_coverage') is not True:
            raise ValueError('hybrid candidate decision ledger must cover all published canonical items')
        if ledger.get('require_registered_probe_candidate_coverage') is not True:
            raise ValueError('hybrid candidate decision ledger must cover registered-source probe candidates')
        if ledger.get('public_surface') is not False:
            raise ValueError('hybrid candidate decision ledger must remain private/non-public')

    sources = cfg.get('priority_sources') or []
    if sources:
        raise ValueError('hybrid preference-derived priority_sources are forbidden; preference examples must remain source-neutral')

    coverage = cfg.get('coverage_audit') or {}
    if coverage.get('require_priority_source_checks') is True:
        raise ValueError('hybrid Coverage Audit must not require preference-derived priority source checks')
    if probe and coverage.get('require_registered_source_probe_when_effective') is not True:
        raise ValueError('hybrid Coverage Audit must require registered source probe when effective')
    if ledger and coverage.get('require_candidate_decision_ledger_when_effective') is not True:
        raise ValueError('hybrid Coverage Audit must require candidate decision ledger when effective')

    refill = cfg.get('targeted_refill') or {}
    if refill.get('use_priority_sources') is not False:
        raise ValueError('hybrid targeted_refill.use_priority_sources must be false')
    if refill.get('use_source_neutrality') is not True:
        raise ValueError('hybrid targeted_refill.use_source_neutrality must be true')
    if source_pool and refill.get('use_discovery_source_pool') is not True:
        raise ValueError('hybrid targeted_refill.use_discovery_source_pool must be true when discovery sources are configured')
    if probe and refill.get('use_registered_source_coverage_probe') is not True:
        raise ValueError('hybrid targeted_refill must consume registered source coverage probe results')

    return cfg


def hybrid_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    value = _date_value(data_or_date)
    return bool(_valid_date(value) and value >= str(cfg['effective_date']))


def preference_learning_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    learning = cfg.get('preference_learning') or {}
    effective = str(learning.get('effective_date', '')).strip()
    value = _date_value(data_or_date)
    return bool(_valid_date(value) and _valid_date(effective) and value >= effective)


def registered_source_probe_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    return _effective_feature_applies(data_or_date, cfg.get('registered_source_coverage_probe') or {})


def candidate_decision_ledger_applies(data_or_date, cfg=None):
    cfg = cfg or load_hybrid_config()
    ledger = cfg.get('candidate_decision_ledger') or {}
    value = _date_value(data_or_date)
    effective = str(ledger.get('effective_date', '')).strip()
    return bool(ledger.get('required') is True and _valid_date(value) and _valid_date(effective) and value >= effective)


def priority_source_coverage_applies(data_or_date, cfg=None):
    return False


def positive_samples(cfg=None):
    cfg = cfg or load_hybrid_config()
    return list((cfg.get('preference_learning') or {}).get('positive_samples') or [])


def discovery_sources(cfg=None):
    cfg = cfg or load_hybrid_config()
    return [x for x in ((cfg.get('discovery_source_pool') or {}).get('sources') or []) if x.get('enabled') is True]


def priority_sources(cfg=None):
    return []


def registered_source_probe_plan(data_or_date, cfg=None):
    """Return the deterministic daily probe set without creating source preference.

    Core sources are checked every day. Non-core registered sources rotate by date
    in fixed-size groups. This bounds Collector work while ensuring the configured
    rolling window covers every enabled source. Selection affects recall work only;
    it contributes no ranking/admission weight.
    """
    cfg = cfg or load_hybrid_config()
    value = _date_value(data_or_date)
    if not _valid_date(value):
        raise ValueError('registered source probe plan requires YYYY-MM-DD')
    probe = cfg.get('registered_source_coverage_probe') or {}
    sources = [str(x.get('id')).strip() for x in discovery_sources(cfg)]
    core = [str(x).strip() for x in (probe.get('core_source_ids') or []) if str(x).strip()]
    noncore = [sid for sid in sources if sid not in set(core)]
    per_day = int(probe.get('rotating_sources_per_day', 0) or 0)
    groups = max(1, (len(noncore) + per_day - 1) // per_day) if per_day else 1
    group = dt.date.fromisoformat(value).toordinal() % groups
    start = group * per_day
    selected = set(core + noncore[start:start + per_day])
    return {
        'selected': [sid for sid in sources if sid in selected],
        'not_scheduled': [sid for sid in sources if sid not in selected],
        'group': group,
        'groups': groups,
    }


def candidate_decision_ledger_path(date, cfg=None):
    cfg = cfg or load_hybrid_config()
    template = str((cfg.get('candidate_decision_ledger') or {}).get('path_template', '')).strip()
    return ROOT / template.format(date=str(date))


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


def registered_source_probe_errors(data, cfg=None):
    cfg = cfg or load_hybrid_config()
    if not registered_source_probe_applies(data, cfg):
        return []
    probe_cfg = cfg.get('registered_source_coverage_probe') or {}
    audit = (data.get('metadata') or {}).get('discovery_coverage') or {}
    probe = audit.get('registered_source_probe') or {}
    errors = []
    if probe.get('performed') is not True:
        errors.append('discovery coverage: registered_source_probe.performed must be true')
    records = probe.get('sources') or {}
    if not isinstance(records, dict):
        return errors + ['discovery coverage: registered_source_probe.sources must be an object']

    ordered = [str(x.get('id')) for x in discovery_sources(cfg)]
    expected = set(ordered)
    plan = registered_source_probe_plan(data, cfg)
    selected = set(plan['selected'])
    unknown = set(records) - expected
    if unknown:
        errors.append(f'discovery coverage: registered_source_probe has unknown sources {sorted(unknown)}')
    allowed_statuses = set(probe_cfg.get('allowed_statuses') or [])
    allowed_methods = set(probe_cfg.get('allowed_methods') or [])
    for sid in ordered:
        rec = records.get(sid)
        if not isinstance(rec, dict):
            errors.append(f'discovery coverage: registered source {sid} requires a probe attempt record')
            continue
        status = str(rec.get('status', '')).strip()
        method = str(rec.get('method', '')).strip()
        if status not in allowed_statuses:
            errors.append(f'discovery coverage: registered source {sid} has invalid status={status!r}')
        if method not in allowed_methods:
            errors.append(f'discovery coverage: registered source {sid} has invalid method={method!r}')
        if sid in selected and status == 'not-scheduled':
            errors.append(f'discovery coverage: registered source {sid} is selected today and must be attempted')
        if status == 'not-scheduled' and method != 'rolling-window':
            errors.append(f'discovery coverage: registered source {sid} not-scheduled must use method=rolling-window')
        found = rec.get('candidates_found')
        if isinstance(found, bool) or not isinstance(found, int) or found < 0:
            errors.append(f'discovery coverage: registered source {sid} candidates_found must be integer >=0')
            found = 0
        candidate_ids = rec.get('candidate_ids') or []
        if not isinstance(candidate_ids, list) or not all(str(x).strip() for x in candidate_ids):
            errors.append(f'discovery coverage: registered source {sid} candidate_ids must be a string list')
            candidate_ids = []
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append(f'discovery coverage: registered source {sid} candidate_ids must be unique')
        if probe_cfg.get('require_candidate_ids_when_found') is True and isinstance(found, int) and found != len(candidate_ids):
            errors.append(f'discovery coverage: registered source {sid} candidates_found must equal candidate_ids count')
        if status != 'checked' and candidate_ids:
            errors.append(f'discovery coverage: registered source {sid} non-checked status cannot report candidates')
        if status == 'not-scheduled' and (found != 0 or candidate_ids):
            errors.append(f'discovery coverage: registered source {sid} not-scheduled cannot report discovered candidates')
        if status in {'unavailable', 'blocked', 'unsupported', 'not-scheduled'} and not str(rec.get('reason', '')).strip():
            errors.append(f'discovery coverage: registered source {sid} status={status} requires reason')
    return errors


def candidate_decision_ledger_errors(data, cfg=None, ledger_data=None):
    cfg = cfg or load_hybrid_config()
    if not candidate_decision_ledger_applies(data, cfg):
        return []
    ledger_cfg = cfg.get('candidate_decision_ledger') or {}
    date = _date_value(data)
    errors = []
    if ledger_data is None:
        path = candidate_decision_ledger_path(date, cfg)
        if not path.exists():
            return [f'candidate decision ledger missing: {path.relative_to(ROOT)}']
        try:
            ledger_data = json.loads(path.read_text('utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            return [f'candidate decision ledger unreadable: {exc}']
    if not isinstance(ledger_data, dict):
        return ['candidate decision ledger must be a JSON object']
    if int(ledger_data.get('schema_version', 0) or 0) != int(ledger_cfg.get('schema_version', 1)):
        errors.append('candidate decision ledger schema_version mismatch')
    if str(ledger_data.get('date', '')).strip() != date:
        errors.append(f'candidate decision ledger date mismatch: {ledger_data.get("date")} != {date}')
    items = ledger_data.get('items') or []
    if not isinstance(items, list):
        return errors + ['candidate decision ledger items must be a list']

    terminal = set(ledger_cfg.get('terminal_decisions') or [])
    seen = set()
    by_id = {}
    canonical_ids = {str(x.get('id', '')).strip() for x in data.get('items') or [] if str(x.get('id', '')).strip()}
    published_canonical = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f'candidate decision ledger item {index} must be an object')
            continue
        cid = str(item.get('candidate_id', '')).strip()
        source_url = str(item.get('source_url', '')).strip()
        decision = str(item.get('decision', '')).strip()
        channels = item.get('discovery_channels') or []
        if not cid:
            errors.append(f'candidate decision ledger item {index} requires candidate_id')
            continue
        if cid in seen:
            errors.append(f'candidate decision ledger duplicate candidate_id: {cid}')
        seen.add(cid)
        by_id[cid] = item
        if not source_url.startswith('https://'):
            errors.append(f'candidate decision ledger {cid} requires https source_url')
        if decision not in terminal:
            errors.append(f'candidate decision ledger {cid} has invalid decision={decision!r}')
        if not isinstance(channels, list) or not channels or not all(str(x).strip() for x in channels):
            errors.append(f'candidate decision ledger {cid} requires discovery_channels[]')
        if decision != 'published' and ledger_cfg.get('require_reason_for_non_published') is True and not str(item.get('reason_code', '')).strip():
            errors.append(f'candidate decision ledger {cid} decision={decision} requires reason_code')
        if decision == 'published':
            canonical_id = str(item.get('canonical_id', '')).strip()
            if not canonical_id:
                errors.append(f'candidate decision ledger {cid} published decision requires canonical_id')
            elif canonical_id not in canonical_ids:
                errors.append(f'candidate decision ledger {cid} references unknown canonical_id={canonical_id}')
            else:
                published_canonical.add(canonical_id)

    if ledger_cfg.get('require_published_canonical_coverage') is True:
        missing = canonical_ids - published_canonical
        if missing:
            errors.append(f'candidate decision ledger missing published canonical ids: {sorted(missing)}')

    if ledger_cfg.get('require_registered_probe_candidate_coverage') is True:
        audit = (data.get('metadata') or {}).get('discovery_coverage') or {}
        probe = audit.get('registered_source_probe') or {}
        probe_ids = set()
        for rec in (probe.get('sources') or {}).values():
            if isinstance(rec, dict):
                probe_ids.update(str(x).strip() for x in (rec.get('candidate_ids') or []) if str(x).strip())
        missing_probe = probe_ids - set(by_id)
        if missing_probe:
            errors.append(f'candidate decision ledger missing registered-source probe candidate ids: {sorted(missing_probe)}')
    return errors


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

    if coverage_cfg.get('require_registered_source_probe_when_effective') is True:
        errors.extend(registered_source_probe_errors(data, cfg))
    if coverage_cfg.get('require_candidate_decision_ledger_when_effective') is True:
        errors.extend(candidate_decision_ledger_errors(data, cfg))
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
