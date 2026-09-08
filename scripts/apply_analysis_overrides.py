#!/usr/bin/env python3
"""Apply explicit, source-reviewed Full Analysis overrides before pre-ready validation."""
from pathlib import Path
import json, re, sys

ROOT=Path(__file__).resolve().parents[1]
DATE_RE=re.compile(r'^20\d{2}-\d{2}-\d{2}$')


def main():
    date=sys.argv[1] if len(sys.argv)>1 else ''
    if not DATE_RE.fullmatch(date):
        raise SystemExit('Usage: apply_analysis_overrides.py YYYY-MM-DD')
    override_path=ROOT/'data'/'analysis-overrides'/f'{date}.json'
    if not override_path.exists():
        print(f'ANALYSIS OVERRIDE: none for {date}')
        return
    data_path=ROOT/'data'/'daily'/f'{date}.json'
    data=json.loads(data_path.read_text('utf-8'))
    override=json.loads(override_path.read_text('utf-8'))
    if override.get('date')!=date:
        raise SystemExit(f'analysis override date mismatch: {override.get("date")!r} != {date}')
    records={str(item.get('id')):item for item in data.get('items') or []}
    patches=override.get('items') or {}
    unknown=sorted(set(patches)-set(records))
    if unknown:
        raise SystemExit(f'analysis override contains unknown ids: {unknown}')
    changed=0
    for rid,blocks in patches.items():
        if not isinstance(blocks,list) or not blocks:
            raise SystemExit(f'analysis override invalid blocks for {rid}')
        if records[rid].get('full_analysis')!=blocks:
            records[rid]['full_analysis']=blocks
            changed+=1
    metadata=data.setdefault('metadata',{})
    metadata['full_analysis_depth_contract']=str(override.get('contract') or 'v4-source-supported-production-depth')
    metadata['full_analysis_style_reference']='2026-09-01'
    metadata['full_analysis_heading_language']='zh-Hant'
    if changed:
        data_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(f'ANALYSIS OVERRIDE: {date} applied={changed} reviewed={len(patches)}')


if __name__=='__main__':
    main()
