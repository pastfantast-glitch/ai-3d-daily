"""Bounded operational metadata, never source paragraphs, HTML or preferences."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def workflow_mutation_errors(content):
    parts = content.split('      - name: Persist bounded Collector monitoring metadata', 1)
    if len(parts) != 2 or parts[0].count('git commit ') != 1 or parts[0].count('git push ') != 1:
        return ['Collector must have one canonical/private artifact commit path']
    monitor = parts[1]
    required = (
        'git add data/ops/collection-monitor.json',
        'test "$(git diff --cached --name-only)" = "data/ops/collection-monitor.json"',
        'git diff --cached --quiet ||',
        'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"',
        'git commit -m "Record Collector monitor $DATE"',
    )
    if (any(monitor.count(command) != 1 for command in ('git add ', 'git commit ', 'git push '))
            or any(token not in monitor for token in required)):
        return ['Collector monitoring must only commit its fixed metadata path with a current-main guard']
    return []


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
               if field in ('status', 'candidates_found', 'published_links_skipped', 'reason', 'article_pages_checked', 'evidence_extracted', 'body_readable_before_topic', 'topic_rejected', 'awaiting_review', 'review_approved', 'quality_pass_unpublished', 'selected', 'approved_reserve')
               and isinstance(value, (str, int, bool))} for k, v in list((packet.get('sources') or {}).items())[:100] if isinstance(v, dict)}
    return {'schema_version': 1, 'date': date, 'source_run_id': run, 'source_head_sha': head,
            'mode': 'source-trial' if packet.get('mode') == 'source-trial' else 'daily',
            'collector_conclusion': conclusion, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'counts': counts, 'articles': rows, 'sources': sources}


def with_yield_history(current, previous, root):
    """Bounded run observations, not sums of overlapping retries or approvals.

Review inventory is sampled at Collector completion; later review merges appear
in the live reserve view immediately and in this trend at the next observation.
"""
    from editorial_reserve import reserve_seeds
    from collection_settings import load_settings
    from editorial_review import read_review_file
    from url_identity import canonicalize_url
    from datetime import date as day, timedelta
    settings = load_settings(root)
    date = current['date']
    cutoff = (day.fromisoformat(date) - timedelta(days=29)).isoformat()
    records = []
    for p in sorted((root/'data/editorial-reviews').glob('20*.json')):
        if cutoff <= p.name[:10] <= date:
            data = read_review_file(p)
            records.extend(r for r in data['items'].values() if r.get('review', {}).get('approved') is True)
    unique = {canonicalize_url(r['source_url']): r for r in records}
    published = set()
    for p in (root/'data/publish').glob('*.done.json'):
        data_path = root/'data/daily'/f'{p.name[:10]}.json'
        if data_path.exists():
            receipt = json.loads(p.read_text('utf-8'))
            data = json.loads(data_path.read_text('utf-8'))
            from collection_settings import all_items
            if not any(canonicalize_url(x['source_url']) in unique for x in all_items(data)):
                continue
            from daily_release_status import receipt_errors, read
            if not receipt_errors(p.name[:10],root,receipt,data,read(root/'data/publish/latest-success.json'),allow_newer_latest=True):
                published.update(canonicalize_url(x['source_url']) for x in all_items(data))
    seeds = reserve_seeds(root, date, settings['sources'])
    def source_for(url):
        host = (urlsplit(url).hostname or '').removeprefix('www.')
        return next((s['id'] for s in settings['sources'] if host == (urlsplit(s['base_url']).hostname or '').removeprefix('www.')), None)
    supply = {}
    for s in settings['sources']:
        sid = s['id']
        urls = {u for u in unique if source_for(u) == sid}
        supply[sid] = {'approved_30d':len(urls), 'published_from_approvals_30d':len(urls & published),
                       'reserve_pending_recheck':sum(x['source_id'] == sid for x in seeds)}
    observation = {k:current[k] for k in ('date','source_run_id','source_head_sha','mode','counts','sources')}
    observation.update(observed_at=current['observed_at'], inventory=supply)
    history = [x for x in previous.get('yield_history', []) if isinstance(x,dict)
               and cutoff <= str(x.get('date','')) <= date and x.get('source_run_id') != current['source_run_id']]
    # Keep only our fixed metadata projection, never old arbitrary payload fields.
    history = [{k:x[k] for k in ('date','source_run_id','source_head_sha','mode','counts','sources','observed_at','inventory') if k in x} for x in history]
    current['yield_history'] = (history + [observation])[-60:]
    current['yield_inventory'] = supply
    current['yield_window_start'] = cutoff
    current['yield_note'] = 'Run observations overlap; never sum candidate counts across retries. Inventory excludes published, held and expired reviews; pending recheck is not ready to publish.'
    return current


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--conclusion', required=True, choices=['success', 'failure', 'cancelled'])
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / 'data/ops/collection-monitor.json'
    previous = json.loads(output.read_text('utf-8')) if output.exists() else {}
    data = with_yield_history(summarize(json.loads(args.packet.read_text('utf-8')), args.conclusion), previous, output.parents[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')
