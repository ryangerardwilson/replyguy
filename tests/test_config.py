from __future__ import annotations

import json
import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from replyguy.config import OLD_REPLY_GUIDELINES, REPLY_GUIDELINES, load_config
from replyguy.paths import config_path


class ConfigTests(TestCase):
    def test_load_config_migrates_old_root_reply_guidelines_path(self) -> None:
        with TemporaryDirectory() as tmp:
            env = {
                "XDG_CONFIG_HOME": f"{tmp}/config",
                "XDG_STATE_HOME": f"{tmp}/state",
                "XDG_CACHE_HOME": f"{tmp}/cache",
            }
            with patch.dict(os.environ, env, clear=False):
                config_path().parent.mkdir(parents=True, exist_ok=True)
                config_path().write_text(
                    json.dumps({"codex_context_paths": [OLD_REPLY_GUIDELINES]})
                    + "\n",
                    encoding="utf-8",
                )

                config = load_config()

                self.assertEqual(config["codex_context_paths"], [REPLY_GUIDELINES])
                saved = json.loads(config_path().read_text(encoding="utf-8"))
                self.assertEqual(saved["codex_context_paths"], [REPLY_GUIDELINES])
