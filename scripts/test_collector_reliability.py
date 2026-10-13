"""Real editorial failures and bounded discovery budget regressions."""
import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import run_daily_collector as collector
from content_quality import editorial_title, production_summary, reader_language_ok
from check_editorial_quality import copy_signature


def candidate(index, title, description):
    url = f"https://80.lv/articles/fixture-{index}"
    return {"candidate_id": f"fixture-{index}", "source_url": url,
            "category": "blender-dcc", "subcategory": "blender", "ranking_score": 80,
            "meta": {"url": url, "title": title, "description": description}}


class ReliabilityTests(unittest.TestCase):
    def test_refill_continues_past_twenty_and_preserves_verified_overflow(self):
        topics = ['肩膀','膝蓋','手腕','腳踝','腰部','頸部','手指','眼睛','嘴巴','眉毛','肘部','髖部','胸部','衣服','帽子','鞋子','裙子','頭髮','背包','手套','門窗','屋頂','地板','岩石','樹木','草地','河流','橋樑','牆面','階梯','欄杆','雕像','路燈','長椅']
        cases = []
        for i, topic in enumerate(topics):
            c = candidate(i, f'Blender：{topic}製作教學', f'這篇教學說明{topic}的製作流程，提供操作範例供美術使用自己的資產測試與比較。')
            c.update(source_id='80-level' if i < 20 else 'cg-channel', title=c['meta']['title'], description=c['meta']['description'], published='2026-10-13',window='24h',brief_reason='single-source-verified-production-tip')
            cases.append(c)
        def probe(source, *args, **kwargs):
            batch = cases[:20] if source['id'] == '80-level' else cases[20:]
            return batch, {'status':'checked','method':'latest-index','candidates_found':len(batch),'candidate_ids':[x['candidate_id'] for x in batch],'refill_links_checked':1}
        outputs = {}
        original = collector.load_json
        def load(path):
            return {'schema_version':1,'items':[]} if path == collector.BACKLOG_PATH else original(path)
        def capture(path, value):
            outputs['backlog' if path == collector.BACKLOG_PATH else str(path.relative_to(collector.ROOT))] = value
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(collector, 'ROOT', Path(temporary)), \
             patch.object(collector.sys, 'argv', ['collector','2026-10-13']), \
             patch.object(collector, 'load_json', side_effect=load), \
             patch.object(collector, 'registered_source_probe_plan', return_value={'selected':['80-level']}), \
             patch.object(collector, 'registered_source_refill_plan', return_value={'selected':['cg-channel']}), \
             patch.object(collector, 'source_probe', side_effect=probe) as mocked, \
             patch.object(collector, 'write_json', side_effect=capture), \
             patch('builtins.print'):
            collector.main()
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(len(outputs['backlog']['items']), 4)
        self.assertEqual(len({x['source_url'] for x in outputs['backlog']['items']}), 4)
        self.assertEqual(len(outputs['data/daily/2026-10-13.json']['items']), 30)

    def test_blender_headline_after_translation_passes_the_actual_language_rule(self):
        for title in ["Blender 4.2 LTS Is Finally Here", "Blender 4.5 LTS Is Out: Check Out Its Features"]:
            c = candidate(0, title, "Blender rendering feature update.")
            generated = editorial_title(c["meta"], c["category"], c["subcategory"])
            self.assertTrue(reader_language_ok(generated, 4.0), generated)
            self.assertIn("Blender", generated)
            self.assertNotIn("Finally Here", generated)

    def test_painting_summaries_preserve_real_method_differences(self):
        subjects = ["Oil painting brush strokes", "Watercolor compositing nodes", "Kuwahara filter and edge detection", "Painterly color palette"]
        summaries = []
        for i, subject in enumerate(subjects):
            c = candidate(i, "Turn Photos Into Paintings With Blender: " + subject, subject + " workflow tutorial.")
            text = production_summary(c["meta"], c["category"], c["subcategory"])
            self.assertTrue(reader_language_ok(text, 2.5), text)
            summaries.append(text)
        self.assertEqual(len({copy_signature(x) for x in summaries}), 4)

    def test_ambiguous_four_article_collision_is_rejected_and_other_copy_fills(self):
        cases = [candidate(i, prefix + " Photos & 3D Renders Into Paintings With This Blender Filter", "A Blender rendering workflow tutorial.")
                 for i, prefix in enumerate(["Turn", "Convert", "Create", "Transform"])]
        # Keep rejection strict rather than making the gate ignore repeated copy.
        cases.append(candidate(4, "Blender：角色肩膀製作教學", "這篇教學說明角色肩膀的建模與關節處理，提供操作範例供美術以自己的資產測試與比較。"))
        accepted, rejected = collector.readable_candidates(cases, "2026-10-13")
        self.assertTrue(rejected)
        self.assertIn("fixture-4", [x["candidate_id"] for x in accepted])
        self.assertTrue(any("summary boilerplate" in " ".join(errors) for _, errors in rejected))
        self.assertEqual(collector.unpublished_survivor_count(cases, set(), set(), "2026-10-13"), len(accepted))

    def test_published_links_do_not_consume_article_budget(self):
        runtime = copy.deepcopy(json.loads(collector.RUNTIME_PATH.read_text()))
        runtime["discovery"].update(max_pages_per_source=1, refill_pages_per_source=1, index_pages_per_source=0, feed_urls_per_source=0)
        old = "https://80.lv/articles/already-published"
        fresh = "https://80.lv/articles/new-workflow"
        related = "https://80.lv/articles/related-workflow"
        html = "INDEX"
        fetched = []
        def fetch(session, url, timeout, **kwargs):
            fetched.append(url)
            return {"url": url, "final_url": url, "html": html if url.endswith('/articles/') else 'ARTICLE', "status": 200}
        def links(content, *args):
            return [(old, "Old"), (fresh, "New")] if content == html else [(old, "Old"), (related, "Related")]
        def metadata(result, fallback):
            return {"url": result['url'], "title": "Blender modeling tutorial", "description": "Blender modeling workflow.", "published": "2026-10-13", "html": 'ARTICLE'}
        with patch.object(collector, 'fetch', side_effect=fetch), \
             patch.object(collector, 'extract_links', side_effect=links), \
             patch.object(collector, 'extract_pagination_links', return_value=[]), \
             patch.object(collector, 'extract_feed_urls', return_value=[]), \
             patch.object(collector, 'page_metadata', side_effect=metadata), \
             patch.object(collector, 'relevant', return_value=True):
            cases, record = collector.source_probe({'id':'80-level','domain':'80.lv'}, ['https://80.lv/articles/'], runtime, None, '2026-10-13', set(), published_sources={old})
        self.assertNotIn(old, fetched)
        self.assertIn(fresh, fetched)
        self.assertIn(related, fetched)
        self.assertEqual(record['published_links_skipped'], 1)
        self.assertEqual(len(cases), 2)


if __name__ == '__main__':
    unittest.main()
