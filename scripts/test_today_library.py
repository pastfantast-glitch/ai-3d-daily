"""All admitted articles remain discoverable beyond the TOP5 + next10 selection."""
import json
import io
from contextlib import redirect_stdout
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
import render_information_architecture as ia
import render_home_archive_links as history
import normalize_release_seed as seed


class TodayLibraryTests(unittest.TestCase):
    def test_release_seed_retains_all_expanded_cards_and_legacy_tiers(self):
        for count in (12, 20, 30):
            for expanded in (False, True):
                with self.subTest(count=count, expanded=expanded), tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    items = [dict(id=f'item-{n}', title=f'Title {n}', summary='Source summary',
                                  source_url=f'https://example.com/{n}', rank_global=n,
                                  homepage_tier='top5' if n < 5 else 'next10' if n < 15 else 'category_only')
                             for n in range(count)]
                    # Deliberately unsorted input catches accidental dataset-order rendering.
                    data = {'items': list(reversed(items))}
                    marker = ' data-card-library="all"' if expanded else ''
                    (root / 'index.html').write_text('<html><body><main><section id="today"></section>'
                        f'<section id="more"{marker}></section></main></body></html>', 'utf-8')
                    with patch.object(seed, 'ROOT', root):
                        seed.normalize_home('2026-11-26', data)
                        seed.normalize_home('2026-11-26', data)
                    soup = BeautifulSoup((root / 'index.html').read_text('utf-8'), 'html.parser')
                    ids = [c['data-intel-id'] for c in soup.select('[data-intel-role="card"]')]
                    self.assertEqual(ids, [f'item-{n}' for n in range(count if expanded else min(count, 15))])
                    self.assertEqual(len(soup.select('#today .top-item')), 5)
                    self.assertEqual(len(ids), len(set(ids)))

    def test_twenty_article_seed_passes_real_release_gate_and_rejects_card_corruption(self):
        import sys
        import check_release_input as gate
        date = '2026-11-26'
        data = json.loads((ia.ROOT / f'data/daily/{date}.json').read_text('utf-8'))
        self.assertEqual(len(data['items']), 20)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'data/daily').mkdir(parents=True)
            (root / f'data/daily/{date}.json').write_text(json.dumps(data), 'utf-8')
            (root / '2026-11-25').mkdir()
            (root / '2026-11-25/index.html').write_bytes((ia.ROOT / '2026-11-25/index.html').read_bytes())
            (root / 'index.html').write_bytes((ia.ROOT / 'index.html').read_bytes())
            with patch.object(seed, 'ROOT', root):
                seed.normalize_home(date, data)
                seed.normalize_daily(date, data)
            original = (root / 'index.html').read_text('utf-8')
            with patch.object(gate.core, 'ROOT', root), patch.object(sys, 'argv', ['check_release_input.py', date]):
                with patch.object(gate.core, 'errors', []):
                    gate.core.main()
                for defect in ('missing', 'duplicate', 'wrong-order'):
                    with self.subTest(defect=defect), patch.object(gate.core, 'errors', []):
                        soup = BeautifulSoup(original, 'html.parser')
                        cards = soup.select('#more .more-card')
                        if defect == 'missing': cards[-1].decompose()
                        elif defect == 'duplicate': cards[-1]['data-intel-id'] = cards[0]['data-intel-id']
                        else: cards[0].insert_before(cards[-1].extract())
                        (root / 'index.html').write_text(str(soup), 'utf-8')
                        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit): gate.core.main()
                        self.assertTrue(any('homepage' in e for e in gate.core.errors))

    def test_merged_cards_are_unique_paged_and_preserve_dates(self):
        cfg = ia.load_config()
        category = cfg['categories'][0]['id']
        items = [dict(id=f'fixture-{n}', title='<script>literal title</script>',
                      summary='來源支持的摘要', category=category, rank_global=n+1,
                      source_url=f'https://example.com/{n}', quick_impact='★★★☆☆',
                      homepage_tier='top5' if n<5 else 'next10' if n<15 else 'category_only',
                      source_published_at='2021-01-01' if n == 0 else '2026-11-08') for n in range(30)]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'index.html').write_text((ia.ROOT/'index.html').read_text('utf-8'),'utf-8')
            with patch.object(ia,'ROOT',root):
                ia.render_home('2026-11-09', {'items':items}, cfg)
                ia.render_home('2026-11-09', {'items':items}, cfg)
            soup = BeautifulSoup((root/'index.html').read_text('utf-8'),'html.parser')
        cards = soup.select('[data-library-id]')
        self.assertEqual(len(cards),30)
        self.assertEqual(len({c['data-library-id'] for c in cards}),30)
        self.assertEqual(len(soup.select('#today .top-item')),5)
        self.assertEqual(len(soup.select('#more .more-card')),25)
        self.assertEqual(len(soup.select('#more .more-card:not([hidden])')),10)
        self.assertEqual(len(soup.select('.today-library')),1)
        self.assertFalse(soup.select('.library-row'))
        self.assertEqual(soup.select_one('#more h2').get_text(strip=True),'今天還有什麼')
        self.assertIn('2026-11-09',soup.select_one('.edition-stamp').text)
        self.assertIn('30 篇',soup.select_one('.edition-stamp').text)
        self.assertEqual(len(soup.select('[data-freshness="reference"]')),1)
        self.assertIn('2021-01-01',soup.select_one('.library-meta').text)
        self.assertEqual(len(soup.select('#today-search')),1)
        self.assertFalse(soup.select('[data-library-id] script'))
        self.assertEqual(len(soup.select('[data-library-id] details.home-full-analysis')),30)

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
            manifest = json.loads(soup.select_one('#history-article-index').string)
            self.assertEqual(manifest['schema_version'],2)
            data = json.loads((root/'history'/manifest['months'][0]['url']).read_text('utf-8'))
            self.assertEqual(data[0]['title'], title)
            self.assertEqual(data[0]['url'], '../2026-11-08/blender-dcc/#intel-x')
            self.assertEqual(len(soup.select('script:not([src])')), 1)


if __name__ == '__main__':
    unittest.main()
