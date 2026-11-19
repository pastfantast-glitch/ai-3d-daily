"""Bounded operational metadata, never source paragraphs, HTML or preferences."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def summarize(packet, conclusion):
    date = packet.get('date', '')
    run = packet.get('source_run_id')
    head = packet.get('source_head_sha', '')
    if (not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date) or type(run) is not int or run < 1
            or not re.fullmatch(r'[a-f0-9]{40}', head)):
        raise ValueError('Invalid Collector provenance')
    rows = []
    for article in packet.get('articles', [])[:500]:
        url = article.get('source_url', '')
        if not isinstance(url, str) or urlsplit(url).scheme != 'https' or urlsplit(url).username:
            continue
        evidence = article.get('evidence') or {}
        rows.append({
            'id': str(article.get('id', ''))[:180], 'source_url': url[:1500],
            'title': str(article.get('source_title') or article.get('id', ''))[:300],
            'source_date': str(article.get('source_published_at') or '')[:10],
            'review_status': str(article.get('review_status', 'unknown'))[:60],
            'errors': [str(e)[:300] for e in article.get('editorial_errors', [])[:12]],
            'body_readable': evidence.get('status') == 'extracted' and evidence.get('truncated') is False,
        })
    supply = (packet.get('summary') or {}).get('content_supply') or {}
    counts = {k: supply[k] for k in ('body_readable', 'review_approved', 'awaiting_review',
              'quality_pass_unpublished', 'selected', 'approved_reserve') if type(supply.get(k)) is int}
    sources = {str(k)[:80]: {field: value[:300] if isinstance(value, str) else value for field, value in v.items()
               if field in ('status', 'candidates_found', 'published_links_skipped', 'reason')
               and isinstance(value, (str, int, bool))} for k, v in list((packet.get('sources') or {}).items())[:100] if isinstance(v, dict)}
    return {'schema_version': 1, 'date': date, 'source_run_id': run, 'source_head_sha': head,
            'collector_conclusion': conclusion, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'counts': counts, 'articles': rows, 'sources': sources}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--conclusion', required=True, choices=['success', 'failure', 'cancelled'])
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / 'data/ops/collection-monitor.json'
    data = summarize(json.loads(args.packet.read_text('utf-8')), args.conclusion)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')
