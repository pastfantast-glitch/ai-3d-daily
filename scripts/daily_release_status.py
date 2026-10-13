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


def release_status(date, root=ROOT, runs=(), publish_result='', exclude_run_id=None, collector_log=''):
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date):
        raise ValueError('date must be YYYY-MM-DD')
    receipt = read(root / 'data' / 'publish' / f'{date}.done.json')
    canonical = read(root / 'data' / 'daily' / f'{date}.json')
    latest = read(root / 'data' / 'publish' / 'latest-success.json')
    result = {'date': date, 'state': 'NOT_STARTED', 'last_verified_date': latest.get('date'),
              'item_count': len(canonical.get('items') or []), 'workflow_success_is_publication': False}
    if receipt:
        source = str(receipt.get('site_url') or '').rstrip('/')
        ids = [x.get('id') for x in canonical.get('items') or []]
        valid = (receipt.get('state') == 'DONE' and receipt.get('date') == date
                 and canonical.get('date') == date and ids
                 and (receipt.get('qa') or {}).get('pages') == 'pass'
                 and (receipt.get('canonical') or {}).get('ids') == ids
                 and (receipt.get('canonical') or {}).get('item_count') == len(ids)
                 and source.startswith('https://')
                 and receipt.get('daily_url') == source + '/' + date + '/'
                 and commit_exists(root, receipt.get('publish_commit_sha')))
        result.update(state='DONE' if valid else 'INVALID_RECEIPT')
        if valid:
            result.update(daily_url=receipt['daily_url'], publish_commit_sha=receipt['publish_commit_sha'])
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
    elif canonical.get('items') and (root / 'data' / 'candidates' / 'collection-session' / f'{date}.json').exists():
        result['state'] = 'AWAITING_HANDOFF'
    else:
        collectors = [r for r in relevant if r.get('name') == 'Autonomous daily Collector' and r.get('conclusion') != 'skipped']
        if collectors:
            last = max(collectors, key=lambda r: (int(r['id']), int(r.get('run_attempt', 1))))
            result['state'] = 'COLLECTOR_FAILED' if last.get('conclusion') == 'failure' else 'NOT_PUBLISHED'
            result['collector_run_id'] = last['id']
            shortage = re.search(r'verified unpublished survivors=(\d+) below configured fallback floor=(\d+)', collector_log)
            if last.get('conclusion') == 'failure' and shortage:
                result.update(state='CANDIDATES_INSUFFICIENT', verified_unpublished=int(shortage[1]), minimum=int(shortage[2]))
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
