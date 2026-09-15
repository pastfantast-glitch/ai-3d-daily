#!/usr/bin/env python3
"""Fail-closed contract for single-owner automatic cloud sync.

The production runtime must use one authenticated owner session, keep local state
usable offline, push immediately after local preference/bookmark changes, and pull
when the page opens/resumes. Legacy per-device sync IDs are bootstrap-only and
must not remain the active synchronization model.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / 'cloud-sync-owner.js'
PREFERENCE = ROOT / 'preference.js'
LEGACY = ROOT / 'cloud-sync-v3.js'


def main():
    errors = []
    for path in (SYNC, PREFERENCE, LEGACY):
        if not path.exists():
            errors.append(f'missing file: {path.name}')
    if errors:
        raise SystemExit('CLOUD SYNC CONTRACT FAIL:\n- ' + '\n- '.join(errors))

    text = SYNC.read_text('utf-8')
    preference = PREFERENCE.read_text('utf-8')
    legacy = LEGACY.read_text('utf-8')

    required = (
        "@supabase/supabase-js@2.116.0",
        "const DIRTY_STORE='ai3d-owner-sync-dirty-v1'",
        "supabase.auth.signInWithPassword",
        "supabase.auth.getSession()",
        "supabase.auth.onAuthStateChange",
        "supabase.from('user_sync_state')",
        'async function pushLocal',
        'async function pullCloud',
        'function queuePush(event)',
        "window.addEventListener('ai3d:preference-change',queuePush)",
        "window.addEventListener('ai3d:bookmark-change',queuePush)",
        "window.addEventListener('online',resumeSync)",
        "window.addEventListener('focus',resumeSync)",
        "document.addEventListener('visibilitychange'",
        'setInterval(',
        'local_state:localState()',
        '第一次建立主人帳號',
        'window.ai3dCloudSyncNow',
        'window.ai3dCloudAccount',
    )
    for marker in required:
        if marker not in text:
            errors.append(f'missing owner-sync marker: {marker}')

    forbidden = (
        'function register()',
        'function importCode()',
        'window.ai3dCloudSyncCode',
        'window.ai3dCloudSyncImport',
        'location.reload()',
        'MutationObserver',
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f'owner runtime contains retired/unsafe behavior: {marker}')

    if "cloud-sync-owner.js?v=20260915-owner-v1" not in preference:
        errors.append('preference.js must load cache-isolated single-owner runtime')
    if 'window.ai3dPreferenceReloadFromStorage' not in preference:
        errors.append('preference.js must expose same-tab storage reload hook')

    if 'cloud-sync-owner.js?v=20260915-owner-v1' not in legacy:
        errors.append('legacy cloud-sync-v3.js must delegate to owner runtime')
    if 'ai3d-sync' in legacy or 'sync_id' in legacy or 'makeSecret' in legacy:
        errors.append('legacy cloud-sync-v3.js must not retain paired-sync logic')

    if "if(isDirty())return pushLocal({silent});" not in text:
        errors.append('pull must push dirty offline state before reading cloud')
    if "clearTimeout(pushTimer);pushTimer=setTimeout(()=>pushLocal({silent:true}),180);" not in text:
        errors.append('local feedback/bookmark changes must schedule immediate cloud push')
    if "if(data?.state)applyCloudState(data.state);" not in text:
        errors.append('open/resume sync must apply canonical cloud state locally')

    if errors:
        raise SystemExit('CLOUD SYNC CONTRACT FAIL:\n- ' + '\n- '.join(errors))
    print('CLOUD SYNC CONTRACT PASS: one owner session + automatic open/resume pull + immediate mutation push + offline dirty recovery')


if __name__ == '__main__':
    main()
