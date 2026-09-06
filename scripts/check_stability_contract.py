#!/usr/bin/env python3
"""Validate publication stability controls that sit across registry, regression and Pages.

This check is intentionally repository-local. GitHub branch/ruleset administration is
an external control and is reported, not faked, when the connector cannot enforce it.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from url_identity import canonicalize_url

CONFIG = ROOT / 'config' / 'stability-contract.json'
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def main() -> int:
    try:
        cfg = json.loads(CONFIG.read_text('utf-8'))
    except Exception as exc:
        print(f'STABILITY CONTRACT FAILED: invalid/missing config: {exc}')
        return 1

    if cfg.get('version') != 1:
        fail(f"stability contract version must be 1, got {cfg.get('version')!r}")

    history = cfg.get('historical_regression') or {}
    recent_days = history.get('recent_days')
    if not isinstance(recent_days, int) or recent_days < 1:
        fail('historical_regression.recent_days must be an integer >= 1')
    sentinels = history.get('sentinel_dates') or []
    modes = history.get('sentinel_modes') or {}
    allowed_modes = {'snapshot_only', 'canonical_parity'}
    if not isinstance(sentinels, list) or not sentinels:
        fail('historical_regression.sentinel_dates must be a non-empty list')
    else:
        if len(set(sentinels)) != len(sentinels):
            fail('historical_regression.sentinel_dates must be unique')
        if not isinstance(modes, dict):
            fail('historical_regression.sentinel_modes must be an object')
            modes = {}
        for date in sentinels:
            if not isinstance(date, str) or not DATE_RE.fullmatch(date):
                fail(f'invalid sentinel date: {date!r}')
                continue
            archive = ROOT / date / 'index.html'
            if not archive.exists():
                fail(f'sentinel archive missing: {archive.relative_to(ROOT)}')
            mode = modes.get(date)
            if mode not in allowed_modes:
                fail(f'sentinel {date} mode must be one of {sorted(allowed_modes)}, got {mode!r}')
        stale_modes = sorted(set(modes) - set(sentinels))
        if stale_modes:
            fail('sentinel_modes contains dates not listed in sentinel_dates: ' + ', '.join(stale_modes))

    pages = cfg.get('pages_verify') or {}
    attempts = pages.get('minimum_attempts')
    delay = pages.get('minimum_delay_seconds')
    timeout = pages.get('timeout_seconds')
    if not isinstance(attempts, int) or attempts < 8:
        fail('pages_verify.minimum_attempts must be an integer >= 8')
    if not isinstance(delay, int) or delay < 5:
        fail('pages_verify.minimum_delay_seconds must be an integer >= 5')
    if not isinstance(timeout, int) or timeout < 10:
        fail('pages_verify.timeout_seconds must be an integer >= 10')

    # Canonical URL identity must remove tracking noise but preserve real selectors.
    url_cases = {
        'https://Example.com/a/?utm_source=x#section': 'https://example.com/a',
        'https://example.com/a?item=7&utm_medium=email': 'https://example.com/a?item=7',
        'https://example.com/a?item=7&gclid=abc': 'https://example.com/a?item=7',
        'https://example.com:443/a/': 'https://example.com/a',
        'https://example.com/a?view=2': 'https://example.com/a?view=2',
    }
    for source, expected in url_cases.items():
        actual = canonicalize_url(source)
        if actual != expected:
            fail(f'URL identity mismatch: {source!r} -> {actual!r}, expected {expected!r}')

    wiring = {
        ROOT / 'scripts' / 'normalize_registry_identity.py': ('from url_identity import canonicalize_url',),
        ROOT / 'scripts' / 'check_registry_contract.py': ('from url_identity import canonicalize_url',),
        ROOT / 'scripts' / 'check_historical_regression.py': ('stability-contract.json', 'sentinel_dates', 'sentinel_modes'),
        ROOT / 'scripts' / 'verify_pages_publish.py': ('stability-contract.json', 'minimum_attempts'),
    }
    for path, tokens in wiring.items():
        if not path.exists():
            fail(f'stability-wired module missing: {path.relative_to(ROOT)}')
            continue
        text = path.read_text('utf-8')
        for token in tokens:
            if token not in text:
                fail(f'{path.relative_to(ROOT)} missing stability token: {token}')

    branch = cfg.get('branch_protection') or {}
    if branch.get('desired') is not True:
        fail('branch_protection.desired must be true')
    if branch.get('enforcement') != 'external_admin_setting':
        fail("branch_protection.enforcement must be 'external_admin_setting'")

    if errors:
        print('STABILITY CONTRACT FAILED')
        for error in errors:
            print('-', error)
        return 1

    print(
        'STABILITY CONTRACT PASS: canonical URL identity + sentinel historical regression + '
        f'Pages retry floor attempts={attempts} delay={delay}s timeout={timeout}s'
    )
    print('SENTINEL MODES:', ', '.join(f'{date}={modes[date]}' for date in sentinels))
    print('BRANCH PROTECTION NOTICE: desired=true; enforcement requires GitHub repository administration outside repo code.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
