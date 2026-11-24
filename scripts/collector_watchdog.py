#!/usr/bin/env python3
"""Repository-scoped Watchdog. Read-only unless --apply; one CAS write, no retries."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

REPO = 'pastfantast-glitch/ai-3d-daily'
PREFIX = '/repos/' + REPO
TRIGGER = 'data/ops/collector-watchdog.json'
ACTIVE = ('queued', 'in_progress', 'waiting', 'pending', 'requested')
WRITERS = ('Autonomous daily Collector', 'Canonical intelligence publish', 'Collector handoff gate')
TAIPEI = timezone(timedelta(hours=8))
MUTATION = '''mutation($input:CreateCommitOnBranchInput!){
 createCommitOnBranch(input:$input){commit{oid url}}}'''


def credential():
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    proc = subprocess.run(['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
                          input='protocol=https\nhost=github.com\n\n', capture_output=True,
                          text=True, env=env)
    fields = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
    if proc.returncode or not fields.get('password'):
        raise RuntimeError('Existing GitHub credential unavailable')
    return fields['password']


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, path, payload=None):
        req = urllib.request.Request('https://api.github.com' + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + self.token,
                     'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
                     'User-Agent': 'ai3d-collector-watchdog'})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # Do not expose request headers, credentials, or arbitrary response bodies.
            raise RuntimeError(f'GitHub HTTP {error.code}') from None

    def get(self, path):
        if not (path == PREFIX or path.startswith(PREFIX + '/')):
            raise ValueError('Repository scope required')
        return self.request(path)

    def main(self):
        return self.get(PREFIX + '/git/ref/heads/main')['object']['sha']

    def file(self, path, sha):
        try:
            value = self.get(PREFIX + '/contents/' + path + '?ref=' + sha)
        except RuntimeError as error:
            if str(error) == 'GitHub HTTP 404':
                return None
            raise
        return json.loads(base64.b64decode(value['content']))

    def runs(self, query):
        results = []
        for page in range(1, 12):
            data = self.get(PREFIX + '/actions/runs?' + urllib.parse.urlencode(
                dict(query, per_page=100, page=page)))
            if data['total_count'] > 1000:
                raise RuntimeError('Actions search exceeds API coverage limit')
            results.extend(data['workflow_runs'])
            if len(results) >= data['total_count']:
                return results
            if not data['workflow_runs']:
                raise RuntimeError('Incomplete Actions pagination')
        raise RuntimeError('Incomplete Actions pagination')

    def commit_trigger(self, expected_sha, date, reason):
        # Only this fixed mutation may use /graphql; never pass it to a REST-only wrapper.
        value = trigger_input(expected_sha, date, reason)
        response = self.request('/graphql', {'query': MUTATION, 'variables': {'input': value}})
        if response.get('errors'):
            raise RuntimeError('GitHub rejected Watchdog compare-and-swap mutation')
        return response['data']['createCommitOnBranch']['commit']


def trigger_input(sha, date, reason):
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid main SHA')
    if datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d') != date:
        raise ValueError('Invalid date')
    payload = {'schema_version': 1, 'date': date, 'state': 'WATCHDOG_TRIGGER',
               'trigger': 'chatgpt-0740-watchdog', 'reason': reason,
               'writer_idle_confirmed_externally': True}
    return {'branch': {'repositoryNameWithOwner': REPO, 'branchName': 'main'},
            'expectedHeadOid': sha,
            'message': {'headline': f'Collector watchdog {date} [collector-watchdog]'},
            'fileChanges': {'additions': [{'path': TRIGGER, 'contents': base64.b64encode(
                (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode()).decode()}]}}


def inspect_state(client, date):
    sha = client.main()
    midnight = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=TAIPEI)
    start = midnight.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    end = (midnight + timedelta(days=1, seconds=-1)).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    for path, state in [(f'data/publish/{date}.done.json', 'RECEIPT_PRESENT'),
                        (f'data/candidates/collection-session/{date}.json', 'AWAITING_HANDOFF'),
                        (f'data/daily/{date}.json', 'CANONICAL_PRESENT')]:
        if client.file(path, sha) is not None:
            return {'state': state, 'main': sha, 'path': path}
    for status in ACTIVE:
        active = [r for r in client.runs({'status': status}) if r['name'] in WRITERS]
        if active:
            return {'state': 'ACTIVE_PIPELINE', 'main': sha,
                    'run_urls': [r['html_url'] for r in active]}
    today = client.runs({'branch': 'main', 'created': start + '..' + end})
    genuine = [r for r in today if r['name'] == WRITERS[0] and r.get('conclusion') != 'skipped']
    if genuine:
        return {'state': 'EXISTING_COLLECTOR', 'main': sha,
                'run_urls': [r['html_url'] for r in genuine]}
    marker = client.file(TRIGGER, sha)
    if marker and marker.get('date') == date:
        return {'state': 'WATCHDOG_ALREADY_REQUESTED', 'main': sha}
    if client.main() != sha:
        raise RuntimeError('Current main changed during Watchdog preflight')
    return {'state': 'NOT_STARTED', 'main': sha, 'window': start + '..' + end,
            'observed_at': datetime.now(timezone.utc).isoformat()}


def execute(client, date, apply=False):
    before = inspect_state(client, date)
    if not apply or before['state'] != 'NOT_STARTED':
        return before
    confirmed = inspect_state(client, date)
    if confirmed['state'] != 'NOT_STARTED' or confirmed['main'] != before['main']:
        return dict(confirmed, write_skipped='Preflight changed; no mutation')
    reason = (f"At {confirmed['observed_at']}, main {confirmed['main']} has no {date} "
              f"DONE, canonical dataset, persisted session or genuine main Collector run in "
              f"{confirmed['window']}; no queued/in_progress/waiting/pending/requested "
              'Collector, handoff or Publisher. Verified twice before compare-and-swap.')
    try:
        commit = client.commit_trigger(confirmed['main'], date, reason)
    except Exception as error:
        try:
            after = client.main()
        except Exception:
            after = 'UNKNOWN (main verification failed)'
        raise RuntimeError(f'{error}; main after failed write: {after}; no retry') from None
    return {'state': 'WATCHDOG_TRIGGERED', 'date': date, 'commit': commit,
            'next_step': 'Confirm existing Collector run starts; trigger is not publication success.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default=datetime.now(TAIPEI).date().isoformat())
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.date != datetime.now(TAIPEI).date().isoformat():
        parser.error('Watchdog only acts on the current Asia/Taipei date')
    print(json.dumps(execute(GitHub(credential()), args.date, args.apply), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
