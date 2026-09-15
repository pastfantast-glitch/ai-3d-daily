#!/usr/bin/env python3
"""Fail-closed contract for paired cross-device cloud sync.

Cloud sync must never auto-register a device and must never reload the page to
apply remote data. Once two devices explicitly share one sync code, the runtime
may safely pull on load/visibility/online and poll at a bounded interval.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / 'cloud-sync-v3.js'
PREFERENCE = ROOT / 'preference.js'


def main():
    errors = []
    if not SYNC.exists():
        raise SystemExit('CLOUD SYNC CONTRACT FAIL: cloud-sync-v3.js missing')
    if not PREFERENCE.exists():
        raise SystemExit('CLOUD SYNC CONTRACT FAIL: preference.js missing')

    text = SYNC.read_text('utf-8')
    preference = PREFERENCE.read_text('utf-8')

    required = (
        "const ENDPOINT='https://epumcdxfkcujulqrcjrw.supabase.co/functions/v1/ai3d-sync'",
        "const CRED_STORE='ai3d-cloud-sync-v1'",
        'const POLL_MS=60000',
        'function mergeForLink(local,remote)',
        'function applyRemote(remote',
        'function queuePush(event)',
        "if(event?.detail?.remote)return",
        'function schedulePolling()',
        "document.addEventListener('visibilitychange'",
        "window.addEventListener('online'",
        'window.ai3dCloudSyncCode',
        'window.ai3dCloudSyncStatus',
        'window.ai3dCloudSyncNow',
        'window.ai3dCloudSyncImport',
        'setTimeout(()=>controller.abort(),8000)',
        'window.ai3dPreferenceReloadFromStorage',
    )
    for marker in required:
        if marker not in text:
            errors.append(f'missing marker: {marker}')

    if "cloud-sync-v3.js?v=20260915-r6" not in preference:
        errors.append('preference.js must load cache-isolated cloud-sync-v3.js with explicit version token')
    if 'window.ai3dPreferenceReloadFromStorage' not in preference:
        errors.append('preference.js must expose same-tab storage reload hook for remote sync')

    forbidden = (
        'MutationObserver',
        'observer.observe(',
        'else register();',
        'location.reload()',
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f'cloud runtime contains forbidden behavior: {marker}')

    init_start = text.find('function init(){')
    init_end = text.find('window.ai3dCloudSyncCode', init_start)
    init_block = text[init_start:init_end] if init_start >= 0 and init_end > init_start else ''
    if not init_block:
        errors.append('init block not found')
    else:
        if 'register()' in init_block:
            errors.append('init must never auto-register a new sync account')
        if 'location.reload()' in init_block:
            errors.append('init must not reload the page')
        if 'if(credentials())setTimeout(()=>pull({silent:true}),400)' not in init_block:
            errors.append('linked devices must perform a bounded silent initial pull')

    menu_start = text.find('async function menu(){')
    menu_end = text.find('function injectStyle()', menu_start)
    menu_block = text[menu_start:menu_end] if menu_start >= 0 and menu_end > menu_start else ''
    if '連結另一台裝置' not in text or '共同代號' not in text:
        errors.append('pairing UX must make shared-account linking explicit')

    if errors:
        raise SystemExit('CLOUD SYNC CONTRACT FAIL:\n- ' + '\n- '.join(errors))
    print('CLOUD SYNC CONTRACT PASS: explicit pairing + automatic pull/push + no reload/auto-register')


if __name__ == '__main__':
    main()
