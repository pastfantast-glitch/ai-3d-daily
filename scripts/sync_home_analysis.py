#!/usr/bin/env python3
from pathlib import Path
from copy import deepcopy
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'index.html'


def normalize_href(href: str) -> str:
    return (href or '').strip().rstrip('/')


def current_date(home_soup: BeautifulSoup) -> str:
    spans = home_soup.select('.home-hero .topline span')
    return spans[-1].get_text(strip=True) if spans else ''


def canonical_cards(daily_soup: BeautifulSoup):
    out = {}
    for card in daily_soup.select('article.news, article.category-news'):
        source = card.select_one('a.source[href]')
        details = card.find('details')
        if source and details:
            out[normalize_href(source.get('href'))] = details
    return out


def main():
    home_soup = BeautifulSoup(HOME.read_text('utf-8'), 'html.parser')
    date = current_date(home_soup)
    daily_path = ROOT / date / 'index.html'
    if not date or not daily_path.exists():
        raise RuntimeError(f'Canonical daily report not found for {date!r}')

    daily_soup = BeautifulSoup(daily_path.read_text('utf-8'), 'html.parser')
    canonical = canonical_cards(daily_soup)
    synced = 0
    missing = []

    for card in home_soup.select('.top-item, .more-card'):
        source = card.select_one('a.source[href]')
        target = card.find('details')
        if not source or not target:
            continue
        href = normalize_href(source.get('href'))
        source_details = canonical.get(href)
        if not source_details:
            missing.append(href)
            continue

        replacement = deepcopy(source_details)
        replacement['class'] = sorted(set(replacement.get('class', []) + ['home-full-analysis']))
        body = replacement.select_one('.detail-body')
        if body:
            body['class'] = sorted(set(body.get('class', []) + ['home-analysis-body']))
        target.replace_with(replacement)
        synced += 1

    HOME.write_text(home_soup.prettify(), 'utf-8')
    print(f'Synced {synced} homepage full analyses from {date} daily report')
    if missing:
        print('No canonical analysis for:', *missing, sep='\n - ')


if __name__ == '__main__':
    main()
