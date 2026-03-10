from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import ReplyGuyError

REPO_ROOT = Path(__file__).resolve().parents[1]


class CodexResponder:
    def __init__(self, config: dict[str, Any]) -> None:
        self._model = str(config.get("codex_model") or "gpt-5-codex")
        self._reasoning_effort = str(config.get("codex_reasoning_effort") or "high")

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "replies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "source_url": {"type": "string"},
                            "source_excerpt": {"type": "string"},
                            "recommended_reply": {"type": "string"},
                            "alternate_replies": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "why_it_works": {"type": "string"},
                        },
                        "required": [
                            "source_url",
                            "source_excerpt",
                            "recommended_reply",
                            "alternate_replies",
                            "why_it_works",
                        ],
                    },
                },
                "skipped": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "item": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["item", "reason"],
                    },
                },
            },
            "required": ["replies", "skipped"],
        }
        prompt = (
            f"{system_prompt}\n\n"
            "Return only the final JSON object that matches the provided schema.\n\n"
            f"{user_prompt}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "schema.json"
            output_path = Path(tmp) / "output.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            command = [
                "codex",
                "exec",
                "--skip-git-repo-check",
                "--color",
                "never",
                "-s",
                "read-only",
                "-C",
                str(REPO_ROOT),
                "-m",
                self._model,
                "-c",
                f'model_reasoning_effort="{self._reasoning_effort}"',
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "-",
            ]
            result = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise ReplyGuyError((result.stderr or result.stdout or "codex exec failed").strip())
            raw = output_path.read_text(encoding="utf-8").strip()
            if not raw:
                raise ReplyGuyError("codex exec returned empty output")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ReplyGuyError("codex exec output was not a JSON object")
            return parsed
