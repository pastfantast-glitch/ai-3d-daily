#!/usr/bin/env python3
from pathlib import Path
import re,sys
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$'); errors=[]
dirs=sorted(p for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
for i,d in enumerate(dirs):
    text=(d/'index.html').read_text('utf-8'); soup=BeautifulSoup(text,'html.parser'); date=d.name
    def need(ok,msg):
        if not ok: errors.append(f'{date}: {msg}')
    need('null' not in text.lower(),'literal null present')
    need('archive-page' in soup.body.get('class',[]),'missing archive-page class')
    need(soup.body.get('data-report-date')==date,'report date contract mismatch')
    need(bool(soup.find('link',href=re.compile(r'\.\./styles\.css\?v='))),'missing shared styles.css')
    need(bool(soup.find('link',href=re.compile(r'\.\./daily\.css\?v='))),'missing daily.css')
    need(bool(soup.find('script',src=re.compile(r'\.\./daily\.js\?v='))),'missing daily.js')
    need(not soup.find('script',src=re.compile(r'accordion\.js')),'legacy accordion.js still referenced')

    header=soup.select_one('header.site-head')
    main=soup.select_one('main.page')
    need(bool(header and 'daily-hero' in header.get('class',[])),'missing shared daily-hero presentation class')
    need(bool(main and 'daily-main' in main.get('class',[])),'missing shared daily-main presentation class')

    top_cards=soup.select('#top .news')
    need(len(top_cards)==5,f'TOP section must contain exactly 5 cards, got {len(top_cards)}')
    more_cards=soup.select('.category-news')
    for card in top_cards:
        classes=set(card.get('class',[]))
        need({'daily-card','daily-card-top'}<=classes,'TOP card missing shared daily-card presentation classes')
        need('important' not in classes,'legacy important presentation modifier returned')
    for card in more_cards:
        classes=set(card.get('class',[]))
        need({'daily-card','daily-card-more'}<=classes,'Supplemental card missing shared daily-card presentation classes')

    # Presentation QA validates the class of an element when that element exists.
    # Whether legacy snapshot content contains a source/impact/details block is an
    # intelligence/content contract concern, not a reason to rewrite old history.
    for card in soup.select('[data-intel-role="card"]'):
        rid=card.get('data-intel-id','?')
        details=card.select_one('details')
        if details: need('daily-full-analysis' in details.get('class',[]),f'{rid}: details missing daily-full-analysis class')
        body=card.select_one('.detail-body')
        if body: need('daily-analysis-body' in body.get('class',[]),f'{rid}: detail-body missing daily-analysis-body class')
        source=card.select_one('a.source')
        if source: need('daily-source' in source.get('class',[]),f'{rid}: source missing daily-source class')
        impact=card.select_one('.quick-impact')
        if impact: need('daily-impact' in impact.get('class',[]),f'{rid}: quick-impact missing daily-impact class')
        visual=card.select_one('figure.case-preview')
        if visual: need('daily-visual' in visual.get('class',[]),f'{rid}: visual missing daily-visual class')

    for a in soup.find_all('a',target='_blank'):
        rel=set(a.get('rel',[])); need({'noopener','noreferrer'}<=rel,'unsafe target=_blank link')
    expected_prev=dirs[i-1].name if i else '' ; expected_next=dirs[i+1].name if i+1<len(dirs) else ''
    need(soup.body.get('data-previous','')==expected_prev,'previous date mismatch')
    need(soup.body.get('data-next','')==expected_next,'next date mismatch')
if errors:
    print('DAILY CONTRACT FAILED');print('\n'.join('- '+e for e in errors));sys.exit(1)
print(f'DAILY CONTRACT PASS: {len(dirs)} reports / shared presentation contract v2')
