"""Bind an automatic handoff to its upstream run, never an unrelated old session."""
from pathlib import Path
import hashlib
import json
import re
import subprocess


def collector_target(run, receipt):
    """Use the upstream preflight's resolved date, including explicit dispatches."""
    if (run.get('head_branch') != 'main' or run.get('status') != 'completed'
            or run.get('conclusion') != 'success'
            or receipt.get('schema_version') != 1
            or receipt.get('source_run_id') != run.get('id')
            or receipt.get('head_sha') != run.get('head_sha')
            or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', str(receipt.get('date', '')))
            or type(receipt.get('policy_republish')) is not bool):
        raise ValueError('Collector target provenance invalid')
    policy = receipt['policy_republish']
    if policy and (run.get('event') != 'push' or '[policy-recollect]' not in
                   str((run.get('head_commit') or {}).get('message', ''))):
        raise ValueError('policy republish requires explicit upstream intent')
    return receipt['date'], policy


def pending_session(root, date, policy=False):
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date):
        return False
    pub = Path(root) / 'data/publish'
    return ((Path(root) / f'data/candidates/collection-session/{date}.json').is_file()
            and (policy or not (pub / f'{date}.done.json').exists())
            and not any((pub / f'{date}.{suffix}').exists() for suffix in ('collector', 'request'))
            and (policy or not (pub / f'{date}.ready').exists()))


def route_receipt(root, date, commit, run_id):
    marker = Path(root) / f'data/publish/{date}.collector'
    return {'schema_version': 1, 'date': date, 'handoff_run_id': int(run_id),
            'marker_commit': commit,
            'marker_sha256': hashlib.sha256(marker.read_bytes()).hexdigest()}


def verify_route(root, receipt, run_id):
    date = str(receipt.get('date', ''))
    if (receipt.get('schema_version') != 1 or receipt.get('handoff_run_id') != int(run_id)
            or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date)
            or not re.fullmatch(r'[0-9a-f]{40}', str(receipt.get('marker_commit', '')))):
        raise ValueError('handoff route provenance invalid')
    marker = Path(root) / f'data/publish/{date}.collector'
    if hashlib.sha256(marker.read_bytes()).hexdigest() != receipt.get('marker_sha256'):
        raise ValueError('handoff marker changed after upstream run')
    data = json.loads(marker.read_text('utf-8'))
    if (data.get('date') != date or data.get('state') != 'COLLECTOR_PERSISTED'
            or data.get('writer_idle_confirmed_externally') is not True):
        raise ValueError('handoff marker invalid')
    commit = receipt['marker_commit']
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=root, check=True)
    original = subprocess.check_output(['git', 'show', f'{commit}:data/publish/{date}.collector'], cwd=root)
    if hashlib.sha256(original).hexdigest() != receipt['marker_sha256']:
        raise ValueError('handoff marker commit does not match receipt')
    return date
