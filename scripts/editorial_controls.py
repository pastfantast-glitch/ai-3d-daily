"""Owner holds defer collection; releasing a hold never approves an article."""
import json
from urllib.parse import urlsplit


def held_urls(root):
    path = root / 'config/editorial-selection.json'
    if not path.exists():
        return set()
    data = json.loads(path.read_text('utf-8'))
    urls = data.get('held_urls')
    if (set(data) != {'schema_version', 'held_urls'} or data['schema_version'] != 1
            or not isinstance(urls, list) or len(urls) > 500
            or any(not isinstance(u, str) or len(u) > 1500 or urlsplit(u).scheme != 'https'
                   or not urlsplit(u).hostname or urlsplit(u).username or urlsplit(u).password for u in urls)):
        raise ValueError('Invalid editorial selection controls')
    return set(urls)
