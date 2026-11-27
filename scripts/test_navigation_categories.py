import copy
import json
from pathlib import Path
import unittest
from collection_settings import validate_settings, topic_matches, effective_hybrid
from navigation_categories import BUILTINS

ROOT=Path(__file__).resolve().parents[1]
def configured():
    s=json.loads((ROOT/'config/collection-admin.json').read_text('utf-8'))
    s['navigation']=[dict(id=id,name=id,description='',enabled=True,visible=True,hide_empty=False,order=i,include_terms=[],exclude_terms=[],source_ids=[x['id'] for x in s['sources']],manual_urls=[],excluded_urls=[]) for i,id in enumerate(sorted(BUILTINS))]
    return s

class NavigationTests(unittest.TestCase):
    def test_legacy_and_navigation_snapshot_validate(self):
        s=configured();validate_settings(s);del s['navigation'];validate_settings(s)
    def test_connections_and_terms_never_bypass_relevance_or_source_age(self):
        s=configured();source=s['sources'][0];meta={'title':'Houdini Vellum cloth','published':'2026-11-26'}
        self.assertEqual(topic_matches(meta,source,s,True,'2026-11-27'),['ai-3d'])
        self.assertEqual(topic_matches(meta,source,s,False,'2026-11-27'),[])
        for c in s['navigation']:c['source_ids']=[]
        c=s['navigation'][0];c['source_ids']=[source['id']];c['include_terms']=['Vellum'];c['exclude_terms']=['sponsored']
        self.assertEqual(topic_matches(meta,source,s,True,'2026-11-27'),['ai-3d'])
        for change in [{'title':'unrelated'},{'title':'sponsored Vellum'},{'published':'2024-01-01'}]:
            self.assertEqual(topic_matches({**meta,**change},source,s,True,'2026-11-27'),[])
        c['source_ids']=[]
        self.assertEqual(topic_matches(meta,source,s,True,'2026-11-27'),[])
    def test_hybrid_does_not_fetch_unconnected_source(self):
        s=configured();sid=s['sources'][0]['id']
        for c in s['navigation']:c['source_ids'].remove(sid)
        base=json.loads((ROOT/'config/discovery-hybrid.json').read_text('utf-8'))
        effective=effective_hybrid(base,s)
        self.assertFalse(next(x for x in effective['discovery_source_pool']['sources'] if x['id']==sid)['enabled'])
    def test_strict_shape_and_supply(self):
        for mutate in [lambda s:s['navigation'][0].update(id='top5'),lambda s:s['navigation'][0].update(unknown=True),lambda s:[c.update(enabled=False) for c in s['navigation']],lambda s:s['navigation'][0].update(source_ids=['missing'])]:
            s=configured();mutate(s)
            with self.assertRaises(ValueError):validate_settings(s)
    def test_handoff_checks_persisted_navigation_membership(self):
        from topic_contract import topic_errors
        data=json.loads((ROOT/'data/daily/2026-11-27.json').read_text('utf-8'))
        data['metadata']['collection_settings']=configured()
        for item in data['items']:item['navigation_category_ids']=[item['category']]
        self.assertEqual(topic_errors(data),[])
        data['items'][0]['navigation_category_ids']=['not-configured']
        self.assertTrue(any('navigation category binding' in e for e in topic_errors(data)))

if __name__=='__main__':unittest.main()
