#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict
import json, re
from bs4 import BeautifulSoup
from render_information_architecture import global_nav

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')
CFG=ROOT/'config'/'intelligence-v2.json'
HISTORY_DIR=ROOT/'history'
HISTORY_INDEX=HISTORY_DIR/'index.html'


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


def current_report_date(home_soup, dates):
    marker=home_soup.select_one('.week-asof')
    marked=marker.get_text(' ',strip=True) if marker else ''
    if marked in dates: return marked
    return dates[0] if dates else ''


def remove_home_history(home_soup):
    for node in home_soup.select('.current-report-entry, section.history-section'):
        node.decompose()


def append_current_report(soup, main, current):
    if not current: return
    wrap=tag(soup,'div',attrs={'class':'current-report-entry','data-current-report-date':current})
    a=tag(soup,'a',href=f'../{current}/',attrs={'class':'category-nav-card current-report-link','aria-label':f'查看 {current} 今日完整日報'})
    text=tag(soup,'div',attrs={'class':'current-report-copy'})
    eyebrow=tag(soup,'span',attrs={'class':'current-report-eyebrow'}); eyebrow.string='TODAY'; text.append(eyebrow)
    strong=tag(soup,'strong'); strong.string='查看今日完整日報'; text.append(strong)
    date=tag(soup,'span',attrs={'class':'current-report-date'}); date.string=current
    a.append(text); a.append(date); wrap.append(a); main.append(wrap)


def append_controls(soup, section, cfg):
    controls=tag(soup,'div',attrs={'class':'history-controls','data-history-controls':''})
    search=tag(soup,'input',attrs={'class':'history-search','type':'search','placeholder':'搜尋 Meshy / Blender / Retarget / UE5…','aria-label':'搜尋歷史情報'})
    controls.append(search)

    cats=tag(soup,'div',attrs={'class':'history-filter-row','aria-label':'歷史分類篩選'})
    all_btn=tag(soup,'button',attrs={'type':'button','class':'history-filter is-active','data-history-category':'all'}); all_btn.string='全部'; cats.append(all_btn)
    for c in cfg.get('categories',[]):
        b=tag(soup,'button',attrs={'type':'button','class':'history-filter','data-history-category':c['id']}); b.string=c['label']; cats.append(b)
    controls.append(cats)

    ranges=tag(soup,'div',attrs={'class':'history-filter-row history-range-row','aria-label':'歷史日期範圍'})
    for value,label in [('7','最近 7 天'),('30','30 天'),('all','全部日期')]:
        cls='history-filter'+(' is-active' if value=='all' else '')
        b=tag(soup,'button',attrs={'type':'button','class':cls,'data-history-range':value}); b.string=label; ranges.append(b)
    controls.append(ranges)
    section.append(controls)


def append_history_list(soup, section, current, dates):
    history_dates=[d for d in dates if d!=current]
    grouped=defaultdict(lambda:defaultdict(list))
    for d in history_dates:
        y,m,_=d.split('-'); grouped[y][m].append(d)

    box=tag(soup,'div',attrs={'class':'history-list'})
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
                search_text=f'{date} 歷史日報 {terms}'.lower()
                a=tag(soup,'a',href=f'../{date}/',attrs={
                    'class':'history-entry',
                    'data-history-date':date,
                    'data-history-categories':' '.join(categories_for_day),
                    'data-history-search':search_text,
                })
                strong=tag(soup,'strong'); strong.string=date
                span=tag(soup,'span'); span.string='歷史日報'
                a.append(strong); a.append(span); entries.append(a)
            md.append(entries); months.append(md)
        yd.append(months); box.append(yd)
    empty=tag(soup,'p',attrs={'class':'history-empty','hidden':''}); empty.string='找不到符合條件的歷史情報。'; box.append(empty)
    section.append(box)
    return history_dates


def render_history_page(current, dates, cfg):
    soup=BeautifulSoup('<!doctype html><html lang="zh-Hant"><head></head><body></body></html>','html.parser')
    head=soup.head
    head.append(tag(soup,'meta',attrs={'charset':'utf-8'}))
    head.append(tag(soup,'meta',attrs={'name':'viewport','content':'width=device-width,initial-scale=1'}))
    title=tag(soup,'title'); title.string='歷史日報｜AI 3D Production Intelligence'; head.append(title)
    for href in ('../styles.css','../shared-components.css','../home.css','../home-content.css','../home-components.css'):
        head.append(tag(soup,'link',attrs={'rel':'stylesheet','href':href}))

    body=soup.body; body['class']=['home-page','history-page']; body['data-report-date']=current
    body.append(global_nav(soup,current,cfg,active='history',context='history'))
    main=tag(soup,'main',attrs={'class':'page home-main history-main'})
    append_current_report(soup,main,current)

    section=tag(soup,'section',attrs={'class':'home-section history-section','id':'history'})
    headrow=tag(soup,'div',attrs={'class':'block-head'})
    headinner=tag(soup,'div')
    kicker=tag(soup,'span'); kicker.string='ARCHIVE'; headinner.append(kicker)
    h1=tag(soup,'h1'); h1.string='歷史日報'; headinner.append(h1); headrow.append(headinner); section.append(headrow)
    note=tag(soup,'p',attrs={'class':'history-note'}); note.string='搜尋與回顧往期 Production Intelligence；首頁只保留今天的重要情報。'; section.append(note)
    append_controls(soup,section,cfg)
    history_dates=append_history_list(soup,section,current,dates)
    main.append(section); body.append(main)
    body.append(tag(soup,'script',src='../history.js'))
    body.append(tag(soup,'script',src='../preference.js',attrs={'type':'module'}))

    HISTORY_DIR.mkdir(parents=True,exist_ok=True)
    HISTORY_INDEX.write_text(soup.prettify()+'\n','utf-8')
    return history_dates


def main():
    home_path=ROOT/'index.html'
    if not home_path.exists(): raise SystemExit('homepage index.html missing')
    home_soup=BeautifulSoup(home_path.read_text('utf-8'),'html.parser')
    dates=sorted((p.name for p in ROOT.iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name) and (p/'index.html').exists()),reverse=True)
    current=current_report_date(home_soup,dates)
    cfg=load_cfg()

    remove_home_history(home_soup)
    home_path.write_text(home_soup.prettify()+'\n','utf-8')
    history_dates=render_history_page(current,dates,cfg)

    print('HISTORY PORTAL CURRENT REPORT:',current or 'none')
    print('HISTORY PORTAL ARCHIVES:',', '.join(history_dates))
    print('HOMEPAGE HISTORY EMBED: removed')

if __name__=='__main__': main()
