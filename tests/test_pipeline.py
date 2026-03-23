import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from replyguy.pipeline import sync_bookmark_queue


class ReplyGuyPipelineTests(unittest.TestCase):
    def test_sync_notifies_when_nothing_to_inhale(self) -> None:
        with TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": str(Path(tmp) / "config"),
                "XDG_STATE_HOME": str(Path(tmp) / "state"),
                "XDG_CACHE_HOME": str(Path(tmp) / "cache"),
            }
            with patch.dict("os.environ", env, clear=False):
                with patch("replyguy.pipeline.load_config", return_value={}):
                    with patch("replyguy.pipeline.CodexResponder"):
                        with patch("replyguy.pipeline.list_bookmarks", return_value=[]):
                            with patch("replyguy.pipeline.notify") as notify:
                                result = sync_bookmark_queue()

        self.assertEqual(result.summary, "bookmarks=0")
        self.assertEqual(result.new_inhaled, 0)
        self.assertEqual(result.awaiting_exhale, 0)
        self.assertEqual([call.args for call in notify.call_args_list], [("replyguy", "nothing to inhale")])

    def test_sync_notifies_when_nothing_left_to_inhale_but_queue_is_waiting(self) -> None:
        existing_item = {
            "tweet_id": "1",
            "author_username": "one",
            "text": "first",
            "url": "https://x.com/example/status/1",
            "reply_options": ["reply"],
            "status": "pending",
            "generated_at": "2026-03-11T00:00:00+00:00",
            "why_it_works": "",
            "skip_reason": "",
            "posted_reply_id": "",
            "bookmark_removed": False,
            "generation_error": "",
        }
        with TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": str(Path(tmp) / "config"),
                "XDG_STATE_HOME": str(Path(tmp) / "state"),
                "XDG_CACHE_HOME": str(Path(tmp) / "cache"),
            }
            with patch.dict("os.environ", env, clear=False):
                with patch("replyguy.pipeline.load_config", return_value={}):
                    with patch("replyguy.pipeline.CodexResponder"):
                        with patch("replyguy.pipeline.load_queue", return_value={"synced_at": "", "items": [existing_item]}):
                            with patch("replyguy.pipeline.list_bookmarks", return_value=[]):
                                with patch("replyguy.pipeline.notify") as notify:
                                    result = sync_bookmark_queue()

        self.assertEqual(result.summary, "bookmarks=0")
        self.assertEqual(result.new_inhaled, 0)
        self.assertEqual(result.awaiting_exhale, 1)
        self.assertEqual(
            [call.args for call in notify.call_args_list],
            [("replyguy", "nothing left to inhale, 1 awaiting exhale")],
        )

    def test_sync_does_not_notify_for_each_processed_bookmark(self) -> None:
        bookmarks = [
            {
                "tweet_id": "1",
                "author_username": "one",
                "text": "first",
                "url": "https://x.com/example/status/1",
            },
            {
                "tweet_id": "2",
                "author_username": "two",
                "text": "second",
                "url": "https://x.com/example/status/2",
            },
        ]
        draft = {
            "tweet_id": "1",
            "reply_options": ["reply"],
            "status": "pending",
            "generated_at": "2026-03-11T00:00:00+00:00",
            "why_it_works": "",
            "skip_reason": "",
            "posted_reply_id": "",
            "bookmark_removed": False,
            "generation_error": "",
        }
        with TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": str(Path(tmp) / "config"),
                "XDG_STATE_HOME": str(Path(tmp) / "state"),
                "XDG_CACHE_HOME": str(Path(tmp) / "cache"),
            }
            with patch.dict("os.environ", env, clear=False):
                with patch("replyguy.pipeline.load_config", return_value={}):
                    with patch("replyguy.pipeline.CodexResponder"):
                        with patch("replyguy.pipeline.list_bookmarks", return_value=bookmarks):
                            with patch("replyguy.pipeline._draft_bookmark", return_value=draft):
                                with patch("replyguy.pipeline.notify") as notify:
                                    sync_bookmark_queue()

        self.assertEqual(
            [call.args for call in notify.call_args_list],
            [
                ("replyguy", "inhale started"),
                ("replyguy", "inhale done: 2 new, 2 awaiting exhale"),
            ],
        )

    def test_sync_reports_only_new_bookmarks_when_existing_queue_matches(self) -> None:
        existing_item = {
            "tweet_id": "1",
            "author_username": "one",
            "text": "first",
            "url": "https://x.com/example/status/1",
            "reply_options": ["reply"],
            "status": "pending",
            "generated_at": "2026-03-11T00:00:00+00:00",
            "why_it_works": "",
            "skip_reason": "",
            "posted_reply_id": "",
            "bookmark_removed": False,
            "generation_error": "",
        }
        bookmark = {
            "tweet_id": "1",
            "author_username": "one",
            "text": "first updated",
            "url": "https://x.com/example/status/1",
        }
        with TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": str(Path(tmp) / "config"),
                "XDG_STATE_HOME": str(Path(tmp) / "state"),
                "XDG_CACHE_HOME": str(Path(tmp) / "cache"),
            }
            with patch.dict("os.environ", env, clear=False):
                with patch("replyguy.pipeline.load_config", return_value={}):
                    with patch("replyguy.pipeline.CodexResponder"):
                        with patch(
                            "replyguy.pipeline.load_queue",
                            return_value={"synced_at": "", "items": [deepcopy(existing_item)]},
                        ):
                            with patch("replyguy.pipeline.list_bookmarks", return_value=[bookmark]):
                                with patch("replyguy.pipeline.notify") as notify:
                                    result = sync_bookmark_queue()

        self.assertEqual(result.summary, "bookmarks=1")
        self.assertEqual(result.new_inhaled, 0)
        self.assertEqual(result.awaiting_exhale, 1)
        self.assertEqual(
            [call.args for call in notify.call_args_list],
            [
                ("replyguy", "inhale started"),
                ("replyguy", "nothing left to inhale, 1 awaiting exhale"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
