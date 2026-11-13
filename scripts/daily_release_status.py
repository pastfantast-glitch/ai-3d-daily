#!/usr/bin/env python3
"""Read-only, date-scoped publication status; workflow success is not DONE."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    try:
        return json.loads(path.read_text('utf-8'))
    except (OSError, ValueError):
        return {}


def commit_exists(root, sha):
    if not re.fullmatch(r'[0-9a-f]{40}', str(sha or '')):
        return False
    return subprocess.run(['git', 'cat-file', '-e', sha + '^{commit}'], cwd=root,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


SITE_URL = 'https://pastfantast-glitch.github.io/ai-3d-daily/'


def committed_dataset(root, sha, date):
    if not commit_exists(root, sha):
        return None
    proc = subprocess.run(['git', 'show', f'{sha}:data/daily/{date}.json'], cwd=root,
                          capture_output=True, encoding='utf-8')
    try:
        return json.loads(proc.stdout) if proc.returncode == 0 else None
    except ValueError:
        return None


def receipt_errors(date, root, receipt, canonical, latest, *, allow_newer_latest=False):
    errors = []
    ids = [x.get('id') for x in canonical.get('items') or []]
    if receipt.get('state') != 'DONE' or receipt.get('date') != date or canonical.get('date') != date:
        errors.append('receipt/canonical date or state mismatch')
    if not ids or any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        errors.append('canonical IDs missing or duplicated')
    if (receipt.get('canonical') or {}).get('ids') != ids or (receipt.get('canonical') or {}).get('item_count') != len(ids):
        errors.append('receipt canonical IDs/count mismatch')
    if (receipt.get('qa') or {}).get('pages') != 'pass':
        errors.append('Pages QA is not pass')
    if receipt.get('site_url') != SITE_URL or receipt.get('daily_url') != SITE_URL + date + '/':
        errors.append('site/daily URL mismatch')
    sha = receipt.get('publish_commit_sha')
    if committed_dataset(root, sha, date) != canonical:
        errors.append('publish commit does not contain the current canonical dataset')
    if latest.get('date') != date and not (allow_newer_latest and str(latest.get('date') or '') > date):
        errors.append('latest-success edition mismatch')
    elif latest.get('date') == date:
        health = latest.get('health') or {}
        if (latest.get('publish_commit_sha') != sha or latest.get('site_url') != SITE_URL
                or latest.get('receipt') != f'data/publish/{date}.done.json'
                or health.get('date') != date or health.get('publish_commit_sha') != sha
                or health.get('state') != 'HEALTHY' or (health.get('checks') or {}).get('pages') != 'pass'):
            errors.append('latest-success provenance/health mismatch')
    return errors


def release_status(date, root=ROOT, runs=(), publish_result='', exclude_run_id=None, collector_log=''):
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date):
        raise ValueError('date must be YYYY-MM-DD')
    receipt = read(root / 'data' / 'publish' / f'{date}.done.json')
    canonical = read(root / 'data' / 'daily' / f'{date}.json')
    latest = read(root / 'data' / 'publish' / 'latest-success.json')
    result = {'date': date, 'state': 'NOT_STARTED', 'last_verified_date': latest.get('date'),
              'item_count': len(canonical.get('items') or []), 'workflow_success_is_publication': False}
    if receipt:
        errors = receipt_errors(date, root, receipt, canonical, latest)
        valid = not errors
        if errors:
            result.update(first_blocker=errors[0], issues=errors)
        result.update(state='DONE' if valid else 'INVALID_RECEIPT')
        if valid:
            result.update(daily_url=receipt['daily_url'], publish_commit_sha=receipt['publish_commit_sha'])
            if (canonical.get('metadata') or {}).get('content_supply'):
                result['content_supply'] = {**canonical['metadata']['content_supply'], 'published': len(canonical['items'])}
        return result
    relevant = []
    for run in runs:
        if str(run.get('id')) == str(exclude_run_id):
            continue
        if run.get('head_branch') != 'main':
            continue
        try:
            local_date = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Taipei')).date().isoformat()
        except (ValueError, KeyError):
            continue
        if local_date == date:
            relevant.append(run)
    active = [r for r in relevant if r.get('status') in ('queued', 'in_progress')]
    if any(r.get('name') == 'Canonical intelligence publish' for r in active):
        result['state'] = 'PUBLISHING'
    elif any(r.get('name') == 'Autonomous daily Collector' for r in active):
        result['state'] = 'COLLECTING'
    elif publish_result == 'failure':
        result['state'] = 'PUBLISH_FAILED'
    elif any(r.get('name') in ('Collector handoff gate', 'Canonical intelligence publish') and r.get('conclusion') == 'failure' for r in relevant):
        failed = max((r for r in relevant if r.get('name') in ('Collector handoff gate', 'Canonical intelligence publish') and r.get('conclusion') == 'failure'), key=lambda r: int(r['id']))
        result.update(state='HANDOFF_FAILED' if failed['name'] == 'Collector handoff gate' else 'PUBLISH_FAILED',
                      first_blocker='Existing pipeline failed; inspect failed job before a bounded recovery.',
                      run_url=failed.get('html_url'), run_id=failed['id'])
    elif read(root / 'data/ops/handoff' / f'{date}.json').get('state') == 'HANDOFF_FAILED':
        report = read(root / 'data/ops/handoff' / f'{date}.json')
        result.update(state='HANDOFF_FAILED', first_blocker=report.get('reason'),
                      issues=report.get('issues'), run_url=report.get('run_url'), next_step=report.get('next_step'))
    elif canonical.get('items') and (root / 'data' / 'candidates' / 'collection-session' / f'{date}.json').exists():
        result['state'] = 'AWAITING_HANDOFF'
    else:
        collectors = [r for r in relevant if r.get('name') == 'Autonomous daily Collector' and r.get('conclusion') != 'skipped']
        if collectors:
            last = max(collectors, key=lambda r: (int(r['id']), int(r.get('run_attempt', 1))))
            result['state'] = 'COLLECTOR_FAILED' if last.get('conclusion') == 'failure' else 'NOT_PUBLISHED'
            result['collector_run_id'] = last['id']
            result['run_url'] = last.get('html_url')
            if last.get('conclusion') == 'failure':
                result['first_blocker'] = 'Collector failed; source/editing counts require its log or evidence artifact.'
            shortage = re.search(r'verified unpublished survivors=(\d+) below configured fallback floor=(\d+)', collector_log)
            if last.get('conclusion') == 'failure' and shortage:
                result.update(state='CANDIDATES_INSUFFICIENT', verified_unpublished=int(shortage[1]), minimum=int(shortage[2]))
    supply = (canonical.get('metadata') or {}).get('content_supply')
    if supply:
        result['content_supply'] = {**supply, 'published': None}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('date')
    parser.add_argument('--runs-json')
    parser.add_argument('--publish-result', default='')
    parser.add_argument('--exclude-run-id')
    parser.add_argument('--collector-log')
    args = parser.parse_args()
    runs = read(Path(args.runs_json)).get('workflow_runs', []) if args.runs_json else []
    log = Path(args.collector_log).read_text('utf-8') if args.collector_log else ''
    print(json.dumps(release_status(args.date, runs=runs, publish_result=args.publish_result,
                                   exclude_run_id=args.exclude_run_id, collector_log=log), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
