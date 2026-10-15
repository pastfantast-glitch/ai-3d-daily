"""Extract bounded article evidence for human review, never page-wide filler."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

BODY_SELECTORS = (
    '[id="80lv__article__body"]', '.post_content', '[itemprop="articleBody"]',
    '.entry-content', '.article-content', '.article-body', '.post-content',
    'article main', 'article',
)
NOISE = re.compile(r'(?:^|[\s_-])(?:related|sidebar|comments?|conversation|newsletter|'
                   r'social|share|advertisement|advert|cookie|next-prev|post-meta)(?:$|[\s_-])', re.I)
MAX_CHARS = 48000
MAX_BLOCKS = 200
TEXT_NOISE = re.compile(r'^(?:Have your say on this story|Are you a fan of what we do here)'
                        r'|subscribe to our Newsletter.*80 Level', re.I)


def clean(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def extract_article_evidence(html: str, url: str) -> dict:
    soup = BeautifulSoup(html or '', 'html.parser')
    selector, body = '', None
    for candidate in BODY_SELECTORS:
        node = soup.select_one(candidate)
        if node is not None:
            selector, body = candidate, node
            break
    empty = {'status': 'body-missing', 'selector': selector, 'blocks': [],
             'char_count': 0, 'observed_char_count': 0, 'truncated': False,
             'sha256': '', 'links': []}
    if body is None:
        return empty
    # Operate on a copy: metadata dates and crawler links still use the original.
    body = BeautifulSoup(str(body), 'html.parser')
    for node in list(body.find_all(True)):
        if node.parent is None:
            continue
        identity = ' '.join([str(node.get('id') or ''), ' '.join(node.get('class') or [])])
        if (node.name in {'script', 'style', 'noscript', 'nav', 'aside', 'footer', 'form', 'button'}
                or NOISE.search(identity) or 'Article__widget_type_article-items' in identity):
            node.decompose()
    blocks, seen, observed, retained = [], set(), 0, 0
    section = ''
    for node in body.find_all(['h2', 'h3', 'h4', 'h5', 'p', 'li', 'figcaption']):
        # Avoid nested list and paragraph duplication.
        if node.name == 'li' and node.find(['p', 'li']):
            continue
        text = clean(node.get_text(' ', strip=True))
        if node.name in {'h2', 'h3', 'h4', 'h5'}:
            if re.fullmatch(r'(related (?:posts|articles|topics)|comments?|関連記事|コメント)', text, re.I):
                break
            section = text
            continue
        if len(text) < 20 or text in seen or TEXT_NOISE.search(text):
            continue
        seen.add(text)
        observed += len(text)
        if len(blocks) >= MAX_BLOCKS or retained + len(text) > MAX_CHARS:
            continue
        retained += len(text)
        blocks.append({'id': f'p{len(blocks) + 1:03}', 'section': section,
                       'kind': node.name, 'text': text})
    links, seen_links = [], set()
    for node in body.find_all('a', href=True):
        target = urljoin(url, node['href'])
        label = clean(node.get_text(' ', strip=True))
        if urlparse(target).scheme != 'https' or not label or target in seen_links:
            continue
        seen_links.add(target)
        links.append({'label': label[:160], 'url': target})
        if len(links) >= 30:
            break
    text = '\n'.join(block['text'] for block in blocks)
    return {'status': 'extracted' if retained >= 200 and len(blocks) >= 2 else 'body-thin',
            'selector': selector, 'blocks': blocks, 'char_count': retained,
            'observed_char_count': observed, 'truncated': observed > retained,
            'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest() if text else '',
            'links': links}


def review_record(candidate: dict, errors: list[str]) -> dict:
    meta = candidate.get('meta') or {}
    evidence = meta.get('article_evidence') or {}
    return {'id': candidate.get('candidate_id'), 'source_url': candidate.get('source_url'),
            'source_title': meta.get('title'), 'source_published_at': meta.get('published'),
            'description': meta.get('description'), 'evidence': evidence,
            'review_status': (candidate.get('scheduled_review') or {}).get('status', 'needs-human-review'),
            'scheduled_review': candidate.get('scheduled_review') or {},
            'editorial_errors': errors}


def loss_summary(candidates, rejections):
    counts = {}
    for _, errors in rejections:
        # Reasons overlap; count each class at most once per rejected article.
        reasons = set()
        for error in errors:
            if 'generic analysis padding' in error:
                reasons.add('generic-analysis')
            elif 'old source requires' in error:
                reasons.add('historical-label-missing')
            elif 'postdates' in error:
                reasons.add('future-source')
            elif 'publication date' in error:
                reasons.add('date-missing-or-invalid')
            else:
                reasons.add('other-editorial')
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    bodies = {}
    for candidate in candidates:
        status = (candidate.get('meta', {}).get('article_evidence') or {}).get('status', 'not-recorded')
        bodies[status] = bodies.get(status, 0) + 1
    return {'candidates': len(candidates), 'body_status': bodies,
            'editorial_rejected': len(rejections), 'rejection_classes': counts,
            'reason_counts_overlap': True}
