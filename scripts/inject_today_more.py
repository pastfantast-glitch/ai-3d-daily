from __future__ import annotations
import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'today-more.json').read_text(encoding='utf-8'))
DATE = DATA['date']


def homepage_date(soup):
    spans = soup.select('.home-hero .topline span')
    return spans[-1].get_text(strip=True) if spans else ''


def make_details(soup, item):
    details = soup.new_tag('details', attrs={'class':'home-full-analysis'})
    summary = soup.new_tag('summary'); summary.string = '完整分析'; details.append(summary)
    body = soup.new_tag('div', attrs={'class':'detail-body home-analysis-body'})
    for heading, text in item['analysis']:
        h4 = soup.new_tag('h4'); h4.string = heading; body.append(h4)
        p = soup.new_tag('p'); p.string = text; body.append(p)
    details.append(body)
    return details


def make_card(soup, item):
    article = soup.new_tag('article', attrs={'class':'more-card', 'data-supplemental-id':item['id']})
    meta = soup.new_tag('div', attrs={'class':'item-meta'})
    pill = soup.new_tag('span', attrs={'class':f"pill {item['pill_class']}"}); pill.string = item['pill']; meta.append(pill)
    status = soup.new_tag('span', attrs={'class':'status-badge status-track'}); status.string = item['status']; meta.append(status)
    article.append(meta)
    h4 = soup.new_tag('h4'); h4.string = item['title']; article.append(h4)
    p = soup.new_tag('p'); p.string = item['summary']; article.append(p)
    qi = soup.new_tag('div', attrs={'class':'quick-impact'})
    for k, v in item['quick']:
        span = soup.new_tag('span'); b = soup.new_tag('b'); b.string = k; span.append(b); span.append(' ' + v); qi.append(span)
    article.append(qi)
    article.append(make_details(soup, item))
    a = soup.new_tag('a', attrs={'class':'source','href':item['source'],'target':'_blank','rel':'noopener noreferrer'})
    a.string = item['source_label'] + ' ↗'; article.append(a)
    return article


def normalize_home(path: Path):
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    target = soup.select_one('.more-grid')
    if not target:
        raise RuntimeError('Could not find 今天還有什麼 .more-grid')

    current_date = homepage_date(soup)

    # Always remove workflow-managed cards before deciding whether DATA is current.
    for old in target.select('[data-supplemental-id]'):
        old.decompose()

    if DATE == current_date:
        for item in DATA['items']:
            target.append(make_card(soup, item))
        action = f'injected {len(DATA["items"])} cards'
    else:
        # Stale payloads must never contaminate a newer homepage.
        action = f'skipped stale payload {DATE}; homepage is {current_date}'
        for archive in soup.select('.history-list > a'):
            if archive.get('href') == f'{DATE}/':
                span = archive.find('span')
                if span:
                    span.string = '歷史日報'
                break

    count = len(target.select('.more-card'))
    head = target.find_parent('section').select_one('.home-section-head') if target.find_parent('section') else None
    if head:
        desc = head.find('p')
        if desc:
            desc.string = f'獨立 Supplemental Discovery · {count} 則有效情報'

    for archive in soup.select('.history-list > a'):
        if archive.get('href') == f'{current_date}/':
            span = archive.find('span')
            if span:
                span.string = f'TOP 5 + {count} 則 Supplemental'
            break

    for a in soup.find_all('a', target='_blank'):
        rel = set(a.get('rel', [])); rel.update({'noopener','noreferrer'}); a['rel'] = sorted(rel)
    path.write_text(str(soup), encoding='utf-8')
    return current_date, action


def inject_daily(path: Path):
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    old = soup.find('section', attrs={'data-supplemental-daily':'true'})
    if old:
        old.decompose()
    main = soup.find('main') or soup.body
    section = soup.new_tag('section', attrs={'class':'block','data-supplemental-daily':'true'})
    head = soup.new_tag('div', attrs={'class':'block-head'})
    left = soup.new_tag('div'); kicker = soup.new_tag('span', attrs={'class':'section-kicker'}); kicker.string='SUPPLEMENTAL'; left.append(kicker)
    h2 = soup.new_tag('h2'); h2.string='今天還有什麼'; left.append(h2); head.append(left)
    note = soup.new_tag('p'); note.string='獨立 Supplemental Discovery；不是 TOP 5 落選區。'; head.append(note); section.append(head)
    for item in DATA['items']:
        article = soup.new_tag('article', attrs={'class':'category-news','data-supplemental-id':item['id']})
        meta = soup.new_tag('div', attrs={'class':'meta'})
        pill=soup.new_tag('span', attrs={'class':f"pill {item['pill_class']}"}); pill.string=item['pill']; meta.append(pill)
        status=soup.new_tag('span', attrs={'class':'status-badge status-track'}); status.string=item['status']; meta.append(status); article.append(meta)
        h4=soup.new_tag('h4'); h4.string=item['title']; article.append(h4)
        p=soup.new_tag('p', attrs={'class':'summary'}); p.string=item['summary']; article.append(p)
        qi=soup.new_tag('div', attrs={'class':'quick-impact'})
        for k,v in item['quick']:
            span=soup.new_tag('span'); b=soup.new_tag('b'); b.string=k; span.append(b); span.append(' '+v); qi.append(span)
        article.append(qi); article.append(make_details(soup,item))
        a=soup.new_tag('a', attrs={'class':'source','href':item['source'],'target':'_blank','rel':'noopener noreferrer'}); a.string=item['source_label']+' ↗'; article.append(a)
        section.append(article)
    main.append(section)
    path.write_text(str(soup), encoding='utf-8')


current_date, action = normalize_home(ROOT / 'index.html')
if DATE == current_date:
    daily = ROOT / DATE / 'index.html'
    if daily.exists():
        inject_daily(daily)
print(f'Supplemental injector: {action}')
