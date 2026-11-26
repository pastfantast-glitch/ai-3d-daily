"""Evidence-only trial in the existing Collector job; no canonical/session writes."""
import copy
import json
import os
from pathlib import Path
import sys
import subprocess
import requests
import run_daily_collector as collector
from article_evidence import review_record, loss_summary
from collection_settings import load_settings, effective_hybrid
from discovery_hybrid import load_hybrid_config
from daily_release_status import release_status

SOURCE_IDS = ('cg-channel', 'godot-official', 'khronos-official', 'blendernation')


def collect(date):
    # A manual post-publication trial may add evidence, never reopen an edition.
    if release_status(date, collector.ROOT)['state'] != 'DONE':
        raise ValueError('Source trial requires an existing valid DONE for this date')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=collector.ROOT,text=True).strip() != os.environ.get('GITHUB_SHA'):
        raise ValueError('Checkout does not match the source run head SHA')
    settings = load_settings(collector.ROOT)
    config = effective_hybrid(load_hybrid_config(), settings)
    sources = {s['id']: s for s in config['discovery_source_pool']['sources'] if s['enabled']}
    if not set(SOURCE_IDS) <= sources.keys():
        raise ValueError('All trial sources must be admitted and active first')
    endpoints = {s['id']: s['endpoints'] for s in settings['sources']}
    runtime = copy.deepcopy(collector.load_json(collector.RUNTIME_PATH))
    runtime['http']['max_workers'] = 3
    runtime['discovery'].update(max_pages_per_source=8, refill_pages_per_source=2,
        max_links_per_endpoint=20, index_pages_per_source=0, feed_urls_per_source=1,
        category_indexes_per_source=0)
    session = requests.Session()
    session.managed_sources = True
    session.headers.update(collector.collector_http_headers(runtime))
    published, _, _ = collector.load_registry(date, collector.load_json(collector.SNAPSHOT_PATH))
    discovered, records, used = [], {}, set()
    for sid in SOURCE_IDS:
        candidates, record = collector.source_probe(sources[sid], endpoints[sid], runtime,
            session, date, used, published_sources=published, collection_settings=settings)
        discovered.extend(candidates)
        records[sid] = record
    if len(discovered) > 40:
        raise ValueError('Trial exceeds the review batch limit')
    # Actual prose validation, never auto-approval or template-generated filler.
    accepted, rejected = collector.readable_candidates(discovered, date)
    errors = {c['candidate_id']: e for c, e in rejected}
    articles = [review_record(c, errors.get(c['candidate_id'], [])) for c in discovered]
    for sid, record in records.items():
        rows = [c for c in discovered if c['source_id'] == sid]
        record.update(awaiting_review=sum((c.get('scheduled_review') or {}).get('status') == 'awaiting-review' for c in rows),
            review_approved=sum(c['source_id'] == sid for c in accepted),
            quality_pass_unpublished=sum(c['source_id'] == sid for c in accepted),
            selected=0, approved_reserve=0)
    supply = dict(body_readable=sum(a['evidence']['status']=='extracted' and a['evidence']['truncated'] is False for a in articles),
        review_approved=len(accepted), awaiting_review=sum(r['awaiting_review'] for r in records.values()),
        quality_pass_unpublished=len(accepted), selected=0, approved_reserve=0, published=None)
    summary = loss_summary(discovered, rejected)
    summary['content_supply'] = supply
    return dict(schema_version=1, mode='source-trial', date=date,
        source_run_id=int(os.environ['GITHUB_RUN_ID']), source_head_sha=os.environ['GITHUB_SHA'],
        summary=summary, sources=records, articles=articles)


if __name__ == '__main__':
    packet = collect(sys.argv[1])
    collector.write_json(Path(os.environ['COLLECTOR_REVIEW_PACKET']), packet)
    print(json.dumps({'date':packet['date'], 'mode':packet['mode'], 'sources':packet['sources'],
                      'counts':packet['summary']['content_supply']}, ensure_ascii=False))
