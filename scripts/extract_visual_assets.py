#!/usr/bin/env python3
import io, json, re, hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'visual-assets.json'
OUT_DIR = ROOT / 'assets' / 'visual'
OUT_DIR.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'
TIMEOUT = 25

BAD = re.compile(r'(logo|icon|avatar|author|cookie|banner|advert|ads|sprite|placeholder|zoom-icon|tracking|pixel|emoji)', re.I)
GOOD = re.compile(r'(final|render|hero|cover|scene|character|portrait|environment|unreal|blender|result|project)', re.I)


def norm_url(base, value):
    if not value: return None
    value = value.strip()
    if value.startswith('//'): value = 'https:' + value
    return urljoin(base, value)


def srcset_best(base, value):
    if not value: return None
    parts = []
    for chunk in value.split(','):
        bits = chunk.strip().split()
        if not bits: continue
        u = norm_url(base, bits[0])
        weight = 0
        if len(bits) > 1:
            m = re.match(r'(\d+)(w|x)', bits[1])
            if m: weight = int(m.group(1))
        parts.append((weight, u))
    return max(parts, default=(0, None))[1]


def collect_candidates(page_url, html, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    def add(url, score, reason, context=''):
        url = norm_url(page_url, url)
        if not url or not url.startswith(('http://','https://')): return
        text = f'{url} {context}'
        if BAD.search(text): score -= 120
        if GOOD.search(text): score += 22
        for k in keywords:
            if k.lower() in text.lower(): score += 8
        prev = found.get(url)
        if not prev or score > prev['score']:
            found[url] = {'url':url,'score':score,'reason':reason,'context':context[:300]}

    for prop, base_score in [('og:image',96),('twitter:image',88),('twitter:image:src',88)]:
        tag = soup.find('meta', attrs={'property':prop}) or soup.find('meta', attrs={'name':prop})
        if tag: add(tag.get('content'), base_score, prop)

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
        except Exception:
            continue
        stack = [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                if 'image' in obj:
                    imgs = obj['image'] if isinstance(obj['image'], list) else [obj['image']]
                    for v in imgs:
                        if isinstance(v, str): add(v, 82, 'jsonld:image')
                        elif isinstance(v, dict): add(v.get('url') or v.get('contentUrl'), 82, 'jsonld:image')
                stack.extend(obj.values())
            elif isinstance(obj, list): stack.extend(obj)

    for img in soup.find_all('img'):
        context = ' '.join(filter(None,[img.get('alt',''), img.get('title',''), img.get('class') and ' '.join(img.get('class'))]))
        for attr,score in [('data-src',72),('data-lazy-src',72),('data-original',72),('src',66)]:
            add(img.get(attr), score, f'img:{attr}', context)
        ss = srcset_best(page_url, img.get('srcset') or img.get('data-srcset'))
        if ss: add(ss, 78, 'img:srcset', context)
    return sorted(found.values(), key=lambda x:x['score'], reverse=True)


def fetch_image(session, page_url, cand):
    r = session.get(cand['url'], timeout=TIMEOUT, headers={'Referer':page_url}, allow_redirects=True)
    r.raise_for_status()
    ctype = r.headers.get('content-type','').lower()
    if 'image' not in ctype: raise ValueError(f'not image: {ctype}')
    im = Image.open(io.BytesIO(r.content))
    im.load()
    w,h = im.size
    if w < 640 or h < 320: raise ValueError(f'too small {w}x{h}')
    area = w*h
    ratio = w/h
    score = cand['score'] + min(45, area/350000) + (8 if 1.1 <= ratio <= 2.2 else 0)
    return r, im, score


def save_image(entry, im):
    # Normalize to web-friendly JPEG while preserving composition; no hard crop.
    if im.mode not in ('RGB','L'):
        bg = Image.new('RGB', im.size, (18,24,39))
        if 'A' in im.getbands(): bg.paste(im, mask=im.getchannel('A'))
        else: bg.paste(im)
        im = bg
    else:
        im = im.convert('RGB')
    max_w = 1600
    if im.width > max_w:
        nh = round(im.height * max_w / im.width)
        im = im.resize((max_w, nh), Image.Resampling.LANCZOS)
    out = OUT_DIR / f"{entry['id']}.jpg"
    im.save(out, 'JPEG', quality=88, optimize=True, progressive=True)
    return out


def main():
    cfg = json.loads(MANIFEST.read_text('utf-8'))
    session = requests.Session(); session.headers.update({'User-Agent':UA, 'Accept-Language':'en-US,en;q=0.8'})
    report = {'generated_by':'scripts/extract_visual_assets.py','entries':[]}
    for entry in cfg['entries']:
        rec = {'id':entry['id'],'page_url':entry['page_url'],'status':'missing'}
        try:
            page = session.get(entry['page_url'], timeout=TIMEOUT)
            page.raise_for_status()
            cands = collect_candidates(entry['page_url'], page.text, entry.get('keywords',[]))
            tested=[]; winner=None
            for cand in cands[:18]:
                try:
                    _, im, score = fetch_image(session, entry['page_url'], cand)
                    tested.append({'url':cand['url'],'score':round(score,2),'size':list(im.size),'reason':cand['reason']})
                    if winner is None or score > winner[0]: winner=(score,cand,im.copy())
                except Exception as e:
                    continue
            if not winner: raise RuntimeError('no valid image candidate')
            score,cand,im = winner
            out = save_image(entry, im)
            rec.update({'status':'ok','asset_path':str(out.relative_to(ROOT)).replace('\\','/'),'source_image_url':cand['url'],'source_kind':cand['reason'],'width':im.width,'height':im.height,'label':entry.get('label','SOURCE PREVIEW'),'tested':tested[:8]})
        except Exception as e:
            rec['error'] = str(e)
        report['entries'].append(rec)
    (OUT_DIR/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), 'utf-8')
    ok=sum(1 for x in report['entries'] if x['status']=='ok')
    print(f'visual assets: {ok}/{len(report["entries"])}')
    if ok == 0: raise SystemExit(2)

if __name__ == '__main__': main()
