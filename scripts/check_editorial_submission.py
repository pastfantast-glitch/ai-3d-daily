"""Validate changed review files against official Actions evidence before merge.
Read-only token; bounded ZIP reads, no extraction or execution of artifact data.
"""
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
import requests
from editorial_review import ROOT, ReviewError, read_review, validate_packet, validate_run
from url_identity import canonicalize_url

REPO = 'pastfantast-glitch/ai-3d-daily'
MAX_BYTES = 32 * 1024 * 1024


def packet_from_zip(blob):
    if len(blob) > MAX_BYTES:
        raise ReviewError('artifact exceeds size limit')
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = [e for e in archive.infolist() if e.filename == 'collector-review.json']
        if len(entries) != 1 or entries[0].file_size > MAX_BYTES:
            raise ReviewError('one bounded collector-review.json required')
        return json.loads(archive.read(entries[0]).decode('utf-8'))


def api(path):
    response = requests.get('https://api.github.com/repos/' + REPO + path,
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/vnd.github+json'}, timeout=60, allow_redirects=False)
    response.raise_for_status()
    return response


def original_packet(data):
    run_id = data['source_run_id']
    run = api(f'/actions/runs/{run_id}').json()
    validate_run(data, run, data['date'])
    matches = []
    for page in range(1, 11):
        rows = api(f'/actions/runs/{run_id}/artifacts?per_page=100&page={page}').json()['artifacts']
        matches.extend(a for a in rows if a['name'] == f"collector-review-{data['date']}-{run_id}")
        if len(rows) < 100:
            break
    if len(matches) != 1 or matches[0]['expired']:
        raise ReviewError('original review artifact missing, ambiguous or expired')
    response = api(f"/actions/artifacts/{matches[0]['id']}/zip")
    if response.status_code == 302:
        url = response.headers.get('Location', '')
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ''
        if not url.startswith('https://') or not (host.endswith('.blob.core.windows.net') or host.endswith('.githubusercontent.com')):
            raise ReviewError('unexpected artifact redirect host')
        # Never forward the GitHub token to the signed artifact host.
        with requests.get(url, timeout=60, stream=True) as download:
            download.raise_for_status()
            chunks, size = [], 0
            for chunk in download.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ReviewError('artifact download exceeds size limit')
                chunks.append(chunk)
        blob = b''.join(chunks)
    elif response.status_code == 200:
        blob = response.content
    else:
        raise ReviewError('artifact download failed')
    return validate_packet(data, packet_from_zip(blob), data['date'])


def readiness_errors(copies, date, root=ROOT):
    published_ids, published_urls = set(), set()
    for receipt in (root / 'data/publish').glob('*.done.json'):
        path = root / 'data/daily' / (receipt.name[:10] + '.json')
        if path.exists():
            for item in json.loads(path.read_text('utf-8')).get('items', []):
                published_ids.add(item['id'])
                published_urls.add(canonicalize_url(item.get('source_url', '')))
    eligible = [c for c in copies if c['id'] not in published_ids and canonicalize_url(c['source_url']) not in published_urls]
    cfg = json.loads((ROOT / 'config/discovery-hybrid.json').read_text('utf-8'))
    floor = cfg['low_volume_release']['fallback_floor']
    errors = []
    if len(eligible) < floor:
        errors.append(f'unpublished reviewed articles={len(eligible)} below fallback floor={floor}; keep PR draft')
    if (root / 'data/publish' / f'{date}.done.json').exists():
        errors.append('edition already has a receipt; do not submit another review')
    if (root / 'data/candidates/collection-session' / f'{date}.json').exists():
        errors.append('persisted session already belongs to handoff')
    return errors


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text('utf-8'))
    if 'pull_request' not in event:
        print('EDITORIAL SUBMISSION: not a PR; no historical artifacts replayed')
        return
    pr = event['pull_request']
    base, head = pr['base']['sha'], pr['head']['sha']
    if not all(re.fullmatch('[0-9a-f]{40}', s) for s in (base, head)):
        raise ReviewError('invalid PR commit identity')
    files = subprocess.check_output(['git', 'diff', '--name-only', base + '...' + head], encoding='utf-8').splitlines()
    reviews = [f for f in files if re.fullmatch(r'data/editorial-reviews/20[0-9]{2}-[0-9]{2}-[0-9]{2}\.json', f)]
    if not reviews:
        print('EDITORIAL SUBMISSION: no changed review files')
        return
    if len(reviews) != 1 or files != reviews:
        raise ReviewError('review PR must contain exactly one edition review file')
    date = Path(reviews[0]).stem
    data = read_review(date)
    if not data:
        raise ReviewError('review file missing/deleted')
    copies = original_packet(data)
    errors = readiness_errors(copies, date)
    if errors:
        raise ReviewError('; '.join(errors))
    print(f'EDITORIAL SUBMISSION PASS: {date} approved={len(copies)}; live source/CI/writer gates remain required at handoff')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, requests.RequestException, zipfile.BadZipFile) as error:
        raise SystemExit('EDITORIAL SUBMISSION FAILED: ' + str(error).split('?')[0]) from None
