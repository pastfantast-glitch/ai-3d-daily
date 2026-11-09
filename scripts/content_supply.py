"""Bounded discovery and reserve helpers; no admission or publication authority."""
from datetime import date
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from url_identity import canonicalize_url


def section_links(html, base, same_domain, limit):
    """Follow topic indexes actually declared by a publisher; never guess routes."""
    out = []
    for anchor in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = canonicalize_url(urljoin(base, anchor['href']))
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not same_domain(url) or parsed.query:
            continue
        parts = parsed.path.strip('/').lower().split('/')
        is_index = (any(x in parts for x in ('category', 'categories', 'tag', 'tags'))
                    or parts[-1] in ('tutorials', 'training', 'releases', 'news', 'blog', 'articles'))
        text = (anchor.get_text(' ', strip=True) + ' ' + parsed.path).lower()
        relevant = any(term in text for term in (
            '3d', 'animation', 'rigging', 'model', 'texture', 'material', 'shader',
            'blender', 'unreal', 'unity', 'houdini', 'tutorial', 'training', 'release',
            'workflow', 'game', 'vfx', 'ai', '教學', '動畫', '制作', '製作'))
        if is_index and relevant and url != canonicalize_url(base) and url not in out:
            out.append(url)
            if len(out) >= limit:
                break
    return out if limit > 0 else []


def retained_entries(entries, report_date, published, max_age_days):
    kept = []
    for entry in entries:
        url = canonicalize_url(str(entry.get('source_url', '')))
        try:
            age = (date.fromisoformat(report_date) - date.fromisoformat(entry['discovered_for'])).days
        except (ValueError, KeyError, TypeError):
            continue
        if url.startswith('https://') and url not in published and 0 <= age <= max_age_days:
            kept.append({**entry, 'source_url': url})
    return kept


def reserve_output(overflow, retry_entries, previous, report_date, maximum):
    """Keep verified overflow and temporarily unavailable prior reserves without raw bodies."""
    original = {canonicalize_url(x['source_url']): x for x in previous}
    out = {}
    for candidate in overflow:
        url = canonicalize_url(candidate['source_url'])
        out[url] = {key: candidate[key] for key in
                    ('source_id', 'title', 'category', 'subcategory', 'ranking_score')}
        out[url].update(id=candidate['candidate_id'], source_url=url,
                        discovered_for=original.get(url, {}).get('discovered_for', report_date),
                        last_checked=report_date, refresh_status='verified')
    for entry in retry_entries:
        url = entry['source_url']
        # Fixed allowlist: never persist evidence, HTML, credentials or reader drafts.
        out.setdefault(url, {**{k: entry[k] for k in (
            'id', 'source_id', 'title', 'source_url', 'category', 'subcategory',
            'ranking_score', 'discovered_for') if k in entry},
            'last_checked': report_date, 'refresh_status': 'temporarily-unavailable'})
    return list(out.values())[:maximum]
