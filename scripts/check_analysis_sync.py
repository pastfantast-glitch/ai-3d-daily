#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup
import sys

ROOT=Path(__file__).resolve().parents[1]
home=BeautifulSoup((ROOT/'index.html').read_text('utf-8'),'html.parser')
spans=home.select('.home-hero .topline span')
date=spans[-1].get_text(strip=True) if spans else ''
daily_path=ROOT/date/'index.html'
errors=[]

def norm(h): return (h or '').strip().rstrip('/')
def body_text(details):
    body=details.select_one('.detail-body') if details else None
    return ' '.join(body.stripped_strings) if body else ''

if not daily_path.exists():
    errors.append(f'canonical daily missing for {date}')
else:
    daily=BeautifulSoup(daily_path.read_text('utf-8'),'html.parser')
    canonical={}
    for card in daily.select('article.news, article.category-news'):
        a=card.select_one('a.source[href]'); d=card.find('details')
        if a and d: canonical[norm(a.get('href'))]=body_text(d)
    checked=0
    for card in home.select('.top-item, .more-card'):
        a=card.select_one('a.source[href]'); d=card.find('details')
        if not a or not d: continue
        href=norm(a.get('href')); expected=canonical.get(href)
        if expected is None:
            errors.append(f'no canonical daily card for {href}')
        elif body_text(d)!=expected:
            errors.append(f'full analysis drift: {href}')
        checked+=1
    if checked < 11:
        errors.append(f'expected at least 11 homepage cards with analysis, got {checked}')

if errors:
    print('FULL ANALYSIS PARITY FAILED')
    print('\n'.join('- '+e for e in errors))
    sys.exit(1)
print(f'FULL ANALYSIS PARITY PASS: homepage matches {date} daily report')
