import unittest
from io import StringIO
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
        self.assertIn("replyguy inhale", help_output)
        self.assertIn("replyguy ti", help_output)
        self.assertIn("replyguy td", help_output)
        self.assertIn("replyguy st", help_output)
        self.assertIn("replyguy exhale", help_output)
        self.assertIn("replyguy status", help_output)
        self.assertNotIn("replyguy rant", help_output)
        self.assertNotIn("replyguy sync", help_output)
        self.assertNotIn("replyguy muse", help_output)
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

    def test_inhale_starts_background_job(self) -> None:
        with patch("replyguy.cli._spawn_background") as spawn_background:
            code = main(["inhale"])
        self.assertEqual(code, 0)
        spawn_background.assert_called_once_with("_inhale_bookmarks")

    def test_exhale_runs_interactive_session(self) -> None:
        with patch("replyguy.muse.run_muse_session", return_value=0) as run_session:
            code = main(["exhale"])
        self.assertEqual(code, 0)
        run_session.assert_called_once_with()

    def test_status_prints_rendered_status(self) -> None:
        with patch("replyguy.status.render_status", return_value="replyguy status\n") as render_status:
            with patch("sys.stdout", new=StringIO()) as stdout:
                code = main(["status"])
        self.assertEqual(code, 0)
        render_status.assert_called_once_with()
        self.assertEqual(stdout.getvalue(), "replyguy status\n\n")

    def test_ti_installs_timer(self) -> None:
        with patch("replyguy.cli._write_timer_units") as write_units, patch(
            "replyguy.cli._systemctl_user"
        ) as systemctl:
            code = main(["ti"])
        self.assertEqual(code, 0)
        write_units.assert_called_once_with()
        systemctl.assert_any_call("daemon-reload")
        systemctl.assert_any_call("enable", "--now", "replyguy.timer")

    def test_td_disables_timer(self) -> None:
        with patch("replyguy.cli._write_timer_units") as write_units, patch(
            "replyguy.cli._systemctl_user"
        ) as systemctl:
            code = main(["td"])
        self.assertEqual(code, 0)
        write_units.assert_called_once_with()
        systemctl.assert_called_with("disable", "--now", "replyguy.timer")

    def test_build_runtime_command_uses_launcher_only_when_frozen(self) -> None:
        with patch("sys.executable", "/tmp/replyguy"), patch("sys.frozen", True, create=True):
            self.assertEqual(_build_runtime_command("_inhale_bookmarks"), "/tmp/replyguy _inhale_bookmarks")

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
