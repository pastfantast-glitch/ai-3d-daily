from __future__ import annotations
import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'today-more.json').read_text(encoding='utf-8'))
DATE = DATA['date']


def make_details(soup, item):
    details = soup.new_tag('details')
    summary = soup.new_tag('summary')
    summary.string = '完整分析'
    details.append(summary)
    body = soup.new_tag('div', attrs={'class':'detail-body'})
    for heading, text in item['analysis']:
        h4 = soup.new_tag('h4'); h4.string = heading; body.append(h4)
        p = soup.new_tag('p'); p.string = text; body.append(p)
    details.append(body)
    return details


def make_card(soup, item):
    article = soup.new_tag('article', attrs={'class':'more-card', 'data-supplemental-id':item['id']})
    meta = soup.new_tag('div', attrs={'class':'meta'})
    pill = soup.new_tag('span', attrs={'class':f"pill {item['pill_class']}"}); pill.string = item['pill']; meta.append(pill)
    status = soup.new_tag('span', attrs={'class':'status-badge status-track'}); status.string = item['status']; meta.append(status)
    article.append(meta)
    h4 = soup.new_tag('h4'); h4.string = item['title']; article.append(h4)
    p = soup.new_tag('p', attrs={'class':'summary'}); p.string = item['summary']; article.append(p)
    qi = soup.new_tag('div', attrs={'class':'quick-impact'})
    for k,v in item['quick']:
        span = soup.new_tag('span'); b = soup.new_tag('b'); b.string=k; span.append(b); span.append(' '+v); qi.append(span)
    article.append(qi)
    article.append(make_details(soup,item))
    a = soup.new_tag('a', attrs={'class':'source','href':item['source'],'target':'_blank','rel':'noreferrer'})
    a.string = item['source_label'] + ' ↗'; article.append(a)
    return article


def inject_home(path: Path):
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    for old in soup.select('[data-supplemental-group="true"]'):
        old.decompose()
    target = None
    for h2 in soup.find_all('h2'):
        if h2.get_text(strip=True) == '今天還有什麼':
            section = h2.find_parent('section', class_='home-section')
            if section:
                target = section.select_one('.more-feed')
            break
    if not target:
        raise RuntimeError('Could not find 今天還有什麼 .more-feed')
    group = soup.new_tag('section', attrs={'class':'more-group','data-supplemental-group':'true'})
    head = soup.new_tag('header', attrs={'class':'more-group-head'})
    no = soup.new_tag('span', attrs={'class':'more-group-no'}); no.string='02'; head.append(no)
    div = soup.new_tag('div'); title = soup.new_tag('h3'); title.string=DATA['group_title']; div.append(title); head.append(div); group.append(head)
    for item in DATA['items']:
        group.append(make_card(soup,item))
    target.append(group)
    path.write_text(str(soup), encoding='utf-8')


def inject_daily(path: Path):
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    for old in soup.select('[data-supplemental-daily="true"]'):
        old.decompose()
    main = soup.find('main') or soup.body
    section = soup.new_tag('section', attrs={'class':'category-section','data-supplemental-daily':'true'})
    h2 = soup.new_tag('h2'); h2.string='補充有效情報'; section.append(h2)
    intro = soup.new_tag('p'); intro.string='TOP 5 之外、通過可信度、版本有效性與歷史去重的當日補充情報。'; section.append(intro)
    for item in DATA['items']:
        article = soup.new_tag('article', attrs={'class':'category-news','data-supplemental-id':item['id']})
        h3 = soup.new_tag('h3'); h3.string=f"{item['status']}｜{item['title']}"; article.append(h3)
        p = soup.new_tag('p'); p.string=item['summary']; article.append(p)
        qi = soup.new_tag('div', attrs={'class':'quick-impact'})
        for k,v in item['quick']:
            span=soup.new_tag('span'); b=soup.new_tag('b'); b.string=k; span.append(b); span.append(' '+v); qi.append(span)
        article.append(qi)
        article.append(make_details(soup,item))
        a=soup.new_tag('a', attrs={'class':'source','href':item['source'],'target':'_blank','rel':'noreferrer'}); a.string=item['source_label']+' ↗'; article.append(a)
        section.append(article)
    main.append(section)
    path.write_text(str(soup), encoding='utf-8')


inject_home(ROOT / 'index.html')
daily = ROOT / DATE / 'index.html'
if daily.exists():
    inject_daily(daily)
print(f'Injected {len(DATA["items"])} supplemental items for {DATE}')
