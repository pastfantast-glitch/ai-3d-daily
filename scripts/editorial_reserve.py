"""Approved unpublished copy only; no source bodies, new approvals or writers.

Prior review records are reusable only after candidate_copy matches freshly
fetched evidence and the Collector applies today's reader and registry gates.
"""
from datetime import date as date_cls
from functools import lru_cache
import json


@lru_cache(maxsize=8)
def approved_reserve(root, date):
    from editorial_review import read_review
    published = set()
    for path in (root / 'data/publish').glob('*.done.json'):
        edition = path.name[:10]
        data_path = root / 'data/daily' / f'{edition}.json'
        if data_path.exists():
            published.update(i.get('source_url') for i in json.loads(data_path.read_text('utf-8')).get('items', []))
    result = {}
    for path in sorted((root / 'data/editorial-reviews').glob('20??-??-??.json'), reverse=True):
        age = (date_cls.fromisoformat(date) - date_cls.fromisoformat(path.stem)).days
        if not 1 <= age <= 180:
            continue
        data = read_review(path.stem, root)
        for record in data['items'].values():
            url = record.get('source_url')
            if url and url not in published and record.get('review', {}).get('approved') is True:
                result.setdefault(url, (data, record))
    return result


def reserve_seeds(root, date, sources):
    """Seed only registered publishers; actual fetching remains Collector-owned."""
    from urllib.parse import urlparse
    entries = []
    for url, (data, record) in approved_reserve(root, date).items():
        source = next((s for s in sources if s.get('enabled', True) and urlparse(s.get('base_url', '')).hostname == urlparse(url).hostname), None)
        if source:
            entries.append({'source_url': url, 'source_id': source['id'], 'title': record['title'],
                'discovered_for': data['date']})
    return entries
