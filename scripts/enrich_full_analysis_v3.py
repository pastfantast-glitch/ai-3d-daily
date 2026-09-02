#!/usr/bin/env python3
"""Validate/repair schema-v3 Full Analysis, heading language and canonical taxonomy.

This canonical-data stage follows config/intelligence-v2.json. It preserves valid
adaptive 3–5 block analysis text, normalizes English-only analysis headings into
concise Traditional Chinese, repairs structurally shallow legacy records, and
migrates legacy 3D-production technical subcategories into the current asset-oriented
taxonomy before release preflight.
"""
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / 'config' / 'intelligence-v2.json'

CATEGORY_HEADINGS = {
    'ai-generation': ('生成流程', '製作價值', '導入測試'),
    '3d-production': ('製作流程', '流程價值', '實測'),
    '3d-animation': ('動作製作流程', 'Rig / 輸出', '導入測試'),
    'engine-art': ('引擎工作流', '製作價值', '平台實測'),
    'emerging-case': ('技術方向', '製作潛力', '成熟度判斷'),
    'blender-dcc': ('DCC 工作流', '製作價值', '升版 / 導入測試'),
}

EXACT_HEADING_TRANSLATIONS = {
    'Topology / Mesh Quality': '拓樸與網格品質',
    'Game Asset Pipeline': '遊戲資產製作流程',
    'Lighting Pipeline': '光照製作流程',
    'Production Value': '製作價值',
    'Dynamic Reconstruction': '動態重建',
    'Production Potential': '製作潛力',
    'Animation Workflow': '動作製作流程',
    'Root Motion / Cleanup': 'Root Motion 與動作清理',
    'UV Workflow': 'UV 製作流程',
    'Lighting / Rendering': '光照與渲染',
    'Performance Budget': '效能預算',
    'Texture / Concept Workflow': '貼圖與概念製作流程',
    'Modeling / Skinning': '建模與蒙皮',
    'Character Pipeline': '角色製作流程',
    'Generation Workflow': '生成流程',
    'Production Workflow': '製作流程',
    'Pipeline Value': '流程價值',
    'Rig / Output': 'Rig 與輸出',
    'Engine Workflow': '引擎工作流',
    'Technical Direction': '技術方向',
    'DCC Workflow': 'DCC 工作流',
    'Asset Pipeline': '資產製作流程',
    'Asset Workflow': '資產製作流程',
    'Character Workflow': '角色製作流程',
    'Environment Workflow': '場景製作流程',
    'Material Workflow': '材質製作流程',
    'Texture Workflow': '貼圖製作流程',
    'Modeling Workflow': '建模流程',
    'Rigging Workflow': 'Rig 製作流程',
    'Retarget Workflow': 'Retarget 流程',
    'Rendering Workflow': '渲染流程',
    'Scene Workflow': '場景製作流程',
    'Tool Workflow': '工具工作流',
    'Pipeline Impact': '流程影響',
    'Production Impact': '製作影響',
    'Mesh Quality': '網格品質',
    'Output Quality': '輸出品質',
    'Technical Quality': '技術品質',
    'Performance': '效能',
    'Limitations': '限制',
    'Adoption Test': '導入測試',
    'Production Test': '製作實測',
    'Platform Test': '平台實測',
    'Maturity': '成熟度判斷',
}

PHRASE_REPLACEMENTS = (
    ('Production Workflow', '製作流程'),
    ('Production Pipeline', '製作流程'),
    ('Production Value', '製作價值'),
    ('Production Potential', '製作潛力'),
    ('Production Impact', '製作影響'),
    ('Game Pipeline', '遊戲製作流程'),
    ('Asset Pipeline', '資產製作流程'),
    ('Asset Workflow', '資產製作流程'),
    ('Character Pipeline', '角色製作流程'),
    ('Character Workflow', '角色製作流程'),
    ('Environment Pipeline', '場景製作流程'),
    ('Environment Workflow', '場景製作流程'),
    ('Animation Pipeline', '動作製作流程'),
    ('Animation Workflow', '動作製作流程'),
    ('Lighting Pipeline', '光照製作流程'),
    ('Lighting Workflow', '光照製作流程'),
    ('Rendering Pipeline', '渲染流程'),
    ('Rendering Workflow', '渲染流程'),
    ('Texture Workflow', '貼圖製作流程'),
    ('Material Workflow', '材質製作流程'),
    ('Modeling Workflow', '建模流程'),
    ('Rigging Workflow', 'Rig 製作流程'),
    ('Retarget Workflow', 'Retarget 流程'),
    ('Technical Direction', '技術方向'),
    ('Pipeline Value', '流程價值'),
    ('Pipeline Impact', '流程影響'),
    ('Performance Budget', '效能預算'),
    ('Mesh Quality', '網格品質'),
    ('Output Quality', '輸出品質'),
    ('Technical Quality', '技術品質'),
    ('Root Motion', 'Root Motion'),
    ('Cleanup', '清理'),
    ('Reconstruction', '重建'),
    ('Generation', '生成'),
    ('Workflow', '工作流'),
    ('Pipeline', '流程'),
    ('Rendering', '渲染'),
    ('Lighting', '光照'),
    ('Animation', '動作'),
    ('Modeling', '建模'),
    ('Skinning', '蒙皮'),
    ('Texture', '貼圖'),
    ('Material', '材質'),
    ('Quality', '品質'),
    ('Performance', '效能'),
    ('Potential', '潛力'),
    ('Impact', '影響'),
    ('Value', '價值'),
    ('Limitations', '限制'),
    ('Testing', '測試'),
    ('Test', '測試'),
)

CATEGORY_TEST = {
    'ai-generation': '以代表性 input 驗證輸出一致性、可編輯性、格式、人工 cleanup、授權與 DCC/engine 接續成本，再決定是否納入 production。',
    '3d-production': '用同一代表性資產比較操作步驟、返工時間、拓樸/UV/bake/材質一致性與 engine 交付結果，避免只看單次成功案例。',
    '3d-animation': '用既有 skeleton/Control Rig 驗 body、root motion、foot contact、retarget、曲線可編輯性與 cleanup 時間，最終仍由 animator 驗收。',
    'engine-art': '在代表性場景與目標平台比較畫質、CPU/GPU、記憶體、scalability 與 regression，並保留可回退方案。',
    'emerging-case': '先以隔離 R&D prototype 驗證輸入需求、輸出表示、時間一致性、可控性與能否轉成 production 可消費資料，不把論文展示直接視為量產能力。',
    'blender-dcc': '在實際專案副本測 import/export、版本相容、plugin/API、材質、rig/animation 與批次處理，再決定是否更新團隊工具基線。',
}

CURRENT_3D_PRODUCTION = {
    'character-production', 'prop-production', 'environment-production', 'production-workflow',
}
CHARACTER_SIGNALS = (
    'character', 'fighter', 'face', 'facial', 'hair', 'cloth', 'skin', 'anatomy',
    'human', 'creature', 'almalexia', 'torso', 'finger', 'fingers', 'arm', 'arms',
    'leg', 'legs', 'neck', 'body', 'portrait',
)
ENVIRONMENT_SIGNALS = (
    'environment', 'scene', 'building', 'architecture', 'foliage', 'terrain',
    'landscape', 'vegetation', 'modular', 'ruin', 'village', 'forest', 'courtyard',
    'world building', 'world-building',
)
PROP_SIGNALS = (
    'prop', 'weapon', 'guitar', 'hard-surface', 'hard surface', 'decal', 'bevel',
    'trim', 'asset', 'object', 'product', 'furniture', 'vehicle',
)


def clean(text): return ' '.join(str(text or '').split())
def has_han(text): return bool(re.search(r'[\u3400-\u4dbf\u4e00-\u9fff]', clean(text)))

def translate_heading(label, category):
    label = clean(label)
    if not label or has_han(label):
        return label
    if label in EXACT_HEADING_TRANSLATIONS:
        return EXACT_HEADING_TRANSLATIONS[label]
    translated = label
    for src, dst in PHRASE_REPLACEMENTS:
        translated = re.sub(re.escape(src), dst, translated, flags=re.I)
    translated = clean(translated.replace(' / ', ' / ').replace(' & ', ' 與 '))
    if has_han(translated):
        return translated
    # Fail-safe remains semantic by category rather than merely prefixing English.
    return CATEGORY_HEADINGS.get(category, CATEGORY_HEADINGS['3d-production'])[0]


def normalize_heading_language(data, rule):
    if rule.get('heading_language') != 'zh-Hant':
        return 0
    changed = 0
    for item in data.get('items', []):
        for block in item.get('full_analysis') or []:
            if not isinstance(block, dict):
                continue
            old = clean(block.get('label'))
            new = translate_heading(old, item.get('category'))
            if new and new != old:
                block['label'] = new
                changed += 1
    return changed


def item_text(item):
    parts = [item.get('id'), item.get('title'), item.get('summary'), item.get('quick_impact')]
    for block in item.get('full_analysis') or []:
        if isinstance(block, dict): parts.extend((block.get('label'), block.get('text')))
    return ' '.join(clean(x) for x in parts if x).casefold()

def has_signal(text, signals): return any(signal in text for signal in signals)

def classify_3d_production(item):
    current = clean(item.get('subcategory'))
    if current in CURRENT_3D_PRODUCTION: return current
    text = item_text(item)
    if has_signal(text, ENVIRONMENT_SIGNALS): return 'environment-production'
    if has_signal(text, CHARACTER_SIGNALS): return 'character-production'
    if has_signal(text, PROP_SIGNALS): return 'prop-production'
    return 'production-workflow'

def normalize_3d_production_taxonomy(data):
    changed = 0
    for item in data.get('items', []):
        if item.get('category') != '3d-production': continue
        target = classify_3d_production(item)
        if item.get('subcategory') != target:
            item['subcategory'] = target; changed += 1
    if changed:
        metadata = data.setdefault('metadata', {})
        metadata['3d_production_taxonomy'] = 'asset-oriented-v1'
        metadata['3d_production_taxonomy_rule'] = 'character|prop|environment first; cross-asset technique => production-workflow'
    return changed

def valid_blocks(item, rule):
    blocks = item.get('full_analysis') or []
    min_blocks = int(rule.get('min_blocks', 3)); max_blocks = int(rule.get('max_blocks', 5))
    if not (min_blocks <= len(blocks) <= max_blocks): return False
    labels=[]; texts=[]
    for block in blocks:
        if not isinstance(block, dict): return False
        label=clean(block.get('label')); text=clean(block.get('text'))
        if not label or not text: return False
        if rule.get('heading_language') == 'zh-Hant' and not has_han(label): return False
        labels.append(label.casefold()); texts.append(text.casefold())
    if len(set(labels)) != len(labels) or len(set(texts)) != len(texts): return False
    summary=clean(item.get('summary')).casefold(); impact=clean(item.get('quick_impact')).casefold()
    if any(text == summary or text == impact for text in texts): return False
    return True

def repair(item):
    blocks=[b for b in (item.get('full_analysis') or []) if isinstance(b,dict)]
    existing=[clean(b.get('text')) for b in blocks if clean(b.get('text'))]
    summary=clean(item.get('summary')); category=item.get('category')
    headings=CATEGORY_HEADINGS.get(category,CATEGORY_HEADINGS['3d-production'])
    first=existing[0] if existing else summary
    second=existing[1] if len(existing)>1 else '這項內容的 production 價值應以是否減少實際製作、返工或跨工具摩擦來判斷，而不是只看展示結果。'
    third=existing[2] if len(existing)>2 else CATEGORY_TEST.get(category,CATEGORY_TEST['3d-production'])
    return [
        {'label':headings[0],'text':first},
        {'label':headings[1],'text':second},
        {'label':headings[2],'text':third},
    ]

def main():
    date=sys.argv[1] if len(sys.argv)>1 else max(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    path=ROOT/'data'/'daily'/f'{date}.json'
    data=json.loads(path.read_text('utf-8')); cfg=json.loads(CFG_PATH.read_text('utf-8'))
    if int(data.get('schema_version',0)) != 3:
        print(f'FULL ANALYSIS ENRICHMENT: legacy schema for {date}; no changes'); return
    rule=cfg.get('full_analysis',{})
    taxonomy_changed=normalize_3d_production_taxonomy(data)
    headings_changed=normalize_heading_language(data,rule)
    analysis_changed=0
    for item in data.get('items',[]):
        if not valid_blocks(item,rule):
            item['full_analysis']=repair(item); analysis_changed+=1
    if headings_changed or analysis_changed:
        metadata=data.setdefault('metadata',{})
        metadata['full_analysis_depth_contract']='v3-adaptive-3to5-production-depth'
        metadata['full_analysis_style_reference']=rule.get('style_reference','2026-09-01')
        metadata['full_analysis_heading_language']='zh-Hant'
    if taxonomy_changed or headings_changed or analysis_changed:
        path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n','utf-8')
    print(f'CANONICAL ENRICHMENT: {date} / taxonomy migrated {taxonomy_changed}; translated {headings_changed} Full Analysis headings; repaired {analysis_changed} analyses')

if __name__=='__main__': main()
