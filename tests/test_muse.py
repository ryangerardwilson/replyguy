import unittest
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from replyguy.muse import run_muse_session


class ReplyGuyMuseTests(unittest.TestCase):
    def test_exhale_tells_user_to_inhale_when_queue_is_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": f"{tmp}/config",
                "XDG_STATE_HOME": f"{tmp}/state",
                "XDG_CACHE_HOME": f"{tmp}/cache",
            }
            with patch.dict("os.environ", env, clear=False):
                with patch("replyguy.muse.load_config", return_value={}):
                    with patch("sys.stdout", new=StringIO()) as stdout:
                        code = run_muse_session()

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "Nothing is queued for exhale. Run `replyguy inhale` first.\n")


if __name__ == "__main__":
    unittest.main()
