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


def superseded_by(root, date):
    """Old pending sessions stay auditable but cannot replace a newer edition."""
    dates = [p.stem for p in (Path(root) / 'data/candidates/collection-session').glob('20??-??-??.json')
             if p.stem > date and (Path(root) / f'data/daily/{p.stem}.json').is_file()]
    dates += [p.name[:10] for p in (Path(root) / 'data/publish').glob('20??-??-??.done.json')
              if p.name[:10] > date]
    return max(dates, default='')


def pending_session(root, date, policy=False):
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date):
        return False
    if not policy and superseded_by(root, date):
        return False
    pub = Path(root) / 'data/publish'
    return ((Path(root) / f'data/candidates/collection-session/{date}.json').is_file()
            and (policy or not (pub / f'{date}.done.json').exists())
            and not any((pub / f'{date}.{suffix}').exists() for suffix in ('collector', 'request'))
            and (policy or not (pub / f'{date}.ready').exists()))


def corrected_pending_session(root):
    """Select one newest failed handoff only when its inputs/contracts changed."""
    from handoff_diagnostics import resumed_marker, recovery_error, diagnostic_path
    root = Path(root)
    for path in sorted((root / 'data/candidates/collection-session').glob('20??-??-??.json'), reverse=True):
        date = path.stem
        if superseded_by(root, date):
            continue
        pub = root / 'data/publish'
        if any((pub / f'{date}.{suffix}').exists() for suffix in ('done.json', 'request', 'ready')):
            continue
        if not (root / f'data/daily/{date}.json').exists():
            continue
        marker = pub / f'{date}.collector'
        try:
            if marker.exists():
                resumed_marker(root, date, json.loads(marker.read_text('utf-8')))
            elif not diagnostic_path(root, date).exists():
                continue
            if recovery_error(root, date):
                continue
        except (ValueError, OSError):
            continue
        return date
    return ''


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
