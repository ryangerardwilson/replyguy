import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from replyguy.pipeline import sync_bookmark_queue


class ReplyGuyPipelineTests(unittest.TestCase):
    def test_sync_notifies_when_inhale_starts_and_finishes(self) -> None:
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
        self.assertEqual(notify.call_args_list[0].args, ("replyguy", "inhale started"))
        self.assertEqual(notify.call_args_list[-1].args, ("replyguy", "inhale done: bookmarks=0"))

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
                ("replyguy", "inhale done: bookmarks=2"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
