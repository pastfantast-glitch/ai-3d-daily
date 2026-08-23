#!/usr/bin/env python3
"""Canonical Intelligence renderer.

The daily JSON under data/daily/YYYY-MM-DD.json is the only editable source for
Full Analysis. Homepage and archive consume the same structured blocks and render
them with the same semantic hierarchy. Identity may be shared by multiple DOM
nodes, so render targets must satisfy BOTH structural card selectors and
`data-intel-role=card`.
"""
from pathlib import Path
import json, sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def load(date):
    return json.loads((ROOT / 'data' / 'daily' / f'{date}.json').read_text('utf-8'))


def analysis_html(soup, blocks, home=False):
    details = soup.new_tag('details')
    if home:
        details['class'] = ['home-full-analysis']
    summary = soup.new_tag('summary'); summary.string = '完整分析'; details.append(summary)
    body = soup.new_tag('div'); body['class'] = ['detail-body'] + (['home-analysis-body'] if home else [])
    for block in blocks:
        heading = soup.new_tag('h4'); heading.string = block['label']
        paragraph = soup.new_tag('p'); paragraph.string = block['text']
        body.append(heading); body.append(paragraph)
    details.append(body)
    return details


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else max(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))
    records = {item['id']: item for item in load(date)['items']}
    targets = (
        (ROOT / 'index.html', True, '.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]'),
        (ROOT / date / 'index.html', False, '#top .news[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]'),
    )
    for path, home, selector in targets:
        soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
        rendered = 0
        for card in soup.select(selector):
            record = records.get(card.get('data-intel-id'))
            if not record: continue
            old = card.find('details')
            if not old: continue
            old.replace_with(analysis_html(soup, record['full_analysis'], home)); rendered += 1
        path.write_text(soup.prettify(), 'utf-8')
        print(f'{path.relative_to(ROOT)}: rendered {rendered} canonical analyses')


if __name__ == '__main__': main()
