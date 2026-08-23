#!/usr/bin/env python3
from pathlib import Path
import re
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
VERSION='20260823-1'
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')

def migrate(path,prev,next_):
    text=path.read_text('utf-8'); soup=BeautifulSoup(text,'html.parser'); date=path.parent.name
    body=soup.body; body['class']=sorted(set(body.get('class',[])+['archive-page'])); body['data-report-date']=date
    if prev: body['data-previous']=prev
    elif body.has_attr('data-previous'): del body['data-previous']
    if next_: body['data-next']=next_
    elif body.has_attr('data-next'): del body['data-next']
    # One shared stylesheet and one shared behavior layer for every archive.
    for link in list(soup.find_all('link',rel='stylesheet')):
        href=link.get('href','')
        if href.endswith('styles.css') or '/styles.css' in href or href.startswith('styles.css') or href.startswith('../styles.css'):
            link['href']=f'../styles.css?v={VERSION}'
    if not soup.find('link',href=re.compile(r'\.\./daily\.css')):
        tag=soup.new_tag('link',rel='stylesheet',href=f'../daily.css?v={VERSION}'); soup.head.append(tag)
    for script in list(soup.find_all('script',src=True)):
        if script['src'].endswith('accordion.js'): script.decompose()
    if not soup.find('script',src=re.compile(r'\.\./daily\.js')):
        tag=soup.new_tag('script',src=f'../daily.js?v={VERSION}',defer=True); soup.head.append(tag)
    # Normalize archive identity without rewriting historical intelligence.
    h1=soup.select_one('.site-head h1')
    if h1: h1.string=f'{date} 歷史日報'
    top=soup.select_one('#top .block-head')
    if top:
        p=top.find('p')
        nav=[]
        if prev: nav.append(f'前一日 {prev}')
        if next_: nav.append(f'下一日 {next_}')
        else: nav.append('最新日報')
        if p: p.string=' · '.join(nav)
    # Normalize explicit bottom day-nav if present.
    nav=soup.find('nav',class_='day-nav')
    if nav:
        nav.clear()
        if prev:
            a=soup.new_tag('a',href=f'../{prev}/');a.string=f'← {prev}';nav.append(a)
        home=soup.new_tag('a',href='../');home.string='回首頁';nav.append(home)
        if next_:
            a=soup.new_tag('a',href=f'../{next_}/');a.string=f'{next_} →';nav.append(a)
        else:
            span=soup.new_tag('span');span.string='最新日報';nav.append(span)
    for a in soup.find_all('a',target='_blank'):
        rel=set(a.get('rel',[]));rel.update({'noopener','noreferrer'});a['rel']=sorted(rel)
    path.write_text(soup.prettify(),'utf-8')

def main():
    dirs=sorted(p for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
    for i,d in enumerate(dirs): migrate(d/'index.html',dirs[i-1].name if i else '',dirs[i+1].name if i+1<len(dirs) else '')
    print('Migrated',len(dirs),'daily reports:',', '.join(d.name for d in dirs))
if __name__=='__main__': main()
