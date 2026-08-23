#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
DATE='2026-08-23'
IDS=['blender-52-geometry-nodes-physics','retopoflow-419','endfield-hybrid-npr','procedural-hand-painted-eevee','blender-52-lts','node-preview-thumbnails','geo-nodes-guide','ppeh-tools','node-wrangler-52-preview','stylized-pixelated-caustics','material-lighting-nodes']
for path,selectors in [(ROOT/'index.html',['.top-item','.more-card']),(ROOT/DATE/'index.html',['#top .news','.category-deep .news'])]:
    soup=BeautifulSoup(path.read_text('utf-8'),'html.parser'); cards=[]
    for selector in selectors: cards.extend(soup.select(selector))
    # Match by canonical source href rather than card order for durable migration.
    source_to_id={
      'geometry-nodes-physics':'blender-52-geometry-nodes-physics','retopoflow':'retopoflow-419','project-endfield-character-rendering':'endfield-hybrid-npr','hand-painted-look':'procedural-hand-painted-eevee','blender.org/releases/5-2':'blender-52-lts','node-preview':'node-preview-thumbnails','geo-nodes-guide':'geo-nodes-guide','ppeh-tools':'ppeh-tools','node_wrangler':'node-wrangler-52-preview','pixelated-caustics':'stylized-pixelated-caustics','material-lighting-nodes':'material-lighting-nodes'}
    for card in cards:
        href=' '.join(a.get('href','') for a in card.select('a.source'))
        for key,rid in source_to_id.items():
            if key in href: card['data-intel-id']=rid; break
    path.write_text(soup.prettify(),'utf-8')
    print(path.relative_to(ROOT),sum(1 for c in cards if c.get('data-intel-id')))
