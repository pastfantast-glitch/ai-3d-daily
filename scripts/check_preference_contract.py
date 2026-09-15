#!/usr/bin/env python3
"""Fail-closed contract for shared preference feedback and bookmark surfaces.

Feedback (like/dislike) contributes to the preference profile and may be synced by
the owner-cloud runtime. Bookmarks are a separate knowledge-management store and
MUST contribute zero ranking/discovery weight. Navigation-only destinations such
as 收藏 and 歷史日報 must never be intercepted as current-day category tabs.
"""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def latest_surface_date():
    canonical_dates = sorted(p.stem for p in (ROOT / 'data' / 'daily').glob('20??-??-??.json'))
    if not canonical_dates:
        raise SystemExit('PREFERENCE CONTRACT FAIL: no canonical daily data')
    newest_canonical = canonical_dates[-1]
    if (ROOT / newest_canonical / 'index.html').exists():
        return newest_canonical
    rendered = sorted(
        path.name for path in ROOT.glob('20??-??-??')
        if path.is_dir() and (path / 'index.html').exists()
    )
    if not rendered:
        raise SystemExit('PREFERENCE CONTRACT FAIL: no rendered daily surface')
    return rendered[-1]


def stable_cards_only(soup, surface, errors):
    cards = soup.select('[data-intel-role="card"]')
    unstable = [card for card in cards if not str(card.get('data-intel-id', '')).strip()]
    require(not unstable, f'{surface}: {len(unstable)} intelligence cards missing stable data-intel-id', errors)
    return cards


def main():
    errors = []
    preference_path = ROOT / 'preference.js'
    saved_html_path = ROOT / 'saved' / 'index.html'
    saved_js_path = ROOT / 'saved.js'
    saved_css_path = ROOT / 'saved.css'
    history_html_path = ROOT / 'history' / 'index.html'
    history_js_path = ROOT / 'history.js'
    preference = preference_path.read_text('utf-8')
    home = (ROOT / 'home.js').read_text('utf-8')
    canonical = (ROOT / 'canonical-client.js').read_text('utf-8')
    archive = (ROOT / 'archive-nav-state.js').read_text('utf-8')

    for marker in (
        "ai3d-preferences-v2",
        "ai3d-preferences-v1",
        "ai3d-bookmarks-v1",
        "[data-intel-role=\"card\"][data-intel-id]",
        "category:{},tool:{},topic:{},tag:{}",
        "function ageFactor",
        "function recomputeWeights",
        "data-bookmark",
        "preference-bookmark-link",
        "MutationObserver",
        "window.ai3dPreferenceProfile",
        "window.ai3dPreferenceScore",
        "window.ai3dPreferenceExport",
        "window.ai3dBookmarkList",
        "window.ai3dBookmarkRemove",
        "window.ai3dBookmarkExport",
        "ai3d-preference-ranking-signal",
    ):
        require(marker in preference, f'preference.js missing contract marker: {marker}', errors)

    # Bookmark state must never participate in preference weight computation.
    start = preference.find('function recomputeWeights')
    end = preference.find('function save(){', start)
    recompute = preference[start:end] if start >= 0 and end > start else ''
    require(bool(recompute), 'preference.js recomputeWeights block not found', errors)
    require('bookmark' not in recompute.lower(),
            'bookmark state leaked into recomputeWeights; bookmarks must remain zero-weight', errors)
    require("const BOOKMARK_STORE='ai3d-bookmarks-v1'" in preference,
            'bookmark storage must remain physically separate from preference storage', errors)

    require("const STORE='ai3d-preferences-v1'" not in home,
            'home.js still owns legacy v1 preference implementation', errors)
    require("a.global-category-link[href]:not(.preference-bookmark-link):not(.global-history-link)" in home,
            'homepage workspace router must exclude bookmark + History navigation from TOP5/category interception', errors)
    require("a.global-category-link:not(.preference-bookmark-link):not(.global-history-link)" in home,
            'homepage active-tab painter must exclude bookmark + History navigation', errors)
    require("preference.js" in canonical,
            'canonical-client.js does not bootstrap shared preference.js', errors)
    require("preference.js" in archive,
            'archive-nav-state.js does not bootstrap shared preference.js', errors)

    for path, label in ((saved_html_path, 'saved/index.html'), (saved_js_path, 'saved.js'), (saved_css_path, 'saved.css'), (history_html_path, 'history/index.html'), (history_js_path, 'history.js')):
        require(path.exists(), f'{label} missing', errors)
    if saved_html_path.exists():
        saved_soup = BeautifulSoup(saved_html_path.read_text('utf-8'), 'html.parser')
        require(saved_soup.select_one('#saved-list') is not None, 'saved page missing #saved-list', errors)
        require(saved_soup.select_one('#saved-search') is not None, 'saved page missing search control', errors)
        require(saved_soup.find('script', src=lambda value: value and 'saved.js' in value) is not None,
                'saved page missing saved.js module', errors)
        body_text = saved_soup.get_text(' ', strip=True)
        require('不影響偏好權重' in body_text, 'saved page must disclose zero-weight bookmark behavior', errors)
        require('feedback-v2' in saved_html_path.read_text('utf-8'),
                'saved page must cache-bust the article-visual bookmark runtime', errors)
    if saved_js_path.exists():
        saved_js = saved_js_path.read_text('utf-8')
        for marker in (
            'ai3dBookmarkList', 'ai3dBookmarkRemove', 'ai3d:bookmark-change',
            'resolveBookmarkImage', 'imageFromReportPage', 'figure.case-preview img[src]',
            'saved-card-media', 'candidateReportPages'
        ):
            require(marker in saved_js, f'saved.js missing bookmark API/visual marker: {marker}', errors)
    if saved_css_path.exists():
        saved_css = saved_css_path.read_text('utf-8')
        for marker in ('.saved-card-media', '.saved-card.has-image', 'object-fit:cover'):
            require(marker in saved_css, f'saved.css missing article-visual marker: {marker}', errors)
    if history_html_path.exists():
        history_soup = BeautifulSoup(history_html_path.read_text('utf-8'), 'html.parser')
        require(history_soup.select_one('a.global-history-link[data-global-view="history"]') is not None,
                'History portal missing standalone navigation identity', errors)
        require(history_soup.find('script', src=lambda value: value and 'preference.js' in value) is not None,
                'History portal must bootstrap shared preference/cloud runtime', errors)
    if history_js_path.exists():
        history_js = history_js_path.read_text('utf-8')
        for marker in ('history-search','data-history-category','data-history-range'):
            require(marker in history_js, f'history.js missing archive interaction marker: {marker}', errors)

    date = latest_surface_date()
    cfg_path = ROOT / 'config' / 'intelligence-v2.json'
    import json
    cfg = json.loads(cfg_path.read_text('utf-8'))
    categories = [c['id'] for c in cfg.get('categories', [])]
    require(len(categories) == 6, 'expected exactly six category surfaces', errors)

    home_soup = BeautifulSoup((ROOT / 'index.html').read_text('utf-8'), 'html.parser')
    home_cards = stable_cards_only(home_soup, 'homepage', errors)
    require(bool(home_cards), 'homepage has no intelligence cards', errors)

    daily_path = ROOT / date / 'index.html'
    require(daily_path.exists(), f'{date}: daily archive missing', errors)

    for category in categories:
        path = ROOT / date / category / 'index.html'
        require(path.exists(), f'{date}/{category}: category page missing', errors)
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
        stable_cards_only(soup, f'{date}/{category}', errors)
        script = soup.find('script', src=lambda value: value and 'archive-nav-state.js' in value)
        require(script is not None, f'{date}/{category}: shared workspace bootstrap missing', errors)

    if daily_path.exists():
        daily_soup = BeautifulSoup(daily_path.read_text('utf-8'), 'html.parser')
        daily_cards = stable_cards_only(daily_soup, date, errors)
        require(bool(daily_cards), f'{date}: daily archive has no intelligence cards', errors)
        require(daily_soup.find('script', src=lambda value: value and 'archive-nav-state.js' in value) is not None,
                f'{date}: daily archive shared workspace bootstrap missing', errors)

    if errors:
        raise SystemExit('PREFERENCE CONTRACT FAIL:\n- ' + '\n- '.join(errors))
    print(f'PREFERENCE CONTRACT PASS: like/dislike learning + zero-weight star bookmarks + standalone History navigation + saved visuals + stable-ID sync / rendered={date} / {len(categories)} categories')


if __name__ == '__main__':
    main()
