#!/usr/bin/env python3
"""Render archive previous/next state from the actual set of daily snapshots.

Navigation is structural derived data. Creating a new day must automatically make
the previous day point forward to it; content authors should never hand-maintain
this relationship.
"""
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')

def main():
    dirs=sorted(p for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
    changed=[]
    for i,d in enumerate(dirs):
        path=d/'index.html'; text=path.read_text('utf-8'); soup=BeautifulSoup(text,'html.parser')
        if not soup.body: raise SystemExit(f'{d.name}: missing body')
        prev=dirs[i-1].name if i else ''
        nxt=dirs[i+1].name if i+1<len(dirs) else ''
        soup.body['data-report-date']=d.name
        soup.body['data-previous']=prev
        soup.body['data-next']=nxt

        # Normalize any legacy static day-nav when present. daily.js builds the
        # modern bar from body data attributes, so this is compatibility only.
        nav=soup.find('nav',class_='day-nav')
        if nav:
            nav.clear()
            if prev:
                a=soup.new_tag('a',href=f'../{prev}/'); a.string=f'← {prev}'; nav.append(a)
            else:
                span=soup.new_tag('span'); span.string='最早日報'; nav.append(span)
            if nxt:
                a=soup.new_tag('a',href=f'../{nxt}/'); a.string=f'{nxt} →'; nav.append(a)
            else:
                span=soup.new_tag('span'); span.string='最新日報'; nav.append(span)

        out=soup.prettify()
        if out!=text:
            path.write_text(out,'utf-8'); changed.append(str(path.relative_to(ROOT)))
    print('DAILY NAVIGATION RENDER:', ', '.join(changed) if changed else 'already current')

if __name__=='__main__': main()
