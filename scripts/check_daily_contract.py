#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
from bs4 import BeautifulSoup
from intelligence_v2 import is_v2_dataset, homepage_groups
ROOT=Path(__file__).resolve().parents[1]; DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$'); errors=[]
LEGACY_PILL_COLORS={'purple','blue','green','orange','red'}
dirs=sorted(p for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
for i,d in enumerate(dirs):
    text=(d/'index.html').read_text('utf-8'); soup=BeautifulSoup(text,'html.parser'); date=d.name
    data_path=ROOT/'data'/'daily'/f'{date}.json'; data=json.loads(data_path.read_text('utf-8')) if data_path.exists() else {}; v2=is_v2_dataset(data)
    def need(ok,msg):
        if not ok: errors.append(f'{date}: {msg}')
    need('null' not in text.lower(),'literal null present'); need('archive-page' in soup.body.get('class',[]),'missing archive-page class'); need(soup.body.get('data-report-date')==date,'report date contract mismatch')
    need(bool(soup.find('link',href=re.compile(r'\.\./styles\.css\?v='))),'missing shared styles.css'); need(bool(soup.find('link',href=re.compile(r'\.\./daily\.css\?v='))),'missing daily.css'); need(bool(soup.find('script',src=re.compile(r'\.\./daily\.js\?v='))),'missing daily.js'); need(not soup.find('script',src=re.compile(r'accordion\.js')),'legacy accordion.js still referenced')
    header=soup.select_one('header.site-head'); main=soup.select_one('main.page'); need(bool(header and 'daily-hero' in header.get('class',[])),'missing shared daily-hero presentation class'); need(bool(main and 'daily-main' in main.get('class',[])),'missing shared daily-main presentation class')

    top_section=soup.select_one('#top'); more_section=soup.select_one('#more')
    need(bool(top_section and 'block' in top_section.get('class',[])),'TOP section missing shared block presentation class')
    if more_section: need('block' in more_section.get('class',[]),'Supplemental section missing shared block presentation class')
    if top_section: need(bool(top_section.select_one(':scope > .block-head')),'TOP section missing block-head')
    if more_section: need(bool(more_section.select_one(':scope > .block-head')),'Supplemental section missing block-head')

    top_cards=soup.select('#top .news'); more_cards=soup.select('.category-news')
    if v2:
        expected_top,expected_next=homepage_groups(data)
        need(len(top_cards)==len(expected_top),f'V2 TOP section must match available canonical ranks 1-5, got {len(top_cards)} != {len(expected_top)}')
        need(len(more_cards)==len(expected_next),f'V2 next10 section must match available canonical ranks 6-15, got {len(more_cards)} != {len(expected_next)}')
    else:
        need(len(top_cards)==5,f'legacy TOP section must contain exactly 5 cards, got {len(top_cards)}')
    for rank,card in enumerate(top_cards,1):
        classes=set(card.get('class',[])); need({'daily-card','daily-card-top'}<=classes,'TOP card missing shared daily-card presentation classes'); need('important' not in classes,'legacy important presentation modifier returned')
        rank_node=card.find('div',class_='news-rank',recursive=False); main_node=card.find('div',class_='news-main',recursive=False)
        need(bool(rank_node),f'TOP {rank}: missing news-rank presentation column')
        need(bool(main_node),f'TOP {rank}: missing news-main presentation column')
        if rank_node: need(rank_node.get_text(strip=True)==f'{rank:02d}',f'TOP {rank}: rank label mismatch')
        if main_node:
            need(bool(main_node.find(['h3','h4'],recursive=False)),f'TOP {rank}: news-main missing title')
            need(bool(main_node.select_one('.quick-impact')),f'TOP {rank}: news-main missing quick-impact')
            need(bool(main_node.select_one('details.daily-full-analysis')),f'TOP {rank}: news-main missing Full Analysis')
            need(bool(main_node.select_one('a.source.daily-source')),f'TOP {rank}: news-main missing source')
    for card in more_cards: need({'daily-card','daily-card-more'}<=set(card.get('class',[])),'Supplemental card missing shared daily-card presentation classes')

    for card in soup.select('[data-intel-role="card"]'):
        rid=card.get('data-intel-id','?')
        for pill in card.select('.pill'):
            legacy=LEGACY_PILL_COLORS & set(pill.get('class',[])); need(not legacy,f'{rid}: legacy pill color class returned: {sorted(legacy)}')
        details=card.select_one('details'); body=card.select_one('.detail-body'); source=card.select_one('a.source'); impact=card.select_one('.quick-impact'); visual=card.select_one('figure.case-preview')
        if details: need('daily-full-analysis' in details.get('class',[]),f'{rid}: details missing daily-full-analysis class')
        if body: need('daily-analysis-body' in body.get('class',[]),f'{rid}: detail-body missing daily-analysis-body class')
        if source: need('daily-source' in source.get('class',[]),f'{rid}: source missing daily-source class')
        if impact: need('daily-impact' in impact.get('class',[]),f'{rid}: quick-impact missing daily-impact class')
        if visual: need('daily-visual' in visual.get('class',[]),f'{rid}: visual missing daily-visual class')
    for a in soup.find_all('a',target='_blank'): need({'noopener','noreferrer'}<=set(a.get('rel',[])),'unsafe target=_blank link')
    expected_prev=dirs[i-1].name if i else ''; expected_next=dirs[i+1].name if i+1<len(dirs) else ''; need(soup.body.get('data-previous','')==expected_prev,'previous date mismatch'); need(soup.body.get('data-next','')==expected_next,'next date mismatch')
if errors: print('DAILY CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
print(f'DAILY CONTRACT PASS: {len(dirs)} reports / V2 variable TOP5+next10 + shared presentation v3 + canonical card structure')
