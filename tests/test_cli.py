import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from replyguy.cli import _build_runtime_command, main


class ReplyGuyCliTests(unittest.TestCase):
    def test_no_arg_matches_help(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main([])
            no_arg_output = stdout.getvalue()
        with patch("sys.stdout", new=StringIO()) as stdout:
            help_code = main(["-h"])
            help_output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(help_code, 0)
        self.assertEqual(no_arg_output, help_output)
        self.assertIn("Replyguy CLI", help_output)
        self.assertIn("features:", help_output)
        self.assertIn("replyguy rant", help_output)
        self.assertIn("replyguy rant ~/tmp/ideas.txt", help_output)
        self.assertIn("replyguy muse", help_output)
        self.assertNotIn("commands:", help_output)

    def test_version_prints_single_value(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["-v"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), "0.1.2")

    def test_conf_prefers_visual(self) -> None:
        with TemporaryDirectory() as tmp:
            with patch.dict(
                "os.environ",
                {"XDG_CONFIG_HOME": f"{tmp}/config", "VISUAL": "nvim"},
                clear=False,
            ):
                with patch("subprocess.run") as subprocess_run:
                    subprocess_run.return_value.returncode = 0
                    code = main(["conf"])
        self.assertEqual(code, 0)
        self.assertEqual(subprocess_run.call_args.args[0][0], "nvim")

    def test_rant_processes_and_clears_on_success(self) -> None:
        with TemporaryDirectory() as tmp:
            with patch.dict(
                "os.environ",
                {
                    "XDG_CONFIG_HOME": f"{tmp}/config",
                    "XDG_STATE_HOME": f"{tmp}/state",
                    "XDG_CACHE_HOME": f"{tmp}/cache",
                },
                clear=False,
            ):
                rant_path = Path(tmp) / "state" / "replyguy" / "rant.md"
                rant_path.parent.mkdir(parents=True, exist_ok=True)
                rant_path.write_text("post about AI agents\n", encoding="utf-8")
                with patch("replyguy.cli.open_in_editor", return_value=0):
                    with patch("replyguy.cli._spawn_background") as spawn_background:
                        code = main(["rant"])
                self.assertEqual(code, 0)
                spawn_background.assert_called_once_with("_rant_live")

    def test_rant_with_input_path_skips_editor(self) -> None:
        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "ideas.txt"
            input_path.write_text("post about agents\n", encoding="utf-8")
            with patch("replyguy.cli.open_in_editor") as open_in_editor_mock:
                with patch("replyguy.cli._spawn_background") as spawn_background:
                    code = main(["rant", str(input_path)])
        self.assertEqual(code, 0)
        open_in_editor_mock.assert_not_called()
        spawn_background.assert_called_once_with("_rant_file", str(input_path))

    def test_muse_clears_live_file_after_editor_closes(self) -> None:
        with TemporaryDirectory() as tmp:
            with patch.dict(
                "os.environ",
                {
                    "XDG_STATE_HOME": f"{tmp}/state",
                },
                clear=False,
            ):
                muse_path = Path(tmp) / "state" / "replyguy" / "muse.md"
                muse_path.parent.mkdir(parents=True, exist_ok=True)
                muse_path.write_text("hello\n", encoding="utf-8")
                with patch("replyguy.cli.open_in_editor", return_value=0):
                    code = main(["muse"])
                self.assertEqual(muse_path.read_text(encoding="utf-8"), "")
        self.assertEqual(code, 0)

    def test_build_runtime_command_uses_launcher_only_when_frozen(self) -> None:
        with patch("sys.executable", "/tmp/replyguy"), patch("sys.frozen", True, create=True):
            self.assertEqual(_build_runtime_command("_rant_live"), "/tmp/replyguy _rant_live")

    def test_upgrade_delegates_to_installer_upgrade_mode(self) -> None:
        fake_response = type("Response", (), {"read": lambda self: b"#!/usr/bin/env bash\n"})()

        class _Context:
            def __enter__(self_inner):
                return fake_response

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        with patch("urllib.request.urlopen", return_value=_Context()):
            with patch("subprocess.run") as subprocess_run:
                subprocess_run.return_value.returncode = 0
                code = main(["-u"])
        self.assertEqual(code, 0)
        self.assertIn("-u", subprocess_run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
