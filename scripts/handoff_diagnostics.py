"""Persist bounded handoff diagnostics without collecting or publishing content."""
import hashlib
import json
import subprocess
from pathlib import Path


def fingerprint(root, date, revision=None):
    paths = [f'data/daily/{date}.json', f'data/candidates/collection-session/{date}.json']
    # Any publication gate can block a release (including historical regression).
    # Bind recovery to the complete contract implementation, not a short allowlist.
    paths += sorted(p.relative_to(root).as_posix() for folder, pattern in
                    [('scripts', '*.py'), ('config', '*.json'), ('.github/workflows', '*.yml')]
                    for p in (root / folder).rglob(pattern))
    h = hashlib.sha256()
    for name in paths:
        path = root / name
        h.update(name.encode())
        if revision:
            proc = subprocess.run(['git', 'show', f'{revision}:{name}'], cwd=root, capture_output=True)
            content = proc.stdout if proc.returncode == 0 else b'missing'
        else:
            content = path.read_bytes() if path.exists() else b'missing'
        h.update(content.replace(b'\r\n', b'\n'))
    return h.hexdigest()


def diagnostic_path(root, date):
    return root / 'data/ops/handoff' / f'{date}.json'


def recovery_error(root, date):
    path = diagnostic_path(root, date)
    if not path.exists():
        return None
    report = json.loads(path.read_text('utf-8'))
    if report['attempts'] >= 3:
        return 'handoff recovery limit reached (initial + two corrected attempts)'
    if report['fingerprint'] == fingerprint(root, date):
        return 'handoff input/contracts unchanged since rejection; correct the recorded blocker first'
    return None


def save_failure(root, date, stage, reason, output, run_id):
    path = diagnostic_path(root, date)
    prior = json.loads(path.read_text('utf-8')) if path.exists() else {}
    data = {'schema_version': 1, 'date': date, 'state': 'HANDOFF_FAILED',
        'stage': stage, 'reason': reason, 'attempts': int(prior.get('attempts', 0)) + 1,
        'fingerprint': fingerprint(root, date), 'run_id': str(run_id),
        'run_url': f'https://github.com/pastfantast-glitch/ai-3d-daily/actions/runs/{run_id}',
        'issues': output.strip().splitlines()[-60:],
        'next_step': 'Correct source-supported content/contracts via PR, then dispatch the existing Collector handoff gate for this date. No new Collector; maximum two corrected retries.'}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return path


def resumed_marker(root, date, marker):
    """Bound explicit recovery of a marker left behind by a failed writer."""
    if (marker.get('date') != date or marker.get('state') != 'COLLECTOR_PERSISTED'
            or marker.get('writer_idle_confirmed_externally') is not True
            or marker.get('generated_by') != 'scripts/create_collector_trigger.py'
            or marker.get('intent') != 'canonical-publish'):
        raise ValueError('existing Collector marker is not resumable')
    attempts = marker.get('resume_attempts', 0)
    if type(attempts) is not int or attempts < 0 or attempts >= 2:
        raise ValueError('existing marker recovery limit reached (two corrected attempts)')
    previous = marker.get('input_fingerprint')
    if not previous:
        # Migration for a legacy marker: derive its actual original input/contracts
        # from Git, never invent a receipt or treat elapsed time as a correction.
        commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--',
            f'data/publish/{date}.collector'], cwd=root, text=True).strip()
        if not commit:
            raise ValueError('existing marker commit is missing')
        previous = fingerprint(root, date, revision=commit)
    current = fingerprint(root, date)
    if previous == current:
        raise ValueError('handoff input/contracts unchanged; correct the blocker before resuming')
    return {**marker, 'resume_attempts': attempts + 1, 'input_fingerprint': current}
