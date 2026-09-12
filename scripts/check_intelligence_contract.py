#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset, homepage_groups, category_items, load_config

ROOT=Path(__file__).resolve().parents[1]
DEPTH_PATH=ROOT/'config'/'full-analysis-depth.json'
errors=[]

def norm(s): return re.sub(r'\s+',' ',str(s or '')).strip()
def char_count(s): return len(re.sub(r'\s+','',norm(s)))
def canonical_text(record): return norm(' '.join(f"{b['label']} {b['text']}" for b in record.get('full_analysis',[])))
def has_han(s): return bool(re.search(r'[\u3400-\u4dbf\u4e00-\u9fff]',norm(s)))
def level(record): return norm(record.get('analysis_level') or 'FULL').upper()

def is_done(date):
    path=ROOT/'data'/'publish'/f'{date}.done.json'
    if not path.exists(): return False
    try: return str(json.loads(path.read_text('utf-8')).get('state','')).strip().upper()=='DONE'
    except Exception: return False

def inspect_cards(date,name,path,selector,recs,expected_ids):
    seen={}
    if not path.exists(): errors.append(f'{date} {name}: page missing'); return seen
    soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    for card in soup.select(selector):
        rid=card.get('data-intel-id')
        if rid not in recs: continue
        details=card.find('details'); body=details.find('div',class_='detail-body') if details else None
        if not details: errors.append(f'{date} {name}: {rid} missing analysis details'); continue
        if not body: errors.append(f'{date} {name}: {rid} missing detail-body'); continue
        record=recs[rid]; blocks=record.get('full_analysis',[])
        expected_level=level(record)
        rendered_level=str(details.get('data-analysis-level') or 'FULL').upper()
        if date >= '2026-09-12' and rendered_level!=expected_level:
            errors.append(f'{date} {name}: {rid} rendered analysis level {rendered_level} != {expected_level}')
        headings=body.find_all('h4',recursive=False)
        paragraphs=[p for p in body.find_all('p',recursive=False) if 'analysis-level-note' not in (p.get('class') or [])]
        if len(headings)!=len(blocks) or len(paragraphs)!=len(blocks): errors.append(f'{date} {name}: {rid} semantic block count mismatch')
        else:
            for i,block in enumerate(blocks):
                if norm(headings[i].get_text(' ',strip=True))!=norm(block.get('label')): errors.append(f'{date} {name}: {rid} heading mismatch at block {i+1}')
                if norm(paragraphs[i].get_text(' ',strip=True))!=norm(block.get('text')): errors.append(f'{date} {name}: {rid} paragraph mismatch at block {i+1}')
        rendered=norm(' '.join(x.get_text(' ',strip=True) for pair in zip(headings,paragraphs) for x in pair))
        if rendered!=canonical_text(record): errors.append(f'{date} {name}: {rid} rendered analysis differs from canonical data')
        seen[rid]=rendered
    missing=set(expected_ids)-set(seen)
    if missing: errors.append(f'{date} {name}: missing expected IDs: {sorted(missing)}')
    extra=set(seen)-set(expected_ids)
    if extra: errors.append(f'{date} {name}: unexpected IDs: {sorted(extra)}')
    return seen

def validate_blocks(date,rid,record,min_blocks,max_blocks,min_block_chars,min_total_chars,require_semantics,depth_cfg):
    blocks=record.get('full_analysis',[])
    if len(blocks)<min_blocks: errors.append(f'{date}: {rid} analysis must have >={min_blocks} structured blocks')
    if max_blocks and len(blocks)>max_blocks: errors.append(f'{date}: {rid} analysis must have <={max_blocks} structured blocks')
    labels=[]; texts=[]; total=0
    for i,block in enumerate(blocks,1):
        label=norm(block.get('label')); text=norm(block.get('text')); n=char_count(text); total+=n
        if not label or not text: errors.append(f'{date}: {rid} block {i} requires non-empty label and text')
        if label and not has_han(label): errors.append(f'{date}: {rid} block {i} heading must use Traditional Chinese')
        if min_block_chars and n<min_block_chars: errors.append(f'{date}: {rid} block {i} too shallow ({n}<{min_block_chars})')
        labels.append(label.casefold()); texts.append(text.casefold())
    if len(set(labels))!=len(labels): errors.append(f'{date}: {rid} analysis headings must be distinct')
    if len(set(texts))!=len(texts): errors.append(f'{date}: {rid} analysis text contains duplicates')
    if min_total_chars and total<min_total_chars: errors.append(f'{date}: {rid} total analysis depth too shallow ({total}<{min_total_chars})')
    summary=norm(record.get('summary')).casefold()
    for i,text in enumerate(texts,1):
        if text and text==summary: errors.append(f'{date}: {rid} block {i} merely repeats summary')
    joined=' '.join(norm(b.get('label')) for b in blocks if isinstance(b,dict))
    semantic=depth_cfg.get('required_semantic_groups') or {}
    for group in require_semantics:
        if not any(str(k) in joined for k in semantic.get(group,[])):
            errors.append(f'{date}: {rid} FULL analysis missing semantic angle: {group}')

def validate_depth(date,rid,record,cfg,depth_cfg):
    if date < str(depth_cfg.get('effective_date','9999-12-31')):
        return
    tiered=date>=str(depth_cfg.get('tiered_effective_date','9999-12-31'))
    lv=level(record) if tiered else 'FULL'
    if lv=='REJECT':
        errors.append(f'{date}: {rid} REJECT item cannot be published'); return
    if lv not in {'FULL','BRIEF'}:
        errors.append(f'{date}: {rid} invalid analysis_level={lv}'); return
    if lv=='BRIEF':
        brief=depth_cfg.get('brief') or {}
        reason=norm(record.get('brief_reason'))
        allowed=set(brief.get('allowed_reasons') or [])
        if not reason: errors.append(f'{date}: {rid} BRIEF requires brief_reason')
        elif allowed and reason not in allowed: errors.append(f'{date}: {rid} invalid brief_reason={reason}')
        if norm(record.get('homepage_tier')).lower()=='top5' and not (depth_cfg.get('top5_policy') or {}).get('allow_brief',False):
            errors.append(f'{date}: {rid} BRIEF cannot be homepage TOP5')
        validate_blocks(date,rid,record,int(brief.get('min_blocks',1)),int(brief.get('max_blocks',2)),int(brief.get('min_block_chars',36)),int(brief.get('min_total_text_chars',60)),[],depth_cfg)
    else:
        full=depth_cfg.get('full') or {}
        if not full:
            full={'min_blocks':3,'max_blocks':5,'min_block_chars':48,'min_total_text_chars':180,'required_semantic_groups':['workflow_or_technical_change','production_impact','test_risk_or_limit']}
        validate_blocks(date,rid,record,int(full.get('min_blocks',3)),int(full.get('max_blocks',5)),int(full.get('min_block_chars',48)),int(full.get('min_total_text_chars',180)),full.get('required_semantic_groups') or [],depth_cfg)

def default_candidate():
    dates=sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: return ''
    latest=dates[-1]
    return latest if not is_done(latest) else ''

def selected_dates(candidate=''):
    out=[]
    for p in sorted((ROOT/'data'/'daily').glob('20??-??-??.json')):
        if is_done(p.stem) or p.stem==candidate: out.append(p.stem)
    return out

def main():
    candidate=sys.argv[1] if len(sys.argv)>1 else default_candidate()
    if candidate and not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',candidate): raise SystemExit('Usage: check_intelligence_contract.py [YYYY-MM-DD]')
    if candidate and not (ROOT/'data'/'daily'/f'{candidate}.json').exists(): raise SystemExit(f'Missing candidate canonical dataset: {candidate}')
    dates=selected_dates(candidate); cfg=load_config(); depth_cfg=json.loads(DEPTH_PATH.read_text('utf-8'))
    current=candidate or (dates[-1] if dates else '')
    for date in dates:
        data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8')); recs={x['id']:x for x in data['items']}
        if is_v2_dataset(data):
            top,next10=homepage_groups(data); selected=[x['id'] for x in top+next10]
            daily=inspect_cards(date,'daily',ROOT/date/'index.html','#top .news[data-intel-role="card"][data-intel-id], #more .daily-card-more[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]',recs,selected)
            if date==current:
                home=inspect_cards(date,'home',ROOT/'index.html','.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]',recs,selected)
                for rid in selected:
                    if home.get(rid)!=daily.get(rid): errors.append(f'{date}: home/daily analysis drift for {rid}')
            for cat in cfg['categories']:
                expected=[x['id'] for x in category_items(data,cat['id'])]
                inspect_cards(date,f'category:{cat["id"]}',ROOT/date/cat['id']/'index.html','.category-card[data-intel-role="card"][data-intel-id]',recs,expected)
        for rid,record in recs.items():
            validate_depth(date,rid,record,cfg,depth_cfg)
    if errors:
        print('INTELLIGENCE CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
    scope=f'DONE history + candidate {candidate}' if candidate else 'DONE history only'
    print(f'INTELLIGENCE CONTRACT PASS: {scope}')
if __name__=='__main__': main()
