#!/usr/bin/env python3
"""Normalize shared homepage/archive presentation without changing intelligence content.

Historical reports are immutable content snapshots, while presentation and color
semantics are shared. This normalizer may repair presentation-only wrappers,
semantic classes, heading tags, rank labels, navigation chrome, and Quick Impact
wrappers, but never rewrites intelligence text, source URLs, IDs, or analysis blocks.
"""
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
ARCHIVE_PRESENTATION_TOKEN = 'archive-p16-persistent-history-shell-v1'
LEGACY_PILL_COLORS = {'purple','blue','green','orange','red'}
CATEGORY_NAV = [('ai-generation','AI 生成'),('3d-production','3D 製作'),('3d-animation','3D 動作'),('engine-art','遊戲引擎'),('emerging-case','新技術 / Case'),('blender-dcc','Blender / DCC')]

def add_class(tag,*names):
    if not tag:return
    classes=list(tag.get('class') or [])
    for name in names:
        if name not in classes:classes.append(name)
    tag['class']=classes

def remove_classes(tag,*names):
    if not tag:return
    blocked=set(names);tag['class']=[c for c in (tag.get('class') or []) if c not in blocked]

def normalize_quick_impact_structure(soup,impact):
    if not impact or impact.find_all('span',recursive=False):return
    children=list(impact.contents)
    if not children:return
    wrapper=soup.new_tag('span')
    for child in children:wrapper.append(child.extract())
    impact.append(wrapper)

def set_shared_asset_token(soup):
    for tag in soup.find_all('link',href=True):
        href=tag.get('href','')
        if re.match(r'^\.\./(?:styles|shared-components|daily)\.css(?:\?v=.*)?$',href):tag['href']=f"{href.split('?v=',1)[0]}?v={ARCHIVE_PRESENTATION_TOKEN}"
    for tag in soup.find_all('script',src=True):
        src=tag.get('src','')
        if re.match(r'^\.\./daily\.js(?:\?v=.*)?$',src):tag['src']=f"{src.split('?v=',1)[0]}?v={ARCHIVE_PRESENTATION_TOKEN}"

def ensure_shared_category_nav(soup):
    body=soup.body
    if not body:return
    for legacy in soup.select('.dailybar'):legacy.decompose()
    nav=soup.select_one('nav.global-category-nav')
    if not nav:
        nav=soup.new_tag('nav',attrs={'class':'global-category-nav','aria-label':'Production Intelligence 分類'});inner=soup.new_tag('div',attrs={'class':'page global-category-nav-inner'});nav.append(inner)
        top_link=soup.new_tag('a',attrs={'class':'global-category-link is-active','href':'#top'});top_link.string='TOP5';inner.append(top_link)
        for slug,label in CATEGORY_NAV:
            link=soup.new_tag('a',attrs={'class':'global-category-link','data-category':slug,'href':f'{slug}/'});link.string=label;inner.append(link)
        header=soup.select_one('header.site-head, header.daily-hero')
        if header:header.insert_after(nav)
        else:
            main=soup.select_one('main')
            if main:main.insert_before(nav)
            else:body.insert(0,nav)
    else:
        add_class(nav,'global-category-nav');inner=nav.select_one('.global-category-nav-inner');add_class(inner,'page','global-category-nav-inner');links=nav.select('.global-category-link')
        if links:
            for link in links:remove_classes(link,'is-active')
            add_class(links[0],'is-active');links[0]['href']='#top'

def normalize_section_header(soup,section,kicker):
    if not section:return
    add_class(section,'block')
    if section.select_one(':scope > .block-head'):return
    heading=section.find('h2',recursive=False)
    if not heading:return
    wrapper=soup.new_tag('div',attrs={'class':'block-head'});inner=soup.new_tag('div');label=soup.new_tag('span',attrs={'class':'section-kicker'});label.string=kicker
    heading.insert_before(wrapper);wrapper.append(inner);inner.append(label);inner.append(heading.extract())

def normalize_home_top_card_structure(soup,card,rank):
    add_class(card,'top-item');rank_node=card.find('div',class_='top-no',recursive=False);main_node=card.find('div',class_='top-main',recursive=False)
    if not rank_node:rank_node=soup.new_tag('div',attrs={'class':'top-no'});card.insert(0,rank_node)
    rank_node.string=f'{rank:02d}'
    if not main_node:
        main_node=soup.new_tag('div',attrs={'class':'top-main'});movable=[child for child in list(card.children) if getattr(child,'name',None) is not None and child is not rank_node]
        for child in movable:main_node.append(child.extract())
        card.append(main_node)
    title=main_node.find(['h2','h3'],recursive=False)
    if title and title.name!='h2':title.name='h2'
    normalize_quick_impact_structure(soup,main_node.select_one('.quick-impact'))

def normalize_homepage():
    path=ROOT/'index.html'
    if not path.exists():return False
    original=path.read_text('utf-8');soup=BeautifulSoup(original,'html.parser');today=soup.select_one('#today')
    if not today:return False
    container=today.select_one('.top-list') or today.select_one('.today-grid');add_class(container,'top-list');cards=today.select('[data-intel-role="card"][data-intel-id]')
    for rank,card in enumerate(cards,1):normalize_home_top_card_structure(soup,card,rank)
    for impact in soup.select('.home-page .quick-impact'):normalize_quick_impact_structure(soup,impact)
    rendered=soup.prettify();rendered=rendered if rendered.endswith('\n') else rendered+'\n'
    if rendered!=original:path.write_text(rendered,'utf-8');return True
    return False

def normalize_top_card_structure(soup,card,rank):
    add_class(card,'daily-card','daily-card-top');remove_classes(card,'important');news_main=card.find('div',class_='news-main',recursive=False);rank_node=card.find('div',class_='news-rank',recursive=False)
    if not news_main:
        news_main=soup.new_tag('div',attrs={'class':'news-main'});movable=[child for child in list(card.children) if getattr(child,'name',None) is not None and child is not rank_node]
        for child in movable:news_main.append(child.extract())
        card.append(news_main)
    if not rank_node:rank_node=soup.new_tag('div',attrs={'class':'news-rank'});card.insert(0,rank_node)
    rank_node.string=f'{rank:02d}'
    if not news_main.select_one('.summary'):
        for p in news_main.find_all('p',recursive=False):
            if 'quick-impact' not in (p.get('class') or []):add_class(p,'summary');break
    normalize_quick_impact_structure(soup,news_main.select_one('.quick-impact'))

def normalize_more_card_structure(soup,card):
    remove_classes(card,'news','important','daily-card-top');add_class(card,'category-news','daily-card','daily-card-more');rank_node=card.find('div',class_='news-rank',recursive=False)
    if rank_node:rank_node.decompose()
    main_node=card.find('div',class_='news-main',recursive=False)
    if main_node:
        insert_at=list(card.children).index(main_node);children=list(main_node.children);main_node.extract()
        for child in reversed(children):card.insert(insert_at,child)
    if not card.select_one('.summary'):
        for p in card.find_all('p',recursive=False):
            if 'quick-impact' not in (p.get('class') or []):add_class(p,'summary');break
    normalize_quick_impact_structure(soup,card.select_one('.quick-impact'))

def normalize(path):
    original=path.read_text('utf-8');soup=BeautifulSoup(original,'html.parser');body=soup.body
    if body is None:raise SystemExit(f'{path}: missing body')
    add_class(body,'archive-page');add_class(soup.select_one('header.site-head'),'daily-hero');add_class(soup.select_one('main.page'),'daily-main');set_shared_asset_token(soup);ensure_shared_category_nav(soup)
    top_section=soup.select_one('#top');more_section=soup.select_one('#more');normalize_section_header(soup,top_section,'TODAY');normalize_section_header(soup,more_section,'MORE')
    for rank,card in enumerate(soup.select('#top .news'),1):normalize_top_card_structure(soup,card,rank)
    if more_section:
        seen=set();more_cards=[]
        for card in more_section.select('.category-news, .news'):
            ident=id(card)
            if ident not in seen:seen.add(ident);more_cards.append(card)
        for card in more_cards:normalize_more_card_structure(soup,card)
    for card in soup.select('[data-intel-role="card"]'):
        for pill in card.select('.pill'):pill['class']=[c for c in (pill.get('class') or []) if c not in LEGACY_PILL_COLORS];add_class(pill,'pill')
        for details in card.select('details'):add_class(details,'daily-full-analysis')
        for detail_body in card.select('.detail-body'):add_class(detail_body,'daily-analysis-body')
        for visual in card.select('figure.case-preview'):add_class(visual,'daily-visual')
        for impact in card.select('.quick-impact'):add_class(impact,'daily-impact');normalize_quick_impact_structure(soup,impact)
        for source in card.select('a.source'):add_class(source,'daily-source')
    rendered=soup.prettify();rendered=rendered if rendered.endswith('\n') else rendered+'\n'
    if rendered!=original:path.write_text(rendered,'utf-8');return True
    return False

def main():
    homepage_changed=normalize_homepage();changed=[]
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and DATE_RE.fullmatch(d.name) and (d/'index.html').exists() and normalize(d/'index.html'):changed.append(d.name)
    print('HOMEPAGE TOP PRESENTATION NORMALIZED:','changed' if homepage_changed else 'already current');print('ARCHIVE PRESENTATION NORMALIZED:',', '.join(changed) if changed else 'already current');print('ARCHIVE PRESENTATION TOKEN:',ARCHIVE_PRESENTATION_TOKEN)

if __name__=='__main__':main()
