"""Read-only settings admission: bounded samples, no canonical writes or approvals."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import requests
from collection_settings import validate_settings, effective_hybrid, within_topic_window
from discovery_hybrid import load_hybrid_config, registered_source_probe_plan
from run_daily_collector import fetch, page_metadata, extract_links, extract_feed_article_links

ROOT = Path(__file__).resolve().parents[1]

def changed_sources(active, proposed):
    before = {s['id']: s for s in active['sources']}
    topics = {t['id'] for t in proposed['topics'] if t['enabled']}
    old_topics = {t['id'] for t in active['topics'] if t['enabled']}
    return [s for s in proposed['sources'] if s['enabled'] and topics.intersection(s['topic_ids'])
            and (s['id'] not in before or not before[s['id']]['enabled']
                 or not old_topics.intersection(before[s['id']]['topic_ids'])
                 or any(s[k] != before[s['id']][k] for k in ('base_url', 'endpoints')))]

def preview(source, date, fetcher=fetch):
    """Use the actual Collector metadata/body extractor; do not return body text."""
    session = requests.Session(); session.managed_sources = True
    domain = urlsplit(source['base_url']).hostname.removeprefix('www.')
    samples, errors, seen, links = [], [], set(), []
    def inspect(result):
        meta = page_metadata(result)
        if not meta:return
        ev = meta['article_evidence']
        samples.append({'url':meta['url'], 'source_date':meta['published'], 'body_characters':ev['char_count'],
                        'readable':ev['status']=='extracted' and not ev['truncated'],
                        'date_eligible':within_topic_window(meta['published'], date, 12)})
    for url in source['endpoints']:
        result = fetcher(session, url, 8, allow_feed=True)
        if result.get('status') != 200:
            errors.append(f"{url}: HTTP {result.get('status') or 'unavailable'}");continue
        inspect(result); text=result.get('html',''); final=result.get('final_url') or url
        links += extract_feed_article_links(text,final,domain,5) or extract_links(text,final,domain,5)
    for url,_ in links:
        if url in seen or len(seen)>=3:continue
        seen.add(url)
        result=fetcher(session,url,8)
        if result.get('status')==200:inspect(result)
        else:errors.append(f"{url}: HTTP {result.get('status') or 'unavailable'}")
    ok=any(s['readable'] and s['date_eligible'] for s in samples)
    return {'source_id':source['id'],'passed':ok,'samples':samples,'errors':errors,
            'note':'Bounded source preview only; no editorial approval or formal collection.'}

def validate_candidate(active, pending):
    validate_settings(active);validate_settings(pending['settings'])
    if set(pending)!={'schema_version','base_sha','settings'} or pending['schema_version']!=1:
        raise ValueError('invalid pending schema')
    cfg=effective_hybrid(load_hybrid_config(),pending['settings'])
    registered_source_probe_plan('2026-11-25',cfg)

def main():
    path=ROOT/'config/collection-pending.json'
    if not path.exists():print('SETTINGS VALIDATION: no pending version');return
    active=json.loads((ROOT/'config/collection-admin.json').read_text('utf-8'))
    pending=json.loads(path.read_text('utf-8'));validate_candidate(active,pending)
    if active==pending['settings']:print('SETTINGS VALIDATION: already active');return
    blob=subprocess.check_output(['git','hash-object','config/collection-admin.json'],cwd=ROOT,text=True).strip()
    if blob!=pending['base_sha']:raise SystemExit('SETTINGS VALIDATION FAILED: active version changed; resubmit')
    date=datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()
    failed=[]
    for source in changed_sources(active,pending['settings']):
        result=preview(source,date);print(json.dumps(result,ensure_ascii=False))
        if not result['passed']:failed.append(source['id'])
    if failed:raise SystemExit('SETTINGS VALIDATION FAILED: no readable, dated article within 12 months: '+', '.join(failed)+'. Correct the endpoint or save source paused.')
    print('SETTINGS VALIDATION PASS: proposed settings; active version unchanged')

if __name__=='__main__':main()
