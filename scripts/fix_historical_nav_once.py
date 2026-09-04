#!/usr/bin/env python3
from pathlib import Path
p=Path('scripts/check_historical_regression.py')
s=p.read_text('utf-8')
old="    for d in selected: validate_archive_snapshot(d,stable_dirs)\n"
new="    # Snapshot content remains strict, but previous/next navigation is intentionally\n    # dynamic as a newly published adjacent archive becomes available. Validate nav\n    # against the complete current archive universe, including the staging/latest day.\n    for d in selected: validate_archive_snapshot(d,all_dirs)\n"
if old not in s:
    raise SystemExit('historical snapshot navigation call not found')
p.write_text(s.replace(old,new),'utf-8')
print('historical snapshot navigation now validates against complete current archive dates')
