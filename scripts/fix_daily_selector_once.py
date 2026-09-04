#!/usr/bin/env python3
from pathlib import Path
p=Path('scripts/check_release_input.py')
s=p.read_text('utf-8')
old="daily_more=card_ids(daily,'.category-news','daily Supplemental')"
new="daily_more=card_ids(daily,'.daily-card-more','daily Supplemental')"
if old not in s:
    raise SystemExit('daily Supplemental selector block not found')
s=s.replace(old,new)
s=s.replace("daily_sources=source_map(daily,'#top .news,.category-news','daily')","daily_sources=source_map(daily,'#top .news,.daily-card-more','daily')")
s=s.replace("('daily',daily,'#top .news,.category-news')","('daily',daily,'#top .news,.daily-card-more')")
p.write_text(s,'utf-8')
print('check_release_input daily Supplemental selector aligned to renderer: .daily-card-more')
