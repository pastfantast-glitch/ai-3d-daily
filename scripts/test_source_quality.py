"""Regressions from the 2026-10-13 public edition, including selection/QA parity."""
import unittest
import tempfile
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from source_quality import source_quality_errors, dated_url_upper_bound
from content_quality import admission, source_content_kind, editorial_title, production_summary
import run_daily_collector as collector


class SourceQualityTests(unittest.TestCase):
    def test_pre_handoff_parity_deferral_requires_valid_evidence_and_stops_at_ready(self):
        import check_pages_tier_contract as pages
        date = '2026-10-13'
        data = {'metadata': {'policy_recollect': True}, 'items': [{'id': 'new'}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publish = root / 'data' / 'publish'
            daily = root / 'data' / 'daily'
            publish.mkdir(parents=True)
            daily.mkdir(parents=True)
            canonical = daily / f'{date}.json'
            canonical.write_text(json.dumps(data), encoding='utf-8')
            (publish / f'{date}.done.json').write_text(json.dumps(
                {'state': 'DONE', 'canonical': {'ids': ['old']}}), encoding='utf-8')
            with patch.object(pages, 'ROOT', root), patch.object(pages.subprocess, 'run') as run:
                run.return_value = SimpleNamespace(returncode=1)
                self.assertFalse(pages.policy_recollect_pending(date, data))
                run.return_value = SimpleNamespace(returncode=0)
                self.assertTrue(pages.policy_recollect_pending(date, data))
                self.assertIn('--policy-republish', run.call_args.args[0])
                (publish / f'{date}.ready').write_text(json.dumps({
                    'canonical_sha256': hashlib.sha256(canonical.read_bytes()).hexdigest()
                }), encoding='utf-8')
                run.reset_mock()
                self.assertFalse(pages.policy_recollect_pending(date, data))
                run.assert_not_called()

    def test_grooming_guides_do_not_mean_tutorial(self):
        self.assertEqual(source_content_kind("a guide-based hair grooming tool"), "tool")

    def test_sisir_preserves_product_identity_and_actual_function(self):
        meta = {"url": "https://www.cgchannel.com/2026/07/sisir-is-a-promising-new-free-standalone-hair-grooming-tool",
                "title": "Sisir is a promising new free standalone hair grooming tool",
                "description": "A guide-based tool exporting hair to Blender and Maya."}
        self.assertIn("Sisir", editorial_title(meta, "3d-production", "character-production"))
        self.assertIn("毛髮", production_summary(meta, "3d-production", "character-production"))
        self.assertNotIn("製作教學", editorial_title(meta, "3d-production", "character-production"))
    def test_old_release_cannot_be_current_news(self):
        item = {"source_url": "https://www.cgchannel.com/2016/05/krita-3-0",
                "title": "Krita 3.0：版本更新", "summary": "繪圖與動畫工具更新。"}
        self.assertTrue(source_quality_errors(item, "2026-10-13"))
        item.update(title="歷史版本｜Krita 3.0", summary="2016 年的繪圖與動畫版本回顧。")
        self.assertEqual(source_quality_errors(item, "2026-10-13"), [])

    def test_landing_pages_rejected_even_with_article_metadata(self):
        for url in ("https://80.lv/articles/game-development",
                    "https://www.blender.org/download/requirements",
                    "https://www.sidefx.com/industries/filmtv"):
            self.assertFalse(admission({"url": url, "title": "Blender animation workflow",
                                        "published": "2026-10-13", "article_type": True})[0])

    def test_backfill_rejects_future_article(self):
        self.assertTrue(source_quality_errors({"source_published_at": "2026-10-13"}, "2026-10-12"))
        self.assertTrue(source_quality_errors({"source_url": "https://example.com/2026/11/story"}, "2026-10-12"))

    def test_missing_date_is_not_evergreen_evidence(self):
        self.assertTrue(source_quality_errors({"source_url": "https://example.com/unknown-date"}, "2026-10-13"))

    def test_recent_metadata_cannot_hide_an_old_release_url(self):
        item = {"source_url": "https://example.com/2016/05/krita", "source_published_at": "2026-10-13"}
        self.assertTrue(source_quality_errors(item, "2026-10-13"))

    def test_month_urls_do_not_invent_a_publication_day(self):
        self.assertEqual(str(dated_url_upper_bound("https://example.com/2024/02/post")), "2024-02-29")
        self.assertIsNone(dated_url_upper_bound("https://example.com/2024/99/post"))
        self.assertEqual(source_quality_errors({"source_url": "https://example.com/2026/10/post"}, "2026-10-12"), [])

    def test_changed_subject_does_not_hide_generic_analysis(self):
        for subject in ("Blender", "Sisir", "Houdini"):
            errors = source_quality_errors({"full_analysis": [{"text": f"針對{subject}，可挑與目前作品相近的鏡頭或素材做小型比較。"}]}, "2026-10-13")
            self.assertTrue(errors)

    def test_date_header_ignores_recent_sidebar(self):
        html = '<p>Tuesday, May 31st, 2016 Posted by Jim</p><h1>Krita 3.0</h1><aside><time datetime="2026-10-13">Today</time></aside>'
        result = collector.page_metadata({"url": "https://example.com/krita", "html": html})
        self.assertEqual(result["published"], "2016-05-31")

    def test_cached_copy_still_passes_source_evidence_to_gate(self):
        c = {"candidate_id": "old", "source_url": "https://example.com/2016/05/krita",
             "meta": {"published": "2016-05-31"}, "reader_copy": {"id": "old"}}
        with patch.object(collector, "editorial_errors", return_value=["old source"]) as gate:
            accepted, rejected = collector.readable_candidates([c], "2026-10-13")
        self.assertFalse(accepted)
        self.assertTrue(rejected)
        self.assertEqual(gate.call_args.args[0]["items"][0]["source_published_at"], "2016-05-31")


if __name__ == "__main__":
    unittest.main()
