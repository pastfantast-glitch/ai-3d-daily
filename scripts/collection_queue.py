"""URL-only continuation ledger. Evidence stays in expiring Actions artifacts."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from url_identity import canonicalize_url
from source_quality import source_window_errors

MAX_QUEUE = 1000
ACTIVE = {'awaiting_review', 'discovered', 'source_unavailable', 'recommended'}


def read(path):
    return json.loads(path.read_text('utf-8')) if path.exists() else {}


def source_for(url, sources):
    p = urlsplit(url)
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        return None
    host = (p.hostname or '').removeprefix('www.')
    return next((s for s in sources if host == (urlsplit(s['base_url']).hostname or '').removeprefix('www.')
                 or host.endswith('.' + (urlsplit(s['base_url']).hostname or '').removeprefix('www.'))), None)


def pending_seeds(root, date, settings, published, held=(), limit=40):
    monitor = read(root/'data/ops/collection-monitor.json')
    rows = monitor.get('pending_queue', monitor.get('articles', []))
    intake = read(root/'config/collection-intake.json').get('items', [])
    rows = [dict(x, state=x.get('state') or ('awaiting_review' if 'awaiting-editorial-review' in x.get('errors', []) else 'rejected')) for x in rows]
    known = {canonicalize_url(x['source_url']) for x in rows}
    rows += [dict(x, state='recommended') for x in intake if canonicalize_url(x['source_url']) not in known]
    held = {canonicalize_url(u) for u in held}
    picked = {}
    for row in sorted(rows, key=lambda r: (r.get('last_attempt_on', ''), r.get('first_seen', r.get('requested_on', '')), r['source_url'])):
        url = canonicalize_url(row['source_url'])
        s = source_for(url, settings['sources'])
        if not s or not s['enabled'] or url in published or url in held or row['state'] not in ACTIVE:
            continue
        if row.get('source_date') and source_window_errors({'source_url':url, 'source_published_at':row['source_date']}, date):
            continue
        picked.setdefault(s['id'], []).append((url, row.get('title', '')))
        if sum(map(len, picked.values())) >= limit:
            break
    return picked


def merge_queue(current, previous, root):
    """Merge bounded metadata, retaining unseen pending work across failed runs."""
    date = current['date']
    published = {canonicalize_url(x.get('source_url', '')) for x in read(root/'data/candidates/published-registry-snapshot.json').get('published_sources', [])}
    receipt = read(root/f'data/publish/{date}.done.json')
    from daily_release_status import receipt_errors
    data = read(root/f'data/daily/{date}.json')
    if receipt and not receipt_errors(date,root,receipt,data,read(root/'data/publish/latest-success.json'),allow_newer_latest=True):
        published.update(canonicalize_url(x.get('source_url','')) for x in data.get('items', []) + data.get('topic_items', []))
    allowed = ('id','source_url','title','source_date','source_id','state','errors','first_seen','last_attempt_on','source_run_id','source_head_sha','evidence_date','body_readable')
    rows = {}
    for item in previous.get('pending_queue', previous.get('articles', [])):
        row = {k:item[k] for k in allowed if k in item}
        row.setdefault('state', 'awaiting_review' if 'awaiting-editorial-review' in row.get('errors', []) else 'rejected')
        row.setdefault('first_seen', previous.get('date', date))
        row.setdefault('evidence_date', previous.get('date', date))
        row.setdefault('source_run_id', previous.get('source_run_id'))
        row.setdefault('source_head_sha', previous.get('source_head_sha'))
        rows[canonicalize_url(row['source_url'])] = row
    for sid, source in current.get('sources', {}).items():
        for item in source.get('url_observations', []):
            url = canonicalize_url(item['source_url'])
            old = rows.get(url, {})
            # A failed refresh cannot destroy the last original evidence binding.
            row = {**old, **{k:item[k] for k in ('source_url','state','errors') if k in item}, 'source_id':sid,
                   'first_seen':old.get('first_seen',date)}
            if item.get('state') != 'discovered':
                row['last_attempt_on'] = date
            rows[url] = row
    for item in current['articles']:
        url = canonicalize_url(item['source_url'])
        old = rows.get(url, {})
        state = ('awaiting_review' if 'awaiting-editorial-review' in item['errors'] else
                 'approved' if not item['errors'] else 'rejected')
        rows[url] = {**{k:item[k] for k in allowed if k in item}, 'state':state,
                     'first_seen':old.get('first_seen',date), 'last_attempt_on':date,
                     'evidence_date':date,'source_run_id':current['source_run_id'], 'source_head_sha':current['source_head_sha']}
    for url, row in list(rows.items()):
        if url in published:
            del rows[url]
        elif row.get('source_date') and source_window_errors({'source_url':url,'source_published_at':row['source_date']},date):
            row['state'] = 'date_ineligible'
    # Keep unresolved work first; disclose overflow rather than claim full coverage.
    ordered = sorted(rows.values(), key=lambda r: (r['state'] not in ACTIVE, r.get('first_seen',''), r['source_url']))
    current['pending_queue'] = ordered[:MAX_QUEUE]
    current['queue_overflow'] = max(0, len(ordered)-MAX_QUEUE)
    current['queue_complete'] = not current['queue_overflow']
    return current
