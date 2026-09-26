#!/usr/bin/env python3
"""Fail closed when Collector/prepare/publish executable sources are not watched by source QA."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / '.github' / 'workflows' / 'intelligence-build.yml'
AUTONOMOUS = ROOT / '.github' / 'workflows' / 'daily-collector.yml'
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


def workflow_python_scripts(source: str) -> set[str]:
    return {
        f"scripts/{name}"
        for name in re.findall(r'python\s+scripts/([A-Za-z0-9_.-]+\.py)', source)
    }


def main() -> int:
    writer = read(MAIN)
    autonomous = read(AUTONOMOUS)
    daily = read(DAILY)
    prepare = read(PREPARE)
    finalizer = read(FINALIZER)

    watched = set(re.findall(r"^\s*-\s*'([^']+)'\s*$", daily, re.M))
    required = {
        '.github/workflows/intelligence-build.yml',
        '.github/workflows/daily-collector.yml',
        '.github/workflows/daily-contract.yml',
        'config/collector-runtime.json',
        'scripts/run_daily_collector.py',
        'scripts/check_collector_runtime_contract.py',
        'scripts/prepare_release_candidate.py',
        'scripts/finalize_collection_handoff.py',
        SELF,
    }

    required.update(workflow_python_scripts(writer))
    required.update(workflow_python_scripts(autonomous))
    required.update(invoked_run_scripts(prepare))
    required.update(invoked_run_scripts(finalizer))

    if (
        'pip install -r requirements-pipeline.txt' in writer
        or 'pip install -r requirements-pipeline.txt' in autonomous
        or 'pip install -r requirements-pipeline.txt' in daily
    ):
        required.add('requirements-pipeline.txt')

    missing_files = sorted(path for path in required if not (ROOT / path).exists())
    missing_watches = sorted(required - watched)
    errors = []
    if missing_files:
        errors.append('referenced pipeline source missing from repository: ' + ', '.join(missing_files))
    if missing_watches:
        errors.append('daily-contract.yml path filter misses pipeline source: ' + ', '.join(missing_watches))
    for command in (
        'python scripts/check_source_qa_coverage.py',
        'python scripts/check_collector_runtime_contract.py',
    ):
        if command not in daily:
            errors.append(f'daily-contract.yml must execute {command.split("python ",1)[1]}')

    if errors:
        print('SOURCE QA COVERAGE FAILED')
        for error in errors:
            print('-', error)
        return 1

    print(
        'SOURCE QA COVERAGE PASS: source QA watches autonomous Collector, Collector finalizer, '
        f'pre-ready and canonical-writer executable sources ({len(required)} required paths)'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
