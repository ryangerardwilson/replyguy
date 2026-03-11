import unittest
from unittest.mock import patch

from replyguy.status import render_status


class ReplyGuyStatusTests(unittest.TestCase):
    def test_running_status_hides_stale_queue_error_when_runtime_error_is_empty(self) -> None:
        queue = {
            "synced_at": "2026-03-11T07:01:14+00:00",
            "items": [
                {
                    "tweet_id": "2031469834354167973",
                    "generated_at": "2026-03-11T07:00:58+00:00",
                    "status": "pending",
                    "generation_error": "Error: No such file or directory (os error 2)",
                }
            ],
        }
        runtime = {
            "phase": "drafting",
            "job_id": "bookmark-sync-20260311-123127",
            "current": 4,
            "total": 34,
            "current_tweet_id": "2031469834354167973",
            "last_error": "",
        }
        with patch("replyguy.status.ensure_dirs"), patch(
            "replyguy.status.load_queue", return_value=queue
        ), patch("replyguy.status.load_runtime_status", return_value=runtime), patch(
            "replyguy.status._is_inhale_running", return_value=True
        ), patch("replyguy.status._latest_job_dir", return_value=None):
            rendered = render_status()

        self.assertIn("running      : yes", rendered)
        self.assertIn("latest_error : -", rendered)

    def test_stopped_status_shows_latest_queue_error_when_runtime_error_is_empty(self) -> None:
        queue = {
            "synced_at": "2026-03-11T07:01:14+00:00",
            "items": [
                {
                    "tweet_id": "2031469834354167973",
                    "generated_at": "2026-03-11T07:00:58+00:00",
                    "status": "pending",
                    "generation_error": "Error: No such file or directory (os error 2)",
                }
            ],
        }
        runtime = {
            "phase": "done",
            "job_id": "bookmark-sync-20260311-123127",
            "current": 34,
            "total": 34,
            "current_tweet_id": "",
            "last_error": "",
        }
        with patch("replyguy.status.ensure_dirs"), patch(
            "replyguy.status.load_queue", return_value=queue
        ), patch("replyguy.status.load_runtime_status", return_value=runtime), patch(
            "replyguy.status._is_inhale_running", return_value=False
        ), patch("replyguy.status._latest_job_dir", return_value=None):
            rendered = render_status()

        self.assertIn(
            "latest_error : 2031469834354167973: Error: No such file or directory (os error 2)",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
