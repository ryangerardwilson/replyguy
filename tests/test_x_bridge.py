import json
import unittest
from unittest.mock import MagicMock, patch

from replyguy.x_bridge import list_bookmarks, post_reply, remove_bookmark, remove_bookmark_background


class XBridgeTests(unittest.TestCase):
    def test_list_bookmarks_uses_declarative_x_command(self) -> None:
        payload = {"bookmarks": [{"tweet_id": "123"}]}
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""},
        )()
        with patch("subprocess.run", return_value=completed) as subprocess_run:
            bookmarks = list_bookmarks({"x_command": "x-custom"}, 25)

        self.assertEqual(bookmarks, [{"tweet_id": "123"}])
        self.assertEqual(
            subprocess_run.call_args.args[0],
            ["x-custom", "bookmarks", "list", "json", "limit", "25"],
        )

    def test_post_reply_uses_declarative_x_command(self) -> None:
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "Posted reply to X. id=99\n", "stderr": ""},
        )()
        with patch("subprocess.run", return_value=completed) as subprocess_run:
            reply_id = post_reply({"x_command": "x-custom"}, "123", "hello there")

        self.assertEqual(reply_id, "99")
        self.assertEqual(
            subprocess_run.call_args.args[0],
            ["x-custom", "reply", "to", "123", "body", "hello there"],
        )

    def test_remove_bookmark_uses_declarative_x_command(self) -> None:
        completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("subprocess.run", return_value=completed) as subprocess_run:
            remove_bookmark({"x_command": "x-custom"}, "123")

        self.assertEqual(
            subprocess_run.call_args.args[0],
            ["x-custom", "bookmarks", "remove", "123"],
        )

    def test_remove_bookmark_background_uses_declarative_x_command(self) -> None:
        with patch("subprocess.Popen", return_value=MagicMock()) as popen:
            remove_bookmark_background({"x_command": "x-custom"}, "123")

        self.assertEqual(
            popen.call_args.args[0],
            ["x-custom", "bookmarks", "remove", "123"],
        )


if __name__ == "__main__":
    unittest.main()
