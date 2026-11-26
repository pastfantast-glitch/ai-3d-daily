import copy
import json
from pathlib import Path
import unittest
from check_collection_pending import preview, changed_sources, validate_candidate

class Tests(unittest.TestCase):
    def setUp(self):
        self.active=json.loads((Path(__file__).parent/'fixtures/collection-admin.json').read_text('utf-8'))
    def test_only_new_enabled_changed_endpoints_need_network_checks(self):
        proposed=copy.deepcopy(self.active)
        proposed['sources'][0]['name']='Renamed'
        self.assertEqual(changed_sources(self.active,proposed),[])
        proposed['sources'][0]['endpoints']=['https://80.lv/new']
        self.assertEqual(len(changed_sources(self.active,proposed)),1)
        proposed['sources'][0]['enabled']=False
        self.assertEqual(changed_sources(self.active,proposed),[])
    def test_production_config_and_added_source_preserve_valid_probe_plan(self):
        active=json.loads((Path(__file__).parents[1]/'config/collection-admin.json').read_text('utf-8'))
        proposed=copy.deepcopy(active)
        proposed['sources'].append({'id':'fixture-new','name':'New','base_url':'https://example.com/','endpoints':['https://example.com/rss'],'enabled':True,'topic_ids':['ai-3d']})
        validate_candidate(active,{'schema_version':1,'base_sha':'a'*40,'settings':proposed})
        self.assertEqual([x['id'] for x in changed_sources(active,proposed)],['fixture-new'])
    def test_rss_article_uses_real_extractor_and_date_window(self):
        source={'id':'example','base_url':'https://example.com','endpoints':['https://example.com/rss']}
        for date,passed in [('2026-11-24',True),('2024-01-01',False),('',False)]:
            def fetch(session,url,timeout,**kw):
                html='<rss><channel><item><link>https://example.com/articles/item</link><title>Blender tutorial</title></item></channel></rss>' if url.endswith('rss') else f'<html><title>Blender tutorial</title><meta property="article:published_time" content="{date}"><article><p>{"Blender mesh workflow. "*10}</p><p>{"UV texture painting. "*10}</p></article></html>'
                return {'status':200,'url':url,'final_url':url,'html':html}
            result=preview(source,'2026-11-25',fetch)
            self.assertEqual(result['passed'],passed,result)
            self.assertNotIn('Blender mesh workflow',json.dumps(result))
    def test_blocked_source_fails_without_publication_or_body(self):
        result=preview({'id':'x','base_url':'https://example.com','endpoints':['https://example.com']},'2026-11-25',lambda *a,**k:{'status':403})
        self.assertFalse(result['passed']);self.assertIn('403',result['errors'][0])

    def test_admission_uses_collector_identity_and_reports_challenge(self):
        from run_daily_collector import collector_http_headers
        runtime=json.loads((Path(__file__).parents[1]/'config/collector-runtime.json').read_text('utf-8'))
        def blocked(session,url,timeout,**kw):
            self.assertTrue(session.managed_sources)
            for k,v in collector_http_headers(runtime).items():self.assertEqual(session.headers[k],v)
            return {'status':403,'error':'source-challenge-required'}
        result=preview({'id':'x','base_url':'https://example.com','endpoints':['https://example.com']},'2026-11-26',blocked)
        self.assertFalse(result['passed']);self.assertIn('source-challenge-required',result['errors'][0])

if __name__=='__main__':unittest.main()
