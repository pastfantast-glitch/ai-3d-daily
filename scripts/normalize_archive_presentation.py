#!/usr/bin/env python3
"""Normalize archive presentation markup without changing intelligence content.

Historical reports are immutable content snapshots, while presentation and color
semantics are shared. This normalizer may repair presentation-only wrappers and
semantic classes, but never rewrites intelligence text, source URLs, IDs, or
analysis blocks.
"""
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
ARCHIVE_PRESENTATION_TOKEN = 'archive-p4-daily-structure-v1'
LEGACY_PILL_COLORS = {'purple','blue','green','orange','red'}


def add_class(tag, *names):
    if not tag: return
    classes=list(tag.get('class') or [])
    for name in names:
        if name not in classes: classes.append(name)
    tag['class']=classes


def set_shared_asset_token(soup):
    for tag in soup.find_all('link', href=True):
        href=tag.get('href','')
        if re.match(r'^\.\./(?:styles|daily)\.css(?:\?v=.*)?$', href):
            tag['href']=f"{href.split('?v=',1)[0]}?v={ARCHIVE_PRESENTATION_TOKEN}"
    for tag in soup.find_all('script', src=True):
        src=tag.get('src','')
        if re.match(r'^\.\./daily\.js(?:\?v=.*)?$', src):
            tag['src']=f"{src.split('?v=',1)[0]}?v={ARCHIVE_PRESENTATION_TOKEN}"


def normalize_section_header(soup, section, kicker):
    if not section: return
    add_class(section, 'block')
    if section.select_one(':scope > .block-head'):
        return
    heading=section.find('h2', recursive=False)
    if not heading:
        return
    wrapper=soup.new_tag('div', attrs={'class':'block-head'})
    inner=soup.new_tag('div')
    label=soup.new_tag('span', attrs={'class':'section-kicker'})
    label.string=kicker
    heading.insert_before(wrapper)
    wrapper.append(inner)
    inner.append(label)
    inner.append(heading.extract())


def normalize_top_card_structure(soup, card, rank):
    """Restore the canonical two-column Daily card shell without changing content."""
    add_class(card,'daily-card','daily-card-top')
    card['class']=[c for c in card.get('class',[]) if c!='important']

    news_main=card.find('div', class_='news-main', recursive=False)
    rank_node=card.find('div', class_='news-rank', recursive=False)

    if not news_main:
        news_main=soup.new_tag('div', attrs={'class':'news-main'})
        movable=[child for child in list(card.children) if getattr(child,'name',None) is not None and child is not rank_node]
        for child in movable:
            news_main.append(child.extract())
        card.append(news_main)

    if not rank_node:
        rank_node=soup.new_tag('div', attrs={'class':'news-rank'})
        rank_node.string=f'{rank:02d}'
        card.insert(0,rank_node)
    elif not rank_node.get_text(strip=True):
        rank_node.string=f'{rank:02d}'

    # The first descriptive paragraph is the canonical summary. Do not touch
    # quick-impact or analysis paragraphs.
    if not news_main.select_one('.summary'):
        for p in news_main.find_all('p', recursive=False):
            if 'quick-impact' not in (p.get('class') or []):
                add_class(p,'summary')
                break


def normalize(path: Path) -> bool:
    original=path.read_text('utf-8'); soup=BeautifulSoup(original,'html.parser'); body=soup.body
    if body is None: raise SystemExit(f'{path}: missing body')
    add_class(body,'archive-page'); add_class(soup.select_one('header.site-head'),'daily-hero'); add_class(soup.select_one('main.page'),'daily-main'); set_shared_asset_token(soup)

    top_section=soup.select_one('#top')
    more_section=soup.select_one('#more')
    normalize_section_header(soup,top_section,'TODAY')
    normalize_section_header(soup,more_section,'MORE')

    for rank,card in enumerate(soup.select('#top .news'),1):
        normalize_top_card_structure(soup,card,rank)
    for card in soup.select('.category-news'):
        add_class(card,'daily-card','daily-card-more')
        # Supplemental cards are single-column, but descriptive prose should
        # still use the shared summary semantic when present.
        if not card.select_one('.summary'):
            for p in card.find_all('p', recursive=False):
                if 'quick-impact' not in (p.get('class') or []):
                    add_class(p,'summary')
                    break

    for card in soup.select('[data-intel-role="card"]'):
        for pill in card.select('.pill'):
            pill['class']=[c for c in (pill.get('class') or []) if c not in LEGACY_PILL_COLORS]
            add_class(pill,'pill')
        for details in card.select('details'): add_class(details,'daily-full-analysis')
        for detail_body in card.select('.detail-body'): add_class(detail_body,'daily-analysis-body')
        for visual in card.select('figure.case-preview'): add_class(visual,'daily-visual')
        for impact in card.select('.quick-impact'): add_class(impact,'daily-impact')
        for source in card.select('a.source'): add_class(source,'daily-source')
    rendered=soup.prettify()
    if not rendered.endswith('\n'): rendered+='\n'
    if rendered!=original: path.write_text(rendered,'utf-8'); return True
    return False


def main():
    changed=[]
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and DATE_RE.fullmatch(d.name) and (d/'index.html').exists() and normalize(d/'index.html'): changed.append(d.name)
    print('ARCHIVE PRESENTATION NORMALIZED:', ', '.join(changed) if changed else 'already current')
    print('ARCHIVE PRESENTATION TOKEN:', ARCHIVE_PRESENTATION_TOKEN)

if __name__=='__main__': main()
