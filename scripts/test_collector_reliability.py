"""Real editorial failures and bounded discovery budget regressions."""
import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import run_daily_collector as collector
from content_quality import editorial_title, production_summary, reader_language_ok, production_details
from check_editorial_quality import copy_signature


def candidate(index, title, description):
    url = f"https://80.lv/articles/fixture-{index}"
    return {"candidate_id": f"fixture-{index}", "source_url": url,
            "category": "blender-dcc", "subcategory": "blender", "ranking_score": 80,
            "meta": {"url": url, "title": title, "description": description}}


class ReliabilityTests(unittest.TestCase):
    def test_ai_policy_and_hand_drawn_case_are_described_as_their_actual_subjects(self):
        cases = [candidate(0, 'Epic Games Tells Devs No More Hand-Written Code: AI-First Production', 'AI-first production model.'),
                 candidate(1, 'Creating An Animated Series With Hand-Drawn Textures In Blender', 'Hand-drawn textures for animation.')]
        summaries = [production_summary(x['meta'], x['category'], x['subcategory']) for x in cases]
        self.assertIn('要求與方向', summaries[0])
        self.assertIn('手繪貼圖的製作與使用', summaries[1])
        self.assertTrue(all('作品或工具' not in s for s in summaries))

    def test_article_body_methods_are_used_without_related_story_noise(self):
        result = {'url':'https://80.lv/articles/tool-fixture','final_url':'https://80.lv/articles/tool-fixture',
                  'html':'<title>Blender image filter</title><meta name="description" content="A Blender rendering tool."><nav><p>Watercolor workflow with color palette management in another story.</p></nav><article><p>This Blender filter uses a Kuwahara algorithm to process rendered images.</p><aside><p>Watercolor workflow and oil painting in related stories.</p></aside></article>'}
        m = collector.page_metadata(result)
        self.assertIn('Kuwahara', m['article_excerpt'])
        self.assertIn('Kuwahara 影像濾鏡', production_details(m))
        self.assertNotIn('水彩風格', production_details(m))

    def test_refill_continues_past_twenty_and_preserves_verified_overflow(self):
        topics = ['肩膀','膝蓋','手腕','腳踝','腰部','頸部','手指','眼睛','嘴巴','眉毛','肘部','髖部','胸部','衣服','帽子','鞋子','裙子','頭髮','背包','手套','門窗','屋頂','地板','岩石','樹木','草地','河流','橋樑','牆面','階梯','欄杆','雕像','路燈','長椅']
        cases = []
        for i, topic in enumerate(topics):
            c = candidate(i, f'Blender：{topic}製作教學', f'這篇教學說明{topic}的製作流程，提供操作範例供美術使用自己的資產測試與比較。')
            c.update(source_id='80-level' if i < 20 else 'cg-channel', title=c['meta']['title'], description=c['meta']['description'], published='2026-10-13',window='24h',brief_reason='single-source-verified-production-tip')
            c['meta']['published'] = '2026-10-13'
            # This test covers refill/overflow routing. Supply reviewed fixture
            # copy so it does not depend on the unreviewed prose fallback.
            c['reader_copy'] = {
                'id': c['candidate_id'], 'title': c['meta']['title'],
                'summary': c['meta']['description'],
                'full_analysis': [
                    {'label': '技術／流程變更', 'text': f'{topic}示範以基礎網格開始，逐步建立輪廓與細節，再展示分層修改器的排列方式及最終輸出。'},
                    {'label': 'Production 影響', 'text': f'{topic}的原始模型與完成模型可並列比較，觀察拓樸分布、輪廓變化和不同細分層級之間的差異。'},
                    {'label': '導入測試與限制', 'text': f'{topic}範例只涵蓋示範資產，並未提供大量模型的處理基準；教學使用的外掛與版本需另行核對。'},
                ],
            }
            cases.append(c)
        def probe(source, *args, **kwargs):
            batch = cases[:20] if source['id'] == '80-level' else cases[20:]
            return batch, {'status':'checked','method':'latest-index','candidates_found':len(batch),'candidate_ids':[x['candidate_id'] for x in batch],'refill_links_checked':1}
        outputs = {}
        original = collector.load_json
        def load(path):
            return {'schema_version':1,'items':[]} if path == collector.BACKLOG_PATH else original(path)
        def capture(path, value):
            outputs['backlog' if path == collector.BACKLOG_PATH else path.relative_to(collector.ROOT).as_posix()] = value
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

    def test_historical_summary_collision_is_rejected_and_other_copy_fills(self):
        cases = [candidate(i, prefix + " Photos & 3D Renders Into Paintings With This Blender Filter", "A Blender rendering workflow tutorial.")
                 for i, prefix in enumerate(["Turn", "Convert", "Create", "Transform"])]
        # Keep rejection strict rather than making the gate ignore repeated copy.
        cases.append(candidate(4, "Blender：角色肩膀製作教學", "這篇教學說明角色肩膀的建模與關節處理，提供操作範例供美術以自己的資產測試與比較。"))
        # Preserve the old summary-collision regression separately from the
        # stricter source-evidence policy covered by test_source_quality.py.
        accepted, rejected = collector.readable_candidates(cases, "2026-10-11")
        self.assertTrue(rejected)
        self.assertIn("fixture-4", [x["candidate_id"] for x in accepted])
        self.assertTrue(any("summary boilerplate" in " ".join(errors) for _, errors in rejected))
        self.assertEqual(collector.unpublished_survivor_count(cases, set(), set(), "2026-10-11"), len(accepted))

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
