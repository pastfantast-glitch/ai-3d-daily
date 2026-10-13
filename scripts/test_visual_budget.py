import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import extract_visual_assets as visual


class BudgetTests(unittest.TestCase):
    def test_only_verified_same_day_real_images_can_be_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            visual_root = root / 'assets/visual'
            (visual_root / '2026-10-13').mkdir(parents=True)
            (root / 'data/publish').mkdir(parents=True)
            asset = visual_root / '2026-10-13/article.jpg'
            asset.write_bytes(b'verified fixture')
            report = {'date':'2026-10-13','entries':[{'id':'article','page_url':'https://example.invalid/a','asset_path':'assets/visual/2026-10-13/article.jpg','status':'ok'}, {'id':'fallback','page_url':'https://example.invalid/b','asset_path':'assets/visual/2026-10-13/article.jpg','status':'fallback_card'}]}
            (visual_root / '2026-10-13/manifest.json').write_text(json.dumps(report))
            done = root / 'data/publish/2026-10-13.done.json'
            with patch.object(visual,'ROOT',root), patch.object(visual,'VISUAL_ROOT',visual_root):
                self.assertEqual(visual.verified_visual_cache('2026-10-13'), {})
                done.write_text(json.dumps({'date':'2026-10-13','state':'DONE','qa':{'pages':'pass'}}))
                cache = visual.verified_visual_cache('2026-10-13')
                self.assertEqual(set(cache), {('article','https://example.invalid/a')})
                self.assertEqual(visual.verified_visual_cache('2026-10-14'), {})

    def test_expired_item_does_not_make_another_request(self):
        session = Mock()
        session._visual_deadline = 10
        with patch.object(visual.time,'monotonic',return_value=10), self.assertRaises(TimeoutError):
            visual.request_with_retry(session,'https://example.invalid/image.jpg')
        session.get.assert_not_called()

    def test_stream_stops_at_item_deadline_and_closes_response(self):
        session = Mock()
        session._visual_deadline = 10
        response = Mock(status_code=200)
        response.iter_content.return_value = [b'image']
        session.get.return_value = response
        with patch.object(visual.time,'monotonic',side_effect=[9,10,10]), self.assertRaises(TimeoutError):
            visual.request_with_retry(session,'https://example.invalid/image.jpg')
        session.get.assert_called_once()
        self.assertEqual(session.get.call_args.kwargs['timeout'],1)
        response.close.assert_called_once()

    def test_blocked_and_oversized_responses_are_not_blindly_retried(self):
        for status, chunks, error in [(403,[],PermissionError),(200,[b'1234'],ValueError)]:
            with self.subTest(status=status):
                session = Mock()
                session._visual_deadline = None
                response = Mock(status_code=status)
                response.iter_content.return_value = chunks
                session.get.return_value = response
                with patch.object(visual,'MAX_BYTES',3), self.assertRaises(error):
                    visual.request_with_retry(session,'https://example.invalid/image.jpg')
                session.get.assert_called_once()
                response.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
