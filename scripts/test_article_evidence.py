"""Regressions for source-body coverage and review-packet privacy boundaries."""
import unittest
from article_evidence import extract_article_evidence, review_record, loss_summary, MAX_CHARS
from run_daily_collector import page_metadata
from prepare_editorial_review import review_drafts

URL = 'https://example.com/2026/10/article'


class ArticleEvidenceTests(unittest.TestCase):
    def test_interview_h4_sections_and_unwrapped_related_content(self):
        html = '<article><div id="80lv__article__body"><h4>Rigging method</h4><p>The artist uses Control Rig directly in the engine to pose characters.</p><h2>Related Posts</h2><p>This unrelated product was released many years earlier.</p></div></article>'
        evidence = extract_article_evidence(html, URL)
        self.assertEqual(len(evidence['blocks']), 1)
        self.assertEqual(evidence['blocks'][0]['section'], 'Rigging method')
        self.assertNotIn('unrelated product', str(evidence))

    def test_drafts_cannot_be_mistaken_for_approved_reader_copy(self):
        packet = {'date': '2026-10-14', 'articles': [{'source_url': URL,
                  'source_published_at': '2026-10-13', 'evidence': {'sha256': 'abc'}}]}
        draft = review_drafts(packet)['drafts'][URL]
        self.assertIs(draft['source_reviewed'], False)
        self.assertEqual(draft['summary'], '')
        self.assertEqual(draft['evidence_refs'], [])
        self.assertEqual(draft['source_evidence_sha256'], 'abc')

    def test_specific_body_excludes_related_and_comments_inside_article(self):
        html = '''<article><div class="post_content"><h2>Methods</h2>
        <p>Control Rig animates the character directly inside Unreal Engine.</p>
        <ul><li>The team bakes corrective motion into separate animation layers.</li></ul>
        </div><div id="related_post"><p>UNRELATED article dated 2018.</p></div>
        <div id="comments"><p>COMMENT unrelated reader discussion.</p></div></article>'''
        evidence = extract_article_evidence(html, URL)
        self.assertEqual(evidence['selector'], '.post_content')
        self.assertEqual(len(evidence['blocks']), 2)
        self.assertEqual(evidence['blocks'][1]['section'], 'Methods')
        self.assertNotIn('UNRELATED', str(evidence))
        self.assertNotIn('COMMENT', str(evidence))

    def test_long_interview_retains_late_method_evidence(self):
        paras = ''.join(f'<p>Method {i}: ' + 'The artist uses rig controls and animation layers. ' * 5 + '</p>' for i in range(35))
        evidence = extract_article_evidence('<article>' + paras + '</article>', URL)
        self.assertGreater(evidence['char_count'], 1600)
        self.assertIn('Method 34:', evidence['blocks'][-1]['text'])
        self.assertFalse(evidence['truncated'])

    def test_bounded_body_reports_truncation(self):
        html = '<article>' + ''.join('<p>' + str(i) + 'x' * 800 + '</p>' for i in range(90)) + '</article>'
        evidence = extract_article_evidence(html, URL)
        self.assertLessEqual(evidence['char_count'], MAX_CHARS)
        self.assertTrue(evidence['truncated'])
        self.assertGreater(evidence['observed_char_count'], evidence['char_count'])

    def test_missing_body_does_not_use_navigation_paragraphs(self):
        meta = page_metadata({'html': '<title>Blender update</title><nav><p>' + 'Navigation description ' * 10 + '</p></nav>', 'url': URL})
        self.assertEqual(meta['article_evidence']['status'], 'body-missing')
        self.assertEqual(meta['description'], '')

    def test_article_body_without_article_tag(self):
        html = '<div itemprop="articleBody"><p>' + 'The renderer supports this measured output. ' * 8 + '</p><p>New output exports separate channels for compositing.</p></div>'
        evidence = extract_article_evidence(html, URL)
        self.assertEqual(evidence['status'], 'extracted')
        self.assertEqual(len(evidence['sha256']), 64)

    def test_nested_blocks_deduplicated_and_unsafe_links_excluded(self):
        html = '<article><ul><li><p>Export directly to the animation engine using the built-in plugin.</p></li></ul><p><a href="javascript:bad">Ignore unsafe target</a> and <a href="/docs">Plugin documentation</a>.</p></article>'
        evidence = extract_article_evidence(html, URL)
        self.assertEqual(len(evidence['blocks']), 2)
        self.assertEqual(evidence['links'], [{'label': 'Plugin documentation', 'url': 'https://example.com/docs'}])

    def test_review_packet_does_not_copy_html_or_owner_data(self):
        candidate = {'candidate_id': 'one', 'source_url': URL, 'profile': {'email': 'secret'},
                     'meta': {'html': 'RAW_HTML', 'title': 'Article', 'article_evidence': {'status': 'body-thin'}}}
        packet = review_record(candidate, ['generic analysis padding'])
        self.assertNotIn('RAW_HTML', str(packet))
        self.assertNotIn('secret', str(packet))
        self.assertEqual(packet['review_status'], 'needs-human-review')

    def test_loss_classes_are_per_article_and_explicitly_overlap(self):
        c = {'meta': {'article_evidence': {'status': 'extracted'}}}
        summary = loss_summary([c], [(c, ['generic analysis padding', 'generic analysis padding', 'old source requires label'])])
        self.assertEqual(summary['rejection_classes'], {'generic-analysis': 1, 'historical-label-missing': 1})
        self.assertTrue(summary['reason_counts_overlap'])


if __name__ == '__main__':
    unittest.main()
