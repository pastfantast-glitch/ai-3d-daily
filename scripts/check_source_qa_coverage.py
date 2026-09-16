#!/usr/bin/env python3
"""Fail closed when collector/prepare/publish executable sources are not watched by source QA.

The daily source-contract workflow is the pre-publication safety net for policy and
pipeline changes. This guard derives scripts actually executed by the Collector
finalizer, canonical writer and prepare stage, then verifies every one is included
in the workflow path filter. Adding a new release script without adding QA coverage
must therefore fail on the same commit that changes pipeline topology.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / '.github' / 'workflows' / 'intelligence-build.yml'
DAILY = ROOT / '.github' / 'workflows' / 'daily-contract.yml'
PREPARE = ROOT / 'scripts' / 'prepare_release_candidate.py'
FINALIZER = ROOT / 'scripts' / 'finalize_collection_handoff.py'
SELF = 'scripts/check_source_qa_coverage.py'


def read(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f'SOURCE QA COVERAGE FAIL: missing {path.relative_to(ROOT)}')
    return path.read_text('utf-8')


def invoked_run_scripts(source: str) -> set[str]:
    names = set()
    for match in re.finditer(r"\brun\(\s*(['\"])([^'\"]+\.py)\1", source):
        names.add(f'scripts/{match.group(2)}')
    return names


def main() -> int:
    writer = read(MAIN)
    daily = read(DAILY)
    prepare = read(PREPARE)
    finalizer = read(FINALIZER)

    watched = set(re.findall(r"^\s*-\s*'([^']+)'\s*$", daily, re.M))
    required = {
        '.github/workflows/intelligence-build.yml',
        '.github/workflows/daily-contract.yml',
        'scripts/prepare_release_candidate.py',
        'scripts/finalize_collection_handoff.py',
        SELF,
    }

    required.update(
        f'scripts/{name}'
        for name in re.findall(r'python\s+scripts/([A-Za-z0-9_.-]+\.py)', writer)
    )
    required.update(invoked_run_scripts(prepare))
    required.update(invoked_run_scripts(finalizer))

    if 'pip install -r requirements-pipeline.txt' in writer or 'pip install -r requirements-pipeline.txt' in daily:
        required.add('requirements-pipeline.txt')

    missing_files = sorted(path for path in required if not (ROOT / path).exists())
    missing_watches = sorted(required - watched)
    errors = []
    if missing_files:
        errors.append('referenced pipeline source missing from repository: ' + ', '.join(missing_files))
    if missing_watches:
        errors.append('daily-contract.yml path filter misses pipeline source: ' + ', '.join(missing_watches))
    if 'python scripts/check_source_qa_coverage.py' not in daily:
        errors.append('daily-contract.yml must execute check_source_qa_coverage.py')

    if errors:
        print('SOURCE QA COVERAGE FAILED')
        for error in errors:
            print('-', error)
        return 1

    print(
        'SOURCE QA COVERAGE PASS: daily source QA watches all Collector finalizer, '
        f'pre-ready and canonical-writer executable sources ({len(required)} required paths)'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
