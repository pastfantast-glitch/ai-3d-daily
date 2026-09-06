#!/usr/bin/env python3
"""Canonical URL identity helpers for Published Intelligence Registry dedupe.

The goal is conservative identity normalization: remove transport noise that does
not change the underlying source while preserving query parameters that may select
real content.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid', 'igshid',
}
TRACKING_PREFIXES = ('utm_',)


def _is_tracking_key(key: str) -> bool:
    lowered = key.strip().lower()
    return lowered in TRACKING_KEYS or lowered.startswith(TRACKING_PREFIXES)


def canonicalize_url(url: str) -> str:
    raw = (url or '').strip()
    if not raw:
        return ''

    try:
        parts = urlsplit(raw)
    except Exception:
        return raw.rstrip('/')

    # Keep non-absolute/opaque values conservative rather than guessing.
    if not parts.scheme or not parts.netloc:
        return raw.rstrip('/')

    scheme = parts.scheme.lower()
    hostname = (parts.hostname or '').lower()
    port = parts.port
    if ':' in hostname and not hostname.startswith('['):
        hostname = f'[{hostname}]'
    if port and not ((scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)):
        netloc = f'{hostname}:{port}'
    else:
        netloc = hostname
    if parts.username:
        # Source URLs should not contain credentials, but preserve them if present
        # rather than changing identity silently.
        userinfo = parts.username
        if parts.password:
            userinfo += f':{parts.password}'
        netloc = f'{userinfo}@{netloc}'

    path = parts.path.rstrip('/')
    if path == '/':
        path = ''

    kept = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking_key(key)]
    query = urlencode(kept, doseq=True)

    # Fragments are client-side anchors and do not identify a different source.
    return urlunsplit((scheme, netloc, path, query, ''))


if __name__ == '__main__':
    samples = {
        'https://Example.com/a/?utm_source=x#section': 'https://example.com/a',
        'https://example.com/a?item=7&utm_medium=email': 'https://example.com/a?item=7',
        'https://example.com:443/a/': 'https://example.com/a',
    }
    for source, expected in samples.items():
        actual = canonicalize_url(source)
        if actual != expected:
            raise SystemExit(f'URL identity self-test failed: {source!r} -> {actual!r}, expected {expected!r}')
    print('URL IDENTITY SELF-TEST PASS')
