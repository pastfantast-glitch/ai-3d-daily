#!/usr/bin/env python3
"""Validate the Published Intelligence Registry plus one optional release candidate.

No third registry file is maintained. Only dates with a verified
`data/publish/YYYY-MM-DD.done.json` state=DONE are published history. A current
pre-ready/publish candidate may be supplied as YYYY-MM-DD and is validated against
that DONE history without making failed/WIP dates reserve IDs or source URLs.

Reusing a stable ID on a later published/candidate date means an UPDATE and requires
a non-empty delta. Reusing the same source URL under a new ID is identity drift and
fails publication.
"""
from pathlib import Path
import json
import re
import sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}$')
errors = []
history = {}
source_owner = {}


def norm_url(url):
    return (url or '').strip().rstrip('/')


def is_verified_published(date):
    receipt_path = ROOT / 'data' / 'publish' / f'{date}.done.json'
    if not receipt_path.exists():
        return False
    try:
        receipt = json.loads(receipt_path.read_text('utf-8'))
    except Exception:
        return False
    return str(receipt.get('state', '')).strip().upper() == 'DONE'


def selected_dates(candidate=''):
    dates = []
    for data_path in sorted((ROOT / 'data' / 'daily').glob('20??-??-??.json')):
        date = data_path.stem
        if is_verified_published(date) or date == candidate:
            dates.append(data_path)
    return dates


def main():
    candidate = sys.argv[1] if len(sys.argv) > 1 else ''
    if candidate and not DATE_RE.fullmatch(candidate):
        raise SystemExit('Usage: check_registry_contract.py [YYYY-MM-DD]')
    if candidate and not (ROOT / 'data' / 'daily' / f'{candidate}.json').exists():
        raise SystemExit(f'Missing candidate canonical dataset: data/daily/{candidate}.json')

    for data_path in selected_dates(candidate):
        date = data_path.stem
        data = json.loads(data_path.read_text('utf-8'))
        daily_path = ROOT / date / 'index.html'
        source_by_id = {}
        if daily_path.exists():
            soup = BeautifulSoup(daily_path.read_text('utf-8'), 'html.parser')
            for card in soup.select('[data-intel-role="card"][data-intel-id]'):
                a = card.select_one('a.source[href]')
                if a:
                    source_by_id[card.get('data-intel-id')] = norm_url(a.get('href'))

        for item in data.get('items', []):
            rid = str(item.get('id', '')).strip()
            if not rid:
                continue
            prior = history.get(rid, [])
            if prior:
                status = str(item.get('status', '')).strip().upper()
                delta = str(item.get('delta', '')).strip()
                if status != 'UPDATE':
                    errors.append(f'{date}: repeated stable ID {rid} must declare status=UPDATE')
                if not delta:
                    errors.append(f'{date}: repeated stable ID {rid} requires non-empty delta')
            history.setdefault(rid, []).append(date)

            source = source_by_id.get(rid) or norm_url(item.get('source_url'))
            if source:
                owner = source_owner.get(source)
                if owner and owner != rid:
                    errors.append(f'{date}: source identity drift: {source} was {owner}, now {rid}')
                else:
                    source_owner[source] = rid

    if errors:
        print('PUBLISHED REGISTRY CONTRACT FAILED')
        print('\n'.join('- ' + e for e in errors))
        sys.exit(1)
    scope = f'DONE history + candidate {candidate}' if candidate else 'DONE history only'
    print(f'PUBLISHED REGISTRY CONTRACT PASS: {len(history)} stable IDs / {len(source_owner)} sources / {scope}')


if __name__ == '__main__':
    main()
