"""Discovery and reserve retention must never weaken admission or persist bodies."""
import unittest
from content_supply import section_links, retained_entries, reserve_output


class ContentSupplyTests(unittest.TestCase):
    def test_only_declared_same_publisher_topic_indexes_are_followed(self):
        html = '''<a href="/category/blender">Blender</a><a href="/category/blender">Again</a>
          <a href="https://elsewhere.test/category/vfx">VFX</a><a href="/login">Training</a>
          <a href="/category/finance">Finance</a><a href="/tutorials/">Tutorials</a>
          <a href="/category/animation?page=2">Animation</a>'''
        same = lambda u: u.startswith('https://publisher.test/')
        self.assertEqual(section_links(html, 'https://publisher.test/', same, 4),
                         ['https://publisher.test/category/blender', 'https://publisher.test/tutorials'])
        self.assertEqual(len(section_links(html, 'https://publisher.test/', same, 1)), 1)
        self.assertEqual(section_links(html, 'https://publisher.test/', same, 0), [])

    def test_reserve_rechecks_exclude_published_expired_and_invalid_dates(self):
        def row(n, date):
            return dict(source_url=f'https://publisher.test/{n}', discovered_for=date)
        entries = [row(1, '2026-11-08'), row(2, '2026-11-01'), row(3, '2025-01-01'),
                   row(4, '2026-11-10'), row(5, 'unknown')]
        retained = retained_entries(entries, '2026-11-09', {'https://publisher.test/2'}, 180)
        self.assertEqual([x['source_url'] for x in retained], ['https://publisher.test/1'])

    def test_temporary_failure_survives_without_bodies_and_ttl_is_not_reset(self):
        previous = dict(id='a', source_id='s', title='A', source_url='https://publisher.test/a',
                        category='blender-dcc', subcategory='blender', ranking_score=80,
                        discovered_for='2026-11-01', html='private', article_evidence={'raw':'private'})
        candidate = {**previous, 'candidate_id':'a'}
        verified = reserve_output([candidate], [previous], [previous], '2026-11-09', 80)
        retry = reserve_output([], [previous], [previous], '2026-11-09', 80)
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0]['discovered_for'], '2026-11-01')
        self.assertEqual(retry[0]['refresh_status'], 'temporarily-unavailable')
        for result in verified + retry:
            self.assertNotIn('html', result)
            self.assertNotIn('article_evidence', result)
        self.assertEqual(reserve_output([candidate], [], [], '2026-11-09', 0), [])


if __name__ == '__main__':
    unittest.main()
