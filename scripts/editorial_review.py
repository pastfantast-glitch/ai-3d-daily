"""Consume ChatGPT-scheduled editorial decisions without a model API or another writer."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ('faithful_to_source', 'dates_and_versions_correct', 'traditional_chinese_clear',
          'source_specific', 'inferences_labeled', 'evidence_sufficient')


class ReviewError(ValueError):
    pass


def evidence_hash(evidence):
    return hashlib.sha256('\n'.join(b['text'] for b in evidence['blocks']).encode('utf-8')).hexdigest()


def valid_refs(refs, ids):
    return isinstance(refs, list) and bool(refs) and all(isinstance(x, str) and x in ids for x in refs)


def read_review(date, root=ROOT):
    path = root / 'data' / 'editorial-reviews' / f'{date}.json'
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text('utf-8'))
        valid = (data.get('schema_version') == 1 and data.get('date') == date
                 and data.get('reviewer') == 'chatgpt-scheduled-task'
                 and type(data.get('source_run_id')) is int and data['source_run_id'] > 0
                 and re.fullmatch(r'[0-9a-f]{40}', data.get('source_head_sha', ''))
                 and isinstance(data.get('items'), dict) and 0 < len(data['items']) <= 60)
        if not valid:
            raise ReviewError('editorial review schema/date/provenance invalid')
        return data
    except (ValueError, TypeError, AttributeError) as error:
        raise ReviewError('editorial review unreadable or invalid') from error


def validate_record(record, article, date):
    evidence = article.get('evidence') or {}
    try:
        ids = {b['id'] for b in evidence['blocks']}
        if (evidence.get('status') != 'extracted' or evidence.get('truncated') is not False
                or not ids or evidence_hash(evidence) != evidence.get('sha256')):
            raise ReviewError('complete, unmodified extracted evidence required')
        if (record.get('source_url') != article['source_url']
                or record.get('source_published_at') != article.get('source_published_at')
                or record.get('source_evidence_sha256') != evidence['sha256']
                or record.get('reviewed_on') != date):
            raise ReviewError('review source identity/date/evidence mismatch')
        decision = record.get('review') or {}
        checks = decision.get('checks') or {}
        if (decision.get('approved') is not True or decision.get('method') != 'second-pass-source-check'
                or decision.get('issues') != [] or decision.get('unsupported_claims') != []
                or set(checks) != set(CHECKS) or not all(value is True for value in checks.values())
                or not valid_refs(decision.get('evidence_refs'), ids)):
            raise ReviewError('second-pass source review did not approve all checks')
        if (not all(isinstance(record.get(k), str) and record[k].strip() for k in ('title', 'summary'))
                or not valid_refs(record.get('evidence_refs'), ids)):
            raise ReviewError('draft text or source references missing')
        analysis = record.get('full_analysis')
        if (not isinstance(analysis, list) or len(analysis) != 3
                or any(not isinstance(b, dict)
                       or not all(isinstance(b.get(k), str) and b[k].strip() for k in ('label', 'text'))
                       or not valid_refs(b.get('evidence_refs'), ids) for b in analysis)):
            raise ReviewError('three source-supported analysis angles required')
    except (KeyError, TypeError, AttributeError) as error:
        raise ReviewError('invalid editorial record/evidence structure') from error
    return {'id': article['id'], 'source_url': article['source_url'],
            'source_published_at': article.get('source_published_at'),
            'title': record['title'], 'summary': record['summary'],
            'full_analysis': [{'label': b['label'], 'text': b['text']} for b in analysis]}


def candidate_copy(candidate, date, root=ROOT):
    data = read_review(date, root)
    if data is None or candidate['candidate_id'] not in data['items']:
        return None, []
    article = {'id': candidate['candidate_id'], 'source_url': candidate['source_url'],
               'source_published_at': candidate['meta'].get('published'),
               'evidence': candidate['meta'].get('article_evidence') or {}}
    try:
        reader = validate_record(data['items'][article['id']], article, date)
        candidate['scheduled_review'] = {'status': 'approved', 'source_run_id': data['source_run_id'],
            'source_evidence_sha256': article['evidence']['sha256'], 'reviewed_on': date,
            'method': 'second-pass-source-check'}
        return reader, []
    except ReviewError as error:
        candidate['scheduled_review'] = {'status': 'rejected', 'reason': str(error)}
        return None, [str(error)]


def validate_packet(data, packet, date):
    if packet.get('date') != date:
        raise ReviewError('packet edition mismatch')
    if packet.get('source_run_id') is not None and packet['source_run_id'] != data['source_run_id']:
        raise ReviewError('packet run mismatch')
    if packet.get('source_head_sha') is not None and packet['source_head_sha'] != data['source_head_sha']:
        raise ReviewError('packet commit mismatch')
    articles = {a['id']: a for a in packet['articles']}
    copies = []
    for cid, record in data['items'].items():
        if cid not in articles:
            raise ReviewError('reviewed ID absent from Collector artifact')
        copies.append(validate_record(record, articles[cid], date))
    from check_editorial_quality import editorial_errors, load_editorial_config
    cfg = load_editorial_config()
    errors = editorial_errors({'items': copies, 'metadata': {'editorial': {
        'contract': cfg.get('contract'), 'style_reference': cfg.get('style_reference'),
        'factual_fallback_allowed': True}}}, date)
    if errors:
        raise ReviewError('; '.join(errors))
    return copies


def validate_run(data, run, date):
    try:
        local = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Taipei'))
        valid = (run['id'] == data['source_run_id'] and run['head_sha'] == data['source_head_sha']
                 and run['head_branch'] == 'main' and local.date().isoformat() == date
                 and run['name'] == 'Autonomous daily Collector'
                 and run['status'] == 'completed' and run['conclusion'] == 'failure')
        if not valid:
            raise ReviewError('review must reference a failed main Collector for this edition')
    except (KeyError, TypeError, ValueError) as error:
        raise ReviewError('review source run invalid') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('date')
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--run-json', type=Path)
    parser.add_argument('--run-id-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', args.date):
        parser.error('date must be YYYY-MM-DD')
    try:
        data = read_review(args.date)
        if data is None:
            raise ReviewError('editorial review file missing')
        if args.run_id_only:
            print(data['source_run_id'])
            return
        if not args.packet or not args.run_json:
            parser.error('--packet and --run-json required for source validation')
        validate_run(data, json.loads(args.run_json.read_text()), args.date)
        copies = validate_packet(data, json.loads(args.packet.read_text()), args.date)
        print(f'EDITORIAL REVIEW PASS: {args.date} records={len(copies)} source_run={data["source_run_id"]}')
    except (OSError, ValueError) as error:
        raise SystemExit(f'EDITORIAL REVIEW FAILED: {error}') from None


if __name__ == '__main__':
    main()
