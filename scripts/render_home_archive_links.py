#!/usr/bin/env python3
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')

def main():
    path=ROOT/'index.html'; soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    box=soup.select_one('.history-list')
    if not box: raise SystemExit('homepage .history-list missing')
    existing={}
    for a in box.find_all('a',href=True):
        m=re.fullmatch(r'(20\d{2}-\d{2}-\d{2})/?',a.get('href',''))
        if m:
            span=a.find('span'); existing[m.group(1)]=span.get_text(' ',strip=True) if span else '歷史日報'
    dates=sorted((p.name for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists()),reverse=True)
    box.clear()
    for date in dates:
        a=soup.new_tag('a',href=f'{date}/'); strong=soup.new_tag('strong'); strong.string=date; span=soup.new_tag('span'); span.string=existing.get(date,'歷史日報')
        a.append(strong); a.append(span); box.append(a)
    path.write_text(soup.prettify(),'utf-8'); print('HOME ARCHIVE LINKS:',', '.join(dates))
if __name__=='__main__': main()
