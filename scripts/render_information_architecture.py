#!/usr/bin/env python3
"""Render homepage, date-scoped daily archive and six category pages from canonical V3 data.

Ranking/category decisions are read from canonical schema-v3 data. This renderer
only turns those decisions into presentation surfaces. Schema-v2 historical/current
data remains untouched for backwards compatibility.
"""
from pathlib import Path
import json, sys
from bs4 import BeautifulSoup
from intelligence_v2 import load_config, is_v2_dataset, validate_v2_dataset, homepage_groups, category_items

ROOT = Path(__file__).resolve().parents[1]


def latest_date():
    return max(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))


def ensure_shared_stylesheet(soup, href):
    """Ensure shared components are loaded after the base stylesheet and before page-specific CSS."""
    existing = soup.find('link', href=lambda value: value and 'shared-components.css' in value)
    if existing:
        existing['href'] = href
        return
    link = soup.new_tag('link', attrs={'rel': 'stylesheet', 'href': href})
    page_css = soup.find('link', href=lambda value: value and ('home.css' in value or 'category.css' in value or 'daily.css' in value))
    if page_css:
        page_css.insert_before(link)
    else:
        soup.head.append(link)


def analysis_shell(soup, home=False, daily=False):
    details = soup.new_tag('details')
    if home:
        details['class'] = ['home-full-analysis']
    elif daily:
        details['class'] = ['daily-full-analysis']
    summary = soup.new_tag('summary'); summary.string = '完整分析'; details.append(summary)
    body_class = 'detail-body home-analysis-body' if home else ('detail-body daily-analysis-body' if daily else 'detail-body')
    body = soup.new_tag('div', attrs={'class': body_class})
    details.append(body)
    return details


def impact_node(soup, text, daily=False):
    wrap = soup.new_tag('div', attrs={'class': 'quick-impact daily-impact' if daily else 'quick-impact'})
    span = soup.new_tag('span'); span.string = text; wrap.append(span)
    return wrap


def global_nav(soup, date, cfg, active='top5', context='home'):
    """One shared nav component; only link scope changes by page context."""
    nav = soup.new_tag('nav', attrs={'class': 'global-category-nav', 'aria-label': 'Production Intelligence 分類'})
    inner = soup.new_tag('div', attrs={'class': 'page global-category-nav-inner'})
    if context == 'home':
        top_href = '#today'
    elif context == 'archive':
        top_href = '#top'
    else:  # category page: return to the same date archive TOP5
        top_href = '../../#top'
    top = soup.new_tag('a', attrs={'href': top_href, 'class': 'global-category-link' + (' is-active' if active == 'top5' else '')})
    top.string = 'TOP5'; inner.append(top)
    for cat in cfg['categories']:
        if context == 'home':
            href = f'{date}/{cat["id"]}/'
        elif context == 'archive':
            href = f'{cat["id"]}/'
        else:
            href = f'../{cat["id"]}/'
        classes = 'global-category-link' + (' is-active' if active == cat['id'] else '')
        a = soup.new_tag('a', attrs={'href': href, 'class': classes, 'data-category': cat['id']})
        a.string = cat['label']; inner.append(a)
    nav.append(inner)
    return nav


def home_card(soup, item, top=False, rank=None):
    classes = ['home-card', 'top-item' if top else 'more-card']
    card = soup.new_tag('article', attrs={'class': ' '.join(classes), 'data-intel-role': 'card', 'data-intel-id': item['id']})
    content = card
    if top:
        no = soup.new_tag('div', attrs={'class': 'top-no'}); no.string = f'{rank:02d}'; card.append(no)
        content = soup.new_tag('div', attrs={'class': 'top-main'}); card.append(content)
        title = soup.new_tag('h2')
    else:
        title = soup.new_tag('h4')
    title.string = item['title']; content.append(title)
    summary = soup.new_tag('p', attrs={'class': 'summary'}); summary.string = item['summary']; content.append(summary)
    content.append(impact_node(soup, item['quick_impact']))
    content.append(analysis_shell(soup, home=True))
    source = soup.new_tag('a', attrs={'class': 'source', 'href': item['source_url'], 'target': '_blank', 'rel': 'noopener noreferrer'})
    source.string = '來源'; content.append(source)
    return card


def daily_card(soup, item, top=False, rank=None):
    classes = ['news', 'daily-card', 'daily-card-top' if top else 'daily-card-more']
    card = soup.new_tag('article', attrs={'class': ' '.join(classes), 'data-intel-role': 'card', 'data-intel-id': item['id']})
    if top:
        no = soup.new_tag('div', attrs={'class': 'news-rank'}); no.string = f'{rank:02d}'; card.append(no)
    content = soup.new_tag('div', attrs={'class': 'news-main'}); card.append(content)
    meta = soup.new_tag('div', attrs={'class': 'meta'})
    pill = soup.new_tag('span', attrs={'class': 'pill'}); pill.string = item['subcategory']; meta.append(pill)
    if item.get('status'):
        status = str(item['status']).lower()
        badge = soup.new_tag('span', attrs={'class': f'news-status status-{status}'})
        badge.string = str(item['status']).upper(); meta.append(badge)
    content.append(meta)
    title = soup.new_tag('h3'); title.string = item['title']; content.append(title)
    summary = soup.new_tag('p', attrs={'class': 'summary'}); summary.string = item['summary']; content.append(summary)
    content.append(impact_node(soup, item['quick_impact'], daily=True))
    content.append(analysis_shell(soup, daily=True))
    source = soup.new_tag('a', attrs={'class': 'source daily-source', 'href': item['source_url'], 'target': '_blank', 'rel': 'noopener noreferrer'})
    source.string = '來源'; content.append(source)
    return card


def ensure_category_section(soup, date, cfg):
    main = soup.select_one('main.home-main')
    if not main:
        raise SystemExit('homepage main.home-main missing')
    for old in soup.select('section.category-section, section.test-section'):
        old.decompose()
    section = soup.new_tag('section', attrs={'class': 'home-section category-section', 'id': 'categories'})
    head = soup.new_tag('div', attrs={'class': 'section-head'})
    h2 = soup.new_tag('h2'); h2.string = '探索今天全部情報'; head.append(h2); section.append(head)
    grid = soup.new_tag('div', attrs={'class': 'category-nav-grid'})
    for cat in cfg['categories']:
        a = soup.new_tag('a', attrs={'class': 'category-nav-card', 'href': f'{date}/{cat["id"]}/'})
        strong = soup.new_tag('strong'); strong.string = cat['label']; a.append(strong)
        span = soup.new_tag('span'); span.string = cat['description']; a.append(span)
        grid.append(a)
    section.append(grid)
    more = soup.select_one('section.more-section')
    if more:
        more.insert_after(section)
    else:
        main.append(section)


def render_home(date, data, cfg):
    path = ROOT / 'index.html'
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    ensure_shared_stylesheet(soup, 'shared-components.css')
    top, next10 = homepage_groups(data)
    top_box = soup.select_one('#today .top-list')
    more_box = soup.select_one('#more .more-grid')
    if not top_box or not more_box:
        raise SystemExit('homepage TOP/more containers missing')
    top_box.clear(); more_box.clear()
    for rank, item in enumerate(top, 1):
        top_box.append(home_card(soup, item, top=True, rank=rank))
    for item in next10:
        more_box.append(home_card(soup, item, top=False))
    more_heading = soup.select_one('#more h2')
    if more_heading: more_heading.string = '今天還有什麼'
    ensure_category_section(soup, date, cfg)
    for weekly in soup.select('.week-counts, .week-summary, .week-topic'):
        weekly.decompose()
    for old in soup.select('.global-category-nav'):
        old.decompose()
    main = soup.select_one('main.home-main')
    main.insert_before(global_nav(soup, date, cfg, active='top5', context='home'))
    path.write_text(soup.prettify(), 'utf-8')
    print(f'V2 homepage rendered: {len(top)} TOP + {len(next10)} next + shared sticky nav ({date})')


def render_daily(date, data, cfg):
    """Render the selected historical day as a faithful date-scoped snapshot."""
    path = ROOT / date / 'index.html'
    if not path.exists():
        raise SystemExit(f'daily archive missing: {path.relative_to(ROOT)}')
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    ensure_shared_stylesheet(soup, '../shared-components.css')
    if not soup.body:
        raise SystemExit(f'{date}: daily archive missing body')
    soup.body['data-report-date'] = date
    main = soup.select_one('main.daily-main') or soup.select_one('main')
    if not main:
        raise SystemExit(f'{date}: daily archive main missing')
    top, next10 = homepage_groups(data)

    for old in soup.select('.global-category-nav'):
        old.decompose()
    main.insert_before(global_nav(soup, date, cfg, active='top5', context='archive'))

    top_section = soup.select_one('section#top')
    if not top_section:
        top_section = soup.new_tag('section', attrs={'class': 'block', 'id': 'top'})
        main.insert(0, top_section)
    top_section.clear()
    head = soup.new_tag('div', attrs={'class': 'block-head'})
    head_inner = soup.new_tag('div')
    kicker = soup.new_tag('span'); kicker.string = date; head_inner.append(kicker)
    h2 = soup.new_tag('h2'); h2.string = 'TOP5'; head_inner.append(h2)
    head.append(head_inner); top_section.append(head)
    for rank, item in enumerate(top, 1):
        top_section.append(daily_card(soup, item, top=True, rank=rank))

    old_more = soup.select_one('section#more')
    if old_more:
        old_more.decompose()
    if next10:
        more = soup.new_tag('section', attrs={'class': 'block daily-more', 'id': 'more'})
        mhead = soup.new_tag('div', attrs={'class': 'block-head'})
        minner = soup.new_tag('div')
        mk = soup.new_tag('span'); mk.string = date; minner.append(mk)
        mh = soup.new_tag('h2'); mh.string = '當日其他資訊'; minner.append(mh)
        mhead.append(minner); more.append(mhead)
        for item in next10:
            more.append(daily_card(soup, item, top=False))
        top_section.insert_after(more)

    path.write_text(soup.prettify() + '\n', 'utf-8')
    print(f'V2 daily archive rendered: {date} / {len(top)} TOP + {len(next10)} other / date-scoped shared nav')


def category_footer_nav(soup, category, cfg):
    cats = cfg['categories']; idx = next(i for i, c in enumerate(cats) if c['id'] == category['id'])
    prev_cat = cats[(idx - 1) % len(cats)]; next_cat = cats[(idx + 1) % len(cats)]
    nav = soup.new_tag('nav', attrs={'class': 'category-bottom-nav', 'aria-label': '相鄰分類'})
    prev = soup.new_tag('a', attrs={'href': f'../{prev_cat["id"]}/'}); prev.string = f'← {prev_cat["label"]}'; nav.append(prev)
    top = soup.new_tag('a', attrs={'href': '../../#top'}); top.string = 'TOP5'; nav.append(top)
    nxt = soup.new_tag('a', attrs={'href': f'../{next_cat["id"]}/'}); nxt.string = f'{next_cat["label"]} →'; nav.append(nxt)
    return nav


def category_page(date, category, items, cfg):
    soup = BeautifulSoup('<!doctype html><html lang="zh-Hant"><head></head><body></body></html>', 'html.parser')
    head = soup.head
    meta = soup.new_tag('meta', attrs={'charset': 'utf-8'}); head.append(meta)
    viewport = soup.new_tag('meta', attrs={'name': 'viewport', 'content': 'width=device-width,initial-scale=1'}); head.append(viewport)
    title = soup.new_tag('title'); title.string = f'{category["label"]}｜{date}｜AI 3D Daily'; head.append(title)
    for href in ('../../styles.css', '../../shared-components.css', '../../category.css'):
        head.append(soup.new_tag('link', attrs={'rel': 'stylesheet', 'href': href}))
    body = soup.body; body['class'] = ['category-page']; body['data-report-date'] = date; body['data-category'] = category['id']
    header = soup.new_tag('header', attrs={'class': 'category-hero'})
    page = soup.new_tag('div', attrs={'class': 'page'})
    kicker = soup.new_tag('span', attrs={'class': 'section-kicker'}); kicker.string = date; page.append(kicker)
    h1 = soup.new_tag('h1'); h1.string = category['label']; page.append(h1)
    p = soup.new_tag('p'); p.string = category['description']; page.append(p)
    header.append(page); body.append(header)
    body.append(global_nav(soup, date, cfg, active=category['id'], context='category'))
    main = soup.new_tag('main', attrs={'class': 'page category-main'})
    for item in items:
        card = soup.new_tag('article', attrs={'class': 'category-card', 'data-intel-role': 'card', 'data-intel-id': item['id']})
        meta = soup.new_tag('div', attrs={'class': 'category-meta'}); meta.string = f'#{int(item["rank_global"]):02d} · {item["subcategory"]}'; card.append(meta)
        h2 = soup.new_tag('h2'); h2.string = item['title']; card.append(h2)
        summary = soup.new_tag('p', attrs={'class': 'summary'}); summary.string = item['summary']; card.append(summary)
        card.append(impact_node(soup, item['quick_impact']))
        card.append(analysis_shell(soup, home=False))
        source = soup.new_tag('a', attrs={'class': 'source', 'href': item['source_url'], 'target': '_blank', 'rel': 'noopener noreferrer'}); source.string = '來源 ↗'; card.append(source)
        main.append(card)
    main.append(category_footer_nav(soup, category, cfg))
    body.append(main)
    return soup.prettify() + '\n'


def render_categories(date, data, cfg):
    for category in cfg['categories']:
        folder = ROOT / date / category['id']; folder.mkdir(parents=True, exist_ok=True)
        items = category_items(data, category['id'])
        (folder / 'index.html').write_text(category_page(date, category, items, cfg), 'utf-8')
        print(f'V2 category page: {category["id"]} / {len(items)} items')


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else latest_date()
    data = json.loads((ROOT / 'data' / 'daily' / f'{date}.json').read_text('utf-8'))
    if not is_v2_dataset(data):
        print(f'V2 information architecture: legacy schema {data.get("schema_version")} for {date}; no V2 surfaces rendered')
        return
    errors = validate_v2_dataset(data, strict_pool=True)
    if errors:
        raise SystemExit('V2 canonical dataset invalid:\n- ' + '\n- '.join(errors))
    cfg = load_config()
    render_home(date, data, cfg)
    render_daily(date, data, cfg)
    render_categories(date, data, cfg)


if __name__ == '__main__':
    main()
