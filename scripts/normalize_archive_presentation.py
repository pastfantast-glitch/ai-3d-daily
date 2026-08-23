#!/usr/bin/env python3
"""Normalize archive presentation markup without changing intelligence content.

Historical reports are immutable content snapshots, but their presentation layer is
shared. This script adds the current semantic Daily Presentation Contract classes,
removes legacy presentation-only emphasis, and refreshes historical shared-asset
cache tokens so old archives actually receive the current design system.
"""
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
ARCHIVE_PRESENTATION_TOKEN = 'archive-p2-20260823'


def add_class(tag, *names):
    if not tag:
        return
    classes = list(tag.get('class') or [])
    for name in names:
        if name not in classes:
            classes.append(name)
    tag['class'] = classes


def set_shared_asset_token(soup):
    for tag in soup.find_all('link', href=True):
        href=tag.get('href','')
        if re.match(r'^\.\./(?:styles|daily)\.css(?:\?v=.*)?$', href):
            base=href.split('?v=',1)[0]
            tag['href']=f'{base}?v={ARCHIVE_PRESENTATION_TOKEN}'
    for tag in soup.find_all('script', src=True):
        src=tag.get('src','')
        if re.match(r'^\.\./daily\.js(?:\?v=.*)?$', src):
            base=src.split('?v=',1)[0]
            tag['src']=f'{base}?v={ARCHIVE_PRESENTATION_TOKEN}'


def normalize(path: Path) -> bool:
    original = path.read_text('utf-8')
    soup = BeautifulSoup(original, 'html.parser')
    body = soup.body
    if body is None:
        raise SystemExit(f'{path}: missing body')

    add_class(body, 'archive-page')
    add_class(soup.select_one('header.site-head'), 'daily-hero')
    add_class(soup.select_one('main.page'), 'daily-main')
    set_shared_asset_token(soup)

    for card in soup.select('#top .news'):
        add_class(card, 'daily-card', 'daily-card-top')
        classes = [c for c in (card.get('class') or []) if c != 'important']
        card['class'] = classes

    for card in soup.select('.category-news'):
        add_class(card, 'daily-card', 'daily-card-more')

    for card in soup.select('[data-intel-role="card"]'):
        for details in card.select('details'):
            add_class(details, 'daily-full-analysis')
        for detail_body in card.select('.detail-body'):
            add_class(detail_body, 'daily-analysis-body')
        for visual in card.select('figure.case-preview'):
            add_class(visual, 'daily-visual')
        for impact in card.select('.quick-impact'):
            add_class(impact, 'daily-impact')
        for source in card.select('a.source'):
            add_class(source, 'daily-source')

    rendered = soup.prettify()
    if not rendered.endswith('\n'):
        rendered += '\n'
    if rendered != original:
        path.write_text(rendered, 'utf-8')
        return True
    return False


def main():
    changed = []
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and DATE_RE.fullmatch(d.name) and (d / 'index.html').exists():
            if normalize(d / 'index.html'):
                changed.append(d.name)
    print('ARCHIVE PRESENTATION NORMALIZED:', ', '.join(changed) if changed else 'already current')
    print('ARCHIVE PRESENTATION TOKEN:', ARCHIVE_PRESENTATION_TOKEN)


if __name__ == '__main__':
    main()
