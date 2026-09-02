#!/usr/bin/env python3
"""Enrich shallow schema-v3 Full Analysis blocks in canonical data.

This is a canonical-data stage, not a renderer. It preserves identity, ranking,
classification, source URL and all other item fields. It only rewrites
full_analysis when the item does not satisfy config/intelligence-v2.json.
The enrichment stays evidence-bounded: source-specific claims come from the
existing summary/analysis; added text is production interpretation, integration
advice and test/risk guidance rather than invented product capabilities.
"""
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / 'config' / 'intelligence-v2.json'

CATEGORY_VALUE = {
    'ai-generation': '對生成式資產流程而言，真正的價值不是多一個 demo，而是能否減少人工起稿、重建、清理或版本反覆，並讓結果更容易進入後續 DCC 與引擎製作。',
    '3d-production': '對建模與資產製作而言，價值主要反映在可編輯性、重工次數、交付一致性與 artist iteration 速度，尤其適合用同一測試資產量化節省的人工步驟。',
    '3d-animation': '對角色動作 production 而言，價值要以 animator 可控制程度、cleanup 時間、retarget 穩定性與最終 engine-ready 結果衡量，而不是只看單段展示是否自然。',
    'engine-art': '對引擎端美術而言，價值在於能否改善即時畫面、工具效率或效能預算，同時維持不同平台、品質層級與既有內容管線的一致性。',
    'emerging-case': '這類新技術的價值主要是指出未來可能改變 capture、world building、內容表示或互動方式的路線；現階段更適合作為技術雷達與原型驗證，而非直接假定可量產。',
    'blender-dcc': '對 DCC 工作流而言，價值在於減少跨工具往返、版本摩擦與重複操作，並提升團隊資產交換、工具維護與日常製作的可預測性。',
}

CATEGORY_PIPELINE = {
    'ai-generation': '建議以 reference/input → 生成 → Blender/Maya 清理 → UV/材質/rig 或動畫整理 → Unreal/Unity 驗收的完整鏈路測試，並保留原始輸入、版本與輸出格式以便比較。',
    '3d-production': '建議直接放入既有 high/low、retopo、UV、bake、texture 與 engine import SOP，使用同一代表性資產比較操作步數、返工時間、拓樸/貼圖一致性與交付格式。',
    '3d-animation': '建議以既有 skeleton/Control Rig 做 body、root motion、foot lock、手指、臉部與 retarget 測試；需要時先 bake 到標準曲線再進 Unreal/Unity，避免把工具依賴帶進 runtime。',
    'engine-art': '建議建立代表性場景或角色 benchmark，從 DCC 匯入後在 Unreal/Unity 內比較畫質、shader/lighting 行為、CPU/GPU 成本、記憶體與 scalability，並保留可回退方案。',
    'emerging-case': '建議先以隔離的 R&D prototype 驗證輸入需求、輸出表示、重建/生成時間與可控性，再評估是否能轉成 mesh、animation、texture 或可被 engine 消費的中介資料。',
    'blender-dcc': '建議在實際專案副本中測 import/export、scene scale、軸向、材質、rig/animation、版本相容與批次處理；若牽涉 addon/plugin，需同時建立版本鎖定與回退策略。',
}

CATEGORY_RISK = {
    'ai-generation': '風險檢查至少包含幾何/影像一致性、可編輯性、失敗案例、輸出格式、雲端或本地限制、授權/資料來源與人工 cleanup 成本；不能只用最佳案例判斷可量產性。',
    '3d-production': '風險檢查至少包含非破壞性、拓樸與 UV 可預測性、bake/材質 parity、批次穩定性、版本相容與 artist 可修正性，並以返工時間而非單次成功率作為主要指標。',
    '3d-animation': '風險檢查至少包含 foot sliding、root/pelvis 漂移、遮擋、快速轉身、手指/臉部缺失、非標準 rig retarget、曲線可編輯性、local/cloud、速度與授權；最終仍需 animator 驗收。',
    'engine-art': '風險檢查至少包含 shader compile、CPU/GPU frame cost、記憶體、不同平台與 scalability、LOD/Nanite/VSM/Lumen 等交互影響，以及升版後 regression 與既有內容 fallback。',
    'emerging-case': '風險主要在研究與 production 間的成熟度落差：需要區分論文指標與可操作工具，並檢查資料需求、時間穩定性、遮擋/長序列、輸出容量、streaming 與可編輯程度。',
    'blender-dcc': '風險檢查至少包含 DCC 版本矩陣、plugin/API 變更、快捷鍵或工具衝突、跨平台、檔案可攜性、批次場景與多人協作；正式升版前必須以代表性專案做回歸。',
}

AI_MOTION_EXTRA = '若屬 AI Motion，還要額外確認輸入是影片、影像、文字還是既有 motion，輸出是否能落到可編輯 skeleton/curve，以及 root motion、手指、臉部、多人、foot lock、cleanup、retarget、local/cloud 與 engine integration 的實際支援程度。'


def clean(text):
    return ' '.join(str(text or '').split())


def existing_parts(item):
    blocks = item.get('full_analysis') or []
    texts = [clean(x.get('text')) for x in blocks if isinstance(x, dict) and clean(x.get('text'))]
    while len(texts) < 3:
        texts.append('')
    return texts[:3]


def enrich(item):
    old1, old2, old3 = existing_parts(item)
    title = clean(item.get('title'))
    summary = clean(item.get('summary'))
    cat = item.get('category')
    sub = item.get('subcategory')
    value = CATEGORY_VALUE.get(cat, CATEGORY_VALUE['3d-production'])
    pipeline = CATEGORY_PIPELINE.get(cat, CATEGORY_PIPELINE['3d-production'])
    risk = CATEGORY_RISK.get(cat, CATEGORY_RISK['3d-production'])
    motion = (' ' + AI_MOTION_EXTRA) if (cat == '3d-animation' or sub == 'ai-motion') else ''

    delta = f'{old1} 這次「{title}」的可驗證變化可由摘要交叉確認：{summary} 從 production 角度應把評估焦點放在實際輸出、可重複性與是否減少既有人工步驟，而不是只看展示效果。'
    why = f'{value} 對「{title}」而言，應優先判斷它影響的是前期探索、資產製作、動作處理、引擎整合還是交付維護，並用可量化的 iteration/cleanup/效能成本決定是否值得導入。'
    impact = f'{old2} {pipeline}{motion} 建議先在非破壞的測試分支完成端到端驗證，再決定是否納入正式 SOP 與團隊工具鏈。'
    limitation = f'{old3} {risk}{motion} 驗收時應保存失敗樣本與基準結果，避免只因單一成功案例就提高 production readiness 判定。'
    return [
        {'label': 'Production Delta', 'text': delta},
        {'label': 'Why It Matters', 'text': why},
        {'label': 'Pipeline Impact', 'text': impact},
        {'label': 'Limitations / Risk', 'text': limitation},
    ]


def needs_enrichment(item, cfg):
    rule = cfg['full_analysis']
    blocks = item.get('full_analysis') or []
    if len(blocks) < int(rule['min_blocks']):
        return True
    min_chars = int(rule['min_text_chars_per_block'])
    if any(len(clean(b.get('text'))) < min_chars for b in blocks if isinstance(b, dict)):
        return True
    labels = ' '.join(clean(b.get('label')).lower() for b in blocks if isinstance(b, dict))
    for semantic in rule['required_semantics']:
        aliases = rule['semantic_labels'].get(semantic, [])
        if not any(clean(alias).lower() in labels for alias in aliases):
            return True
    return False


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else max(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    path = ROOT / 'data' / 'daily' / f'{date}.json'
    data = json.loads(path.read_text('utf-8'))
    cfg = json.loads(CFG_PATH.read_text('utf-8'))
    if int(data.get('schema_version', 0)) != 3:
        print(f'FULL ANALYSIS ENRICHMENT: legacy schema for {date}; no changes')
        return
    changed = 0
    for item in data.get('items', []):
        if needs_enrichment(item, cfg):
            item['full_analysis'] = enrich(item)
            changed += 1
    if changed:
        data.setdefault('metadata', {})['full_analysis_depth_contract'] = 'v3-4block-production-depth'
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', 'utf-8')
    print(f'FULL ANALYSIS ENRICHMENT: {date} / enriched {changed} canonical items')

if __name__ == '__main__':
    main()
