#!/usr/bin/env python3
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def replace_required(path, old, new, label):
    p=ROOT/path; s=p.read_text('utf-8')
    if old not in s: raise SystemExit(f'{label}: expected block not found')
    p.write_text(s.replace(old,new),'utf-8')

cfgp=ROOT/'config/intelligence-v2.json'
cfg=json.loads(cfgp.read_text('utf-8'))
cfg['category_pool_min_items']=0
cfg['category_pool_target_items']=5
cfg['category_pool_max_items']=30
cfg['category_fill_policy']='daily_total_20_30_quality_first'
c=cfg['collection']
c['daily_min_items']=20; c['daily_target_items']=30; c['daily_max_items']=30
c['completeness_trigger_total_items']=30
c['fill_target_policy']='Continue discovery through the configured fill ladder aiming for 30 total valid unpublished items after Published Intelligence Registry dedupe and Quality Gate. Twenty items is the release floor, not a discovery stop signal. Category counts are diversity diagnostics, not release quotas. After reasonable exhaustion of all configured tiers, 20-29 valid items may publish; never pad with duplicates, unverifiable claims or low-production-value filler.'
c['completeness_trigger_policy']='Release-ready when 20-30 valid unpublished items survive Published Intelligence Registry dedupe and Quality Gate after the configured discovery ladder has been reasonably exhausted. Target and maximum are 30. Category shortages do not block release and must never be padded.'
c['ranking_guidance']='Production value, practical applicability, source verifiability and freshness drive ranking. Aim for broad six-category coverage without enforcing equal quotas. Continue discovery toward 30 even after reaching the 20-item release floor.'
c['window_policy']['24h']='Prioritize fresh releases, changelogs, model/tool updates and meaningful production news. Fresh valid intelligence gets first claim on the daily ranked pool.'
cfgp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n','utf-8')

p=ROOT/'scripts/intelligence_v2.py'; s=p.read_text('utf-8')
s=s.replace("    if not (pool_min == pool_target == pool_max):\n        raise ValueError('V2 target-fill contract requires min == target == max')\n","")
old="    expected_total = pool_target * len(categories)\n    if int(collection.get('completeness_trigger_total_items', 0) or 0) != expected_total:\n        raise ValueError(f'V2 completeness trigger must equal category target total {expected_total}')\n"
new="    daily_min = int(collection.get('daily_min_items', 0) or 0)\n    daily_target = int(collection.get('daily_target_items', 0) or 0)\n    daily_max = int(collection.get('daily_max_items', 0) or 0)\n    if not (0 < daily_min <= daily_target <= daily_max):\n        raise ValueError('V2 daily totals must satisfy 0 < min <= target <= max')\n    if int(collection.get('completeness_trigger_total_items', 0) or 0) != daily_target:\n        raise ValueError(f'V2 completeness trigger must equal daily target {daily_target}')\n"
if old not in s: raise SystemExit('intelligence_v2 config block not found')
s=s.replace(old,new)
start=s.index("    if target_fill_applies(data, cfg) and strict_pool:\n"); end=s.index("    return errors\n",start)
repl="    if target_fill_applies(data, cfg) and strict_pool:\n        collection = cfg.get('collection') or {}\n        pool_max = int(cfg['category_pool_max_items'])\n        pool_min = int(cfg['category_pool_min_items'])\n        daily_min = int(collection['daily_min_items'])\n        daily_max = int(collection['daily_max_items'])\n    else:\n        metadata = data.get('metadata') or {}\n        pool_max = int(metadata.get('category_pool_max_items', 10) or 10)\n        pool_min = 0\n        daily_min = 0\n        daily_max = pool_max * len(categories)\n\n    for cid, pool in by_category.items():\n        if len(pool) > pool_max:\n            errors.append(f'{cid}: category pool exceeds maximum {pool_max}, got {len(pool)}')\n        if len(pool) < pool_min:\n            errors.append(f'{cid}: category pool below minimum {pool_min}, got {len(pool)}')\n    if len(items) < daily_min:\n        errors.append(f'V2 daily release minimum is {daily_min} items, got {len(items)}')\n    if len(items) > daily_max:\n        errors.append(f'V2 daily release maximum is {daily_max} items, got {len(items)}')\n"
s=s[:start]+repl+s[end:]; p.write_text(s,'utf-8')

p=ROOT/'scripts/normalize_registry_identity.py'; s=p.read_text('utf-8')
a=s.index('def category_deficits(cfg, items):'); b=s.index('\n\ndef main():',a)
s=s[:a]+"def daily_gate(cfg, items):\n    collection = cfg.get('collection') or {}\n    have = len(items)\n    minimum = int(collection['daily_min_items']); target = int(collection['daily_target_items']); maximum = int(collection['daily_max_items'])\n    counts = Counter(str(item.get('category', '')).strip() for item in items)\n    return {'have':have,'min':minimum,'target':target,'max':maximum,'missing_to_min':max(0,minimum-have),'missing_to_target':max(0,target-have),'release_ready':minimum <= have <= maximum,'category_counts':{c['id']:counts.get(c['id'],0) for c in cfg['categories']}}\n"+s[b:]
s=s.replace("    deficits = category_deficits(cfg, kept)\n","    gate = daily_gate(cfg, kept)\n")
s=s.replace("        'refill_required': bool(deficits),\n        'category_deficits': deficits,\n","        'refill_required': not gate['release_ready'],\n        'category_deficits': {},\n        'daily_release_gate': gate,\n")
old="    if deficits:\n        print('REGISTRY REFILL REQUIRED: collection is not release-ready')\n        for cid, rec in deficits.items():\n            print(f\"- {cid}: have={rec['have']} target={rec['target']} missing={rec['missing']}\")\n        print('Continue discovery through the configured fill ladder; do not create .ready yet.')\n        sys.exit(2)\n\n    print('REGISTRY REFILL COMPLETE: all category targets survive Published Intelligence Registry dedupe')\n"
new="    if gate['have'] > gate['max']:\n        print(f\"REGISTRY RELEASE BLOCKED: have={gate['have']} exceeds daily maximum={gate['max']}\"); sys.exit(1)\n    if gate['have'] < gate['min']:\n        print(f\"REGISTRY REFILL REQUIRED: have={gate['have']} minimum={gate['min']} missing={gate['missing_to_min']} target={gate['target']}\")\n        print('Continue discovery toward the daily target through the configured fill ladder; do not create .ready yet.'); sys.exit(2)\n    print(f\"REGISTRY RELEASE GATE PASS: have={gate['have']} minimum={gate['min']} target={gate['target']} maximum={gate['max']} category_counts={gate['category_counts']}\")\n"
if old not in s: raise SystemExit('normalizer exit block not found')
p.write_text(s.replace(old,new),'utf-8')

p=ROOT/'scripts/check_information_architecture.py'; s=p.read_text('utf-8')
s=s.replace("    pool_target = int(cfg['category_pool_target_items'])\n","")
s=s.replace("        if target_mode and len(cards) != pool_target: fail(f'{category[\"id\"]}: target-fill category page must contain exactly {pool_target} items, got {len(cards)}')\n","")
s=s.replace("    mode = f'exact {pool_target}/category target-fill' if target_mode else 'legacy variable-pool compatibility'\n","    col=cfg.get('collection') or {}; mode = f'daily {col.get(\"daily_min_items\")}-{col.get(\"daily_max_items\")} target {col.get(\"daily_target_items\")}' if target_mode else 'legacy variable-pool compatibility'\n")
p.write_text(s,'utf-8')

replace_required('scripts/check_release_input.py',"        target=int(cfg['category_pool_target_items']); categories=len(cfg['categories'])\n        mode=f'V2 {categories}x{target} target-fill / TOP5+next10' if target_fill_applies(data,cfg) else 'V2 legacy variable pools / TOP5+next10'\n","        col=cfg.get('collection') or {}\n        mode=f'V2 daily {col.get(\"daily_min_items\")}-{col.get(\"daily_max_items\")} target {col.get(\"daily_target_items\")} / TOP5+next10' if target_fill_applies(data,cfg) else 'V2 legacy variable pools / TOP5+next10'\n",'release input')
replace_required('scripts/check_pipeline_contract.py',"        target=int(cfg['category_pool_target_items']); expected_total=target*len(categories)\n        if int(collection.get('completeness_trigger_total_items',0))!=expected_total:\n            fail(f'V2 completeness trigger must equal configured category total {expected_total}')\n        candidate_target=int(collection.get('candidate_pool_target_per_category',0) or 0)\n        candidate_stretch=int(collection.get('candidate_pool_stretch_per_category',0) or 0)\n        if candidate_target<target: fail('V2 discovery candidate target must be >= configured publish target')\n","        soft_target=int(cfg['category_pool_target_items']); daily_target=int(collection.get('daily_target_items',0) or 0)\n        if int(collection.get('completeness_trigger_total_items',0))!=daily_target:\n            fail(f'V2 completeness trigger must equal configured daily target {daily_target}')\n        candidate_target=int(collection.get('candidate_pool_target_per_category',0) or 0)\n        candidate_stretch=int(collection.get('candidate_pool_stretch_per_category',0) or 0)\n        if candidate_target<soft_target: fail('V2 discovery candidate target must be >= category balancing target')\n",'pipeline contract')
p=ROOT/'scripts/check_pipeline_contract.py'; p.write_text(p.read_text('utf-8').replace('config-driven target-fill IA','config-driven daily 20-30 release-gate IA'),'utf-8')

# Replace collection synthetic test with a compact total-gate version.
test="""#!/usr/bin/env python3
from datetime import date,timedelta
from intelligence_v2 import load_config, validate_v2_dataset

def make(cfg,n):
    cats=cfg['categories']; top=int(cfg['homepage']['top5']); nxt=int(cfg['homepage']['next10']); items=[]
    for r in range(1,n+1):
        cat=cats[(r-1)%len(cats)]; tier='top5' if r<=top else ('next10' if r<=top+nxt else 'category_only')
        items.append({'id':f'dry-{r:02d}','title':f'Dry {r}','summary':'Synthetic production intelligence.','quick_impact':'Dry ★★★★☆','source_url':f'https://example.invalid/{r}','category':cat['id'],'subcategory':cat['subtypes'][0],'ranking_score':1000-r,'rank_global':r,'homepage_tier':tier,'full_analysis':[{'label':'製作流程','text':'Synthetic.'},{'label':'製作價值','text':'Synthetic.'},{'label':'導入測試','text':'Synthetic.'}]})
    return {'date':cfg['collection_contract_effective_date'],'schema_version':int(cfg.get('schema_version',3)),'metadata':{},'items':items}

def check(name,d,should_pass,fragment=''):
    e=validate_v2_dataset(d,strict_pool=True)
    if should_pass and e: raise AssertionError(f'{name} should pass: {e}')
    if not should_pass and not e: raise AssertionError(f'{name} should fail')
    if fragment and not any(fragment in x for x in e): raise AssertionError(f'{name} wrong failure: {e}')
    print(('PASS' if should_pass else 'FAIL expected'),name)

def main():
    cfg=load_config(); c=cfg['collection']; mn=int(c['daily_min_items']); tg=int(c['daily_target_items']); mx=int(c['daily_max_items'])
    check('target',make(cfg,tg),True); check('23 survivors',make(cfg,23),True); check('minimum',make(cfg,mn),True)
    check('below minimum',make(cfg,mn-1),False,'daily release minimum'); check('above maximum',make(cfg,mx+1),False,'daily release maximum')
    d=make(cfg,mn); d['items'][-1]['source_url']=d['items'][0]['source_url']; check('duplicate source',d,False,'duplicate source URL')
    d=make(cfg,mn); d['items'][-1]['rank_global']=999; check('bad rank',d,False,'contiguous')
    effective=date.fromisoformat(cfg['collection_contract_effective_date']); d=make(cfg,6); d['date']=(effective-timedelta(days=1)).isoformat(); d['metadata']={'category_pool_max_items':10}; check('historical compatibility',d,True)
    print(f'COLLECTION CONTRACT DRY RUN PASS: daily min={mn} target={tg} max={mx}; categories are non-blocking')
if __name__=='__main__': main()
"""
(ROOT/'scripts/check_collection_contract.py').write_text(test,'utf-8')
print('20-30 migration edits applied')
