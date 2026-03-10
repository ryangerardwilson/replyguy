import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from replyguy.cli import _build_runtime_command, main, write_timer_units


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
        self.assertIn("replyguy gi", help_output)
        self.assertIn("replyguy go", help_output)
        self.assertNotIn("commands:", help_output)

    def test_version_prints_single_value(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            code = main(["-v"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), "0.0.0")

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

    def test_gi_processes_and_clears_on_success(self) -> None:
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
                gi_path = Path(tmp) / "state" / "replyguy" / "gi.md"
                gi_path.parent.mkdir(parents=True, exist_ok=True)
                gi_path.write_text("post about AI agents\n", encoding="utf-8")
                with patch("replyguy.cli.open_in_editor", return_value=0):
                    with patch("replyguy.pipeline.process_gi_file") as process_gi_file:
                        process_gi_file.return_value = type(
                            "Result",
                            (),
                            {"summary": "posted=yes replies=0"},
                        )()
                        code = main(["gi"])
                self.assertEqual(code, 0)

    def test_build_runtime_command_uses_launcher_only_when_frozen(self) -> None:
        with patch("sys.executable", "/tmp/replyguy"), patch("sys.frozen", True, create=True):
            self.assertEqual(_build_runtime_command("_tick"), "/tmp/replyguy _tick")

    def test_write_timer_units_uses_hidden_tick(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch("replyguy.cli.Path.home", return_value=home):
                with patch.dict(
                    "os.environ",
                    {
                        "XDG_CONFIG_HOME": f"{tmp}/config",
                        "XDG_STATE_HOME": f"{tmp}/state",
                        "XDG_CACHE_HOME": f"{tmp}/cache",
                    },
                    clear=False,
                ):
                    write_timer_units()
            service_path = home / ".config" / "systemd" / "user" / "replyguy.service"
            service_body = service_path.read_text(encoding="utf-8")
            self.assertIn("_tick", service_body)

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
