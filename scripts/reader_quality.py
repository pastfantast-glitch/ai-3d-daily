"""One read-only prose gate shared by review, Collector and handoff."""
from check_editorial_quality import editorial_errors, load_editorial_config
from enrich_full_analysis_v3 import brief_issues, brief_policy_for_date, full_issues, DEPTH


def reader_errors(items, date):
    cfg = load_editorial_config()
    errors = editorial_errors({'items': items, 'metadata': {'editorial': {
        'contract': cfg.get('contract'), 'style_reference': cfg.get('style_reference'),
        'factual_fallback_allowed': True}}}, date)
    for item in items:
        level = item.get('analysis_level', 'BRIEF')
        if level == 'FULL':
            issues = full_issues(item, DEPTH.get('full') or {})
        elif level == 'BRIEF':
            probe = {**item, 'brief_reason': item.get('brief_reason') or 'single-source-verified-production-tip'}
            issues = brief_issues(probe, brief_policy_for_date(date),
                require_three_angles=date >= DEPTH['brief_reading_contract_effective_date'])
        else:
            issues = ['invalid-analysis-level']
        errors.extend(f"{item.get('id')}: {error}" for error in issues)
    return errors
