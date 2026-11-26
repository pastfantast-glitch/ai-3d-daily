import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
import requests
import run_daily_collector as collector
from collection_monitor import summarize, with_yield_history
from run_source_trial import collect
from publisher_feeds import feed_endpoint


class SourceTrialTests(unittest.TestCase):
    def test_new_graphics_sources_use_complete_body_but_funding_still_fails(self):
        from content_quality import admission, classify_content
        def meta(title,body):
            return {'url':'https://example.com/article/graphics', 'title':title,'description':'Technical progress.',
                    'article_evidence':{'status':'extracted','truncated':False,'blocks':[{'text':body}]}}
        godot=meta('Dev snapshot: Godot 4.8 beta 5','This release fixes rendering and shader issues in the 3D engine.')
        khronos=meta('From portability to conformance','Vulkan rendering uses a layered implementation with conformance tests for this release.')
        self.assertTrue(admission(godot)[0]);self.assertTrue(admission(khronos)[0])
        self.assertEqual(classify_content(godot['title']),('engine-art','tools'))
        self.assertFalse(admission(meta('Godot Foundation welcomes a Platinum Sponsor','The sponsorship funds shader rendering tools.'))[0])
        self.assertFalse(admission(meta('Quarterly accounts','Revenue growth and customer retention.'))[0])
        khronos['article_evidence']['truncated']=True
        self.assertFalse(admission(khronos)[0])

    def test_public_dns_connection_fallback_never_accepts_private_or_invalid_tls(self):
        import public_source_http as http
        import ssl
        answers=[(None,None,None,None,('8.8.8.8',443)),(None,None,None,None,('1.1.1.1',443))]
        response=Mock(status=200);response.getheaders.return_value=[];response.read.return_value=b'public'
        sock=Mock();ctx=Mock();ctx.wrap_socket.return_value=sock
        with patch.object(http.socket,'getaddrinfo',return_value=answers), patch.object(http.socket,'create_connection',side_effect=[OSError('route unavailable'),sock]) as connect, patch.object(http.ssl,'create_default_context',return_value=ctx), patch.object(http.http.client.HTTPSConnection,'request',lambda self,*a,**k:self.connect()), patch.object(http.http.client.HTTPSConnection,'getresponse',return_value=response):
            self.assertEqual(http.get('https://example.com/',8).status_code,200)
            self.assertEqual([x.args[0] for x in connect.call_args_list],[('8.8.8.8',443),('1.1.1.1',443)])
            self.assertEqual(ctx.wrap_socket.call_args.kwargs['server_hostname'],'example.com')
        with patch.object(http.socket,'getaddrinfo',return_value=answers+[(None,None,None,None,('127.0.0.1',443))]), patch.object(http.socket,'create_connection') as connect:
            with self.assertRaises(requests.RequestException):http.get('https://example.com/',8)
            connect.assert_not_called()
        ctx.wrap_socket.side_effect=ssl.SSLCertVerificationError('invalid certificate')
        with patch.object(http.socket,'getaddrinfo',return_value=answers), patch.object(http.socket,'create_connection',return_value=sock) as connect, patch.object(http.ssl,'create_default_context',return_value=ctx), patch.object(http.http.client.HTTPSConnection,'request',lambda self,*a,**k:self.connect()):
            with self.assertRaises(requests.RequestException):http.get('https://example.com/',8)
            self.assertEqual(connect.call_count,1)

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
            (fixture/'data/daily').mkdir(parents=True);(fixture/'data/publish').mkdir()
            (fixture/'data/daily/2026-08-23.json').write_text(json.dumps({'items':[{'id':'legacy-no-source'}]}))
            (fixture/'data/publish/2026-08-23.done.json').write_text('{}')
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
