"""Local, resumable editorial notebook. Never collects, approves automatically or publishes.

Use one persistent workspace/.editorial-work directory across Git worktrees.
Evidence and unfinished copy stay local; export contains approved records only.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from editorial_review import ReviewError, validate_packet, validate_run


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def atomic_write(path, value):
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def envelope(packet, purpose='reserve'):
    return {'schema_version': 1, 'date': packet['date'],
            'reviewer': 'chatgpt-scheduled-task', 'purpose': purpose,
            'source_run_id': packet['source_run_id'],
            'source_head_sha': packet['source_head_sha'], 'items': {}}


def run_identity(run):
    return {key: run[key] for key in ('id', 'head_sha', 'head_branch', 'created_at',
                                     'name', 'status', 'conclusion')}


def initialize(workdir, packet, run):
    """Called only after official artifact expiry/identity checks by the reviewer."""
    date = packet.get('date', '')
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', date):
        raise ReviewError('invalid edition date')
    validate_run(envelope(packet), run, date)
    articles = packet.get('articles', [])
    ids = [a['id'] for a in articles]
    if len(ids) != len(set(ids)) or not ids or not all(isinstance(x, str) and x for x in ids):
        raise ReviewError('missing or duplicate article IDs')
    session = Path(workdir) / f"{date}-{run['id']}"
    if session.exists():
        state, old_packet, old_run = load(session)
        if digest(old_packet) != digest(packet) or run_identity(old_run) != run_identity(run):
            raise ReviewError('existing session has different evidence/run; refusing overwrite')
        return session
    session.mkdir(parents=True)
    atomic_write(session / 'packet.json', packet)
    atomic_write(session / 'run.json', run)
    atomic_write(session / 'progress.json', {
        **envelope(packet), 'revision': 0, 'packet_sha256': digest(packet),
        'run_sha256': digest(run), 'blocked_reason': '', 'submission_url': None,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'items': {cid: {'state': 'pending', 'rounds': 0} for cid in ids}})
    return session


def load(session):
    session = Path(session)
    state, packet, run = (read(session / p) for p in ('progress.json', 'packet.json', 'run.json'))
    if (digest(packet) != state['packet_sha256'] or digest(run) != state['run_sha256']
            or any(state[k] != packet[k] for k in ('date', 'source_run_id', 'source_head_sha'))
            or set(state['items']) != {a['id'] for a in packet['articles']}):
        raise ReviewError('checkpoint provenance/evidence changed; stop and fetch official artifact')
    validate_run(envelope(packet), run, state['date'])
    return state, packet, run


def summary(state):
    counts = {key: sum(x['state'] == key for x in state['items'].values())
              for key in ('pending', 'draft', 'approved', 'excluded')}
    next_id = next((cid for status in ('draft', 'pending') for cid, row in state['items'].items()
                    if row['state'] == status), None)
    phase = ('BLOCKED' if state['blocked_reason'] else
             'SUBMITTED_UNVERIFIED' if state['submission_url'] else
             'REVIEW_INCOMPLETE' if counts['pending'] + counts['draft'] else
             'REVIEWED_UNSUBMITTED' if counts['approved'] else 'NO_APPROVED_CONTENT')
    return {'date': state['date'], 'source_run_id': state['source_run_id'],
            'revision': state['revision'], 'state': phase, 'counts': counts,
            'next_article_id': next_id, 'blocker': state['blocked_reason'],
            'submission_url': state['submission_url'], 'publication_verified': False,
            'next_step': ('Inspect existing PR and live GitHub state' if state['submission_url'] else
                          'Resolve blocker, then resume saved article' if state['blocked_reason'] else
                          'Re-read source and finish draft second pass' if counts['draft'] else
                          'Read next source; save one article at a time' if counts['pending'] else
                          'Validate/export approved subset and submit existing/new PR' if counts['approved'] else
                          'Report exclusions; do not claim successful review/publication')}


def copy_fields(record):
    return {k: v for k, v in record.items() if k not in ('review', 'reviewed_on')}


def check_record_fields(record):
    allowed = {'source_url', 'source_published_at', 'source_evidence_sha256', 'reviewed_on',
               'title', 'summary', 'full_analysis', 'evidence_refs', 'analysis_level', 'content_kind', 'review'}
    if not isinstance(record, dict) or set(record) - allowed:
        raise ReviewError('only reader-copy/review fields allowed; no evidence body/HTML/credentials')
    if not isinstance(record.get('full_analysis'), list):
        raise ReviewError('analysis blocks required')
    for block in record['full_analysis']:
        if not isinstance(block, dict) or set(block) - {'angle', 'label', 'text', 'evidence_refs'}:
            raise ReviewError('unexpected analysis field')
    decision = record.get('review', {})
    if not isinstance(decision, dict) or set(decision) - {'approved', 'method', 'checks', 'issues', 'unsupported_claims', 'evidence_refs'}:
        raise ReviewError('unexpected review field')


def change(session, revision, action, cid=None, record=None, reason='', url=None):
    """Exclusive lock + revision guard prevents silent concurrent overwrites."""
    session = Path(session)
    lock = session / '.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ReviewError('checkpoint locked; verify other task has stopped, never steal its lock') from None
    try:
        os.close(fd)
        state, packet, run = load(session)
        if state['revision'] != revision:
            raise ReviewError('stale checkpoint revision; reload before editing')
        if action in ('draft', 'approve', 'exclude'):
            if state['submission_url']:
                raise ReviewError('PR already recorded; reconcile existing PR before further edits')
            row = state['items'][cid]
            if row['state'] in ('approved', 'excluded'):
                raise ReviewError('article already finalized; do not silently restart review')
            if row['state'] == 'pending' and sum(x['state'] != 'pending' for x in state['items'].values()) >= 40:
                raise ReviewError('40 article session limit reached; report remaining work')
            if action == 'draft':
                check_record_fields(record)
                if record.get('review', {}).get('approved') is True:
                    raise ReviewError('first-pass draft must not be approved')
                if row['rounds'] >= 2:
                    raise ReviewError('two revision limit reached; exclude with reason')
                row.update(state='draft', rounds=row['rounds'] + 1, record=copy.deepcopy(record))
            elif action == 'approve':
                check_record_fields(record)
                if row['state'] != 'draft' or copy_fields(record) != copy_fields(row['record']):
                    raise ReviewError('save exact draft before second-pass approval')
                data = envelope(packet)
                data['items'] = {cid: record}
                validate_packet(data, packet, state['date'])
                row.update(state='approved', record=copy.deepcopy(record))
            else:
                if not reason.strip():
                    raise ReviewError('exclusion reason required')
                row.update(state='excluded', reason=reason.strip())
                row.pop('record', None)
        elif action == 'block':
            if not reason.strip():
                raise ReviewError('specific blocker and next action required')
            state['blocked_reason'] = reason.strip()
        elif action == 'resume':
            state['blocked_reason'] = ''
        elif action == 'submission':
            if not any(x['state'] == 'approved' for x in state['items'].values()):
                raise ReviewError('cannot record submission with zero approved articles')
            if not re.fullmatch(r'https://github\.com/pastfantast-glitch/ai-3d-daily/pull/[1-9][0-9]*', url or ''):
                raise ReviewError('repository PR URL required')
            if state['submission_url'] and state['submission_url'] != url:
                raise ReviewError('resume the same PR; duplicate submission refused')
            state['submission_url'] = url
        else:
            raise ReviewError('unknown checkpoint action')
        state['revision'] += 1
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
        atomic_write(session / 'progress.json', state)
        return summary(state)
    finally:
        lock.unlink()


def export_review(session, purpose):
    state, packet, run = load(session)
    if state['blocked_reason']:
        raise ReviewError('resolve recorded blocker before exporting')
    data = envelope(packet, purpose)
    data['items'] = {cid: row['record'] for cid, row in state['items'].items() if row['state'] == 'approved'}
    if not 0 < len(data['items']) <= 40:
        raise ReviewError('no approved subset to export')
    for record in data['items'].values():
        check_record_fields(record)
    validate_run(data, run, state['date'])
    validate_packet(data, packet, state['date'])
    # Publication floor, published registry, original artifact expiry, PR checks and
    # live writer/main state must still be checked by the existing submission gate.
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--workdir', type=Path, required=True)
    init.add_argument('--packet', type=Path, required=True)
    init.add_argument('--run-json', type=Path, required=True)
    listing = sub.add_parser('list')
    listing.add_argument('--workdir', type=Path, required=True)
    status = sub.add_parser('status')
    status.add_argument('session', type=Path)
    for action in ('draft', 'approve', 'exclude', 'block', 'resume', 'submission'):
        cmd = sub.add_parser(action)
        cmd.add_argument('session', type=Path)
        cmd.add_argument('--revision', type=int, required=True)
        if action in ('draft', 'approve', 'exclude'):
            cmd.add_argument('--id', required=True)
        if action in ('draft', 'approve'):
            cmd.add_argument('--record', type=Path, required=True)
        if action in ('exclude', 'block'):
            cmd.add_argument('--reason', required=True)
        if action == 'submission':
            cmd.add_argument('--url', required=True)
    export = sub.add_parser('export')
    export.add_argument('session', type=Path)
    export.add_argument('--purpose', choices=('release', 'reserve'), required=True)
    args = parser.parse_args()
    try:
        if args.command == 'list':
            result = []
            for session in sorted(args.workdir.glob('20*-*')):
                if not session.is_dir():
                    continue
                try:
                    result.append({'session': str(session), **summary(load(session)[0])})
                except (OSError, ValueError, KeyError, TypeError):
                    result.append({'session': str(session), 'state': 'CHECKPOINT_UNREADABLE',
                                   'next_step': 'Reconcile official artifact and existing PR; never overwrite checkpoint'})
        elif args.command == 'init':
            session = initialize(args.workdir, read(args.packet), read(args.run_json))
            result = {'session': str(session), **summary(load(session)[0])}
        elif args.command == 'status':
            result = summary(load(args.session)[0])
        elif args.command == 'export':
            result = export_review(args.session, args.purpose)
        else:
            result = change(args.session, args.revision, args.command,
                            cid=getattr(args, 'id', None),
                            record=read(args.record) if hasattr(args, 'record') else None,
                            reason=getattr(args, 'reason', ''), url=getattr(args, 'url', None))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f'EDITORIAL CHECKPOINT BLOCKED: {error}') from None


if __name__ == '__main__':
    main()
