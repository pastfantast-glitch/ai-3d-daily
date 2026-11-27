import json
from pathlib import Path
import tempfile
import unittest
from collection_queue import merge_queue, pending_seeds
from article_evidence import loss_summary


class QueueTests(unittest.TestCase):
    def test_new_recommendation_precedes_legacy_already_fetched_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir();(root/'data/ops').mkdir(parents=True)
            (root/'config/collection-intake.json').write_text(json.dumps({'items':[{'source_url':'https://80.lv/articles/z-new','requested_on':'2026-11-27'}]}))
            (root/'data/ops/collection-monitor.json').write_text(json.dumps({'date':'2026-11-27','articles':[{'source_url':'https://80.lv/articles/a-old','errors':['awaiting-editorial-review']}]}))
            result=pending_seeds(root,'2026-11-27',{'sources':[{'id':'80-level','base_url':'https://80.lv','enabled':True}]},set(),limit=1)
            self.assertEqual(result,{'80-level':[('https://80.lv/articles/z-new','')]})

    def test_budget_deferred_link_does_not_downgrade_pending_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            row={'id':'one','source_url':'https://80.lv/articles/a','errors':['awaiting-editorial-review']}
            old={'date':'2026-11-26','source_run_id':10,'source_head_sha':'a'*40,'articles':[row]}
            current={'date':'2026-11-27','source_run_id':11,'source_head_sha':'b'*40,'articles':[],'sources':{'80-level':{'url_observations':[{'source_url':row['source_url'],'state':'discovered','errors':['article-budget-deferred']}]}}}
            result=merge_queue(current,old,Path(tmp))['pending_queue'][0]
            self.assertEqual((result['state'],result['source_run_id'],result['errors']),('awaiting_review',10,['awaiting-editorial-review']))

    def test_queued_article_is_fetched_even_if_index_blocks_and_zero_refill_stays_zero(self):
        import copy
        from types import SimpleNamespace
        from unittest.mock import patch
        import run_daily_collector as c
        runtime=copy.deepcopy(c.load_json(c.RUNTIME_PATH));runtime['discovery'].update(max_pages_per_source=1,refill_pages_per_source=0,index_pages_per_source=0,feed_urls_per_source=0,category_indexes_per_source=0)
        url='https://80.lv/articles/queued';calls=[]
        session=SimpleNamespace(pending_by_source={'80-level':[(url,'Blender workflow')]})
        def fetch(session,target,*a,**k):
            calls.append(target);return {'url':target,'final_url':target,'status':200 if target==url else 403,'html':'ARTICLE' if target==url else ''}
        meta={'url':url,'title':'Blender workflow','description':'Blender modeling','published':'2026-11-26','html':'ARTICLE'}
        with patch.object(c,'fetch',side_effect=fetch),patch.object(c,'page_metadata',return_value=meta),patch.object(c,'relevant',return_value=True):
            found,record=c.source_probe({'id':'80-level','domain':'80.lv'},['https://80.lv/articles/'],runtime,session,'2026-11-27',set())
        self.assertEqual(len(found),1)
        self.assertEqual(calls,['https://80.lv/articles/',url])
        self.assertEqual(record['refill_links_checked'],0)

    def test_pending_survives_partial_trial_with_original_evidence_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            old={'date':'2026-11-26','source_run_id':10,'source_head_sha':'a'*40,
                 'articles':[{'id':'one','source_url':'https://80.lv/articles/a','source_date':'2026-11-25','errors':['awaiting-editorial-review']}]}
            current={'date':'2026-11-27','source_run_id':11,'source_head_sha':'b'*40,'articles':[],'sources':{}}
            result=merge_queue(current,old,Path(tmp))['pending_queue'][0]
            self.assertEqual(result['state'],'awaiting_review')
            self.assertEqual(result['source_run_id'],10)
            self.assertEqual(result['evidence_date'],'2026-11-26')

    def test_refresh_keeps_first_seen_and_updates_exact_evidence_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            row={'id':'one','source_url':'https://80.lv/articles/a','source_date':'2026-11-25','errors':['awaiting-editorial-review']}
            old={'date':'2026-11-26','source_run_id':10,'source_head_sha':'a'*40,'articles':[row]}
            current={'date':'2026-11-27','source_run_id':11,'source_head_sha':'b'*40,'articles':[row],'sources':{}}
            result=merge_queue(current,old,Path(tmp))['pending_queue'][0]
            self.assertEqual((result['first_seen'],result['last_attempt_on'],result['source_run_id']),('2026-11-26','2026-11-27',11))

    def test_recommendations_and_pending_are_seeds_not_approvals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir();(root/'data/ops').mkdir(parents=True)
            sources=[{'id':'80-level','base_url':'https://80.lv','enabled':True,'topic_ids':['ai-3d']}]
            (root/'config/collection-intake.json').write_text(json.dumps({'items':[{'source_url':'https://80.lv/articles/new'}]}))
            (root/'data/ops/collection-monitor.json').write_text(json.dumps({'pending_queue':[
                {'source_url':'https://80.lv/articles/held','state':'awaiting_review'},
                {'source_url':'https://80.lv/articles/old','state':'awaiting_review','source_date':'2020-01-01'},
                {'source_url':'https://80.lv/articles/live','state':'awaiting_review'},
                {'source_url':'https://evil.example/article','state':'awaiting_review'}]}))
            result=pending_seeds(root,'2026-11-27',{'sources':sources},{'https://80.lv/articles/live'},{'https://80.lv/articles/held'})
            self.assertEqual(result,{'80-level':[('https://80.lv/articles/new','')]})

    def test_unreviewed_is_not_prose_rejection(self):
        result=loss_summary([],[(None,['awaiting-editorial-review']),(None,['generic analysis padding'])])
        self.assertEqual(result['editorial_rejected'],1)
        self.assertEqual(result['awaiting_review'],1)

if __name__=='__main__':unittest.main()
