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


if __name__ == "__main__":
    unittest.main()
