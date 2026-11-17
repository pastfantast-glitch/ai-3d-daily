"""Single Publisher renders topic archives using the existing image-card components."""
import json
import sys
from pathlib import Path
from datetime import date as date_type, timedelta
from bs4 import BeautifulSoup
from collection_settings import load_settings, all_items, PRIMARY
from topic_contract import topic_errors
from render_information_architecture import home_card
from build_intelligence import analysis_html
from inject_visual_previews import make_preview

ROOT = Path(__file__).resolve().parents[1]


def build(root, date):
    settings = load_settings(root)
    if not settings:
        return
    editions = []
    for path in sorted((root/'data/daily').glob('20??-??-??.json'), reverse=True):
        if path.stem > date or (path.stem != date and not (root/'data/publish'/f'{path.stem}.done.json').exists()):
            continue
        data = json.loads(path.read_text('utf-8'))
        if path.stem == date:
            errors = topic_errors(data)
            if errors: raise ValueError('; '.join(errors))
        manifest = root/'assets/visual'/path.stem/'manifest.json'
        visuals = {v['id']:v for v in json.loads(manifest.read_text('utf-8')).get('entries', [])} if manifest.exists() else {}
        editions.append((data, visuals))
    catalog = []
    for topic in settings['topics']:
        if topic['id'] == PRIMARY:
            continue
        # Pausing collection preserves all previously published topic articles.
        records, seen = [], set()
        for data, visuals in editions:
            for item in all_items(data):
                if topic['id'] in item.get('topic_ids', []) and item['id'] not in seen:
                    records.append((data['date'], item, visuals.get(item['id'])))
                    seen.add(item['id'])
        soup = BeautifulSoup((root/'topics/template.html').read_text('utf-8'), 'html.parser')
        soup.title.string = topic['name'] + '｜AI／3D Daily'
        soup.select_one('h1').string = topic['name']
        soup.select_one('#description').string = topic['description']
        soup.select_one('#edition').string = f'最新發布：{date}・累計收錄 {len(records)} 篇' + ('・已暫停收集' if not topic['enabled'] else '')
        soup.body['data-topic-id'] = topic['id']
        soup.body['data-release-date'] = date
        grid = soup.select_one('#topic-cards')
        for edition, item, visual in records:
            card = home_card(soup, item)
            card['data-search'] = ' '.join([item['title'], item['summary'], item.get('subcategory', '')]).casefold()
            card.select_one('details').replace_with(analysis_html(soup, item, home=True))
            card.select_one('.article-date').append(f'・收錄 {edition}')
            if not visual or visual.get('status') not in ('ok', 'fallback_card'):
                raise ValueError(f"Topic image unavailable: {item['id']}")
            card.select_one('details').insert_before(make_preview(soup, visual, '../../'))
            grid.append(card)
        if records:
            soup.select_one('#empty')['hidden'] = ''
        out = root/'topics'/topic['id']/'index.html'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(str(soup), 'utf-8')
        catalog.append({'id':topic['id'], 'name':topic['name'], 'description':topic['description'], 'enabled':topic['enabled'], 'count':len(records), 'url':f'{topic["id"]}/'})
    (root/'topics/catalog.json').write_text(json.dumps({'date':date, 'topics':catalog}, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    cutoff = (date_type.fromisoformat(date)-timedelta(days=29)).isoformat()
    metrics = {s['id']:{'checked':0,'candidates':0,'published':0,'rejected':0,'reserve':0} for s in settings['sources']}
    for data, _ in editions:
        if data['date'] < cutoff: continue
        probe = ((data.get('metadata') or {}).get('discovery_coverage') or {}).get('registered_source_probe') or {}
        for sid, record in (probe.get('sources') or {}).items():
            if sid in metrics:
                metrics[sid]['checked'] += int(record.get('status') != 'not-scheduled')
                metrics[sid]['candidates'] += int(record.get('candidates_found') or 0)
        ledger = root/'data/candidates/decision-ledger'/f"{data['date']}.json"
        if ledger.exists():
            for row in json.loads(ledger.read_text('utf-8')).get('items', []):
                from urllib.parse import urlsplit
                host = (urlsplit(row.get('source_url', '')).hostname or '').removeprefix('www.')
                source = next((s for s in settings['sources'] if urlsplit(s['base_url']).hostname.removeprefix('www.') == host), None)
                key = {'published':'published','rejected':'rejected','backlog':'reserve'}.get(row.get('decision'))
                if source and key: metrics[source['id']][key] += 1
    out = root/'data/ops/source-metrics.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'date':date,'from':cutoff,'scope':'verified editions only; failed runs excluded','sources':metrics}, ensure_ascii=False, indent=2)+'\n','utf-8')


if __name__ == '__main__':
    build(ROOT, sys.argv[1])
    print('TOPIC PAGES PASS: existing cards, source dates, analyses and local images rendered')
