#!/usr/bin/env python3
"""Fail-closed contract for the lightweight cloud-sync runtime.

The cloud-sync nav control must not repaint on every DOM mutation. Repainting
text from a childList MutationObserver can self-trigger forever and freeze the
static GitHub Pages UI.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / 'cloud-sync.js'


def main():
    errors = []
    if not SYNC.exists():
        raise SystemExit('CLOUD SYNC CONTRACT FAIL: cloud-sync.js missing')
    text = SYNC.read_text('utf-8')

    required = (
        "const ENDPOINT='https://epumcdxfkcujulqrcjrw.supabase.co/functions/v1/ai3d-sync'",
        "const CRED_STORE='ai3d-cloud-sync-v1'",
        'function injectNav(root=document)',
        'if(inserted)paint()',
        'for(const node of record.addedNodes)',
        'if(node.nodeType===1)injectNav(node)',
        "if(text&&text.textContent!==next)text.textContent=next",
        'window.ai3dCloudSyncCode',
        'window.ai3dCloudSyncNow',
        'window.ai3dCloudSyncImport',
    )
    for marker in required:
        if marker not in text:
            errors.append(f'missing marker: {marker}')

    forbidden = (
        'new MutationObserver(injectNav)',
        'new MutationObserver(()=>injectNav())',
        'new MutationObserver(() => injectNav())',
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f'unsafe self-repainting MutationObserver detected: {marker}')

    # injectNav must not unconditionally repaint after scanning existing navs.
    start = text.find('function injectNav(root=document)')
    end = text.find('function paint(', start)
    block = text[start:end] if start >= 0 and end > start else ''
    if not block:
        errors.append('injectNav block not found')
    else:
        if 'if(inserted)paint()' not in block:
            errors.append('injectNav must repaint only when a control was inserted')
        if block.count('paint()') > 1:
            errors.append('injectNav contains unexpected extra repaint calls')

    if errors:
        raise SystemExit('CLOUD SYNC CONTRACT FAIL:\n- ' + '\n- '.join(errors))
    print('CLOUD SYNC CONTRACT PASS: no self-triggering nav repaint loop')


if __name__ == '__main__':
    main()
