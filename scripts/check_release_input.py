#!/usr/bin/env python3
"""Validate canonical inputs before any derived rendering/publish.

This is intentionally upstream of build_intelligence.py: a release must already
have complete canonical data plus stable-ID card markup in Homepage and Daily.
The renderer enriches those cards; it must never guess article identity.
"""
from pathlib import Path
import json, re, sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
errors = []

def fail(msg): errors.append(msg)

def latest_date():
    dates = sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates: raise SystemExit('No canonical daily datasets found')
    return dates[-1]

def norm_url(url):
    return (url or '').strip().rstrip('/')

def card_ids(soup, selector, label):
    cards = soup.select(selector)
    ids = []
    for i, card in enumerate(cards, 1):
        rid = (card.get('data-intel-id') or '').strip()
        if not rid:
            fail(f'{label} card {i} missing data-intel-id')
            continue
        if card.get('data-intel-role') != 'card':
            fail(f'{label} {rid} missing data-intel-role="card"')
        ids.append(rid)
    if len(ids) != len(set(ids)):
        fail(f'{label} contains duplicate data-intel-id values')
    return ids

def source_map(soup, selector, label):
    out={}
    for card in soup.select(selector):
        rid=(card.get('data-intel-id') or '').strip()
        if not rid: continue
        source=card.select_one('a.source[href]')
        if not source:
            fail(f'{label} {rid}: missing source link')
            continue
        href=norm_url(source.get('href'))
        if not href:
            fail(f'{label} {rid}: empty source href')
            continue
        out[rid]=href
    return out

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else latest_date()
    if not DATE_RE.fullmatch(date): fail(f'invalid date: {date}')
    data_path = ROOT/'data'/'daily'/f'{date}.json'
    if not data_path.exists(): raise SystemExit(f'Missing canonical dataset: {data_path}')
    data = json.loads(data_path.read_text('utf-8'))
    if data.get('date') != date: fail(f'canonical date mismatch: {data.get("date")} != {date}')
    if int(data.get('schema_version', 0)) < 2: fail('canonical schema_version must be >=2')

    items = data.get('items') or []
    ids = [str(x.get('id','')).strip() for x in items]
    if any(not x for x in ids): fail('every canonical item requires a non-empty id')
    if len(ids) != len(set(ids)): fail('canonical item IDs must be unique')
    idset = set(ids)
    top = [x['id'] for x in items if x.get('slot') == 'top']
    more = [x['id'] for x in items if x.get('slot') == 'more']
    unknown_slots = [(x.get('id'), x.get('slot')) for x in items if x.get('slot') not in {'top','more'}]
    if unknown_slots: fail(f'unsupported slot values: {unknown_slots}')
    if len(top) != 5: fail(f'canonical TOP must contain exactly 5 items, got {len(top)}')
    if not 6 <= len(more) <= 12: fail(f'canonical Supplemental must contain 6-12 items, got {len(more)}')
    for item in items:
        blocks = item.get('full_analysis') or []
        if len(blocks) < 3: fail(f'{item.get("id")}: full_analysis requires >=3 blocks')
        for n,b in enumerate(blocks,1):
            if not str(b.get('label','')).strip() or not str(b.get('text','')).strip():
                fail(f'{item.get("id")}: block {n} requires label + text')

    visuals = data.get('visual_evidence') or {}
    orphan_visuals = set(visuals) - idset
    if orphan_visuals: fail(f'visual_evidence contains orphan IDs: {sorted(orphan_visuals)}')
    for rid, rec in visuals.items():
        if rec.get('enabled', True) is not False and not str(rec.get('source_url','')).strip():
            fail(f'{rid}: enabled visual_evidence requires source_url')
        if rec.get('enabled', True) is False and not str(rec.get('reason','')).strip():
            fail(f'{rid}: disabled visual_evidence requires reason')

    home_path = ROOT/'index.html'
    daily_path = ROOT/date/'index.html'
    if not home_path.exists(): fail('index.html missing')
    if not daily_path.exists(): fail(f'{date}/index.html missing')
    if errors:
        print('RELEASE INPUT CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)

    home = BeautifulSoup(home_path.read_text('utf-8'),'html.parser')
    daily = BeautifulSoup(daily_path.read_text('utf-8'),'html.parser')
    home_date = home.select_one('.week-asof')
    if not home_date or home_date.get_text(' ',strip=True) != date:
        fail('homepage current date does not match canonical date')
    if not daily.body or daily.body.get('data-report-date') != date:
        fail('daily body data-report-date does not match canonical date')

    home_top = card_ids(home, '.top-item', 'homepage TOP')
    home_more = card_ids(home, '.more-card', 'homepage Supplemental')
    daily_top = card_ids(daily, '#top .news', 'daily TOP')
    daily_more = card_ids(daily, '.category-news', 'daily Supplemental')

    if home_top != top: fail(f'homepage TOP order/IDs differ from canonical: {home_top} != {top}')
    if home_more != more: fail(f'homepage Supplemental order/IDs differ from canonical: {home_more} != {more}')
    if daily_top != top: fail(f'daily TOP order/IDs differ from canonical: {daily_top} != {top}')
    if daily_more != more: fail(f'daily Supplemental order/IDs differ from canonical: {daily_more} != {more}')
    if set(home_top + home_more) != idset: fail('homepage canonical ID set mismatch')
    if set(daily_top + daily_more) != idset: fail('daily canonical ID set mismatch')

    home_sources=source_map(home,'.top-item,.more-card','homepage')
    daily_sources=source_map(daily,'#top .news,.category-news','daily')
    for rid in idset:
        hs=home_sources.get(rid); ds=daily_sources.get(rid)
        if hs and ds and hs!=ds:
            fail(f'{rid}: homepage/daily source URL drift: {hs} != {ds}')

    for label, soup, selector in [('homepage',home,'.top-item,.more-card'),('daily',daily,'#top .news,.category-news')]:
        for card in soup.select(selector):
            rid = card.get('data-intel-id','?')
            if not card.select_one('details .detail-body'): fail(f'{label} {rid}: missing Full Analysis shell')
    for card in home.select('.top-item,.more-card'):
        rid=card.get('data-intel-id','?')
        if not card.select_one('.quick-impact'): fail(f'homepage {rid}: missing quick-impact')

    if errors:
        print('RELEASE INPUT CONTRACT FAILED'); print('\n'.join('- '+e for e in errors)); sys.exit(1)
    print(f'RELEASE INPUT CONTRACT PASS: {date} / {len(top)} TOP / {len(more)} Supplemental / source parity OK')

if __name__ == '__main__': main()
