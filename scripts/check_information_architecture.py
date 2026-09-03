#!/usr/bin/env python3
"""Fail-closed QA for the V2 six-pool information architecture."""
from pathlib import Path
import json, sys
from bs4 import BeautifulSoup
from intelligence_v2 import load_config, is_v2_dataset, validate_v2_dataset, homepage_groups, category_items, target_fill_applies

ROOT = Path(__file__).resolve().parents[1]
errors = []

def fail(msg): errors.append(msg)

def latest_date():
    return max(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))

def shared_component_contract(soup, name):
    links = [x.get('href','') for x in soup.select('head link[rel="stylesheet"][href]')]
    shared = [x for x in links if 'shared-components.css' in x]
    if len(shared) != 1:
        fail(f'{name}: expected exactly one shared-components.css stylesheet, got {len(shared)}')

def source_css_contract():
    shared = ROOT / 'shared-components.css'
    if not shared.exists():
        fail('shared-components.css missing')
        return
    text = shared.read_text('utf-8')
    for token in ('.global-category-nav', '.global-category-link', '.detail-body', 'details > summary'):
        if token not in text:
            fail(f'shared-components.css missing canonical component selector: {token}')
    for filename in ('home.css','category.css'):
        page_css = (ROOT / filename).read_text('utf-8')
        for token in ('.global-category-nav', '.global-category-link', '.detail-body'):
            if token in page_css:
                fail(f'{filename}: shared component selector must not be duplicated locally: {token}')

def nav_contract(soup, date, cfg, active, category_page=False):
    navs = soup.select('nav.global-category-nav')
    if len(navs) != 1:
        fail(f'{active}: expected exactly one global category nav, got {len(navs)}'); return
    nav = navs[0]
    links = nav.select('a.global-category-link[href]')
    if len(links) != len(cfg['categories']) + 1:
        fail(f'{active}: global nav must contain TOP5 + {len(cfg["categories"])} categories')
        return
    expected_labels = ['TOP5'] + [c['label'] for c in cfg['categories']]
    if [x.get_text(' ', strip=True) for x in links] != expected_labels:
        fail(f'{active}: global nav labels/order drift')

    expected_hrefs = (
        ['../#top'] + [f'../{c["id"]}/' for c in cfg['categories']]
        if category_page
        else ['#today'] + [f'{date}/{c["id"]}/' for c in cfg['categories']]
    )
    actual_hrefs = [x.get('href') for x in links]
    if actual_hrefs != expected_hrefs:
        fail(f'{active}: global nav href/order drift: {actual_hrefs}')

    if category_page:
        controls = nav.select_one('.archive-nav-controls')
        divider = nav.select_one('.archive-nav-divider')
        if not controls or not divider:
            fail(f'{active}: category page must share archive date controls + divider with TOP5')
        else:
            if not controls.select_one('a.archive-nav-home[href="../../"]'):
                fail(f'{active}: category page archive home control drift')
            date_node = controls.select_one('.archive-nav-date span')
            if not date_node or date_node.get_text(' ', strip=True) != date:
                fail(f'{active}: category page archive date control drift')
            for arrow in controls.select('a.archive-nav-arrow[href]'):
                href = arrow.get('href','')
                if not href.startswith('../../') or not href.endswith(f'/{active}/'):
                    fail(f'{active}: category page archive neighbor href drift: {href}')

    active_links = nav.select('a.global-category-link.is-active')
    if len(active_links) != 1:
        fail(f'{active}: global nav must have exactly one active link')
    else:
        expected_active = 'TOP5' if active == 'top5' else next(c['label'] for c in cfg['categories'] if c['id'] == active)
        if active_links[0].get_text(' ', strip=True) != expected_active:
            fail(f'{active}: wrong active global nav item')

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else latest_date()
    data = json.loads((ROOT / 'data' / 'daily' / f'{date}.json').read_text('utf-8'))
    cfg = load_config()
    if not is_v2_dataset(data):
        print(f'V2 INFORMATION ARCHITECTURE PASS (legacy compatibility): {date} schema={data.get("schema_version")}')
        return
    source_css_contract()
    for error in validate_v2_dataset(data, strict_pool=True): fail(error)
    top, next10 = homepage_groups(data)
    home = BeautifulSoup((ROOT / 'index.html').read_text('utf-8'), 'html.parser')
    shared_component_contract(home, 'homepage')
    if home.select('.week-counts, .week-summary, .week-topic'):
        fail('homepage V2 must not contain weekly overview UI')
    sections = home.select('main.home-main > section.home-section')
    roles = []
    for section in sections:
        classes = set(section.get('class') or [])
        roles.append(next((x for x in ('today-section','more-section','category-section','history-section') if x in classes), '?'))
    if roles != ['today-section','more-section','category-section','history-section']:
        fail(f'V2 homepage section order drift: {roles}')
    home_top = [x.get('data-intel-id') for x in home.select('#today .top-item[data-intel-role="card"]')]
    home_next = [x.get('data-intel-id') for x in home.select('#more .more-card[data-intel-role="card"]')]
    if home_top != [x['id'] for x in top]: fail('homepage TOP IDs/order differ from canonical available ranks 1-5')
    if home_next != [x['id'] for x in next10]: fail('homepage next10 IDs/order differ from canonical available ranks 6-15')
    links = {a.get('href') for a in home.select('.category-nav-grid .category-nav-card[href]')}
    expected_links = {f'{date}/{c["id"]}/' for c in cfg['categories']}
    if links != expected_links: fail(f'category navigation mismatch: {links} != {expected_links}')
    nav_contract(home, date, cfg, 'top5', category_page=False)
    pool_max = int(cfg['category_pool_max_items'])
    pool_target = int(cfg['category_pool_target_items'])
    target_mode = target_fill_applies(data, cfg)
    for category in cfg['categories']:
        path = ROOT / date / category['id'] / 'index.html'
        if not path.exists():
            fail(f'missing category page: {path.relative_to(ROOT)}'); continue
        soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
        shared_component_contract(soup, category['id'])
        if not soup.body or soup.body.get('data-category') != category['id']:
            fail(f'{category["id"]}: body category identity mismatch')
        if soup.select_one('header.category-hero'):
            fail(f'{category["id"]}: category hero/title must not render above historical tabs')
        nav_contract(soup, date, cfg, category['id'], category_page=True)
        cards = soup.select('.category-card[data-intel-role="card"][data-intel-id]')
        expected = [x['id'] for x in category_items(data, category['id'])]
        actual = [x.get('data-intel-id') for x in cards]
        if actual != expected: fail(f'{category["id"]}: page item IDs/order mismatch')
        if target_mode and len(cards) != pool_target: fail(f'{category["id"]}: target-fill category page must contain exactly {pool_target} items, got {len(cards)}')
        if len(cards) > pool_max and target_mode: fail(f'{category["id"]}: category page exceeds maximum {pool_max} items, got {len(cards)}')
        bottom = soup.select_one('nav.category-bottom-nav')
        if not bottom or len(bottom.select('a[href]')) != 3:
            fail(f'{category["id"]}: missing bottom previous/TOP5/next navigation')
        else:
            cats = cfg['categories']
            idx = next(i for i, c in enumerate(cats) if c['id'] == category['id'])
            expected_bottom = [
                f'../{cats[(idx - 1) % len(cats)]["id"]}/',
                '../#top',
                f'../{cats[(idx + 1) % len(cats)]["id"]}/',
            ]
            actual_bottom = [a.get('href') for a in bottom.select('a[href]')]
            if actual_bottom != expected_bottom:
                fail(f'{category["id"]}: bottom navigation href drift: {actual_bottom}')
        for card in cards:
            rid = card.get('data-intel-id')
            if not card.select_one('.quick-impact'): fail(f'{category["id"]}/{rid}: missing quick-impact')
            if not card.select_one('details .detail-body'): fail(f'{category["id"]}/{rid}: missing analysis shell')
            if not card.select_one('a.source[href]'): fail(f'{category["id"]}/{rid}: missing source')
    if errors:
        print('V2 INFORMATION ARCHITECTURE FAILED')
        print('\n'.join('- ' + x for x in errors))
        sys.exit(1)
    counts = ', '.join(f'{c["id"]}={len(category_items(data, c["id"]))}' for c in cfg['categories'])
    mode = f'exact {pool_target}/category target-fill' if target_mode else 'legacy variable-pool compatibility'
    print(f'V2 INFORMATION ARCHITECTURE PASS: {mode} + available TOP5/next10 + shared components + no-hero historical category pages + direct-link-safe navigation / {counts}')

if __name__ == '__main__': main()
