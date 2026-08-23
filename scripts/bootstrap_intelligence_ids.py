#!/usr/bin/env python3
"""One-way bootstrap for legacy 2026-08-23 cards that predate stable IDs.

New renderers must write data-intel-id directly. This migration prefers source URL
identity and uses title matching only where the source URL is too generic.
"""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE = '2026-08-23'

RULES = [
    ('blender-52-geometry-nodes-physics', ('geometry-nodes-physics',), ('Geometry Nodes Physics',)),
    ('retopoflow-419', ('retopoflow',), ('RetopoFlow 4.1.9',)),
    ('endfield-hybrid-npr', ('project-endfield-character-rendering',), ('Arknights: Endfield',)),
    ('procedural-hand-painted-eevee', ('hand-painted-look',), ('Procedural Hand-Painted EEVEE Shader',)),
    ('blender-52-lts', ('blender.org/releases/5-2',), ('Blender 5.2 LTS',)),
    ('node-preview-thumbnails', ('node-preview',), ('Node Preview Thumbnails',)),
    ('geo-nodes-guide', ('geo-nodes-guide',), ('Geo Nodes Guide',)),
    ('ppeh-tools', ('ppeh-tools',), ('ppeh_tools',)),
    ('node-wrangler-52-preview', ('node_wrangler',), ('Node Wrangler 5.2',)),
    ('stylized-pixelated-caustics', (), ('Stylized / Pixelated Caustics',)),
    ('material-lighting-nodes', (), ('Material Lighting Nodes',)),
]


def identify(card):
    href = ' '.join(a.get('href', '') for a in card.select('a.source'))
    title_node = card.select_one('h2,h3,h4')
    title = title_node.get_text(' ', strip=True) if title_node else ''
    for rid, href_keys, title_keys in RULES:
        if any(key in href for key in href_keys) or any(key in title for key in title_keys):
            return rid
    return None


def migrate(path, selectors):
    soup = BeautifulSoup(path.read_text('utf-8'), 'html.parser')
    cards = []
    seen_nodes = set()
    for selector in selectors:
        for card in soup.select(selector):
            marker = id(card)
            if marker not in seen_nodes:
                seen_nodes.add(marker)
                cards.append(card)

    assigned = set()
    for card in cards:
        rid = card.get('data-intel-id') or identify(card)
        if rid:
            card['data-intel-id'] = rid
            assigned.add(rid)

    path.write_text(soup.prettify(), 'utf-8')
    print(f'{path.relative_to(ROOT)}: assigned {len(assigned)} unique canonical IDs')


migrate(ROOT / 'index.html', ['.top-item', '.more-card'])
migrate(ROOT / DATE / 'index.html', ['#top .news', '.category-news'])
