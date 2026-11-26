"""Owner-managed sources, separate topic selection and single-writer render regressions."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
from collection_settings import load_settings, validate_settings, effective_hybrid, topic_matches, all_items
from discovery_hybrid import load_hybrid_config, registered_source_probe_plan
from topic_contract import select_topics, topic_errors
from test_editorial_review import article, record, DATE
from editorial_review import validate_record
from render_topic_pages import build
from public_source_http import get
import requests

ROOT=Path(__file__).resolve().parents[1]


def configured():
    data=json.loads((ROOT/'scripts/fixtures/collection-admin.json').read_text('utf-8'))
    data['topics'].append({'id':'cloth','name':'衣物設計','description':'布料與衣褶製作', 'enabled':True,
        'include_terms':['cloth'],'exclude_terms':['sponsored'],'target_items':2,'max_age_months':12})
    data['sources'].append({'id':'example','name':'Example','base_url':'https://example.com/',
        'endpoints':['https://example.com/articles/'],'enabled':True,'topic_ids':['cloth']})
    return data


class Tests(unittest.TestCase):
    def test_disconnected_sources_are_preserved_but_never_probed(self):
        settings=configured();source=settings['sources'][0]
        source.update(topic_ids=[],enabled=False)
        validate_settings(settings)
        cfg=effective_hybrid(load_hybrid_config(),settings)
        self.assertNotIn(source['id'],registered_source_probe_plan(DATE,cfg)['selected'])
        source['enabled']=True
        with self.assertRaises(ValueError):validate_settings(settings)
        source['enabled']=False
        for item in settings['sources']:item['enabled']=False
        with self.assertRaises(ValueError):validate_settings(settings)

    def test_settings_change_actual_probe_plan_and_keep_frozen_history(self):
        settings=configured();validate_settings(settings)
        settings['sources'][0]['enabled']=False
        base=load_hybrid_config();cfg=effective_hybrid(base,settings)
        self.assertNotIn(settings['sources'][0]['id'],registered_source_probe_plan(DATE,cfg)['selected'])
        self.assertTrue(base['discovery_source_pool']['sources'][0]['enabled'])
        enabled={s['id'] for s in cfg['discovery_source_pool']['sources'] if s['enabled']}
        self.assertIn('example',enabled)
        settings['topics'][1]['enabled']=False
        self.assertFalse(next(s for s in effective_hybrid(base,settings)['discovery_source_pool']['sources'] if s['id']=='example')['enabled'])

    def test_scope_date_and_exclusions_apply_before_selection(self):
        settings=configured();source=settings['sources'][-1]
        meta={'title':'Cloth construction','published':DATE}
        self.assertEqual(topic_matches(meta,source,settings,True,DATE),['cloth'])
        self.assertFalse(topic_matches({**meta,'published':'2024-01-01'},source,settings,True,DATE))
        self.assertFalse(topic_matches({**meta,'published':'2027-01-01'},source,settings,True,DATE))
        self.assertFalse(topic_matches({**meta,'title':'sponsored cloth'},source,settings,True,DATE))
        self.assertFalse(topic_matches({**meta,'title':'Unrelated article'},source,settings,True,DATE))
        # Leap day clamps to February 28, not March 1.
        self.assertEqual(topic_matches({**meta,'published':'2027-02-28'},source,settings,False,'2028-02-29'),['cloth'])

    def test_topic_selection_never_fills_main_quota_and_excess_becomes_reserve(self):
        settings=configured()
        candidates=[{'candidate_id':str(i),'topic_ids':['ai-3d','cloth'] if i==0 else ['ai-3d'] if i<3 else ['cloth']} for i in range(6)]
        main,extras,reserve=select_topics(candidates,settings,2)
        self.assertEqual([c['candidate_id'] for c in main],['0','1'])
        self.assertEqual([c['candidate_id'] for c in extras],['3'])
        self.assertEqual([c['candidate_id'] for c in reserve],['2','4','5'])
        self.assertEqual(len({c['candidate_id'] for c in main+extras}),3)

    def test_shared_review_contract_and_existing_image_card_render(self):
        settings=configured();a=article();item=validate_record(record(a),a,DATE)
        item.update(topic_ids=['cloth'],homepage_tier='category_only',quick_impact='★★★☆☆',analysis_level='BRIEF')
        data={'date':DATE,'items':[],'topic_items':[item],'metadata':{'collection_settings':settings}}
        self.assertEqual(topic_errors(data),[])
        broken=copy.deepcopy(data);broken['topic_items'][0]['full_analysis']=[]
        self.assertTrue(topic_errors(broken))
        broken=copy.deepcopy(data);broken['items']=[item]
        self.assertTrue(any('duplicate' in e for e in topic_errors(broken)))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for folder in ['config','data/daily','assets/visual/'+DATE,'topics']:(root/folder).mkdir(parents=True)
            (root/'config/collection-admin.json').write_text(json.dumps(settings),'utf-8')
            (root/f'data/daily/{DATE}.json').write_text(json.dumps(data),'utf-8')
            visual={'id':item['id'],'status':'ok','asset_path':f'assets/visual/{DATE}/fixture.webp','page_url':item['source_url']}
            (root/f'assets/visual/{DATE}/manifest.json').write_text(json.dumps({'entries':[visual]}),'utf-8')
            shutil.copyfile(ROOT/'topics/template.html',root/'topics/template.html')
            # A concurrent settings restore must not remove the in-flight topic surface.
            (root/'config/collection-admin.json').write_text(json.dumps(load_settings()),'utf-8')
            build(root,DATE)
            soup=BeautifulSoup((root/'topics/cloth/index.html').read_text('utf-8'),'html.parser')
            self.assertEqual(len(soup.select('.home-card')),1)
            self.assertEqual(soup.select_one('figure img')['src'],'../../'+visual['asset_path'])
            self.assertEqual(len(soup.select('details .detail-body h4')),3)
            self.assertIn(DATE,soup.select_one('.article-date').text)
            self.assertEqual(soup.body['data-release-date'],DATE)

    def test_configured_rss_collects_custom_topic_without_ai_admission(self):
        import run_daily_collector as collector
        settings=configured();source=effective_hybrid(load_hybrid_config(),settings)['discovery_source_pool']['sources'][-1]
        runtime=json.loads((ROOT/'config/collector-runtime.json').read_text('utf-8'))
        runtime['discovery'].update(index_pages_per_source=0,feed_urls_per_source=0,category_indexes_per_source=0,refill_pages_per_source=0)
        rss='<rss><channel><item><title>Cloth story</title><link>https://example.com/articles/cloth-story</link></item></channel></rss>'
        def fetch(session,url,timeout,**kwargs):
            return {'url':url,'final_url':url,'status':200,'html':rss if url.endswith('/rss') else '<article>Body</article>'}
        meta={'url':'https://example.com/articles/cloth-story','title':'Cloth story','description':'Cloth construction','published':DATE,'html':'<article>Body</article>'}
        with patch.object(collector,'fetch',side_effect=fetch),patch.object(collector,'page_metadata',return_value=meta),patch.object(collector,'relevant',return_value=False):
            rows,_=collector.source_probe(source,['https://example.com/rss'],runtime,requests.Session(),DATE,set(),collection_settings=settings)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['topic_ids'],['cloth'])

    def test_collector_persists_primary_topic_and_reserve_in_one_batch(self):
        import run_daily_collector as collector
        import io
        from contextlib import redirect_stdout
        published=json.loads((ROOT/'data/daily/2026-11-17.json').read_text('utf-8'))
        settings=configured();settings['topics'][1]['target_items']=1
        for source in settings['sources']:source['topic_ids']=['ai-3d','cloth']
        candidates=[]
        from urllib.parse import urlsplit
        from source_quality import source_window_errors
        fresh=[i for i in published['items'] if not source_window_errors(i,'2026-11-17')]
        for n,item in enumerate(fresh[:14]):
            host=urlsplit(item['source_url']).hostname.removeprefix('www.')
            source=next(s for s in settings['sources'] if host==urlsplit(s['base_url']).hostname.removeprefix('www.') or host.endswith('.'+urlsplit(s['base_url']).hostname.removeprefix('www.')))
            candidates.append({'candidate_id':item['id'],'source_id':source['id'],'source_url':item['source_url'],
                'title':item['title'],'description':item['summary'],'published':item['source_published_at'],
                'window':collector.window_for(item['source_published_at'],'2026-11-17'),
                'category':item['category'],'subcategory':item['subcategory'],'ranking_score':100-n,
                'brief_reason':item['brief_reason'],'reader_copy':copy.deepcopy(item),
                'topic_ids':['ai-3d'] if n<12 else ['cloth'],
                'meta':{'title':item['title'],'description':item['summary'],'published':item['source_published_at']}})
        def probe(source,*args,**kwargs):
            rows=[c for c in candidates if c['source_id']==source['id']]
            return rows, {'status':'checked','method':'latest-index','candidates_found':len(rows),'candidate_ids':[c['candidate_id'] for c in rows],'refill_links_checked':1}
        outputs={};original_load=collector.load_json
        def read(path):return {'schema_version':1,'items':[]} if path==collector.BACKLOG_PATH else original_load(path)
        def write(path,value):outputs['backlog' if path==collector.BACKLOG_PATH else path.parent.name]=value
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()), patch.object(collector,'ROOT',Path(td)), patch.object(collector,'load_settings',return_value=settings), patch.object(collector,'load_json',side_effect=read), patch.object(collector,'load_registry',return_value=(set(),set(),{})), patch.object(collector.sys,'argv',['collector','2026-11-17']), patch.object(collector,'load_owner_preferences',return_value=({}, {'status':'disabled','vote_count':0})), patch.object(collector,'source_probe',side_effect=probe), patch.object(collector,'write_json',side_effect=write):
            self.assertEqual(collector.main(),0)
        daily=outputs['daily']
        self.assertEqual(len(daily['items']),12)
        self.assertEqual(len(daily['topic_items']),1)
        self.assertEqual(topic_errors(daily),[])
        self.assertEqual(sum(r['decision']=='published' for r in outputs['decision-ledger']['items']),13)
        self.assertEqual(len(outputs['backlog']['items']),1)

    def test_topic_reviews_cannot_satisfy_main_merge_minimum(self):
        from check_editorial_submission import readiness_errors
        copies=[{'id':str(i),'source_url':f'https://example.com/{i}','topic_ids':['cloth']} for i in range(20)]
        with tempfile.TemporaryDirectory() as td:
            errors=readiness_errors(copies,DATE,Path(td))
        self.assertTrue(any('below fallback floor' in error for error in errors))

    def test_handoff_rejects_topic_window_drift_before_rendering(self):
        settings=configured();settings['topics'][1]['max_age_months']=1
        a=article();item=validate_record(record(a),a,DATE)
        item.update(topic_ids=['cloth'],homepage_tier='category_only',source_published_at='2026-07-15')
        data={'date':DATE,'items':[],'topic_items':[item],'metadata':{'collection_settings':settings}}
        self.assertTrue(any('exceeds configured source window' in e for e in topic_errors(data)))

    def test_source_metrics_include_subdomains_and_count_canonical_publications(self):
        from render_topic_pages import source_metrics, source_for_url
        settings=configured()
        self.assertEqual(source_for_url(settings['sources'],'https://forum.blender.org/t/example')['id'],'blender-official')
        self.assertIsNone(source_for_url(settings['sources'],'https://evilblender.org/t/example'))
        specific=settings['sources']+[{'id':'blender-forum','base_url':'https://forum.blender.org/'}]
        self.assertEqual(source_for_url(specific,'https://forum.blender.org/t/example')['id'],'blender-forum')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'data/candidates/decision-ledger';folder.mkdir(parents=True)
            (folder/'2026-11-25.json').write_text(json.dumps({'items':[
                {'source_url':'https://forum.blender.org/t/published','decision':'published'},
                {'source_url':'https://forum.blender.org/t/selected-but-not-published','decision':'published'},
                {'source_url':'https://forum.blender.org/t/rejected','decision':'rejected'}]}),'utf-8')
            editions=[({'date':'2026-11-25','items':[{'source_url':'https://forum.blender.org/t/published'}],'topic_items':[]}, {})]
            row=source_metrics(root,editions,settings,'2026-11-25')['sources']['blender-official']
            self.assertEqual(row['published'],1)
            self.assertEqual(row['rejected'],1)

    def test_public_fetch_rejects_private_dns_without_opening_connection(self):
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]), patch('socket.create_connection') as connect:
            with self.assertRaises(requests.RequestException):get('https://example.com/',3)
            connect.assert_not_called()

    def test_invalid_settings_cannot_disable_last_main_source_or_expand_age(self):
        for mutate in [lambda s:s['topics'][0].update(max_age_months=13),lambda s:s.update(secret='no'),lambda s:[x.update(enabled=False) for x in s['sources']]]:
            settings=configured();mutate(settings)
            with self.assertRaises(ValueError):validate_settings(settings)


if __name__=='__main__':unittest.main()
