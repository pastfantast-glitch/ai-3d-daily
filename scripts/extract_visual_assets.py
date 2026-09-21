#!/usr/bin/env python3
import html as html_lib
import io, json, re, sys, time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
VISUAL_ROOT = ROOT / 'assets' / 'visual'
VISUAL_ROOT.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'
TIMEOUT = 25
RETRIES = 2
MAX_CANDIDATES = 28

BAD = re.compile(
    r'(logo|icon|avatar|author|cookie|banner|advert|ads|sprite|placeholder|'
    r'zoom-icon|tracking|pixel|emoji|newsletter|social-share)',
    re.I,
)
GOOD = re.compile(
    r'(final|render|hero|cover|scene|character|portrait|environment|unreal|'
    r'blender|result|project|screenshot|preview|showcase|demo|tutorial)',
    re.I,
)
# Known affiliate/tracking hosts repeatedly surfaced ahead of real article media on
# 3DNchu and similar WordPress pages. These are never representative article images.
BAD_HOSTS = {
    'm.media-amazon.com',
    'images-na.ssl-images-amazon.com',
    'image.moshimo.com',
    'i.moshimo.com',
    't.afi-b.com',
    'www.afi-b.com',
    'afi-b.com',
    'scdn.line-apps.com',
    'www.facebook.com',
    'facebook.com',
}
STRONG_REASONS = {
    'og:image',
    'twitter:image',
    'twitter:image:src',
    'meta:itemprop:image',
    'link:image_src',
    'jsonld:image',
    'video:poster',
    'youtube:thumbnail',
    'wp-mshots:link-preview',
}


def latest_date():
    dates = sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates:
        raise SystemExit('No canonical daily datasets found')
    return dates[-1]


def load_entries(date):
    data = json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    explicit = data.get('visual_evidence') or {}
    entries = []
    seen = set()

    # Explicit visual evidence remains authoritative when provided.
    for intel_id, cfg in explicit.items():
        if cfg.get('enabled', True) is False:
            seen.add(intel_id)
            continue
        page_url = cfg.get('source_url')
        if not page_url:
            continue
        entries.append({
            'id': intel_id,
            'page_url': page_url,
            'keywords': cfg.get('keywords', []),
            'label': cfg.get('label', 'SOURCE PREVIEW'),
            'confidence': cfg.get('confidence', 'candidate'),
            'title': str(cfg.get('title') or ''),
        })
        seen.add(intel_id)

    # Canonical source fallback: every canonical item remains a visual attempt even
    # when upstream omitted explicit visual_evidence.
    for item in data.get('items') or []:
        intel_id = item.get('id')
        page_url = item.get('source_url')
        if not intel_id or not page_url or intel_id in seen:
            continue
        title = str(item.get('title') or '')
        category = str(item.get('category') or '')
        subcategory = str(item.get('subcategory') or '')
        keywords = [
            x for x in re.split(r'[^A-Za-z0-9_+.-]+', f'{title} {category} {subcategory}')
            if len(x) >= 3
        ][:12]
        entries.append({
            'id': intel_id,
            'page_url': page_url,
            'keywords': keywords,
            'label': 'SOURCE PREVIEW',
            'confidence': 'canonical-source-fallback',
            'title': title,
        })
        seen.add(intel_id)

    return entries


def request_with_retry(session, url, **kwargs):
    last = None
    for attempt in range(RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT, allow_redirects=True, **kwargs)
            if r.status_code in (401, 403, 429):
                raise PermissionError(f'blocked HTTP {r.status_code}')
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise last


def norm_url(base, value):
    if not value:
        return None
    value = str(value).strip()
    if value.startswith('//'):
        value = 'https:' + value
    return urljoin(base, value)


def host_of(url):
    try:
        return urlparse(url).netloc.lower().split(':', 1)[0]
    except Exception:
        return ''


def mshots_target(url):
    """Return the page URL encoded by WordPress mShots, if this is an mShots URL."""
    try:
        parsed = urlparse(url)
        if parsed.netloc.lower() != 's0.wp.com' or '/mshots/v1/' not in parsed.path:
            return ''
        encoded = parsed.path.split('/mshots/v1/', 1)[1]
        return unquote(encoded)
    except Exception:
        return ''


def blocked_candidate(url):
    host = host_of(url)
    if host in BAD_HOSTS:
        return True
    target = mshots_target(url)
    if target and host_of(target) in BAD_HOSTS:
        return True
    low = url.lower()
    return (
        '/pixel' in low
        or 'impression?' in low
        or '/lead/' in low
        or 'doubleclick.' in low
    )


def srcset_best(base, value):
    if not value:
        return None
    parts = []
    for chunk in value.split(','):
        bits = chunk.strip().split()
        if not bits:
            continue
        u = norm_url(base, bits[0])
        weight = 0
        if len(bits) > 1:
            m = re.match(r'(\d+(?:\.\d+)?)(w|x)', bits[1])
            if m:
                n = float(m.group(1))
                weight = int(n if m.group(2) == 'w' else n * 1000)
        parts.append((weight, u))
    return max(parts, default=(0, None))[1]


def youtube_id(value):
    if not value:
        return ''
    try:
        parsed = urlparse(value)
        host = parsed.netloc.lower()
        path = parsed.path.strip('/')
        if host in {'www.youtube.com', 'youtube.com', 'www.youtube-nocookie.com', 'youtube-nocookie.com'}:
            if path.startswith('embed/'):
                return path.split('/', 1)[1].split('/', 1)[0]
            if path.startswith('watch'):
                from urllib.parse import parse_qs
                return (parse_qs(parsed.query).get('v') or [''])[0]
        if host == 'youtu.be':
            return path.split('/', 1)[0]
    except Exception:
        pass
    return ''


def css_urls(style):
    if not style:
        return []
    out = []
    for match in re.finditer(r'url\(\s*([\'"]?)(.*?)\1\s*\)', style, re.I):
        value = match.group(2).strip()
        if value and not value.startswith('data:'):
            out.append(value)
    return out


def collect_candidates(page_url, html, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    found = {}

    def add(url, score, reason, context=''):
        url = norm_url(page_url, url)
        if not url or not url.startswith(('http://', 'https://')):
            return
        if blocked_candidate(url):
            return

        # WordPress mShots is a page preview, not arbitrary article media. When it
        # points to a non-affiliate outbound target it is still a high-confidence
        # visual representation of that linked primary resource.
        if mshots_target(url):
            reason = 'wp-mshots:link-preview'
            score = max(score, 104)

        text = f'{url} {context}'
        if BAD.search(text):
            score -= 120
        if GOOD.search(text):
            score += 22
        for k in keywords:
            if str(k).lower() in text.lower():
                score += 8

        # A heavily bad-scored candidate is intentionally dropped instead of using
        # network budget that should be spent on actual article media.
        if score < 0:
            return

        prev = found.get(url)
        if not prev or score > prev['score']:
            found[url] = {
                'url': url,
                'score': score,
                'reason': reason,
                'context': context[:300],
            }

    # Strong metadata first.
    for prop, score in [
        ('og:image', 120),
        ('twitter:image', 112),
        ('twitter:image:src', 112),
    ]:
        tag = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
        if tag:
            add(tag.get('content'), score, prop)

    for tag in soup.find_all('meta', attrs={'itemprop': 'image'}):
        add(tag.get('content'), 108, 'meta:itemprop:image')

    for tag in soup.find_all('link'):
        rel = [str(x).lower() for x in (tag.get('rel') or [])]
        if 'image_src' in rel:
            add(tag.get('href'), 108, 'link:image_src')

    # JSON-LD often contains the canonical hero even when the visible page is JS-heavy.
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
                        if isinstance(v, str):
                            add(v, 100, 'jsonld:image')
                        elif isinstance(v, dict):
                            add(v.get('url') or v.get('contentUrl'), 100, 'jsonld:image')
                stack.extend(obj.values())
            elif isinstance(obj, list):
                stack.extend(obj)

    # Video posters / YouTube thumbnails are strong visual evidence for tutorial/talk pages.
    for video in soup.find_all(['video', 'amp-video']):
        add(video.get('poster') or video.get('data-poster'), 108, 'video:poster')

    for frame in soup.find_all(['iframe', 'amp-youtube']):
        src = frame.get('src') or frame.get('data-src') or ''
        vid = youtube_id(src)
        if not vid and frame.name == 'amp-youtube':
            vid = frame.get('data-videoid') or ''
        if vid:
            add(f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg', 111, 'youtube:thumbnail', frame.get('title', ''))
            add(f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg', 96, 'youtube:thumbnail', frame.get('title', ''))

    for a in soup.find_all('a', href=True):
        vid = youtube_id(a.get('href'))
        if vid:
            context = ' '.join(a.stripped_strings)
            add(f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg', 105, 'youtube:thumbnail', context)

    # Standard and lazy-loaded images.
    for img in soup.find_all('img'):
        classes = img.get('class') or []
        context = ' '.join(filter(None, [
            img.get('alt', ''),
            img.get('title', ''),
            ' '.join(classes) if classes else '',
        ]))
        for attr, score in [
            ('data-src', 82),
            ('data-lazy-src', 82),
            ('data-original', 82),
            ('data-lazy', 80),
            ('src', 74),
        ]:
            add(img.get(attr), score, f'img:{attr}', context)
        ss = srcset_best(page_url, img.get('srcset') or img.get('data-srcset'))
        if ss:
            add(ss, 88, 'img:srcset', context)

    # Responsive <picture> and CSS/data-background patterns used by docs portals.
    for source in soup.find_all('source'):
        ss = srcset_best(page_url, source.get('srcset') or source.get('data-srcset'))
        if ss:
            add(ss, 90, 'source:srcset')

    for node in soup.find_all(True):
        for attr in ('data-bg', 'data-background', 'data-background-image', 'data-src-bg'):
            add(node.get(attr), 86, f'background:{attr}', node.get('aria-label', ''))
        for value in css_urls(node.get('style', '')):
            add(value, 84, 'background:style', node.get('aria-label', ''))

    return sorted(found.values(), key=lambda x: x['score'], reverse=True)


def min_dimensions(cand):
    """Dimension floor by evidence strength.

    600×450 WordPress mShots and high-confidence metadata/video previews are useful
    and were incorrectly rejected by the old 640px hard floor. Generic inline
    images keep the stricter floor so small avatars/ads do not become article art.
    """
    reason = str((cand or {}).get('reason') or '')
    if reason in STRONG_REASONS:
        return 560, 280, 160_000
    return 640, 320, 220_000


def fetch_image(session, page_url, cand):
    r = request_with_retry(
        session,
        cand['url'],
        headers={
            'Referer': page_url,
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        },
    )
    content_type = r.headers.get('content-type', '').lower()
    if 'text/html' in content_type or 'application/json' in content_type:
        raise ValueError('not_image')

    try:
        im = Image.open(io.BytesIO(r.content))
        im.load()
    except Exception:
        raise ValueError('not_image')

    w, h = im.size
    min_w, min_h, min_area = min_dimensions(cand)
    if w < min_w or h < min_h or w * h < min_area:
        raise ValueError(f'too_small:{w}x{h}')

    ratio = w / h
    area = w * h
    return im, cand['score'] + min(45, area / 350000) + (8 if 1.1 <= ratio <= 2.2 else 0)


def save_image(date, intel_id, im):
    if im.mode not in ('RGB', 'L'):
        bg = Image.new('RGB', im.size, (18, 24, 39))
        bg.paste(im, mask=im.getchannel('A') if 'A' in im.getbands() else None)
        im = bg
    else:
        im = im.convert('RGB')
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.Resampling.LANCZOS)
    out_dir = VISUAL_ROOT / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{intel_id}.jpg'
    im.save(out, 'JPEG', quality=88, optimize=True, progressive=True)
    return out


def source_card_svg(title, page_url):
    domain = host_of(page_url) or 'source'
    safe_title = html_lib.escape((title or 'Production Intelligence').strip())
    safe_domain = html_lib.escape(domain)
    # Browser-rendered SVG avoids depending on CJK fonts being installed on the
    # GitHub runner. It is explicitly a generated source card, never claimed to be
    # extracted visual evidence.
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#111827"/>
      <stop offset="1" stop-color="#263449"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="675" fill="url(#g)"/>
  <rect x="72" y="72" width="1056" height="531" rx="30" fill="#ffffff" fill-opacity="0.06" stroke="#ffffff" stroke-opacity="0.12"/>
  <text x="112" y="150" fill="#9fb3c8" font-size="30" font-family="system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans TC',sans-serif">SOURCE PREVIEW</text>
  <foreignObject x="108" y="205" width="984" height="270">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans TC',sans-serif;color:#f8fafc;font-size:48px;font-weight:700;line-height:1.28;overflow:hidden;max-height:250px">{safe_title}</div>
  </foreignObject>
  <text x="112" y="548" fill="#d2dae5" font-size="28" font-family="system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans TC',sans-serif">{safe_domain}</text>
</svg>'''


def save_fallback_card(date, intel_id, title, page_url):
    out_dir = VISUAL_ROOT / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{intel_id}.svg'
    out.write_text(source_card_svg(title, page_url), 'utf-8')
    return out


def classify_failure(exc, candidate_count=0):
    s = str(exc).lower()
    if 'blocked http' in s or any(x in s for x in ('403', '401', '429')):
        return 'blocked'
    if 'too_small' in s:
        return 'too_small'
    if 'not_image' in s:
        return 'not_image'
    if any(x in s for x in ('timeout', 'connection', 'http')):
        return 'http_error'
    if candidate_count == 0:
        return 'no_candidate'
    return 'identity_uncertain'


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else latest_date()
    entries = load_entries(date)
    session = requests.Session()
    session.headers.update({'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.8'})
    report = {
        'date': date,
        'identity': 'data-intel-id',
        'asset_versioning': 'daily-snapshot',
        'visual_contract_version': 2,
        'generated_by': 'scripts/extract_visual_assets.py',
        'entries': [],
    }

    for entry in entries:
        rec = {
            'id': entry['id'],
            'page_url': entry['page_url'],
            'status': 'pending',
            'confidence': entry['confidence'],
            'candidate_count': 0,
        }
        candidates = []
        failures = []
        try:
            page = request_with_retry(session, entry['page_url'])
            candidates = collect_candidates(entry['page_url'], page.text, entry['keywords'])
            rec['candidate_count'] = len(candidates)
            winner = None
            tested = []
            for cand in candidates[:MAX_CANDIDATES]:
                try:
                    im, score = fetch_image(session, entry['page_url'], cand)
                    tested.append({
                        'url': cand['url'],
                        'score': round(score, 2),
                        'size': list(im.size),
                        'reason': cand['reason'],
                    })
                    if winner is None or score > winner[0]:
                        winner = (score, cand, im.copy())
                except Exception as exc:
                    failures.append({'url': cand['url'], 'reason': str(exc)[:180]})

            if not winner:
                raise RuntimeError('no valid representative image candidate')

            score, cand, im = winner
            out = save_image(date, entry['id'], im)
            rec.update({
                'status': 'ok',
                'asset_path': str(out.relative_to(ROOT)).replace('\\', '/'),
                'source_image_url': cand['url'],
                'source_kind': cand['reason'],
                'width': im.width,
                'height': im.height,
                'label': entry['label'],
                'score': round(score, 2),
                'tested': tested[:10],
                'failures': failures[:10],
            })
        except Exception as exc:
            extraction_status = classify_failure(exc, len(candidates))
            out = save_fallback_card(
                date,
                entry['id'],
                entry.get('title') or entry['id'],
                entry['page_url'],
            )
            rec.update({
                'status': 'fallback_card',
                'extraction_status': extraction_status,
                'fallback_reason': str(exc),
                'error': str(exc),
                'asset_path': str(out.relative_to(ROOT)).replace('\\', '/'),
                'source_kind': 'generated:source-card',
                'label': 'SOURCE CARD',
                'width': 1200,
                'height': 675,
                'failures': failures[:10],
            })

        report['entries'].append(rec)
        extra = f" extraction={rec.get('extraction_status')}" if rec['status'] == 'fallback_card' else ''
        print(f"visual {entry['id']}: {rec['status']} candidates={rec['candidate_count']}{extra}")

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    # Current manifest is a convenience pointer for Homepage/runtime hydration.
    (VISUAL_ROOT/'manifest.json').write_text(payload, 'utf-8')
    # Per-date manifest preserves the historical evidence snapshot and diagnostics.
    date_dir = VISUAL_ROOT/date
    date_dir.mkdir(parents=True, exist_ok=True)
    (date_dir/'manifest.json').write_text(payload, 'utf-8')

    ok = sum(x['status'] == 'ok' for x in report['entries'])
    fallback = sum(x['status'] == 'fallback_card' for x in report['entries'])
    print(f'visual assets {date}: extracted={ok} fallback={fallback} rendered={ok + fallback}/{len(report["entries"])}')
    # External extraction failures stay observable through extraction_status/error,
    # but every attempted canonical item has a deterministic renderable fallback card.

if __name__ == '__main__':
    main()
