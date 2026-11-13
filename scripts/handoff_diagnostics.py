"""Persist bounded handoff diagnostics without collecting or publishing content."""
import hashlib
import json
from pathlib import Path


def fingerprint(root, date):
    paths = [f'data/daily/{date}.json', f'data/candidates/collection-session/{date}.json']
    paths += ['scripts/' + name + '.py' for name in ('reader_quality', 'editorial_review', 'enrich_full_analysis_v3', 'source_quality', 'finalize_collection_handoff')]
    h = hashlib.sha256()
    for name in paths:
        path = root / name
        h.update(name.encode())
        h.update(path.read_bytes().replace(b'\r\n', b'\n') if path.exists() else b'missing')
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
