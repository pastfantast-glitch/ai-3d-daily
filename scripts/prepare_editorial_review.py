"""Turn a Collector evidence packet into unapproved human editorial drafts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def review_drafts(packet):
    drafts = {}
    for article in packet.get('articles', []):
        evidence = article.get('evidence') or {}
        drafts[article['source_url']] = {
            'source_url': article['source_url'],
            'source_published_at': article.get('source_published_at'),
            'source_reviewed': False,
            'reviewed_on': None,
            'source_evidence_sha256': evidence.get('sha256'),
            'evidence_refs': [],
            'title': '', 'summary': '',
            'full_analysis': [{'label': label, 'text': ''} for label in (
                '技術／流程變更', 'Production 影響', '導入測試與限制')],
        }
    return {'edition_date': packet.get('date'), 'drafts': drafts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; refusing to overwrite human edits')
    packet = json.loads(args.packet.read_text('utf-8'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(review_drafts(packet), ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(f'Prepared {len(packet.get("articles", []))} unapproved drafts: {args.output}')


if __name__ == '__main__':
    main()
