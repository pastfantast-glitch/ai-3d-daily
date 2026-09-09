#!/usr/bin/env python3
"""Fail-closed contract for shared preference feedback surfaces.

This validates wiring only. Browser votes remain client-local until a cloud-backed
preference source is introduced; build-time ranking must not pretend otherwise.
"""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def latest_daily_date():
    dates = sorted(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))
    if not dates:
        raise SystemExit('PREFERENCE CONTRACT FAIL: no canonical daily data')
    return dates[-1]


def main():
    errors = []
    preference = (ROOT / 'preference.js').read_text('utf-8')
    home = (ROOT / 'home.js').read_text('utf-8')
    canonical = (ROOT / 'canonical-client.js').read_text('utf-8')
    archive = (ROOT / 'archive-nav-state.js').read_text('utf-8')

    for marker in (
        "ai3d-preferences-v2",
        "ai3d-preferences-v1",
        "[data-intel-role=\"card\"][data-intel-id]",
        "category:{},tool:{},topic:{},tag:{}",
        "function ageFactor",
        "MutationObserver",
        "window.ai3dPreferenceProfile",
        "window.ai3dPreferenceScore",
        "window.ai3dPreferenceExport",
        "ai3d-preference-ranking-signal",
    ):
        require(marker in preference, f'preference.js missing contract marker: {marker}', errors)

    require("const STORE='ai3d-preferences-v1'" not in home,
            'home.js still owns legacy v1 preference implementation', errors)
    require("preference.js" in canonical,
            'canonical-client.js does not bootstrap shared preference.js', errors)
    require("preference.js" in archive,
            'archive-nav-state.js does not bootstrap shared preference.js', errors)

    date = latest_daily_date()
    cfg_path = ROOT / 'config' / 'intelligence-v2.json'
    import json
    cfg = json.loads(cfg_path.read_text('utf-8'))
    categories = [c['id'] for c in cfg.get('categories', [])]
    require(len(categories) == 6, 'expected exactly six category surfaces', errors)

    home_soup = BeautifulSoup((ROOT / 'index.html').read_text('utf-8'), 'html.parser')
    home_cards = home_soup.select('[data-intel-role="card"][data-intel-id]')
    require(bool(home_cards), 'homepage has no stable-ID intelligence cards', errors)

    for category in categories:
        path = ROOT / date / category / 'index.html'
        require(path.exists(), f'{date}/{category}: category page missing', errors)
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
        cards = soup.select('[data-intel-role="card"][data-intel-id]')
        require(bool(cards), f'{date}/{category}: no stable-ID intelligence cards', errors)
        script = soup.find('script', src=lambda value: value and 'archive-nav-state.js' in value)
        require(script is not None, f'{date}/{category}: shared workspace bootstrap missing', errors)

    daily_path = ROOT / date / 'index.html'
    if daily_path.exists():
        daily_soup = BeautifulSoup(daily_path.read_text('utf-8'), 'html.parser')
        require(bool(daily_soup.select('[data-intel-role="card"][data-intel-id]')),
                f'{date}: daily archive has no stable-ID intelligence cards', errors)
        require(daily_soup.find('script', src=lambda value: value and 'archive-nav-state.js' in value) is not None,
                f'{date}: daily archive shared workspace bootstrap missing', errors)

    if errors:
        raise SystemExit('PREFERENCE CONTRACT FAIL:\n- ' + '\n- '.join(errors))
    print(f'PREFERENCE CONTRACT PASS: shared v2 feedback + stable-ID sync wiring / {date} / {len(categories)} categories')


if __name__ == '__main__':
    main()
