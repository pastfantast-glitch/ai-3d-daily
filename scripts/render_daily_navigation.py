#!/usr/bin/env python3
"""Render archive navigation and normalize shared presentation structure.

Archive intelligence is immutable snapshot content. Navigation and semantic
presentation classes are derived structure, so every canonical publish updates both
from the actual archive set before QA.
"""
from pathlib import Path
import re
from bs4 import BeautifulSoup
from normalize_archive_presentation import main as normalize_presentation

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def ensure_shared_stylesheet(soup):
    """Ensure archive pages consume the canonical shared component stylesheet."""
    if soup.head is None:
        raise SystemExit('archive page missing head')
    existing=soup.head.find('link', href=re.compile(r'^\.\./shared-components\.css(?:\?v=.*)?$'))
    if existing:
        return
    link=soup.new_tag('link', rel='stylesheet', href='../shared-components.css')
    daily=soup.head.find('link', href=re.compile(r'^\.\./daily\.css(?:\?v=.*)?$'))
    if daily:
        daily.insert_before(link)
    else:
        soup.head.append(link)


def ensure_history_nav(soup, href):
    """Keep History as one global content destination on every archive shell."""
    inner=soup.select_one('nav.global-category-nav .global-category-nav-inner')
    if not inner:
        return False
    links=inner.select('a.global-history-link[data-global-view="history"]')
    if links:
        primary=links[0]; primary['href']=href; primary.string='歷史日報'
        for duplicate in links[1:]: duplicate.decompose()
        return False
    link=soup.new_tag('a',href=href,attrs={
        'class':'global-category-link global-history-link',
        'data-global-view':'history',
    })
    link.string='歷史日報'; inner.append(link)
    return True


def normalize_category_history_nav(date_dir):
    changed=[]
    for path in sorted(date_dir.glob('*/index.html')):
        text=path.read_text('utf-8'); soup=BeautifulSoup(text,'html.parser')
        if ensure_history_nav(soup,'../../history/'):
            out=soup.prettify()
            if not out.endswith('\n'): out+='\n'
            path.write_text(out,'utf-8'); changed.append(str(path.relative_to(ROOT)))
        else:
            # Existing link may need its href normalized after a legacy render.
            link=soup.select_one('a.global-history-link[data-global-view="history"]')
            if link and link.get('href')!='../../history/':
                link['href']='../../history/'
                out=soup.prettify()
                if not out.endswith('\n'): out+='\n'
                path.write_text(out,'utf-8'); changed.append(str(path.relative_to(ROOT)))
    return changed


def main():
    dirs=sorted(p for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists())
    changed=[]
    for i,d in enumerate(dirs):
        path=d/'index.html'; text=path.read_text('utf-8'); soup=BeautifulSoup(text,'html.parser')
        if not soup.body: raise SystemExit(f'{d.name}: missing body')
        ensure_shared_stylesheet(soup)
        prev=dirs[i-1].name if i else ''
        nxt=dirs[i+1].name if i+1<len(dirs) else ''
        soup.body['data-report-date']=d.name
        soup.body['data-previous']=prev
        soup.body['data-next']=nxt
        ensure_history_nav(soup,'../history/')

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
        if not out.endswith('\n'): out+='\n'
        if out!=text:
            path.write_text(out,'utf-8'); changed.append(str(path.relative_to(ROOT)))
        changed.extend(normalize_category_history_nav(d))
    print('DAILY NAVIGATION RENDER:', ', '.join(changed) if changed else 'already current')

    # Presentation normalization is structural derived data too. Keeping it in the
    # same archive-render stage guarantees old and new reports use one Daily DOM
    # contract without introducing another writer or rewriting intelligence text.
    normalize_presentation()

if __name__=='__main__': main()
