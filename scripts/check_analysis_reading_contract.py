#!/usr/bin/env python3
"""Regression guard for the 2026-09-16 BRIEF three-angle reading contract."""
from enrich_full_analysis_v3 import DEPTH, brief_issues, brief_policy_for_date


def block(label, text):
    return {'label': label, 'text': text}


def main():
    legacy_date = '2026-09-15'
    effective_date = str(DEPTH.get('brief_reading_contract_effective_date', ''))
    if effective_date != '2026-09-16':
        raise SystemExit(f'ANALYSIS READING CONTRACT FAIL: unexpected effective date {effective_date!r}')

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
        raise SystemExit('ANALYSIS READING CONTRACT FAIL: 2026-09-15 historical two-block BRIEF must remain valid: ' + ', '.join(legacy_issues))

    current_issues = brief_issues(two_block, brief_policy_for_date(effective_date), True)
    if not any(issue.startswith('block-count=2 expected=3-3') for issue in current_issues):
        raise SystemExit('ANALYSIS READING CONTRACT FAIL: two-block BRIEF did not fail after 2026-09-16')

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
        raise SystemExit('ANALYSIS READING CONTRACT FAIL: valid three-angle BRIEF rejected: ' + ', '.join(three_issues))

    print('ANALYSIS READING CONTRACT PASS: historical 1-2 block BRIEF preserved; 2026-09-16+ requires three source-grounded reading angles')


if __name__ == '__main__':
    main()
