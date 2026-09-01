#!/usr/bin/env python3
"""Normalize current release seed markup into the canonical semantic shell.

This renderer is intentionally structure-only. It may add/repair presentation
classes, source-link semantics, date markers, and Full Analysis containers using
canonical IDs/source URLs, but it never rewrites titles, summaries, quick-impact
copy, or canonical intelligence blocks.
"""
from pathlib import Path
import json, sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def add_class(tag, *names):
    if not tag:
        return
    classes = list(tag.get('class') or [])
    for name in names:
        if name not in classes:
            classes.append(name)
    tag['class'] = classes


def ensure_analysis_shell(soup, card, home=False):
    details = card.select_one('details')
    if not details:
        details = soup.new_tag('details')
        summary = soup.new_tag('summary')
        summary.string = '完整分析'
        details.append(summary)
        card.append(details)
    if home:
        add_class(details, 'home-full-analysis')
    else:
        add_class(details, 'daily-full-analysis')

    body = details.select_one(':scope > .detail-body')
    if not body:
        body = soup.new_tag('div')
        body['class'] = ['detail-body']
        movable = [c for c in list(details.children) if getattr(c, 'name', None) and c.name != 'summary']
        for child in movable:
            body.append(child.extract())
        details.append(body)
    if home:
        add_class(body, 'home-analysis-body')
    else:
        add_class(body, 'daily-analysis-body')
    return details


def ensure_source(soup, card, source_url, home=False):
    source = card.select_one('a.source[href]')
    if not source:
        for a in card.select('a[href]'):
            if (a.get('href') or '').rstrip('/') == source_url.rstrip('/'):
                source = a
                add_class(source, 'source')
                break
    if not source:
        source = soup.new_tag('a', href=source_url)
        source.string = '來源'
        add_class(source, 'source')
        card.append(source)
    if not home:
        add_class(source, 'daily-source')
    return source


def ensure_analysis_before_source(card):
    """Keep semantic card order deterministic without rewriting intelligence copy.

    Full Analysis is part of the card body while source is terminal metadata. Seeds
    can arrive with either order, so normalize the existing nodes before canonical
    analysis rendering replaces the details shell in-place.
    """
    details = card.select_one('details')
    source = card.select_one('a.source[href]')
    if not details or not source:
        return
    nodes = [node for node in card.descendants if getattr(node, 'name', None)]
    try:
        if nodes.index(details) > nodes.index(source):
            details.extract()
            source.insert_before(details)
    except ValueError:
        return


def normalize_home(date, data):
    path = ROOT / 'index.html'
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    body = soup.body
    add_class(body, 'home-page')
    main = soup.select_one('main')
    add_class(main, 'page', 'home-main')

    section_roles = {
        'today': 'today-section',
        'more': 'more-section',
        'test': 'test-section',
        'history': 'history-section',
    }
    for sid, role in section_roles.items():
        section = soup.select_one(f'#{sid}')
        add_class(section, 'home-section', role)

    marker = soup.select_one('.week-asof')
    if not marker:
        spans = soup.select('.topline span')
        marker = spans[-1] if spans else None
        if marker:
            add_class(marker, 'week-asof')
    if not marker:
        host = soup.select_one('.home-hero .page') or soup.body
        marker = soup.new_tag('span', attrs={'class': 'week-asof'})
        marker.string = date
        host.append(marker)

    today = soup.select_one('#today')
    if today:
        container = today.select_one('.today-grid') or today.select_one('.top-list')
        add_class(container, 'top-list')
        for card in today.select('[data-intel-role="card"][data-intel-id]'):
            add_class(card, 'top-item')
    more = soup.select_one('#more')
    if more:
        container = more.select_one('.more-grid')
        add_class(container, 'more-grid')
        for card in more.select('[data-intel-role="card"][data-intel-id]'):
            add_class(card, 'more-card')

    records = {x['id']: x for x in data.get('items', [])}
    for card in soup.select('.top-item[data-intel-id], .more-card[data-intel-id]'):
        rid = card.get('data-intel-id')
        rec = records.get(rid)
        if not rec:
            continue
        card['data-intel-role'] = 'card'
        ensure_analysis_shell(soup, card, home=True)
        ensure_source(soup, card, str(rec.get('source_url', '')).strip(), home=True)
        ensure_analysis_before_source(card)

    path.write_text(soup.prettify() + '\n', 'utf-8')


def normalize_daily(date, data):
    path = ROOT / date / 'index.html'
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    body = soup.body
    add_class(body, 'archive-page')
    body['data-report-date'] = date
    add_class(soup.select_one('header.site-head'), 'daily-hero')
    add_class(soup.select_one('main.page'), 'daily-main')

    for rank, card in enumerate(soup.select('#top .news[data-intel-id]'), 1):
        add_class(card, 'daily-card', 'daily-card-top')
        card['data-intel-role'] = 'card'
        rank_node = card.find('div', class_='news-rank', recursive=False)
        if rank_node:
            rank_node.string = f'{rank:02d}'

    more = soup.select_one('#more')
    if more:
        for card in more.select('.news[data-intel-id], .category-news[data-intel-id]'):
            add_class(card, 'category-news', 'daily-card', 'daily-card-more')
            card['data-intel-role'] = 'card'

    records = {x['id']: x for x in data.get('items', [])}
    for card in soup.select('[data-intel-role="card"][data-intel-id]'):
        rid = card.get('data-intel-id')
        rec = records.get(rid)
        if not rec:
            continue
        ensure_analysis_shell(soup, card, home=False)
        ensure_source(soup, card, str(rec.get('source_url', '')).strip(), home=False)
        ensure_analysis_before_source(card)
        for impact in card.select('.quick-impact'):
            add_class(impact, 'daily-impact')
        for visual in card.select('figure.case-preview'):
            add_class(visual, 'daily-visual')

    path.write_text(soup.prettify() + '\n', 'utf-8')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: normalize_release_seed.py YYYY-MM-DD')
    date = sys.argv[1]
    data_path = ROOT / 'data' / 'daily' / f'{date}.json'
    data = json.loads(data_path.read_text('utf-8'))
    normalize_home(date, data)
    normalize_daily(date, data)
    print(f'RELEASE SEED NORMALIZED: {date} / structure-only canonical semantic shell')


if __name__ == '__main__':
    main()
