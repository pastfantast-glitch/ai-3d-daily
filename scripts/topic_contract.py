"""Topics share canonical identity, source-age and reader gates, never homepage quotas."""
from collection_settings import PRIMARY, all_items, validate_settings, within_topic_window
from source_quality import source_window_errors
from reader_quality import reader_errors
from urllib.parse import urlsplit


def select_topics(survivors, settings, maximum):
    primary = [c for c in survivors if PRIMARY in c.get('topic_ids', [PRIMARY])][:maximum]
    selected = {c['candidate_id'] for c in primary}
    extras = []
    assignments = {}
    for topic in (settings or {}).get('topics', []):
        if not topic['enabled'] or topic['id'] == PRIMARY:
            continue
        matches = [c for c in survivors if topic['id'] in c.get('topic_ids', [])][:topic['target_items']]
        assignments[topic['id']] = {c['candidate_id'] for c in matches}
        for candidate in matches:
            if candidate['candidate_id'] not in selected:
                extras.append(candidate)
                selected.add(candidate['candidate_id'])
    def bound(candidate):
        bindings = ([PRIMARY] if candidate in primary else []) + [tid for tid, ids in assignments.items() if candidate['candidate_id'] in ids]
        return {**candidate, 'topic_ids':bindings}
    return [bound(c) for c in primary], [bound(c) for c in extras], [c for c in survivors if c['candidate_id'] not in selected]


def topic_errors(data):
    extras = data.get('topic_items', [])
    settings = (data.get('metadata') or {}).get('collection_settings')
    if not settings:
        return ['topic items require collection settings snapshot'] if extras else []
    try:
        validate_settings(settings)
    except (TypeError, ValueError, KeyError) as exc:
        return [str(exc)]
    errors = []
    if not isinstance(extras, list) or any(not isinstance(x, dict) for x in extras):
        return ['topic_items must contain article objects']
    topics = {t['id']:t for t in settings['topics'] if t['enabled']}
    sources = {urlsplit(s['base_url']).hostname.removeprefix('www.'):s for s in settings['sources'] if s['enabled']}
    ids, urls = set(), set()
    for item in all_items(data):
        rid, url = item.get('id'), item.get('source_url')
        if not rid or not url or rid in ids or url in urls:
            errors.append('topic/homepage duplicate or missing identity')
        ids.add(rid); urls.add(url)
        bindings = item.get('topic_ids', [PRIMARY])
        host = (urlsplit(url or '').hostname or '').removeprefix('www.')
        source = next((s for domain,s in sources.items() if host == domain or host.endswith('.'+domain)), None)
        if (not isinstance(bindings, list) or not bindings or any(t not in topics for t in bindings)
                or not source or not set(bindings) <= set(source['topic_ids'])):
            errors.append(f'{rid}: invalid enabled source/topic binding')
        if 'navigation_category_ids' in item:
            nav=item['navigation_category_ids']; allowed={c['id'] for c in settings.get('navigation',[]) if c['enabled'] and source and source['id'] in c['source_ids']}
            if not isinstance(nav,list) or any(not isinstance(x,str) for x in nav) or len(set(nav))!=len(nav) or not set(nav)<=allowed:
                errors.append(f'{rid}: invalid navigation category binding')
        if item in data.get('items', []) and PRIMARY not in bindings:
            errors.append(f'{rid}: unrelated article reached AI/3D homepage')
        if item in extras:
            if item.get('homepage_tier') != 'category_only' or not set(bindings) - {PRIMARY}:
                errors.append(f'{rid}: topic-only item requires a separate topic')
        errors.extend(f'{rid}: {e}' for e in source_window_errors(item, data['date']))
        for tid in bindings if isinstance(bindings,list) else []:
            if tid in topics and not within_topic_window(item.get('source_published_at'),data['date'],topics[tid]['max_age_months']):
                errors.append(f'{rid}: exceeds configured source window for {tid}')
    for tid, topic in topics.items():
        if tid != PRIMARY and sum(tid in i.get('topic_ids', []) for i in all_items(data)) > topic['target_items']:
            errors.append(f'{tid}: per-edition topic limit exceeded')
    if extras:
        errors.extend(reader_errors(all_items(data), data['date']))
    return errors


def topic_receipt(data):
    extras = data.get('topic_items', [])
    return {'item_count':len(extras), 'ids':[x['id'] for x in extras]}
