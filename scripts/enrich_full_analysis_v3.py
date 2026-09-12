#!/usr/bin/env python3
"""Validate schema-v3 analysis depth using FULL / BRIEF / REJECT tiers.

FULL keeps the original 3-5 block production-depth contract. BRIEF allows verified,
high-value intelligence with limited source depth to publish in category/daily pages
without fabricating analysis. REJECT items are never allowed in canonical publish.
"""
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / 'config' / 'intelligence-v2.json'
DEPTH_PATH = ROOT / 'config' / 'full-analysis-depth.json'

CATEGORY_HEADINGS = {
    'ai-generation': ('生成流程', '製作價值', '導入測試'),
    '3d-production': ('製作流程', '流程價值', '實測'),
    '3d-animation': ('動作製作流程', 'Rig / 輸出', '導入測試'),
    'engine-art': ('引擎工作流', '製作價值', '平台實測'),
    'emerging-case': ('技術方向', '製作潛力', '成熟度判斷'),
    'blender-dcc': ('DCC 工作流', '製作價值', '升版 / 導入測試'),
}

CURRENT_3D_PRODUCTION = {
    'character-production', 'prop-production', 'environment-production', 'production-workflow',
}
CHARACTER_SIGNALS = ('character', 'face', 'facial', 'hair', 'cloth', 'skin', 'anatomy', 'human', 'creature', 'body', 'portrait')
ENVIRONMENT_SIGNALS = ('environment', 'scene', 'building', 'architecture', 'foliage', 'terrain', 'landscape', 'modular', 'ruin', 'forest')
PROP_SIGNALS = ('prop', 'weapon', 'hard-surface', 'hard surface', 'decal', 'bevel', 'trim', 'vehicle', 'furniture')


def clean(text):
    return ' '.join(str(text or '').split())


def char_count(text):
    return len(re.sub(r'\s+', '', clean(text)))


def has_han(text):
    return bool(re.search(r'[\u3400-\u4dbf\u4e00-\u9fff]', clean(text)))


def item_text(item):
    parts = [item.get('id'), item.get('title'), item.get('summary'), item.get('quick_impact')]
    for block in item.get('full_analysis') or []:
        if isinstance(block, dict):
            parts.extend((block.get('label'), block.get('text')))
    return ' '.join(clean(x) for x in parts if x).casefold()


def classify_3d_production(item):
    current = clean(item.get('subcategory'))
    if current in CURRENT_3D_PRODUCTION:
        return current
    text = item_text(item)
    if any(x in text for x in ENVIRONMENT_SIGNALS):
        return 'environment-production'
    if any(x in text for x in CHARACTER_SIGNALS):
        return 'character-production'
    if any(x in text for x in PROP_SIGNALS):
        return 'prop-production'
    return 'production-workflow'


def normalize_3d_production_taxonomy(data):
    changed = 0
    for item in data.get('items', []):
        if item.get('category') != '3d-production':
            continue
        target = classify_3d_production(item)
        if item.get('subcategory') != target:
            item['subcategory'] = target
            changed += 1
    if changed:
        meta = data.setdefault('metadata', {})
        meta['3d_production_taxonomy'] = 'asset-oriented-v1'
        meta['3d_production_taxonomy_rule'] = 'character|prop|environment first; cross-asset technique => production-workflow'
    return changed


def normalized_level(item, tiered):
    if not tiered:
        return 'FULL'
    level = clean(item.get('analysis_level') or 'FULL').upper()
    return level if level in {'FULL', 'BRIEF', 'REJECT'} else 'INVALID'


def common_structure_issues(item, min_blocks, max_blocks, heading_language='zh-Hant'):
    issues = []
    blocks = item.get('full_analysis') or []
    if not (min_blocks <= len(blocks) <= max_blocks):
        return [f'block-count={len(blocks)} expected={min_blocks}-{max_blocks}']
    labels, texts = [], []
    for i, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            issues.append(f'block-{i}-not-object')
            continue
        label = clean(block.get('label'))
        text = clean(block.get('text'))
        if not label or not text:
            issues.append(f'block-{i}-empty')
        if heading_language == 'zh-Hant' and label and not has_han(label):
            issues.append(f'block-{i}-heading-not-zh-Hant')
        labels.append(label.casefold())
        texts.append(text.casefold())
    if len(labels) != len(set(labels)):
        issues.append('duplicate-headings')
    if len(texts) != len(set(texts)):
        issues.append('duplicate-text')
    summary = clean(item.get('summary')).casefold()
    for i, text in enumerate(texts, 1):
        if text and text == summary:
            issues.append(f'block-{i}-repeats-summary')
    return issues


def text_depth_issues(item, min_block_chars, min_total_chars):
    issues = []
    total = 0
    for i, block in enumerate(item.get('full_analysis') or [], 1):
        if not isinstance(block, dict):
            continue
        n = char_count(block.get('text'))
        total += n
        if n < min_block_chars:
            issues.append(f'block-{i}-too-shallow={n}<{min_block_chars}')
    if total < min_total_chars:
        issues.append(f'total-depth={total}<{min_total_chars}')
    return issues


def full_issues(item, cfg):
    issues = common_structure_issues(
        item, int(cfg.get('min_blocks', 3)), int(cfg.get('max_blocks', 5))
    )
    issues += text_depth_issues(
        item, int(cfg.get('min_block_chars', 48)), int(cfg.get('min_total_text_chars', 180))
    )
    labels = ' '.join(clean(b.get('label')) for b in item.get('full_analysis') or [] if isinstance(b, dict))
    semantic = DEPTH.get('required_semantic_groups') or {}
    for group in cfg.get('required_semantic_groups') or []:
        keywords = semantic.get(group) or []
        if not any(str(k) in labels for k in keywords):
            issues.append(f'missing-semantic={group}')
    return issues


def brief_issues(item, cfg):
    issues = common_structure_issues(
        item, int(cfg.get('min_blocks', 1)), int(cfg.get('max_blocks', 2))
    )
    issues += text_depth_issues(
        item, int(cfg.get('min_block_chars', 36)), int(cfg.get('min_total_text_chars', 60))
    )
    reason = clean(item.get('brief_reason'))
    allowed = set(cfg.get('allowed_reasons') or [])
    if not reason:
        issues.append('brief_reason-missing')
    elif allowed and reason not in allowed:
        issues.append(f'brief_reason-not-allowed={reason}')
    if clean(item.get('homepage_tier')).lower() == 'top5' and not DEPTH.get('top5_policy', {}).get('allow_brief', False):
        issues.append('BRIEF-cannot-be-top5')
    return issues


def legacy_repair(item):
    blocks = [b for b in (item.get('full_analysis') or []) if isinstance(b, dict)]
    texts = [clean(b.get('text')) for b in blocks if clean(b.get('text'))]
    headings = CATEGORY_HEADINGS.get(item.get('category'), CATEGORY_HEADINGS['3d-production'])
    summary = clean(item.get('summary'))
    return [
        {'label': headings[0], 'text': texts[0] if texts else summary},
        {'label': headings[1], 'text': texts[1] if len(texts) > 1 else '此項目的製作價值需以實際流程、返工成本與可重現性驗證。'},
        {'label': headings[2], 'text': texts[2] if len(texts) > 2 else '建議以小型 production test 驗證品質、相容性、限制與導入成本。'},
    ]


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else max(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))
    path = ROOT / 'data' / 'daily' / f'{date}.json'
    data = json.loads(path.read_text('utf-8'))
    if int(data.get('schema_version', 0)) != 3:
        print(f'ANALYSIS DEPTH: legacy schema for {date}; no changes')
        return

    tiered = date >= str(DEPTH.get('tiered_effective_date', '9999-12-31'))
    old_strict = date >= str(DEPTH.get('effective_date', '9999-12-31'))
    taxonomy_changed = normalize_3d_production_taxonomy(data)
    failures = []
    counts = {'FULL': 0, 'BRIEF': 0, 'REJECT': 0}
    repaired = 0

    for item in data.get('items', []):
        rid = str(item.get('id') or '<missing-id>')
        level = normalized_level(item, tiered)
        if level == 'INVALID':
            failures.append(f'{rid}: invalid analysis_level')
            continue
        if level == 'REJECT':
            counts['REJECT'] += 1
            failures.append(f'{rid}: REJECT items cannot appear in canonical publish')
            continue

        if tiered:
            item['analysis_level'] = level
            if level == 'FULL':
                counts['FULL'] += 1
                issues = full_issues(item, DEPTH.get('full') or {})
            else:
                counts['BRIEF'] += 1
                issues = brief_issues(item, DEPTH.get('brief') or {})
        elif old_strict:
            counts['FULL'] += 1
            issues = full_issues(item, {
                'min_blocks': 3, 'max_blocks': 5, 'min_block_chars': 48,
                'min_total_text_chars': 180,
                'required_semantic_groups': ['workflow_or_technical_change', 'production_impact', 'test_risk_or_limit'],
            })
        else:
            issues = common_structure_issues(item, 3, 5)
            if issues:
                item['full_analysis'] = legacy_repair(item)
                repaired += 1
                issues = []

        if issues:
            failures.append(f'{rid} [{level}]: ' + ', '.join(issues))

    if failures:
        print('ANALYSIS DEPTH FAILED')
        for failure in failures:
            print('- ' + failure)
        print('Do not pad or fabricate evidence. Downgrade eligible limited-evidence items to BRIEF; otherwise reject them from publish.')
        sys.exit(1)

    meta = data.setdefault('metadata', {})
    if tiered:
        meta['full_analysis_depth_contract'] = 'v5-tiered-full-brief-reject'
        meta['analysis_level_counts'] = counts
        meta['analysis_level_policy'] = 'quality-gate-first-then-evidence-depth; FULL=3-5 blocks, BRIEF=1-2 blocks, REJECT=not-publishable'
    elif old_strict:
        meta['full_analysis_depth_contract'] = 'v4-source-supported-production-depth'
    meta['full_analysis_style_reference'] = DEPTH.get('style_reference', '2026-09-01')
    meta['full_analysis_heading_language'] = 'zh-Hant'

    if taxonomy_changed or repaired or old_strict or tiered:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    mode = 'tiered-v5' if tiered else ('strict-v4' if old_strict else 'legacy-v3')
    print(f'CANONICAL ENRICHMENT: {date} / mode={mode}; FULL={counts["FULL"]} BRIEF={counts["BRIEF"]} REJECT={counts["REJECT"]}; taxonomy={taxonomy_changed}; repaired={repaired}')


DEPTH = json.loads(DEPTH_PATH.read_text('utf-8'))

if __name__ == '__main__':
    main()
