#!/usr/bin/env python3
"""Regression guard for BRIEF reading depth and first-heading presentation.

This guard also verifies policy parity across the configured BRIEF reading date
boundary so canonical enrichment and the public Pages verifier cannot drift apart.
"""
from datetime import date as date_value, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

from enrich_full_analysis_v3 import DEPTH, brief_issues, brief_policy_for_date
from build_intelligence import analysis_html
from verify_pages_publish import analysis_policy

ROOT = Path(__file__).resolve().parents[1]


def block(label, text):
    return {'label': label, 'text': text}


def configured_boundary_dates():
    effective_text = str(DEPTH.get('brief_reading_contract_effective_date', '')).strip()
    tiered_text = str(DEPTH.get('tiered_effective_date', '')).strip()
    try:
        effective = date_value.fromisoformat(effective_text)
        tiered = date_value.fromisoformat(tiered_text)
    except ValueError as exc:
        raise SystemExit(f'ANALYSIS READING CONTRACT FAIL: invalid configured effective date: {exc}')
    legacy = effective - timedelta(days=1)
    if legacy < tiered:
        raise SystemExit(
            'ANALYSIS READING CONTRACT FAIL: brief_reading_contract_effective_date must leave at least one tiered legacy-BRIEF day'
        )
    return legacy.isoformat(), effective.isoformat()


def assert_heading_first(record):
    soup = BeautifulSoup('<html><body></body></html>', 'html.parser')
    details = analysis_html(soup, record)
    body = details.select_one('.detail-body')
    first = next((node for node in body.children if getattr(node, 'name', None)), None)
    if not first or first.name != 'h4':
        raise SystemExit(
            f'ANALYSIS READING CONTRACT FAIL: {record["analysis_level"]} first analysis element must be h4, got {getattr(first, "name", None)!r}'
        )
    expected = record['full_analysis'][0]['label']
    if first.get_text(strip=True) != expected:
        raise SystemExit(
            f'ANALYSIS READING CONTRACT FAIL: first heading {first.get_text(strip=True)!r} != canonical label {expected!r}'
        )
    note = body.select_one('.analysis-level-note')
    if record['analysis_level'] == 'BRIEF':
        if note is None:
            raise SystemExit('ANALYSIS READING CONTRACT FAIL: BRIEF evidence note missing')
        if body.find_all(recursive=False)[-1] is not note:
            raise SystemExit('ANALYSIS READING CONTRACT FAIL: BRIEF evidence note must follow analysis blocks, not precede the first heading')


def assert_runtime_heading_first():
    source = (ROOT / 'canonical-client.js').read_text('utf-8')
    loop = source.find('(record.full_analysis||[]).forEach')
    note = source.find("if(level==='BRIEF')", loop)
    if loop < 0 or note < 0 or note < loop:
        raise SystemExit('ANALYSIS READING CONTRACT FAIL: browser renderer must append canonical analysis blocks before BRIEF metadata')


def assert_pages_policy(date, record, expected_rule):
    level, minimum, maximum, policy_error = analysis_policy(date, record, DEPTH, 3)
    if policy_error:
        raise SystemExit(f'ANALYSIS READING CONTRACT FAIL: Pages verifier policy error for {date}: {policy_error}')
    if level != 'BRIEF':
        raise SystemExit(f'ANALYSIS READING CONTRACT FAIL: Pages verifier level for {date} is {level}, expected BRIEF')
    expected_min = int(expected_rule.get('min_blocks', 0) or 0)
    expected_max = int(expected_rule.get('max_blocks', 0) or 0)
    if (minimum, maximum) != (expected_min, expected_max):
        raise SystemExit(
            'ANALYSIS READING CONTRACT FAIL: Pages verifier drift at '
            f'{date}: got BRIEF blocks={minimum}-{maximum}, expected={expected_min}-{expected_max}'
        )


def main():
    legacy_date, effective_date = configured_boundary_dates()

    two_block = {
        'id': 'fixture-brief-two-block',
        'summary': '測試摘要',
        'analysis_level': 'BRIEF',
        'brief_reason': 'short-official-announcement',
        'homepage_tier': 'next10',
        'full_analysis': [
            block('流程變化', '這是一段來源可支持的流程變化說明，清楚交代工具輸入輸出與工作流影響，不補寫來源沒有提供的技術細節。'),
            block('導入判斷', '這是一段來源可支持的導入判斷，明確指出尚缺效能 benchmark 與相容性資料，需要由團隊自行驗證。'),
        ],
    }

    legacy_issues = brief_issues(two_block, brief_policy_for_date(legacy_date), False)
    if legacy_issues:
        raise SystemExit(
            f'ANALYSIS READING CONTRACT FAIL: {legacy_date} historical two-block BRIEF must remain valid: '
            + ', '.join(legacy_issues)
        )

    current_issues = brief_issues(two_block, brief_policy_for_date(effective_date), True)
    current_rule = DEPTH.get('brief_reading') or DEPTH.get('brief') or {}
    current_min = int(current_rule.get('min_blocks', 0) or 0)
    current_max = int(current_rule.get('max_blocks', 0) or 0)
    expected_count_error = f'block-count=2 expected={current_min}-{current_max}'
    if not any(issue == expected_count_error for issue in current_issues):
        raise SystemExit(
            f'ANALYSIS READING CONTRACT FAIL: two-block BRIEF did not fail at configured boundary {effective_date}'
        )

    three_block = {
        'id': 'fixture-brief-three-angle',
        'summary': '測試摘要',
        'analysis_level': 'BRIEF',
        'brief_reason': 'short-official-announcement',
        'homepage_tier': 'next10',
        'full_analysis': [
            block('生成流程', '來源確認這項更新改變了既有生成流程的輸入方式，能減少中間資產搬運步驟，但目前公開資訊仍只涵蓋功能層級。'),
            block('製作價值', '對 production 的直接價值是降低重複操作與串接錯誤點，適合先放進小型自動化流程評估，而不是直接宣稱能縮短固定比例工時。'),
            block('導入測試', '目前來源沒有提供品質 benchmark、失敗率或完整相容性資料，因此應測試重跑、版本追蹤、權限與錯誤恢復，再決定是否正式導入。'),
        ],
    }
    three_issues = brief_issues(three_block, brief_policy_for_date(effective_date), True)
    if three_issues:
        raise SystemExit('ANALYSIS READING CONTRACT FAIL: valid configured-boundary BRIEF rejected: ' + ', '.join(three_issues))

    # Cross-check the public verifier against the same config on both sides of the
    # effective-date boundary. This is the guard that prevents a future contract
    # change from passing canonical QA but failing only after Atomic Publish.
    assert_pages_policy(legacy_date, two_block, DEPTH.get('brief') or {})
    assert_pages_policy(effective_date, three_block, current_rule)
    post_effective = (date_value.fromisoformat(effective_date) + timedelta(days=1)).isoformat()
    assert_pages_policy(post_effective, three_block, current_rule)

    full_fixture = {
        'id': 'fixture-full',
        'analysis_level': 'FULL',
        'full_analysis': three_block['full_analysis'],
    }
    assert_heading_first(two_block)
    assert_heading_first(three_block)
    assert_heading_first(full_fixture)
    assert_runtime_heading_first()

    print(
        'ANALYSIS READING CONTRACT PASS: configured BRIEF boundary '
        f'{legacy_date}->{effective_date} is consistent across canonical enrichment + Pages verifier; '
        'FULL/BRIEF both open with canonical h4 heading; BRIEF metadata follows analysis blocks'
    )


if __name__ == '__main__':
    main()
