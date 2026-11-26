"""Replay preparation and rendering in a disposable copy; never publish or fetch.

The latest receipt supplies a real canonical fixture, including its session and
decision ledger. Only the isolated fixture's DONE is removed to exercise prepare.
No credentials, Git metadata, ignored evidence, or new source content is copied.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    date = json.loads((ROOT / 'data/publish/latest-success.json').read_text('utf-8'))['date']
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    with tempfile.TemporaryDirectory(prefix='ai3d-release-preflight-') as td:
        root = Path(td)
        for name in names:
            if not name:
                continue
            source = ROOT / name
            if source.is_file() and not source.is_symlink():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        # Test fixture only. The actual worktree receipt and canonical are untouched.
        (root / f'data/publish/{date}.done.json').unlink()
        sequence = [('prepare_release_candidate.py', date), ('check_ready_contract.py', date),
            ('render_daily_navigation.py',), ('render_home_archive_links.py',),
            ('render_information_architecture.py', date), ('build_intelligence.py', date),
            ('inject_visual_previews.py', date), ('render_topic_pages.py', date),
            ('apply_cache_bust.py', date), ('check_intelligence_contract.py',),
            ('check_visual_contract.py', date), ('check_home_contract.py',),
            ('check_daily_contract.py',), ('check_information_architecture.py', date),
            ('check_pages_tier_contract.py',), ('check_historical_regression.py', '--days', '4')]
        for script, *args in sequence:
            print('ISOLATED RELEASE:', script, *args, flush=True)
            subprocess.run([sys.executable, str(root / 'scripts' / script), *args], cwd=root, check=True)
    print(f'ISOLATED RELEASE PASS: {date}; prepare/render/history gates, existing visual cache; no Discovery, network extraction, deployment or DONE written to repository.')


if __name__ == '__main__':
    main()
