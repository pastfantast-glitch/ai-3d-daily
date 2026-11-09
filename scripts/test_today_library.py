"""All admitted articles remain discoverable beyond the TOP5 + next10 selection."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
import render_information_architecture as ia
import render_home_archive_links as history


class TodayLibraryTests(unittest.TestCase):
    def test_all_thirty_items_have_safe_dated_deep_links_and_source_dates(self):
        cfg = ia.load_config()
        category = cfg['categories'][0]['id']
        items = [dict(id=f'fixture-{n}', title='<script>literal title</script>',
                      summary='來源支持的摘要', category=category, rank_global=n,
                      source_published_at='2021-01-01' if n == 0 else '2026-11-08') for n in range(30)]
        soup = BeautifulSoup('<html><body><header class="home-hero"><div class="page"></div></header><main><section id="today"></section></main></body></html>', 'html.parser')
        ia.ensure_today_library(soup, '2026-11-09', {'items':items}, cfg)
        ia.ensure_today_library(soup, '2026-11-09', {'items':items}, cfg)
        self.assertEqual(len(soup.select('.today-library')), 1)
        self.assertEqual(len(soup.select('.library-row')), 30)
        self.assertEqual(len(soup.select('.library-row[data-freshness="reference"]')), 1)
        self.assertEqual(len(soup.select('.library-row[data-freshness="recent"]')), 29)
        self.assertFalse(soup.select('script'))
        self.assertTrue(soup.select('.library-link')[-1]['href'].endswith('#intel-fixture-29'))
        self.assertIn('2021-01-01', soup.select_one('.library-meta').text)

    def test_empty_category_is_explained_with_history_link(self):
        cfg = ia.load_config()
        soup = BeautifulSoup(ia.category_page('2026-11-09', cfg['categories'][0], [], cfg), 'html.parser')
        self.assertIn('暫無符合品質標準', soup.select_one('.category-empty').text)
        self.assertEqual(soup.select_one('.category-empty a')['href'], '../../history/')

    def test_history_payload_preserves_literal_text_without_script_breakout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'data/daily').mkdir(parents=True)
            (root/'2026-11-08/blender-dcc').mkdir(parents=True)
            (root/'2026-11-08/blender-dcc/index.html').write_text('fixture')
            title = '</script><script>alert(1)</script>'
            (root/'data/daily/2026-11-08.json').write_text(json.dumps({'items':[
                dict(id='x', title=title, summary='摘要', category='blender-dcc')]}), 'utf-8')
            with patch.object(history, 'ROOT', root), patch.object(history, 'HISTORY_DIR', root/'history'), patch.object(history, 'HISTORY_INDEX', root/'history/index.html'):
                history.render_history_page('2026-11-09', ['2026-11-09','2026-11-08'], ia.load_config())
            soup = BeautifulSoup((root/'history/index.html').read_text('utf-8'), 'html.parser')
            data = json.loads(soup.select_one('#history-article-index').string)
            self.assertEqual(data[0]['title'], title)
            self.assertEqual(data[0]['url'], '../2026-11-08/blender-dcc/#intel-x')
            self.assertEqual(len(soup.select('script:not([src])')), 1)


if __name__ == '__main__':
    unittest.main()
