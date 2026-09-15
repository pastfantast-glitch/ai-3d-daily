#!/usr/bin/env python3
"""Fail-closed contract for the passive cloud-sync runtime.

Cloud sync must be cache-isolated and must not do automatic DOM observation,
automatic registration, automatic pull, or automatic reload on page load. Local
preference/bookmark behavior must remain usable even when Supabase is unavailable.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / 'cloud-sync-v2.js'
PREFERENCE = ROOT / 'preference.js'


def main():
    errors = []
    if not SYNC.exists():
        raise SystemExit('CLOUD SYNC CONTRACT FAIL: cloud-sync-v2.js missing')
    if not PREFERENCE.exists():
        raise SystemExit('CLOUD SYNC CONTRACT FAIL: preference.js missing')

    text = SYNC.read_text('utf-8')
    preference = PREFERENCE.read_text('utf-8')

    required = (
        "const ENDPOINT='https://epumcdxfkcujulqrcjrw.supabase.co/functions/v1/ai3d-sync'",
        "const CRED_STORE='ai3d-cloud-sync-v1'",
        'function injectNav()',
        'function queuePush()',
        'window.ai3dCloudSyncCode',
        'window.ai3dCloudSyncNow',
        'window.ai3dCloudSyncImport',
        'setTimeout(()=>controller.abort(),8000)',
    )
    for marker in required:
        if marker not in text:
            errors.append(f'missing marker: {marker}')

    if "cloud-sync-v2.js?v=20260915-r4" not in preference:
        errors.append('preference.js must load cache-isolated cloud-sync-v2.js with explicit version token')
    if "./cloud-sync.js'" in preference or 'cloud-sync.js",' in preference:
        errors.append('preference.js still references legacy cloud-sync.js')

    forbidden = (
        'MutationObserver',
        'observer.observe(',
        'else register();',
        'if(credentials())pull();',
        'window.addEventListener(\'online\'',
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f'passive runtime contains forbidden automatic behavior: {marker}')

    init_start = text.find('function init(){')
    init_end = text.find('window.ai3dCloudSyncCode', init_start)
    init_block = text[init_start:init_end] if init_start >= 0 and init_end > init_start else ''
    if not init_block:
        errors.append('init block not found')
    else:
        for marker in ('register()', 'pull()', 'location.reload()', 'fetch('):
            if marker in init_block:
                errors.append(f'init must not execute automatic cloud/network/reload action: {marker}')

    if errors:
        raise SystemExit('CLOUD SYNC CONTRACT FAIL:\n- ' + '\n- '.join(errors))
    print('CLOUD SYNC CONTRACT PASS: passive manual sync + cache-isolated v2 runtime')


if __name__ == '__main__':
    main()
