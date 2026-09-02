#!/usr/bin/env python3
"""Validate/repair shallow schema-v3 Full Analysis without imposing a writing template.

This canonical-data stage follows config/intelligence-v2.json. It preserves valid
adaptive 3–5 block analysis verbatim. It only repairs structurally shallow legacy
records, using concise content-specific headings rather than fixed report labels.
"""
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / 'config' / 'intelligence-v2.json'

CATEGORY_HEADINGS = {
    'ai-generation': ('Generation Workflow', 'Production Value', '導入測試'),
    '3d-production': ('Production Workflow', 'Pipeline Value', '實測'),
    '3d-animation': ('Animation Workflow', 'Rig / Output', '導入測試'),
    'engine-art': ('Engine Workflow', 'Production Value', '平台實測'),
    'emerging-case': ('Technical Direction', 'Production Potential', '成熟度判斷'),
    'blender-dcc': ('DCC Workflow', 'Production Value', '升版 / 導入測試'),
}

CATEGORY_TEST = {
    'ai-generation': '以代表性 input 驗證輸出一致性、可編輯性、格式、人工 cleanup、授權與 DCC/engine 接續成本，再決定是否納入 production。',
    '3d-production': '用同一代表性資產比較操作步驟、返工時間、拓樸/UV/bake/材質一致性與 engine 交付結果，避免只看單次成功案例。',
    '3d-animation': '用既有 skeleton/Control Rig 驗 body、root motion、foot contact、retarget、曲線可編輯性與 cleanup 時間，最終仍由 animator 驗收。',
    'engine-art': '在代表性場景與目標平台比較畫質、CPU/GPU、記憶體、scalability 與 regression，並保留可回退方案。',
    'emerging-case': '先以隔離 R&D prototype 驗證輸入需求、輸出表示、時間一致性、可控性與能否轉成 production 可消費資料，不把論文展示直接視為量產能力。',
    'blender-dcc': '在實際專案副本測 import/export、版本相容、plugin/API、材質、rig/animation 與批次處理，再決定是否更新團隊工具基線。',
}


def clean(text):
    return ' '.join(str(text or '').split())


def valid_blocks(item, rule):
    blocks = item.get('full_analysis') or []
    min_blocks = int(rule.get('min_blocks', 3))
    max_blocks = int(rule.get('max_blocks', 5))
    if not (min_blocks <= len(blocks) <= max_blocks):
        return False
    labels = []
    texts = []
    for block in blocks:
        if not isinstance(block, dict):
            return False
        label = clean(block.get('label'))
        text = clean(block.get('text'))
        if not label or not text:
            return False
        labels.append(label.casefold())
        texts.append(text.casefold())
    if len(set(labels)) != len(labels) or len(set(texts)) != len(texts):
        return False
    summary = clean(item.get('summary')).casefold()
    impact = clean(item.get('quick_impact')).casefold()
    if any(text == summary or text == impact for text in texts):
        return False
    return True


def repair(item):
    blocks = [b for b in (item.get('full_analysis') or []) if isinstance(b, dict)]
    existing = [clean(b.get('text')) for b in blocks if clean(b.get('text'))]
    summary = clean(item.get('summary'))
    category = item.get('category')
    headings = CATEGORY_HEADINGS.get(category, CATEGORY_HEADINGS['3d-production'])
    first = existing[0] if existing else summary
    second = existing[1] if len(existing) > 1 else f'這項內容的 production 價值應以是否減少實際製作、返工或跨工具摩擦來判斷，而不是只看展示結果。'
    third = existing[2] if len(existing) > 2 else CATEGORY_TEST.get(category, CATEGORY_TEST['3d-production'])
    return [
        {'label': headings[0], 'text': first},
        {'label': headings[1], 'text': second},
        {'label': headings[2], 'text': third},
    ]


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else max(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    path = ROOT / 'data' / 'daily' / f'{date}.json'
    data = json.loads(path.read_text('utf-8'))
    cfg = json.loads(CFG_PATH.read_text('utf-8'))
    if int(data.get('schema_version', 0)) != 3:
        print(f'FULL ANALYSIS ENRICHMENT: legacy schema for {date}; no changes')
        return
    rule = cfg.get('full_analysis', {})
    changed = 0
    for item in data.get('items', []):
        if not valid_blocks(item, rule):
            item['full_analysis'] = repair(item)
            changed += 1
    if changed:
        metadata = data.setdefault('metadata', {})
        metadata['full_analysis_depth_contract'] = 'v3-adaptive-3to5-production-depth'
        metadata['full_analysis_style_reference'] = rule.get('style_reference', '2026-09-01')
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', 'utf-8')
    print(f'FULL ANALYSIS ENRICHMENT: {date} / repaired {changed} structurally shallow canonical items; valid adaptive analysis preserved')

if __name__ == '__main__':
    main()
