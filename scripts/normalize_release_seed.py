#!/usr/bin/env python3
"""Synchronize current Homepage/Daily release seed from canonical intelligence.

Only the current release seed is regenerated. Historical intelligence remains
immutable. Presentation/runtime classes are normalized here so release preflight
validates the same canonical IDs, order, source URLs and Full Analysis shells
that downstream renderers consume.
"""
from pathlib import Path
import json, sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

def add_class(tag, *names):
    if not tag: return
    classes=list(tag.get('class') or [])
    for name in names:
        if name not in classes: classes.append(name)
    tag['class']=classes

def selected(data):
    items=sorted(data.get('items') or [], key=lambda x:int(x.get('rank_global',999999)))
    top=[x for x in items if x.get('homepage_tier')=='top5']
    more=[x for x in items if x.get('homepage_tier')=='next10']
    return top,more

def analysis_details(soup,item,home=False):
    details=soup.new_tag('details')
    add_class(details,'home-full-analysis' if home else 'daily-full-analysis')
    summary=soup.new_tag('summary'); summary.string='完整分析'; details.append(summary)
    body=soup.new_tag('div'); add_class(body,'detail-body','home-analysis-body' if home else 'daily-analysis-body')
    for block in item.get('full_analysis') or []:
        h=soup.new_tag('h4'); h.string=str(block.get('label','')).strip(); body.append(h)
        p=soup.new_tag('p'); p.string=str(block.get('text','')).strip(); body.append(p)
    details.append(body); return details

def meta_row(soup,item):
    meta=soup.new_tag('div'); add_class(meta,'meta')
    pill=soup.new_tag('span'); add_class(pill,'pill'); pill.string=str(item.get('subcategory') or item.get('category') or '')
    meta.append(pill)
    status=item.get('status')
    if status:
        badge=soup.new_tag('span'); add_class(badge,'news-status',f"status-{str(status).lower()}")
        badge.string=str(status); meta.append(badge)
    return meta

def quick_impact(soup,item,home=False):
    q=soup.new_tag('div'); add_class(q,'quick-impact')
    if not home: add_class(q,'daily-impact')
    span=soup.new_tag('span'); span.string=str(item.get('quick_impact') or '')
    q.append(span); return q

def source_link(soup,item,daily=False):
    a=soup.new_tag('a',href=str(item.get('source_url') or '')); add_class(a,'source')
    if daily: add_class(a,'daily-source')
    a.string='來源'; return a

def home_top_card(soup,item,rank):
    card=soup.new_tag('article'); add_class(card,'top-item')
    card['data-intel-id']=item['id']; card['data-intel-role']='card'
    no=soup.new_tag('div'); add_class(no,'top-no'); no.string=f'{rank:02d}'; card.append(no)
    main=soup.new_tag('div'); add_class(main,'top-main')
    main.append(meta_row(soup,item))
    h=soup.new_tag('h2'); h.string=item['title']; main.append(h)
    p=soup.new_tag('p'); p.string=item['summary']; main.append(p)
    main.append(quick_impact(soup,item,home=True))
    main.append(analysis_details(soup,item,home=True))
    main.append(source_link(soup,item))
    card.append(main); return card

def home_more_card(soup,item):
    card=soup.new_tag('article'); add_class(card,'more-card')
    card['data-intel-id']=item['id']; card['data-intel-role']='card'
    card.append(meta_row(soup,item))
    h=soup.new_tag('h3'); h.string=item['title']; card.append(h)
    p=soup.new_tag('p'); p.string=item['summary']; card.append(p)
    card.append(quick_impact(soup,item,home=True))
    card.append(analysis_details(soup,item,home=True))
    card.append(source_link(soup,item))
    return card

def daily_top_card(soup,item,rank):
    card=soup.new_tag('article'); add_class(card,'news','daily-card','daily-card-top')
    card['data-intel-id']=item['id']; card['data-intel-role']='card'
    no=soup.new_tag('div'); add_class(no,'news-rank'); no.string=f'{rank:02d}'; card.append(no)
    main=soup.new_tag('div'); add_class(main,'news-main')
    main.append(meta_row(soup,item))
    h=soup.new_tag('h3'); h.string=item['title']; main.append(h)
    p=soup.new_tag('p'); add_class(p,'summary'); p.string=item['summary']; main.append(p)
    main.append(quick_impact(soup,item))
    main.append(analysis_details(soup,item))
    main.append(source_link(soup,item,daily=True))
    card.append(main); return card

def daily_more_card(soup,item):
    card=soup.new_tag('article'); add_class(card,'category-news','daily-card','daily-card-more')
    card['data-intel-id']=item['id']; card['data-intel-role']='card'
    card.append(meta_row(soup,item))
    h=soup.new_tag('h4'); h.string=item['title']; card.append(h)
    p=soup.new_tag('p'); add_class(p,'summary'); p.string=item['summary']; card.append(p)
    card.append(quick_impact(soup,item))
    card.append(analysis_details(soup,item))
    card.append(source_link(soup,item,daily=True))
    return card

def ensure_section(soup,sid,after=None):
    section=soup.select_one(f'#{sid}')
    if section: return section
    section=soup.new_tag('section',id=sid); add_class(section,'block')
    if after: after.insert_after(section)
    else: (soup.select_one('main') or soup.body).append(section)
    return section

def normalize_home(date,data):
    path=ROOT/'index.html'; soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    add_class(soup.body,'home-page'); add_class(soup.select_one('main'),'page','home-main')
    marker=soup.select_one('.week-asof')
    if not marker:
        marker=soup.new_tag('span'); add_class(marker,'week-asof')
        (soup.select_one('.home-hero .page') or soup.body).append(marker)
    marker.string=date
    top,more=selected(data)

    today=ensure_section(soup,'today'); add_class(today,'home-section','today-section')
    container=today.select_one('.top-list') or today.select_one('.today-grid')
    if not container:
        container=soup.new_tag('div'); add_class(container,'top-list'); today.append(container)
    add_class(container,'top-list')
    for old in list(container.select(':scope > [data-intel-role="card"], :scope > .top-item')): old.decompose()
    for rank,item in enumerate(top,1): container.append(home_top_card(soup,item,rank))

    more_sec=ensure_section(soup,'more',today); add_class(more_sec,'home-section','more-section')
    grid=more_sec.select_one('.more-grid')
    if not grid:
        grid=soup.new_tag('div'); add_class(grid,'more-grid'); more_sec.append(grid)
    for old in list(grid.select(':scope > [data-intel-role="card"], :scope > .more-card')): old.decompose()
    for item in more: grid.append(home_more_card(soup,item))

    for sid,role in [('test','test-section'),('history','history-section')]:
        add_class(soup.select_one(f'#{sid}'),'home-section',role)
    path.write_text(soup.prettify()+'\n','utf-8')

def normalize_daily(date,data):
    path=ROOT/date/'index.html'; soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    add_class(soup.body,'archive-page'); soup.body['data-report-date']=date
    add_class(soup.select_one('header.site-head'),'daily-hero'); add_class(soup.select_one('main.page'),'daily-main')
    top,more=selected(data)

    top_sec=ensure_section(soup,'top'); add_class(top_sec,'block')
    for old in list(top_sec.select(':scope > .news, :scope > [data-intel-role="card"]')): old.decompose()
    for rank,item in enumerate(top,1): top_sec.append(daily_top_card(soup,item,rank))

    more_sec=ensure_section(soup,'more',top_sec); add_class(more_sec,'block')
    for old in list(more_sec.select(':scope > .news, :scope > .category-news, :scope > [data-intel-role="card"]')): old.decompose()
    for item in more: more_sec.append(daily_more_card(soup,item))
    path.write_text(soup.prettify()+'\n','utf-8')

def main():
    if len(sys.argv)<2: raise SystemExit('usage: normalize_release_seed.py YYYY-MM-DD')
    date=sys.argv[1]
    data=json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    normalize_home(date,data); normalize_daily(date,data)
    top,more=selected(data)
    print(f'RELEASE SEED SYNCHRONIZED: {date} / TOP={len(top)} / NEXT={len(more)} / canonical IDs+order+copy')

if __name__=='__main__': main()
