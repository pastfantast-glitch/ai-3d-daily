#!/usr/bin/env python3
from pathlib import Path
import re,sys
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$'); errors=[]
dirs=sorted(p for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
for i,d in enumerate(dirs):
    text=(d/'index.html').read_text('utf-8'); soup=BeautifulSoup(text,'html.parser'); date=d.name
    def need(ok,msg):
        if not ok: errors.append(f'{date}: {msg}')
    need('null' not in text.lower(),'literal null present')
    need('archive-page' in soup.body.get('class',[]),'missing archive-page class')
    need(soup.body.get('data-report-date')==date,'report date contract mismatch')
    need(bool(soup.find('link',href=re.compile(r'\.\./styles\.css\?v='))),'missing shared styles.css')
    need(bool(soup.find('link',href=re.compile(r'\.\./daily\.css\?v='))),'missing daily.css')
    need(bool(soup.find('script',src=re.compile(r'\.\./daily\.js\?v='))),'missing daily.js')
    need(not soup.find('script',src=re.compile(r'accordion\.js')),'legacy accordion.js still referenced')
    need(bool(soup.select('#top .news')),'missing TOP section/cards')
    for a in soup.find_all('a',target='_blank'):
        rel=set(a.get('rel',[])); need({'noopener','noreferrer'}<=rel,'unsafe target=_blank link')
    expected_prev=dirs[i-1].name if i else '' ; expected_next=dirs[i+1].name if i+1<len(dirs) else ''
    need(soup.body.get('data-previous','')==expected_prev,'previous date mismatch')
    need(soup.body.get('data-next','')==expected_next,'next date mismatch')
if errors:
    print('DAILY CONTRACT FAILED');print('\n'.join('- '+e for e in errors));sys.exit(1)
print(f'DAILY CONTRACT PASS: {len(dirs)} reports')
