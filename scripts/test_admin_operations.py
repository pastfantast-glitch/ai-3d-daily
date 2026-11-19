import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from collection_monitor import summarize
from editorial_controls import held_urls
import check_main_ci as ci
class AdminOperations(unittest.TestCase):
 def test_monitor_allowlist_drops_bodies_html_and_secrets(self):
  packet={'date':'2026-11-19','source_run_id':123,'source_head_sha':'a'*40,'secret':'NEVER','summary':{'content_supply':{'selected':15,'private':'NEVER'}},'articles':[{'id':'one','source_url':'https://example.com/a','source_title':'Title','evidence':{'status':'extracted','truncated':False,'paragraphs':['NEVER']},'html':'NEVER','editorial_errors':['awaiting-editorial-review']}], 'sources':{'example':{'status':'ok','private':'NEVER'}}}
  r=summarize(packet,'failure');self.assertNotIn('NEVER',json.dumps(r));self.assertTrue(r['articles'][0]['body_readable']);self.assertEqual(r['counts'],{'selected':15})
  with self.assertRaises(ValueError):summarize({**packet,'source_run_id':None},'failure')
 def test_holds_strict_and_optional(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.assertEqual(held_urls(root),set());(root/'config').mkdir();p=root/'config/editorial-selection.json';p.write_text(json.dumps({'schema_version':1,'held_urls':['https://example.com/a']}));self.assertEqual(held_urls(root),{'https://example.com/a'});p.write_text('{"schema_version":1,"held_urls":[],"approved":true}')
   with self.assertRaises(ValueError):held_urls(root)
 def test_hold_skips_quality_and_retains_reserve(self):
  from content_supply import reserve_output
  from test_editorial_review import article, candidate, DATE
  import run_daily_collector as collector
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'config').mkdir();c=candidate(article());url=c['source_url']
   (root/'config/editorial-selection.json').write_text(json.dumps({'schema_version':1,'held_urls':[url]}))
   with patch.object(collector,'ROOT',root),patch.object(collector,'candidate_copy') as review:
    accepted,rejected=collector.readable_candidates([c],DATE)
    self.assertFalse(accepted);self.assertEqual(rejected[0][1],['owner-held-for-later']);review.assert_not_called()
   entry={'id':'held','source_url':url,'source_published_at':DATE,'title':'Retained','discovered_for':DATE}
   kept=reserve_output([],[],[entry],DATE,240,held={url});self.assertEqual(kept[0]['refresh_status'],'owner-held');self.assertEqual(kept[0]['title'],'Retained')
 def test_monitor_commit_inherits_ci_only_for_exact_bot_and_path(self):
  for email,changes,expected in [(ci.GITHUB_ACTIONS_BOT_EMAIL,'M\tdata/ops/collection-monitor.json',True),(ci.GITHUB_ACTIONS_BOT_EMAIL,'M\tdata/ops/collection-monitor.json\nM\tscripts/source.py',False),('user@example.com','M\tdata/ops/collection-monitor.json',False)]:
   with patch.object(ci,'git',side_effect=lambda *args:changes if args[0]=='diff-tree' else f'current\x00parent\x00{email}\x00Record Collector monitor 2026-11-19'):
    self.assertEqual(ci.writer_generated_commit('current')[0],expected)
if __name__=='__main__':unittest.main()
