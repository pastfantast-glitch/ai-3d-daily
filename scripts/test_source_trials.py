import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import requests
import run_daily_collector as collector
from collection_monitor import summarize, with_yield_history
from run_source_trial import collect
from publisher_feeds import feed_endpoint


class SourceTrialTests(unittest.TestCase):
    def test_only_declared_feed_is_resolved_and_article_domain_stays_bound(self):
        source = 'https://www.cgchannel.com/feed/'
        destination = 'https://feeds2.feedburner.com/cgchannel/nHpU'
        self.assertEqual(feed_endpoint(source), destination)
        for url in [source+'?anything=1', 'http://www.cgchannel.com/feed/', 'https://www.cgchannel.com.evil/feed/']:
            self.assertEqual(feed_endpoint(url), url)
        response=requests.Response();response.status_code=200;response._content=b'<rss/>';response.url=destination;response.headers['content-type']='application/xml'
        session=requests.Session();session.managed_sources=True
        with patch('public_source_http.get',return_value=response) as request:
            collector.fetch(session,source,8,allow_feed=True)
            self.assertEqual(request.call_args.args[0],destination)
            collector.fetch(session,source,8)
            self.assertEqual(request.call_args.args[0],source)
        xml='<rss><channel><item><title>Bad</title><link>https://evil.org/article/a</link></item><item><title>Good</title><link>https://www.cgchannel.com/2026/11/example</link></item></channel></rss>'
        self.assertEqual(collector.extract_feed_article_links(xml,destination,'cgchannel.com',5), [('https://www.cgchannel.com/2026/11/example','Good')])

    def test_double_encoded_feed_tracking_does_not_create_duplicate_identity(self):
        xml='<rss><channel><item><title>Vulkan</title><link>https://www.khronos.org/blog/vulkan?utm_medium=social&amp;amp;utm_source=news&amp;amp;item=7</link></item></channel></rss>'
        self.assertEqual(collector.extract_feed_article_links(xml,'https://www.khronos.org/feeds/news_feed','khronos.org',3), [('https://www.khronos.org/blog/vulkan?item=7','Vulkan')])

    def test_godot_original_date_requires_one_publisher_article_date(self):
        for text, expected in [('Published 2026/11/24','2026-11-24'), ('2026-11-24 12:00:00 +0000','2026-11-24'), ('2026/11/245',None), ('2026/13/24',None)]:
            self.assertEqual(collector.parse_date(text), expected)
        html='<title>Godot rendering</title><span class="date" data-post-date="2026-11-24 12:00:00 +0000">24 November 2026</span>'
        url='https://godotengine.org/article/rendering/'
        self.assertEqual(collector.page_metadata({'url':url,'html':html})['published'],'2026-11-24')
        for other in ['https://godotengine.org/blog/', 'https://evil.org/article/rendering/']:
            self.assertIsNone(collector.page_metadata({'url':other,'html':html})['published'])
        self.assertIsNone(collector.page_metadata({'url':url,'html':html+html})['published'])

    def test_trial_cannot_run_before_valid_done(self):
        with patch('run_source_trial.release_status',return_value={'state':'NOT_STARTED'}), patch.object(collector,'source_probe') as probe:
            with self.assertRaisesRegex(ValueError,'valid DONE'):collect('2026-11-26')
            probe.assert_not_called()

    def test_trial_workflow_has_no_session_commit_or_handoff_target(self):
        workflow=(Path(__file__).parents[1]/'.github/workflows/daily-collector.yml').read_text('utf-8')
        self.assertIn('group: autonomous-daily-collector',workflow)
        for step in ['Run genuine source-grounded Discovery and build Collector artifacts', 'Validate Collector session and canonical/private boundary', 'Reconfirm current main and commit only Collector artifacts', 'Preserve resolved Collector target', 'Upload resolved Collector target']:
            condition=workflow.split('- name: '+step,1)[1].splitlines()[1]
            self.assertIn("steps.preflight.outputs.source_trial != 'true'",condition)
        self.assertIn('Trial must use today',workflow)
        self.assertIn('Existing writer/handoff active',workflow)

    def test_history_retains_failed_run_without_double_counting_retry_or_bodies(self):
        root=Path(__file__).parents[1]
        packet={'date':'2026-11-26','source_run_id':123,'source_head_sha':'a'*40,'mode':'source-trial',
                'articles':[], 'sources':{'example':{'status':'blocked','reason':'http-403','html':'secret'}},
                'summary':{'content_supply':{'body_readable':0,'approved_reserve':0,'selected':0,'raw':'secret'}}}
        with tempfile.TemporaryDirectory() as td:
            fixture=Path(td);(fixture/'config').mkdir()
            (fixture/'config/collection-admin.json').write_bytes((root/'config/collection-admin.json').read_bytes())
            one=with_yield_history(summarize(packet,'failure'),{},fixture)
            two=with_yield_history(summarize(packet,'failure'),one,fixture)
            self.assertEqual(len(two['yield_history']),1)
            self.assertNotIn('secret',json.dumps(two))
            self.assertNotIn('published',two['counts'])
            packet['source_run_id']=124
            three=with_yield_history(summarize(packet,'success'),two,fixture)
            self.assertEqual(len(three['yield_history']),2)
            self.assertEqual(three['counts']['body_readable'],0)


if __name__=='__main__':unittest.main()
