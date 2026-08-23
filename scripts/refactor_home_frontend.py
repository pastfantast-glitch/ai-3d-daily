#!/usr/bin/env python3
from pathlib import Path
import logging
import re

from bs4 import BeautifulSoup
import cssbeautifier
import cssutils

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20260823-2'

cssutils.log.setLevel(logging.CRITICAL)
cssutils.ser.prefs.useMinified()

DYNAMIC_CLASSES = {
    # Semantic variants used by the daily template even if not present today.
    'purple', 'blue', 'green', 'orange', 'priority', 'hot', 'beta',
    'status-new', 'status-update', 'status-track', 'important',
    # JS/runtime and reusable homepage components.
    'preference-vote', 'is-up', 'is-down', 'top-item-expandable',
    'home-full-analysis', 'home-analysis-body', 'analysis-source-row',
    'source-inline', 'video-embed', 'video-fallback', 'case-preview',
    'summary', 'detail-body', 'meta',
}


def html_classes(soup):
    out = set()
    for el in soup.find_all(class_=True):
        out.update(el.get('class', []))
    return out


def selector_allowed(selector, allowed):
    classes = set(re.findall(r'\.([A-Za-z_][\w-]*)', selector))
    return not classes or classes.issubset(allowed)


def prune_rule_list(rule_list, allowed):
    for i in range(rule_list.length - 1, -1, -1):
        rule = rule_list.item(i)
        if rule.type == rule.STYLE_RULE:
            selectors = [s.selectorText for s in rule.selectorList]
            keep = [s for s in selectors if selector_allowed(s, allowed)]
            if not keep:
                rule_list.deleteRule(i)
            else:
                rule.selectorText = ', '.join(keep)
        elif rule.type == rule.MEDIA_RULE:
            prune_rule_list(rule.cssRules, allowed)
            if rule.cssRules.length == 0:
                rule_list.deleteRule(i)


def clean_css(text, allowed, header):
    sheet = cssutils.parseString(text)
    prune_rule_list(sheet.cssRules, allowed)
    raw = sheet.cssText.decode('utf-8')
    pretty = cssbeautifier.beautify(raw, {
        'indent_size': 2,
        'newline_between_rules': True,
        'selector_separator_newline': True,
        'end_with_newline': True,
    })
    return f'/* {header} */\n' + pretty


def update_index():
    path = ROOT / 'index.html'
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    head = soup.head
    if not head:
        raise RuntimeError('index.html has no <head>')

    for link in list(head.find_all('link', rel='stylesheet')):
        href = link.get('href', '')
        if href.split('?', 1)[0] in {'home.css', 'home-content.css', 'home-layout-fixes.css', 'home-layout.css', 'home-ui.css'}:
            link.decompose()

    styles_link = head.find('link', href=re.compile(r'^styles\.css'))
    layout = soup.new_tag('link', href=f'home-layout.css?v={VERSION}', rel='stylesheet')
    ui = soup.new_tag('link', href=f'home-ui.css?v={VERSION}', rel='stylesheet')
    if styles_link:
        styles_link.insert_after(layout)
        layout.insert_after(ui)
    else:
        head.append(layout)
        head.append(ui)

    script = head.find('script', src=re.compile(r'^home\.js'))
    if script:
        script['src'] = f'home.js?v={VERSION}'

    for a in soup.find_all('a', target='_blank'):
        rel = set(a.get('rel', []))
        rel.update({'noopener', 'noreferrer'})
        a['rel'] = sorted(rel)

    path.write_text(str(soup), 'utf-8')
    return soup


def update_supporting_scripts():
    preview = ROOT / 'scripts' / 'inject_visual_previews.py'
    if preview.exists():
        text = preview.read_text('utf-8')
        text = text.replace("ROOT/'home-content.css'", "ROOT/'home-ui.css'")
        text = text.replace("home-content.css?v=20260822-3", f"home-ui.css?v={VERSION}")
        text = text.replace("home-content.css?v=20260822-4", f"home-ui.css?v={VERSION}")
        preview.write_text(text, 'utf-8')

    visual = ROOT / '.github' / 'workflows' / 'visual-assets.yml'
    if visual.exists():
        text = visual.read_text('utf-8').replace('home-content.css', 'home-ui.css')
        if 'python scripts/check_home_contract.py' not in text:
            text = text.replace('      - name: Commit generated visual assets and preview markup\n', '      - name: Homepage contract QA\n        run: python scripts/check_home_contract.py\n      - name: Commit generated visual assets and preview markup\n')
        visual.write_text(text, 'utf-8')


def main():
    soup = update_index()
    allowed = html_classes(soup) | DYNAMIC_CLASSES

    foundation = (ROOT / 'home.css').read_text('utf-8')
    emergency = (ROOT / 'home-layout-fixes.css').read_text('utf-8')
    ui = (ROOT / 'home-content.css').read_text('utf-8')

    (ROOT / 'home-layout.css').write_text(
        clean_css(foundation + '\n' + emergency, allowed,
                  'Homepage layout and current structural components. Legacy selectors removed by contract migration.'),
        'utf-8'
    )
    (ROOT / 'home-ui.css').write_text(
        clean_css(ui, allowed,
                  'Homepage content system, dark theme, analysis components, and visual evidence styles.'),
        'utf-8'
    )

    for legacy in ('home.css', 'home-content.css', 'home-layout-fixes.css'):
        p = ROOT / legacy
        if p.exists():
            p.unlink()

    update_supporting_scripts()
    print('Homepage frontend refactor complete')


if __name__ == '__main__':
    main()
