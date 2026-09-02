#!/usr/bin/env python3
from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[1]
errors = []

# Layout-specific stylesheets may control geometry, spacing, responsive layout and visibility,
# but shared component visuals belong to shared-components.css.
LAYOUT_FILES = [ROOT / 'home.css', ROOT / 'daily.css']
VISUAL_PROPERTIES = {
    'color', 'background', 'background-color', 'background-image',
    'box-shadow', 'text-shadow', 'border-color', 'outline-color',
    'fill', 'stroke'
}
FULL_ANALYSIS_TOKENS = (
    '.home-full-analysis', '.daily-full-analysis', '.category-full-analysis',
    '.detail-body', '.home-analysis-body', '.daily-analysis-body'
)

COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)
BLOCK_RE = re.compile(r'([^{}]+)\{([^{}]*)\}', re.S)
DECL_RE = re.compile(r'(^|;)\s*([a-zA-Z-]+)\s*:', re.M)

for path in LAYOUT_FILES:
    if not path.exists():
        errors.append(f'missing layout stylesheet: {path.name}')
        continue
    css = COMMENT_RE.sub('', path.read_text('utf-8'))
    for match in BLOCK_RE.finditer(css):
        selector = ' '.join(match.group(1).split())
        body = match.group(2)
        # Skip at-rule wrappers accidentally matched as selectors.
        if selector.startswith('@'):
            continue
        props = {m.group(2).lower() for m in DECL_RE.finditer(';' + body)}
        bad = sorted(props & VISUAL_PROPERTIES)
        if bad:
            errors.append(
                f'{path.name}: shared visual properties must live in shared-components.css: '
                f'{selector} -> {", ".join(bad)}'
            )
        if any(token in selector for token in FULL_ANALYSIS_TOKENS):
            # The one allowed archive rule only controls collapsed-body visibility.
            normalized = re.sub(r'\s+', '', selector)
            allowed = (
                path.name == 'daily.css'
                and normalized == '.archive-pagedetails:not([open]).detail-body'
                and props <= {'display'}
            )
            if not allowed:
                errors.append(
                    f'{path.name}: Full Analysis styling must be owned by shared-components.css: {selector}'
                )

shared = ROOT / 'shared-components.css'
if not shared.exists():
    errors.append('shared-components.css missing')
else:
    text = shared.read_text('utf-8')
    for token in ('details > summary', '.detail-body', '.global-category-nav'):
        if token not in text:
            errors.append(f'shared-components.css missing canonical shared selector: {token}')

if errors:
    print('DESIGN SYSTEM CONTRACT FAILED')
    print('\n'.join('- ' + e for e in errors))
    sys.exit(1)

print('DESIGN SYSTEM CONTRACT PASS: shared visuals centralized; home.css/daily.css remain layout-only')
