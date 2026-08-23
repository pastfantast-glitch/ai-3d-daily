#!/usr/bin/env python3
from pathlib import Path
import json
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
ASSET_VERSION = '20260823-2'


def normalize_rel(soup):
    for a in soup.find_all('a', target='_blank'):
        rel = set(a.get('rel', []))
        rel.update({'noopener', 'noreferrer'})
        a['rel'] = sorted(rel)


def set_cache_version(soup, filename, version):
    for tag in soup.find_all(['link', 'script']):
        attr = 'href' if tag.name == 'link' else 'src'
        value = tag.get(attr, '')
        if value.split('?', 1)[0] == filename:
            tag[attr] = f'{filename}?v={version}'


def repair_home():
    path = ROOT / 'index.html'
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    date_nodes = soup.select('.home-hero .topline span')
    current_date = date_nodes[-1].get_text(strip=True) if date_nodes else ''

    payload_path = ROOT / 'today-more.json'
    payload_date = ''
    if payload_path.exists():
        payload_date = json.loads(payload_path.read_text('utf-8')).get('date', '')

    grid = soup.select_one('.more-grid')
    if not grid:
        raise RuntimeError('Missing .more-grid')

    # Workflow-managed supplemental cards are only valid when payload date equals homepage date.
    if payload_date != current_date:
        for card in grid.select('[data-supplemental-id]'):
            card.decompose()

    count = len(grid.select(':scope > .more-card'))
    section = grid.find_parent('section')
    if section:
        desc = section.select_one('.home-section-head > p')
        if desc:
            desc.string = f'獨立 Supplemental Discovery · {count} 則有效情報'

    for entry in soup.select('.history-list > a'):
        href = entry.get('href', '').rstrip('/')
        span = entry.find('span')
        if not span:
            continue
        if href == current_date:
            span.string = f'TOP 5 + {count} 則 Supplemental'
        elif href == payload_date and payload_date != current_date:
            span.string = '歷史日報'

    for filename in ('home.css', 'home-content.css', 'home-layout-fixes.css', 'home.js'):
        set_cache_version(soup, filename, ASSET_VERSION)

    normalize_rel(soup)
    path.write_text(str(soup), 'utf-8')
    return current_date, count


def repair_daily_navigation():
    dirs = sorted(
        p for p in ROOT.iterdir()
        if p.is_dir() and re.fullmatch(r'20\d{2}-\d{2}-\d{2}', p.name) and (p / 'index.html').exists()
    )
    changed = []
    for i, directory in enumerate(dirs):
        path = directory / 'index.html'
        text = path.read_text('utf-8')
        soup = BeautifulSoup(text, 'html.parser')
        nav = soup.find('nav', class_='day-nav')
        if nav:
            for span in list(nav.find_all('span')):
                if '下一日：null' in span.get_text(strip=True):
                    if i + 1 < len(dirs):
                        next_date = dirs[i + 1].name
                        a = soup.new_tag('a', href=f'../{next_date}/')
                        a.string = f'{next_date} →'
                        span.replace_with(a)
                    else:
                        span.string = '最新日報'
        normalize_rel(soup)
        new_text = str(soup)
        if new_text != text:
            path.write_text(new_text, 'utf-8')
            changed.append(str(path.relative_to(ROOT)))
    return changed


def main():
    date, count = repair_home()
    changed = repair_daily_navigation()
    print(f'Repaired homepage {date}: {count} supplemental cards')
    print('Daily navigation normalized:', ', '.join(changed) if changed else 'no changes')


if __name__ == '__main__':
    main()
