#!/usr/bin/env python3
from pathlib import Path
import json

root=Path('.')

# 1) Daily release contract: total 20-30, no per-category hard minimum.
cfgp=root/'config/intelligence-v2.json'
cfg=json.loads(cfgp.read_text('utf-8'))
cfg['category_pool_min_items']=0
cfg['category_pool_target_items']=5
cfg['category_pool_max_items']=30
cfg['category_fill_policy']='daily_total_20_30_quality_first'
c=cfg['collection']
c['daily_min_items']=20
c['daily_target_items']=30
c['daily_max_items']=30
c['completeness_trigger_total_items']=30
c['fill_target_policy']='Continue discovery through the configured fill ladder aiming for 30 total valid unpublished items after Published Intelligence Registry dedupe and Quality Gate. Twenty items is the release floor, not a discovery stop signal. Category counts are diversity diagnostics, not release quotas. After reasonable exhaustion of all configured tiers, 20-29 valid items may publish; never pad with duplicates, unverifiable claims or low-production-value filler.'
c['completeness_trigger_policy']='Release-ready when 20-30 valid unpublished items survive Published Intelligence Registry dedupe and Quality Gate after the configured discovery ladder has been reasonably exhausted. Target and maximum are 30. Category shortages do not block release and must never be padded.'
c['ranking_guidance']='Production value, practical applicability, source verifiability and freshness drive ranking. Aim for broad six-category coverage without enforcing equal quotas. Continue discovery toward 30 even after reaching the 20-item release floor.'
cfgp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n','utf-8')

# 2) Dataset validator.
p=root/'scripts/intelligence_v2.py'; s=p.read_text('utf-8')
s=s.replace("    if not (pool_min == pool_target == pool_max):\n        raise ValueError('V2 target-fill contract requires min == target == max')\n","")
old="""    expected_total = pool_target * len(categories)\n    if int(collection.get('completeness_trigger_total_items', 0) or 0) != expected_total:\n        raise ValueError(f'V2 completeness trigger must equal category target total {expected_total}')\n"""
new="""    daily_min = int(collection.get('daily_min_items', 0) or 0)\n    daily_target = int(collection.get('daily_target_items', 0) or 0)\n    daily_max = int(collection.get('daily_max_items', 0) or 0)\n    if not (0 < daily_min <= daily_target <= daily_max):\n        raise ValueError('V2 daily totals must satisfy 0 < min <= target <= max')\n    if int(collection.get('completeness_trigger_total_items', 0) or 0) != daily_target:\n        raise ValueError(f'V2 completeness trigger must equal daily target {daily_target}')\n"""
if old not in s: raise SystemExit('intelligence_v2 config block not found')
s=s.replace(old,new)
start=s.index("    if target_fill_applies(data, cfg) and strict_pool:\n")
end=s.index("    return errors\n",start)
repl="""    if target_fill_applies(data, cfg) and strict_pool:\n        collection = cfg.get('collection') or {}\n        pool_max = int(cfg['category_pool_max_items'])\n        pool_min = int(cfg['category_pool_min_items'])\n        daily_min = int(collection['daily_min_items'])\n        daily_max = int(collection['daily_max_items'])\n    else:\n        metadata = data.get('metadata') or {}\n        pool_max = int(metadata.get('category_pool_max_items', 10) or 10)\n        pool_min = 0\n        daily_min = 0\n        daily_max = pool_max * len(categories)\n\n    for cid, pool in by_category.items():\n        if len(pool) > pool_max:\n            errors.append(f'{cid}: category pool exceeds maximum {pool_max}, got {len(pool)}')\n        if len(pool) < pool_min:\n            errors.append(f'{cid}: category pool below minimum {pool_min}, got {len(pool)}')\n    if len(items) < daily_min:\n        errors.append(f'V2 daily release minimum is {daily_min} items, got {len(items)}')\n    if len(items) > daily_max:\n        errors.append(f'V2 daily release maximum is {daily_max} items, got {len(items)}')\n"""
s=s[:start]+repl+s[end:]
p.write_text(s,'utf-8')

# 3) Registry normalizer uses daily total gate.
p=root/'scripts/normalize_registry_identity.py'; s=p.read_text('utf-8')
a=s.index('def category_deficits(cfg, items):')
b=s.index('\n\ndef main():',a)
s=s[:a]+"""def daily_gate(cfg, items):\n    collection = cfg.get('collection') or {}\n    have = len(items)\n    minimum = int(collection['daily_min_items'])\n    target = int(collection['daily_target_items'])\n    maximum = int(collection['daily_max_items'])\n    counts = Counter(str(item.get('category', '')).strip() for item in items)\n    return {\n        'have': have, 'min': minimum, 'target': target, 'max': maximum,\n        'missing_to_min': max(0, minimum-have),\n        'missing_to_target': max(0, target-have),\n        'release_ready': minimum <= have <= maximum,\n        'category_counts': {c['id']: counts.get(c['id'],0) for c in cfg['categories']},\n    }\n"""+s[b:]
s=s.replace("    deficits = category_deficits(cfg, kept)\n", "    gate = daily_gate(cfg, kept)\n")
s=s.replace("        'refill_required': bool(deficits),\n        'category_deficits': deficits,\n", "        'refill_required': not gate['release_ready'],\n        'category_deficits': {},\n        'daily_release_gate': gate,\n")
old="""    if deficits:\n        print('REGISTRY REFILL REQUIRED: collection is not release-ready')\n        for cid, rec in deficits.items():\n            print(f\"- {cid}: have={rec['have']} target={rec['target']} missing={rec['missing']}\")\n        print('Continue discovery through the configured fill ladder; do not create .ready yet.')\n        sys.exit(2)\n\n    print('REGISTRY REFILL COMPLETE: all category targets survive Published Intelligence Registry dedupe')\n"""
new="""    if gate['have'] > gate['max']:\n        print(f\"REGISTRY RELEASE BLOCKED: have={gate['have']} exceeds daily maximum={gate['max']}\")\n        sys.exit(1)\n    if gate['have'] < gate['min']:\n        print(f\"REGISTRY REFILL REQUIRED: have={gate['have']} minimum={gate['min']} missing={gate['missing_to_min']} target={gate['target']}\")\n        print('Continue discovery toward the daily target through the configured fill ladder; do not create .ready yet.')\n        sys.exit(2)\n    print(f\"REGISTRY RELEASE GATE PASS: have={gate['have']} minimum={gate['min']} target={gate['target']} maximum={gate['max']} category_counts={gate['category_counts']}\")\n"""
if old not in s: raise SystemExit('normalizer exit block not found')
s=s.replace(old,new)
p.write_text(s,'utf-8')

# 4) IA/release/pipeline textual hardcoded 6x5 assertions.
p=root/'scripts/check_information_architecture.py'; s=p.read_text('utf-8')
s=s.replace("    pool_target = int(cfg['category_pool_target_items'])\n", "")
s=s.replace("        if target_mode and len(cards) != pool_target: fail(f'{category[\"id\"]}: target-fill category page must contain exactly {pool_target} items, got {len(cards)}')\n", "")
s=s.replace("    mode = f'exact {pool_target}/category target-fill' if target_mode else 'legacy variable-pool compatibility'\n", "    col=cfg.get('collection') or {}; mode = f'daily {col.get(\"daily_min_items\")}-{col.get(\"daily_max_items\")} target {col.get(\"daily_target_items\")}' if target_mode else 'legacy variable-pool compatibility'\n")
p.write_text(s,'utf-8')

p=root/'scripts/check_release_input.py'; s=p.read_text('utf-8')
old="""        target=int(cfg['category_pool_target_items']); categories=len(cfg['categories'])\n        mode=f'V2 {categories}x{target} target-fill / TOP5+next10' if target_fill_applies(data,cfg) else 'V2 legacy variable pools / TOP5+next10'\n"""
new="""        col=cfg.get('collection') or {}\n        mode=f'V2 daily {col.get(\"daily_min_items\")}-{col.get(\"daily_max_items\")} target {col.get(\"daily_target_items\")} / TOP5+next10' if target_fill_applies(data,cfg) else 'V2 legacy variable pools / TOP5+next10'\n"""
if old not in s: raise SystemExit('release input mode block not found')
p.write_text(s.replace(old,new),'utf-8')

p=root/'scripts/check_pipeline_contract.py'; s=p.read_text('utf-8')
old="""        target=int(cfg['category_pool_target_items']); expected_total=target*len(categories)\n        if int(collection.get('completeness_trigger_total_items',0))!=expected_total:\n            fail(f'V2 completeness trigger must equal configured category total {expected_total}')\n        candidate_target=int(collection.get('candidate_pool_target_per_category',0) or 0)\n        candidate_stretch=int(collection.get('candidate_pool_stretch_per_category',0) or 0)\n        if candidate_target<target: fail('V2 discovery candidate target must be >= configured publish target')\n"""
new="""        soft_target=int(cfg['category_pool_target_items']); daily_target=int(collection.get('daily_target_items',0) or 0)\n        if int(collection.get('completeness_trigger_total_items',0))!=daily_target:\n            fail(f'V2 completeness trigger must equal configured daily target {daily_target}')\n        candidate_target=int(collection.get('candidate_pool_target_per_category',0) or 0)\n        candidate_stretch=int(collection.get('candidate_pool_stretch_per_category',0) or 0)\n        if candidate_target<soft_target: fail('V2 discovery candidate target must be >= category balancing target')\n"""
if old not in s: raise SystemExit('pipeline config block not found')
s=s.replace(old,new).replace('config-driven target-fill IA','config-driven daily 20-30 release-gate IA')
p.write_text(s,'utf-8')

# 5) Synthetic contract test.
(root/'scripts/check_collection_contract.py').write_text(r'''#!/usr/bin/env python3
from datetime import date,timedelta
from intelligence_v2 import load_config, validate_v2_dataset

def item(cfg,rank,cat):
    top=int(cfg['homepage']['top5']); nxt=int(cfg['homepage']['next10'])
    tier='top5' if rank<=top else ('next10' if rank<=top+nxt else 'category_only')
    return {'id':f'dry-{rank:02d}','title':f'Dry {rank}','summary':'Synthetic production intelligence.','quick_impact':'Dry ★★★★☆','source_url':f'https://example.invalid/{rank}','category':cat['id'],'subcategory':cat['subtypes'][0],'ranking_score':1000-rank,'rank_global':rank,'homepage_tier':tier,'full_analysis':[{'label':'製作流程','text':'Synthetic workflow.'},{'label':'製作價值','text':'Synthetic value.'},{'label':'導入測試','text':'Synthetic test.'}]}
def fixture(cfg,n):
    cats=cfg['categories']; items=[item(cfg,r,cats[(r-1)%len(cats)]) for r in range(1,n+1)]
    return {'date':cfg['collection_contract_effective_date'],'schema_version':int(cfg.get('schema_version',3)),'metadata':{},'items':items}
def expect(name,data,ok,frag=''):
    e=validate_v2_dataset(data,strict_pool=True)
    if ok and e: raise AssertionError(f'{name} should PASS: {e}')
    if not ok and not e: raise AssertionError(f'{name} should FAIL')
    if frag and not any(frag in x for x in e): raise AssertionError(f'{name} wrong failure: {e}')
    print(('PASS' if ok else 'FAIL expected'),name, e[0] if e else '')
def main():
    cfg=load_config(); col=cfg['collection']; mn=int(col['daily_min_items']); tg=int(col['daily_target_items']); mx=int(col['daily_max_items'])
    expect('target',fixture(cfg,tg),True); expect('23 survivors',fixture(cfg,23),True); expect('minimum',fixture(cfg,mn),True)
    expect('below minimum',fixture(cfg,mn-1),False,'daily release minimum'); expect('above maximum',fixture(cfg,mx+1),False,'daily release maximum')
    dup=fixture(cfg,mn); dup['items'][-1]['source_url']=dup['items'][0]['source_url']; expect('duplicate source',dup,False,'duplicate source URL')
    bad=fixture(cfg,mn); bad['items'][-1]['rank_global']=999; expect('bad rank',bad,False,'contiguous')
    effective=date.fromisoformat(cfg['collection_contract_effective_date']); hist=fixture(cfg,6); hist['date']=(effective-timedelta(days=1)).isoformat(); hist['metadata']={'category_pool_max_items':10}; expect('historical compatibility',hist,True)
    print(f'COLLECTION CONTRACT DRY RUN PASS: daily min={mn} target={tg} max={mx}; categories are non-blocking')
if __name__=='__main__': main()
''','utf-8')

# 6) Preserve canonical identity already established by Published Registry.
dp=root/'data/daily/2026-09-04.json'
d=json.loads(dp.read_text('utf-8'))
fixed=0
for x in d.get('items',[]):
    if x.get('source_url')=='https://www.cgchannel.com/2026/08/nekki-releases-cascadeur-2026-2-with-animation-layers/':
        x['id']='cascadeur-2026-2-layers'; fixed+=1
if fixed!=1: raise SystemExit(f'expected one Cascadeur identity fix, got {fixed}')
dp.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n','utf-8')
print('20-30 migration edits applied; Cascadeur canonical identity preserved')
