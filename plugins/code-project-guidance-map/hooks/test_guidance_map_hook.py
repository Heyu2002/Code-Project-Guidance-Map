#!/usr/bin/env python3
"""Tests for the code-project-guidance-map hook script."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import hook_state


HOOK_SCRIPT = Path(__file__).resolve().parent / "guidance_map_hook.py"
GUIDANCE_MAP = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "code-project-guidance-map"
    / "scripts"
    / "guidance_map.py"
)


GUIDANCE = """### Agent Editing Rules

- [MUST] Keep App changes inside `app`.

### Task Routing

- To add an API: edit `app/routes`.

### Module Dependency Rules

- `app` owns application behavior.

### Module Index

#### App

- Module Path: `app`
- Module Guide: `.agents/guidance-map/modules/app.md`
- Owns: Application behavior.
- Change here when: Application behavior changes.
- Do not put here: Shared utilities.
"""

MODULE_GUIDE = """# App

- Module Path: `app`
- Owns: Application behavior.
- Change here when: Application behavior changes.
- Do not put here: Shared utilities.
- Key entry points: `app/`
"""


class GuidanceMapHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.env = os.environ.copy()
        self.env["CODE_PROJECT_GUIDANCE_MAP_KEY_HOME"] = str(Path(self.tmp.name) / "keys")
        self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE"] = str(Path(self.tmp.name) / "hook-state.json")
        self.env.pop("CODE_PROJECT_GUIDANCE_MAP_SECRET", None)
        self.env.pop("CODE_PROJECT_GUIDANCE_MAP_KEY_FILE", None)
        self.env.pop("CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL", None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_hook(self, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )

    def parse_hook_output(self, result: subprocess.CompletedProcess[str]) -> dict[str, object] | None:
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)

    def write_valid_guide(self) -> None:
        module_file = self.repo / ".agents" / "guidance-map" / "modules" / "app.md"
        module_file.parent.mkdir(parents=True, exist_ok=True)
        module_file.write_text(MODULE_GUIDE, encoding="utf-8")
        guidance_file = Path(self.tmp.name) / "guidance.md"
        guidance_file.write_text(GUIDANCE, encoding="utf-8")
        subprocess.run(
            [
                sys.executable,
                str(GUIDANCE_MAP),
                "update",
                "--repo",
                str(self.repo),
                "--guidance-file",
                str(guidance_file),
                "--timestamp",
                "2030-01-01T00:00:00Z",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=True,
        )

    def test_session_start_injects_context_when_guide_missing(self) -> None:
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "SessionStart",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "source": "startup",
                "transcript_path": None,
            }
        )
        output = self.parse_hook_output(result)
        self.assertIsNotNone(output)
        context = output["hookSpecificOutput"]["additionalContext"]  # type: ignore[index]
        self.assertIn("AGENTS.md project index or module guides are stale, missing", context)
        self.assertIn("$code-project-guidance-map", context)
        self.assertIn("bounded module subagents", context)

    def test_repeated_same_session_action_is_suppressed(self) -> None:
        payload = {
            "cwd": str(self.repo),
            "hook_event_name": "SessionStart",
            "model": "test",
            "permission_mode": "default",
            "session_id": "session",
            "source": "startup",
            "transcript_path": None,
        }
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))
        self.assertIsNone(self.parse_hook_output(self.run_hook(payload)))

    def test_same_action_is_suppressed_across_start_and_prompt(self) -> None:
        start_payload = {
            "cwd": str(self.repo),
            "hook_event_name": "SessionStart",
            "model": "test",
            "permission_mode": "default",
            "session_id": "session",
            "source": "startup",
            "transcript_path": None,
        }
        prompt_payload = {
            "cwd": str(self.repo),
            "hook_event_name": "UserPromptSubmit",
            "model": "test",
            "permission_mode": "default",
            "prompt": "Implement a new REST API endpoint.",
            "session_id": "session",
            "transcript_path": None,
            "turn_id": "turn",
        }
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(start_payload)))
        self.assertIsNone(self.parse_hook_output(self.run_hook(prompt_payload)))

    def test_different_session_is_not_suppressed(self) -> None:
        payload = {
            "cwd": str(self.repo),
            "hook_event_name": "SessionStart",
            "model": "test",
            "permission_mode": "default",
            "session_id": "session-a",
            "source": "startup",
            "transcript_path": None,
        }
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))
        payload["session_id"] = "session-b"
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))

    def test_different_project_is_not_suppressed(self) -> None:
        payload = {
            "cwd": str(self.repo),
            "hook_event_name": "SessionStart",
            "model": "test",
            "permission_mode": "default",
            "session_id": "session",
            "source": "startup",
            "transcript_path": None,
        }
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))
        other_repo = Path(self.tmp.name) / "other"
        other_repo.mkdir()
        payload["cwd"] = str(other_repo)
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))

    def test_user_prompt_submit_skips_non_code_prompt(self) -> None:
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "test",
                "permission_mode": "default",
                "prompt": "Summarize the project at a high level.",
                "session_id": "session",
                "transcript_path": None,
                "turn_id": "turn",
            }
        )
        self.assertIsNone(self.parse_hook_output(result))

    def test_user_prompt_submit_skips_non_code_action_prompt(self) -> None:
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "test",
                "permission_mode": "default",
                "prompt": "Write a poem about testing.",
                "session_id": "session",
                "transcript_path": None,
                "turn_id": "turn",
            }
        )
        self.assertIsNone(self.parse_hook_output(result))

    def test_user_prompt_submit_injects_context_for_code_edit_when_stale(self) -> None:
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "test",
                "permission_mode": "default",
                "prompt": "Implement a new REST API endpoint.",
                "session_id": "session",
                "transcript_path": None,
                "turn_id": "turn",
            }
        )
        output = self.parse_hook_output(result)
        self.assertIsNotNone(output)
        context = output["hookSpecificOutput"]["additionalContext"]  # type: ignore[index]
        self.assertIn("this looks like a code-edit request", context)
        self.assertIn("$code-project-guidance-map", context)
        self.assertIn("signed project index", context)
        self.assertIn("bounded module subagents", context)

    def test_user_prompt_submit_injects_context_for_chinese_code_edit(self) -> None:
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "test",
                "permission_mode": "default",
                "prompt": "\u5b9e\u73b0\u4e00\u4e2a\u65b0\u7684\u63a5\u53e3",
                "session_id": "session",
                "transcript_path": None,
                "turn_id": "turn",
            }
        )
        output = self.parse_hook_output(result)
        self.assertIsNotNone(output)
        context = output["hookSpecificOutput"]["additionalContext"]  # type: ignore[index]
        self.assertIn("this looks like a code-edit request", context)

    def test_stop_has_no_output_without_code_edit_prompt(self) -> None:
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "Stop",
                "last_assistant_message": "done",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "stop_hook_active": False,
                "transcript_path": None,
                "turn_id": "turn",
            }
        )
        self.assertIsNone(self.parse_hook_output(result))

    def test_stop_outputs_once_after_code_edit_prompt(self) -> None:
        edit_payload = {
            "cwd": str(self.repo),
            "hook_event_name": "UserPromptSubmit",
            "model": "test",
            "permission_mode": "default",
            "prompt": "Implement a new REST API endpoint.",
            "session_id": "session",
            "transcript_path": None,
            "turn_id": "turn",
        }
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(edit_payload)))
        stop_payload = {
            "cwd": str(self.repo),
            "hook_event_name": "Stop",
            "last_assistant_message": "done",
            "model": "test",
            "permission_mode": "default",
            "session_id": "session",
            "stop_hook_active": False,
            "transcript_path": None,
            "turn_id": "turn",
        }
        output = self.parse_hook_output(self.run_hook(stop_payload))
        self.assertIsNotNone(output)
        context = output["systemMessage"]  # type: ignore[index]
        self.assertIn("this task finished", context)
        self.assertIn("$code-project-guidance-map", context)
        self.assertNotIn("hookSpecificOutput", output)
        self.assertIsNone(self.parse_hook_output(self.run_hook(stop_payload)))

    def test_hook_level_off_suppresses_output(self) -> None:
        self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL"] = "off"
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "SessionStart",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "source": "startup",
                "transcript_path": None,
            }
        )
        self.assertIsNone(self.parse_hook_output(result))

    def test_hook_level_error_suppresses_warning_stale(self) -> None:
        self.write_valid_guide()
        module_file = self.repo / ".agents" / "guidance-map" / "modules" / "app.md"
        module_file.write_text(module_file.read_text(encoding="utf-8").replace("Application behavior", "Changed behavior"), encoding="utf-8")
        self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL"] = "error"
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "SessionStart",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "source": "startup",
                "transcript_path": None,
            }
        )
        self.assertIsNone(self.parse_hook_output(result))

    def test_hook_level_error_keeps_error_output(self) -> None:
        self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL"] = "error"
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "SessionStart",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "source": "startup",
                "transcript_path": None,
            }
        )
        self.assertIsNotNone(self.parse_hook_output(result))

    def test_hook_state_level_all_emits_info_events(self) -> None:
        event = hook_state.HookEvent(
            event_name="SessionStart",
            project_id="repo:test",
            session_id="session",
            prompt_is_code_edit=False,
            severity="info",
            recommended_action="review_changed_files",
            stale=False,
            has_error=False,
        )
        state = {"version": 1, "projects": {}}
        self.assertFalse(hook_state.transition(state, event, "stale").should_emit)
        self.assertTrue(hook_state.transition(state, event, "all").should_emit)

    def test_corrupt_state_file_does_not_fail_hook(self) -> None:
        Path(self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE"]).write_text("{bad json", encoding="utf-8")
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "SessionStart",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "source": "startup",
                "transcript_path": None,
            }
        )
        self.assertIsNotNone(self.parse_hook_output(result))

    def test_no_context_when_guide_is_current(self) -> None:
        self.write_valid_guide()
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "SessionStart",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "source": "startup",
                "transcript_path": None,
            }
        )
        self.assertIsNone(self.parse_hook_output(result))

    def test_stop_has_no_output_when_guide_is_current(self) -> None:
        self.write_valid_guide()
        result = self.run_hook(
            {
                "cwd": str(self.repo),
                "hook_event_name": "Stop",
                "last_assistant_message": "done",
                "model": "test",
                "permission_mode": "default",
                "session_id": "session",
                "stop_hook_active": False,
                "transcript_path": None,
                "turn_id": "turn",
            }
        )
        self.assertIsNone(self.parse_hook_output(result))


if __name__ == "__main__":
    unittest.main()
