"""Approved unpublished copy only; no source bodies, new approvals or writers.

Prior review records are reusable only after candidate_copy matches freshly
fetched evidence and the Collector applies today's reader and registry gates.
"""
from datetime import date as date_cls
from functools import lru_cache
import json
from collection_settings import all_items
from source_quality import source_window_errors
from url_identity import canonicalize_url


@lru_cache(maxsize=8)
def approved_reserve(root, date):
    from editorial_review import read_review_file
    published = set()
    for path in (root / 'data/publish').glob('*.done.json'):
        edition = path.name[:10]
        data_path = root / 'data/daily' / f'{edition}.json'
        if data_path.exists():
            published.update(canonicalize_url(i.get('source_url', '')) for i in all_items(json.loads(data_path.read_text('utf-8'))))
    result = {}
    for path in sorted((root / 'data/editorial-reviews').glob('20*.json'), reverse=True):
        age = (date_cls.fromisoformat(date) - date_cls.fromisoformat(path.name[:10])).days
        if not 0 <= age <= 180:
            continue
        data = read_review_file(path)
        for record in data['items'].values():
            url = canonicalize_url(record.get('source_url', ''))
            if (url and url not in published and record.get('review', {}).get('approved') is True
                    and not source_window_errors(record, date)):
                result.setdefault(url, (data, record))
    return result


def reserve_seeds(root, date, sources):
    """Seed only registered publishers; actual fetching remains Collector-owned."""
    from urllib.parse import urlparse
    entries = []
    from editorial_controls import held_urls
    held = held_urls(root)
    for url, (data, record) in approved_reserve(root, date).items():
        if url in held:
            continue
        # Publishers commonly redirect their www host. Match exact normalized
        # hosts only; never accept arbitrary suffix/subdomain lookalikes.
        host = (urlparse(url).hostname or '').removeprefix('www.')
        source = next((s for s in sources if s.get('enabled', True)
            and (urlparse(s.get('base_url', '')).hostname or '').removeprefix('www.') == host), None)
        if source:
            entries.append({'source_url': url, 'source_id': source['id'], 'title': record['title'],
                'discovered_for': data['date'], 'source_published_at': record.get('source_published_at')})
    return entries
