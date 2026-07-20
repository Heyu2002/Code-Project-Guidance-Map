#!/usr/bin/env python3
"""Tests for the modification-only code-project-guidance-map hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import hook_state


HOOK_DIR = Path(__file__).resolve().parent
HOOK_SCRIPT = HOOK_DIR / "guidance_map_hook.py"
HOOK_CONFIG = HOOK_DIR / "hooks.json"
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
        self.env["CODE_PROJECT_GUIDANCE_MAP_BUILD_HOME"] = str(Path(self.tmp.name) / "build-state")
        self.env.pop("CODE_PROJECT_GUIDANCE_MAP_SECRET", None)
        self.env.pop("CODE_PROJECT_GUIDANCE_MAP_KEY_FILE", None)
        self.env.pop("CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL", None)
        self.git("init")
        self.git("config", "user.email", "hook-test@example.com")
        self.git("config", "user.name", "Hook Test")
        (self.repo / "README.md").write_text("seed\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-m", "seed")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

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

    def stop_payload(self, session_id: str = "session") -> dict[str, object]:
        return {
            "cwd": str(self.repo),
            "hook_event_name": "Stop",
            "last_assistant_message": "done",
            "model": "test",
            "permission_mode": "default",
            "session_id": session_id,
            "stop_hook_active": False,
            "transcript_path": None,
            "turn_id": "turn",
        }

    def write_modified_source(self, text: str = "print('changed')\n") -> None:
        source = self.repo / "app" / "routes.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(text, encoding="utf-8")

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
        self.git("add", "AGENTS.md", ".agents")
        self.git("commit", "-m", "guidance")

    def test_hook_config_registers_only_stop(self) -> None:
        config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(set(config["hooks"]), {"Stop"})

    def test_session_start_and_prompt_events_are_ignored(self) -> None:
        for event_name in ("SessionStart", "UserPromptSubmit"):
            payload = {
                "cwd": str(self.repo),
                "hook_event_name": event_name,
                "prompt": "Implement a new REST API endpoint.",
                "session_id": "session",
            }
            self.assertIsNone(self.parse_hook_output(self.run_hook(payload)))

    def test_stop_has_no_output_without_project_changes(self) -> None:
        self.assertIsNone(self.parse_hook_output(self.run_hook(self.stop_payload())))

    def test_stop_emits_after_project_modification(self) -> None:
        self.write_modified_source()
        output = self.parse_hook_output(self.run_hook(self.stop_payload()))
        self.assertIsNotNone(output)
        context = output["systemMessage"]  # type: ignore[index]
        self.assertIn("modification hook", context)
        self.assertIn("Start or synchronize the dedicated builder", context)
        self.assertIn("finalize this thread immediately", context)
        self.assertIn("Do not wait for, poll, read, or follow", context)
        self.assertNotIn("hookSpecificOutput", output)

    def test_same_modification_is_emitted_once_per_session(self) -> None:
        self.write_modified_source()
        payload = self.stop_payload()
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))
        self.assertIsNone(self.parse_hook_output(self.run_hook(payload)))

    def test_same_path_with_new_content_emits_again(self) -> None:
        self.write_modified_source("print('first')\n")
        payload = self.stop_payload()
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))
        self.write_modified_source("print('second')\n")
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(payload)))

    def test_same_modification_can_emit_in_another_session(self) -> None:
        self.write_modified_source()
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(self.stop_payload("session-a"))))
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(self.stop_payload("session-b"))))

    def test_active_builder_suppresses_stop_continuation(self) -> None:
        self.write_modified_source()
        build_env = self.env.copy()
        build_env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] = "Codex Desktop"
        result = subprocess.run(
            [sys.executable, str(GUIDANCE_MAP), "build", "--repo", str(self.repo), "--launcher", "desktop"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=build_env,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)["status"], "desktop_launch_required")
        self.assertIsNone(self.parse_hook_output(self.run_hook(self.stop_payload())))

    def test_hook_level_off_suppresses_modified_project(self) -> None:
        self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL"] = "off"
        self.write_modified_source()
        self.assertIsNone(self.parse_hook_output(self.run_hook(self.stop_payload())))

    def test_hook_level_all_emits_info_change(self) -> None:
        event = hook_state.HookEvent(
            event_name="Stop",
            project_id="repo:test",
            session_id="session",
            severity="info",
            recommended_action="review_changed_files",
            stale=False,
            has_error=False,
            has_changes=True,
            change_fingerprint="fingerprint",
            build_active=False,
        )
        state = {"version": 1, "projects": {}}
        self.assertFalse(hook_state.transition(state, event, "stale").should_emit)
        self.assertTrue(hook_state.transition(state, event, "all").should_emit)

    def test_active_builder_never_emits(self) -> None:
        event = hook_state.HookEvent(
            event_name="Stop",
            project_id="repo:test",
            session_id="session",
            severity="error",
            recommended_action="full_refresh",
            stale=True,
            has_error=False,
            has_changes=True,
            change_fingerprint="fingerprint",
            build_active=True,
        )
        decision = hook_state.transition({"version": 1, "projects": {}}, event, "all")
        self.assertFalse(decision.should_emit)

    def test_corrupt_state_file_does_not_fail_hook(self) -> None:
        Path(self.env["CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE"]).write_text("{bad json", encoding="utf-8")
        self.write_modified_source()
        self.assertIsNotNone(self.parse_hook_output(self.run_hook(self.stop_payload())))

    def test_stop_has_no_output_when_guide_is_current(self) -> None:
        self.write_valid_guide()
        self.assertIsNone(self.parse_hook_output(self.run_hook(self.stop_payload())))


if __name__ == "__main__":
    unittest.main()
