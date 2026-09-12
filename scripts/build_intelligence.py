#!/usr/bin/env python3
"""Canonical Intelligence renderer for homepage, daily archive and V2 category pages."""
from pathlib import Path
import json, sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def load(date):
    return json.loads((ROOT / 'data' / 'daily' / f'{date}.json').read_text('utf-8'))


def analysis_html(soup, record, home=False, daily=False):
    blocks = record.get('full_analysis') or []
    level = str(record.get('analysis_level') or 'FULL').upper()
    details = soup.new_tag('details')
    if home:
        details['class'] = ['home-full-analysis']
    elif daily:
        details['class'] = ['daily-full-analysis']
    details['data-analysis-level'] = level
    summary = soup.new_tag('summary')
    summary.string = '情報簡析' if level == 'BRIEF' else '完整分析'
    details.append(summary)
    body_classes = ['detail-body']
    if level == 'BRIEF':
        body_classes.append('brief-analysis-body')
    if home:
        body_classes.append('home-analysis-body')
    elif daily:
        body_classes.append('daily-analysis-body')
    body = soup.new_tag('div'); body['class'] = body_classes
    if level == 'BRIEF':
        badge = soup.new_tag('p'); badge['class'] = ['analysis-level-note']
        badge.string = 'BRIEF｜來源已驗證，但目前證據深度不足以支持完整 Production Analysis。'
        body.append(badge)
    for block in blocks:
        heading = soup.new_tag('h4'); heading.string = block['label']
        paragraph = soup.new_tag('p'); paragraph.string = block['text']
        body.append(heading); body.append(paragraph)
    details.append(body)
    return details


def render_target(path, records, home, selector, daily=False):
    if not path.exists(): return 0
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    rendered = 0
    for card in soup.select(selector):
        record = records.get(card.get('data-intel-id'))
        if not record: continue
        old = card.find('details')
        if not old: continue
        old.replace_with(analysis_html(soup, record, home=home, daily=daily)); rendered += 1
    path.write_text(soup.prettify(), 'utf-8')
    print(f'{path.relative_to(ROOT)}: rendered {rendered} canonical analyses')
    return rendered


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else max(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))
    data = load(date)
    records = {item['id']: item for item in data['items']}
    render_target(ROOT / 'index.html', records, True, '.top-item[data-intel-role="card"][data-intel-id], .more-card[data-intel-role="card"][data-intel-id]')
    render_target(
        ROOT / date / 'index.html', records, False,
        '#top .news[data-intel-role="card"][data-intel-id], #more .daily-card-more[data-intel-role="card"][data-intel-id], .category-news[data-intel-role="card"][data-intel-id]',
        daily=True,
    )
    if int(data.get('schema_version', 0)) >= 3:
        for path in sorted((ROOT / date).glob('*/index.html')):
            if path.parent.parent == ROOT / date:
                render_target(path, records, False, '.category-card[data-intel-role="card"][data-intel-id]')


if __name__ == '__main__': main()
