#!/usr/bin/env python3
"""Canonical Intelligence renderer.

The daily JSON under data/daily/YYYY-MM-DD.json is the only editable source for
summary, quick impact and full analysis. Homepage and archive are rendered from
that same record, preventing content drift.
"""
from pathlib import Path
import json, re, sys
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]

def load(date):
    p=ROOT/'data'/'daily'/f'{date}.json'
    return json.loads(p.read_text('utf-8'))

def analysis_html(soup, blocks, home=False):
    details=soup.new_tag('details'); details['class']=['home-full-analysis'] if home else []
    summary=soup.new_tag('summary'); summary.string='完整分析'; details.append(summary)
    body=soup.new_tag('div'); body['class']=['detail-body']+(['home-analysis-body'] if home else [])
    for block in blocks:
        p=soup.new_tag('p'); b=soup.new_tag('b'); b.string=block['label']+'：'; p.append(b); p.append(' '+block['text']); body.append(p)
    details.append(body); return details

def replace_analysis(card, record, home):
    old=card.find('details');
    if old: old.replace_with(analysis_html(card if isinstance(card,BeautifulSoup) else card,record['full_analysis'],home))

def main():
    date=sys.argv[1] if len(sys.argv)>1 else max(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    data=load(date); records={x['id']:x for x in data['items']}
    # Render by stable data-intel-id. Both views consume identical full_analysis blocks.
    for path,home in ((ROOT/'index.html',True),(ROOT/date/'index.html',False)):
        soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
        found=0
        for card in soup.select('[data-intel-id]'):
            rid=card.get('data-intel-id'); rec=records.get(rid)
            if not rec: continue
            old=card.find('details')
            if old: old.replace_with(analysis_html(soup,rec['full_analysis'],home))
            found+=1
        path.write_text(soup.prettify(),'utf-8')
        print(path.relative_to(ROOT),found)
if __name__=='__main__': main()
