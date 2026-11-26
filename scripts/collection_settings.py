"""Owner-managed public collection settings; no credentials or publication authority."""
import copy
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = 'ai-3d'
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{1,47}$')


def public_url(value):
    if not isinstance(value, str) or len(value) > 1500:
        return False
    try:
        u = urlsplit(value)
        host = u.hostname or ''
        if (u.scheme != 'https' or u.username or u.password or u.fragment or u.port not in (None, 443)
                or '.' not in host or host.endswith(('.local', '.internal', '.localhost', '.test', '.invalid'))):
            return False
        try:
            ipaddress.ip_address(host)
            return False  # no IP literals; fetching separately verifies DNS and redirects
        except ValueError:
            return bool(re.fullmatch(r'[a-zA-Z0-9.-]+', host)) and not host.endswith('.')
    except ValueError:
        return False


def validate_settings(data):
    def require(ok, message):
        if not ok:
            raise ValueError('Collection settings: ' + message)
    def text(value, limit, empty=False):
        return isinstance(value, str) and len(value) <= limit and (empty or bool(value.strip())) and not any(ord(c) < 32 for c in value)
    require(isinstance(data, dict) and set(data) == {'schema_version', 'topics', 'sources'} and type(data['schema_version']) is int and data['schema_version'] == 1, 'invalid schema')
    require(isinstance(data['topics'], list) and 1 <= len(data['topics']) <= 20, '1–20 topics required')
    ids = set()
    for t in data['topics']:
        require(isinstance(t, dict) and set(t) == {'id','name','description','enabled','include_terms','exclude_terms','target_items','max_age_months'}, 'invalid topic fields')
        require(isinstance(t['id'], str) and SLUG.fullmatch(t['id']) and t['id'] not in ids, 'unique topic URL required')
        ids.add(t['id'])
        require(text(t['name'], 80) and text(t['description'], 500, True), 'invalid topic text')
        require(type(t['enabled']) is bool and type(t['target_items']) is int and 1 <= t['target_items'] <= 30, 'invalid topic target/status')
        require(type(t['max_age_months']) is int and 1 <= t['max_age_months'] <= 12, 'source age must be 1–12 months')
        for key in ('include_terms','exclude_terms'):
            require(isinstance(t[key], list) and len(t[key]) <= 30 and all(text(x,80) for x in t[key]), 'invalid topic keywords')
        require(t['id'] == PRIMARY or bool(t['include_terms']), 'custom topic needs inclusion keywords')
    require(PRIMARY in ids and next(t for t in data['topics'] if t['id']==PRIMARY)['enabled'], 'AI/3D homepage must stay enabled')
    require(next(t for t in data['topics'] if t['id']==PRIMARY)['target_items'] == 30, 'AI/3D target remains governed by publication contract')
    require(isinstance(data['sources'], list) and 1 <= len(data['sources']) <= 100, '1–100 sources required')
    seen, hosts = set(), set()
    for s in data['sources']:
        require(isinstance(s,dict) and set(s)=={'id','name','base_url','endpoints','enabled','topic_ids'}, 'invalid source fields')
        require(isinstance(s['id'],str) and SLUG.fullmatch(s['id']) and s['id'] not in seen, 'unique source ID required')
        seen.add(s['id'])
        require(text(s['name'],100) and public_url(s['base_url']) and type(s['enabled']) is bool, 'invalid source name/URL/status')
        host = urlsplit(s['base_url']).hostname.removeprefix('www.')
        require(host not in hosts, 'use one source with multiple topic bindings per domain'); hosts.add(host)
        require(isinstance(s['topic_ids'],list) and len(s['topic_ids']) <= 20 and len(set(s['topic_ids'])) == len(s['topic_ids']) and set(s['topic_ids']) <= ids, 'invalid source topics')
        require(not s['enabled'] or bool(s['topic_ids']), 'unconnected source must be disabled')
        require(isinstance(s['endpoints'],list) and 1 <= len(s['endpoints']) <= 5, '1–5 source endpoints required')
        require(all(public_url(u) and (urlsplit(u).hostname.removeprefix('www.') == host or urlsplit(u).hostname.endswith('.'+host)) for u in s['endpoints']), 'endpoints must stay on source domain')
    require(any(s['enabled'] and PRIMARY in s['topic_ids'] for s in data['sources']), 'at least one AI/3D source must remain enabled')
    return data


def load_settings(root=ROOT):
    path = root/'config/collection-admin.json'
    return validate_settings(json.loads(path.read_text('utf-8'))) if path.exists() else None


def effective_hybrid(base, settings):
    if not settings:
        return base
    validate_settings(settings)
    cfg = copy.deepcopy(base)
    prior = {s['id']:s for s in cfg['discovery_source_pool']['sources']}
    active_topics = {t['id'] for t in settings['topics'] if t['enabled']}
    cfg['discovery_source_pool']['sources'] = [{**prior.get(s['id'], {}),
        'id':s['id'], 'name':s['name'], 'base_url':s['base_url'], 'domain':urlsplit(s['base_url']).hostname.removeprefix('www.'),
        'enabled':s['enabled'] and bool(set(s['topic_ids']) & active_topics), 'topic_ids':s['topic_ids'],
        'discovery_mode':'active-candidate-source', 'ranking_bonus':0, 'required_daily_check':False,
        'categories':prior.get(s['id'],{}).get('categories', ['emerging-case'])} for s in settings['sources']]
    enabled = {s['id'] for s in cfg['discovery_source_pool']['sources'] if s['enabled']}
    probe = cfg['registered_source_coverage_probe']
    probe['core_source_ids'] = [x for x in probe['core_source_ids'] if x in enabled]
    # Keep the same bounded rotation and neutral ranking. New sources join rotation.
    probe['rolling_window_days'] = max(probe['rolling_window_days'], (len(enabled)+probe['rotating_sources_per_day']-1)//probe['rotating_sources_per_day'])
    return cfg


def snapshot_hybrid(data, cfg):
    settings = (data.get('metadata') or {}).get('collection_settings') if isinstance(data,dict) else None
    return effective_hybrid(cfg, settings) if settings else cfg


def within_topic_window(published, reference_date, months):
    from datetime import date
    import calendar
    try:
        today=date.fromisoformat(reference_date); source=date.fromisoformat(published)
        ym=today.year*12+today.month-1-months;year,month=divmod(ym,12);month+=1
        cutoff=date(year,month,min(today.day,calendar.monthrange(year,month)[1]))
        return cutoff <= source <= today
    except (ValueError,TypeError):
        return False


def topic_matches(meta, source, settings, primary_match=False, reference_date=None):
    text = ' '.join(str(meta.get(k) or '') for k in ('title','description','article_excerpt')).casefold()
    result = []
    for topic in (settings or {}).get('topics', []):
        if not topic['enabled'] or topic['id'] not in source.get('topic_ids', [PRIMARY]):
            continue
        if any(term.casefold() in text for term in topic['exclude_terms']):
            continue
        if reference_date and not within_topic_window(meta.get('published'),reference_date,topic['max_age_months']):
            continue
        if topic['id'] == PRIMARY:
            if primary_match and (not topic['include_terms'] or any(term.casefold() in text for term in topic['include_terms'])):
                result.append(PRIMARY)
            continue
        if any(term.casefold() in text for term in topic['include_terms']):
            result.append(topic['id'])
    return result


def all_items(data):
    return (data.get('items') or []) + (data.get('topic_items') or [])
