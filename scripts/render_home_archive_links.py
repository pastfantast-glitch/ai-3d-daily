#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict
import json, re
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')
CFG=ROOT/'config'/'intelligence-v2.json'

def load_cfg():
    return json.loads(CFG.read_text('utf-8')) if CFG.exists() else {'categories':[]}

def daily_meta(date):
    path=ROOT/'data'/'daily'/f'{date}.json'
    if not path.exists(): return '', []
    try: data=json.loads(path.read_text('utf-8'))
    except Exception: return '', []
    items=data.get('items',[]) if isinstance(data,dict) else []
    cats=sorted({str(x.get('category','')).strip() for x in items if isinstance(x,dict) and x.get('category')})
    terms=[]
    for x in items:
        if not isinstance(x,dict): continue
        terms.extend([
            str(x.get('title','')),
            str(x.get('summary','')),
            str(x.get('quick_impact','')),
        ])
    return ' '.join(terms), cats

def tag(soup,name,**attrs):
    return soup.new_tag(name,**attrs)

def current_report_date(soup, dates):
    marker=soup.select_one('.week-asof')
    marked=marker.get_text(' ',strip=True) if marker else ''
    if marked in dates: return marked
    return dates[0] if dates else ''

def render_current_report_entry(soup,current):
    for old in soup.select('.current-report-entry'):
        old.decompose()
    if not current: return
    history=soup.select_one('section.history-section')
    if not history: return
    wrap=tag(soup,'div',attrs={'class':'current-report-entry','data-current-report-date':current})
    a=tag(soup,'a',href=f'{current}/',attrs={'class':'category-nav-card current-report-link','aria-label':f'查看 {current} 今日完整日報'})
    text=tag(soup,'div',attrs={'class':'current-report-copy'})
    eyebrow=tag(soup,'span',attrs={'class':'current-report-eyebrow'}); eyebrow.string='TODAY'; text.append(eyebrow)
    strong=tag(soup,'strong'); strong.string='查看今日完整日報'; text.append(strong)
    date=tag(soup,'span',attrs={'class':'current-report-date'}); date.string=current; a.append(text); a.append(date)
    wrap.append(a); history.insert_before(wrap)

def main():
    path=ROOT/'index.html'; soup=BeautifulSoup(path.read_text('utf-8'),'html.parser')
    box=soup.select_one('.history-list')
    if not box: raise SystemExit('homepage .history-list missing')
    cfg=load_cfg(); categories=cfg.get('categories',[])
    existing={}
    for a in box.find_all('a',href=True):
        m=re.fullmatch(r'(20\d{2}-\d{2}-\d{2})/?',a.get('href',''))
        if m:
            span=a.find('span'); existing[m.group(1)]=span.get_text(' ',strip=True) if span else '歷史日報'
    dates=sorted((p.name for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists()),reverse=True)
    current=current_report_date(soup,dates)
    history_dates=[d for d in dates if d!=current]
    render_current_report_entry(soup,current)

    old=soup.select_one('.history-controls')
    if old: old.decompose()
    controls=tag(soup,'div',attrs={'class':'history-controls','data-history-controls':''})
    search=tag(soup,'input',attrs={'class':'history-search','type':'search','placeholder':'搜尋 Meshy / Blender / Retarget / UE5…','aria-label':'搜尋歷史情報'})
    controls.append(search)
    cats=tag(soup,'div',attrs={'class':'history-filter-row','aria-label':'歷史分類篩選'})
    all_btn=tag(soup,'button',attrs={'type':'button','class':'history-filter is-active','data-history-category':'all'}); all_btn.string='全部'; cats.append(all_btn)
    for c in categories:
        b=tag(soup,'button',attrs={'type':'button','class':'history-filter','data-history-category':c['id']}); b.string=c['label']; cats.append(b)
    controls.append(cats)
    ranges=tag(soup,'div',attrs={'class':'history-filter-row history-range-row','aria-label':'歷史日期範圍'})
    for value,label in [('7','最近 7 天'),('30','30 天'),('all','全部日期')]:
        cls='history-filter'+(' is-active' if value=='all' else '')
        b=tag(soup,'button',attrs={'type':'button','class':cls,'data-history-range':value}); b.string=label; ranges.append(b)
    controls.append(ranges)
    box.insert_before(controls)

    grouped=defaultdict(lambda:defaultdict(list))
    for d in history_dates:
        y,m,_=d.split('-'); grouped[y][m].append(d)
    box.clear()
    for year in sorted(grouped,reverse=True):
        yd=tag(soup,'details',attrs={'class':'archive-year','data-archive-year':year})
        if current.startswith(year+'-'): yd['open']=''
        ys=tag(soup,'summary'); ys.string=year; yd.append(ys)
        months=tag(soup,'div',attrs={'class':'archive-months'})
        for month in sorted(grouped[year],reverse=True):
            md=tag(soup,'details',attrs={'class':'archive-month','data-archive-month':f'{year}-{month}'})
            if current.startswith(f'{year}-{month}-'): md['open']=''
            ms=tag(soup,'summary'); ms.string=f'{int(month)} 月'; md.append(ms)
            entries=tag(soup,'div',attrs={'class':'archive-entries'})
            for date in grouped[year][month]:
                terms,categories_for_day=daily_meta(date)
                a=tag(soup,'a',href=f'{date}/',attrs={'class':'history-entry','data-history-date':date,'data-history-categories':' '.join(categories_for_day),'data-history-search':f'{date} {existing.get(date,"歷史日報")} {terms}'.lower()})
                strong=tag(soup,'strong'); strong.string=date
                span=tag(soup,'span'); span.string=existing.get(date,'歷史日報')
                a.append(strong); a.append(span); entries.append(a)
            md.append(entries); months.append(md)
        yd.append(months); box.append(yd)
    empty=tag(soup,'p',attrs={'class':'history-empty','hidden':''}); empty.string='找不到符合條件的歷史情報。'; box.append(empty)
    path.write_text(soup.prettify(),'utf-8')
    print('HOME CURRENT REPORT:',current or 'none')
    print('HOME HISTORY LIBRARY:',', '.join(history_dates))
if __name__=='__main__': main()
