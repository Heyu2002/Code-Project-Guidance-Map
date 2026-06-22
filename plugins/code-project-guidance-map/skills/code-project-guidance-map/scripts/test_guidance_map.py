#!/usr/bin/env python3
"""Tests for guidance_map.py."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import guidance_map


TEST_SECRET_HEX = "11" * 32
TEST_SECRET = bytes.fromhex(TEST_SECRET_HEX)
TEST_KEY_ID = "repo:test"


def render_test_block(
    body: str,
    timestamp: str,
    baseline: str,
    generator_version: str = guidance_map.GENERATOR_VERSION,
) -> str:
    return guidance_map.render_block(body, timestamp, baseline, TEST_KEY_ID, TEST_SECRET, generator_version)


class GuidanceMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.old_secret = os.environ.get(guidance_map.SIGNATURE_SECRET_ENV)
        self.old_key_home = os.environ.get(guidance_map.SIGNATURE_KEY_HOME_ENV)
        self.old_build_home = os.environ.get(guidance_map.BUILD_HOME_ENV)
        self.old_codex_command = os.environ.get(guidance_map.BUILD_CODEX_COMMAND_ENV)
        self.old_validate_codex = os.environ.get(guidance_map.BUILD_CODEX_VALIDATE_ENV)
        self.old_launcher = os.environ.get(guidance_map.BUILD_LAUNCHER_ENV)
        self.old_desktop_grace = os.environ.get(guidance_map.BUILD_DESKTOP_LAUNCH_GRACE_SECONDS_ENV)
        self.old_originator = os.environ.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE")
        os.environ[guidance_map.SIGNATURE_SECRET_ENV] = TEST_SECRET_HEX
        os.environ[guidance_map.SIGNATURE_KEY_HOME_ENV] = str(self.repo / ".keys")
        os.environ[guidance_map.BUILD_HOME_ENV] = str(self.repo / ".build-state")
        os.environ.pop(guidance_map.BUILD_CODEX_COMMAND_ENV, None)
        os.environ.pop(guidance_map.BUILD_CODEX_VALIDATE_ENV, None)
        os.environ.pop(guidance_map.BUILD_LAUNCHER_ENV, None)
        os.environ.pop(guidance_map.BUILD_DESKTOP_LAUNCH_GRACE_SECONDS_ENV, None)
        os.environ.pop("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", None)

    def tearDown(self) -> None:
        if self.old_secret is None:
            os.environ.pop(guidance_map.SIGNATURE_SECRET_ENV, None)
        else:
            os.environ[guidance_map.SIGNATURE_SECRET_ENV] = self.old_secret
        if self.old_key_home is None:
            os.environ.pop(guidance_map.SIGNATURE_KEY_HOME_ENV, None)
        else:
            os.environ[guidance_map.SIGNATURE_KEY_HOME_ENV] = self.old_key_home
        if self.old_build_home is None:
            os.environ.pop(guidance_map.BUILD_HOME_ENV, None)
        else:
            os.environ[guidance_map.BUILD_HOME_ENV] = self.old_build_home
        if self.old_codex_command is None:
            os.environ.pop(guidance_map.BUILD_CODEX_COMMAND_ENV, None)
        else:
            os.environ[guidance_map.BUILD_CODEX_COMMAND_ENV] = self.old_codex_command
        if self.old_validate_codex is None:
            os.environ.pop(guidance_map.BUILD_CODEX_VALIDATE_ENV, None)
        else:
            os.environ[guidance_map.BUILD_CODEX_VALIDATE_ENV] = self.old_validate_codex
        if self.old_launcher is None:
            os.environ.pop(guidance_map.BUILD_LAUNCHER_ENV, None)
        else:
            os.environ[guidance_map.BUILD_LAUNCHER_ENV] = self.old_launcher
        if self.old_desktop_grace is None:
            os.environ.pop(guidance_map.BUILD_DESKTOP_LAUNCH_GRACE_SECONDS_ENV, None)
        else:
            os.environ[guidance_map.BUILD_DESKTOP_LAUNCH_GRACE_SECONDS_ENV] = self.old_desktop_grace
        if self.old_originator is None:
            os.environ.pop("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", None)
        else:
            os.environ["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] = self.old_originator
        self.tmp.cleanup()

    def guidance_text(self, owns: str = "A") -> str:
        return (
            "### Agent Editing Rules\n\n"
            "- [MUST] Keep App changes inside `app` unless routing says otherwise.\n"
            "- [MUST] Treat linked module guides as lazy context; read only task-relevant guides.\n"
            "- [SHOULD] Reuse existing services before adding orchestration.\n\n"
            "### Progressive Disclosure\n\n"
            "- Start with AGENTS.md for broad orientation.\n"
            "- Read module guides only when routing or changed files point to them.\n\n"
            "### Task Routing\n\n"
            "- To add an API: edit `app/routes`; keep behavior in `app/services`.\n\n"
            "### Module Dependency Rules\n\n"
            "- `app` owns application behavior and may depend on shared utilities.\n\n"
            "### Module Index\n\n"
            "#### App\n\n"
            "- Module Path: `app`\n"
            "- Module Guide: `.agents/guidance-map/modules/app.md`\n"
            f"- Owns: {owns}\n"
            "- Change here when: B\n"
            "- Do not put here: C\n"
            "- Read guide when: Editing App behavior.\n"
            "- Usually skip when: Only changing docs.\n"
        )

    def module_doc_text(self, owns: str = "A") -> str:
        return (
            "# App\n\n"
            "- Module Path: `app`\n"
            f"- Owns: {owns}\n"
            "- Change here when: B\n"
            "- Do not put here: C\n"
            "- Key entry points:\n\n"
            "```text\n"
            "app/\n"
            "```\n"
        )

    def write_guidance(self, text: str | None = None) -> Path:
        module_path = self.repo / ".agents" / "guidance-map" / "modules" / "app.md"
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(self.module_doc_text(), encoding="utf-8")
        path = self.repo / "guidance.md"
        path.write_text(text or self.guidance_text(), encoding="utf-8")
        return path

    def test_update_creates_agents_when_missing(self) -> None:
        result = guidance_map.update(self.repo, self.write_guidance(), "2026-01-01T00:00:00Z")
        text = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(result["has_block"])
        self.assertIn(guidance_map.START_MARKER, text)
        self.assertIn("Generator: code-project-guidance-map", text)
        self.assertIn("Generator version: 0.2.1", text)
        self.assertIn("Guide format: action-map:v3", text)
        self.assertIn("Local change baseline: sha256:", text)
        self.assertIn("Signature key id: repo:", text)
        self.assertNotIn("Signature algorithm:", text)
        self.assertRegex(text, r"Signature: hmac-sha256:[0-9a-f]{64}")
        self.assertIn("- Module Guide: `.agents/guidance-map/modules/app.md`", text)
        self.assertRegex(text, r"- Module Signature: `hmac-sha256:[0-9a-f]{64}`")
        self.assertIn("- Owns: A", text)
        module_text = (self.repo / ".agents" / "guidance-map" / "modules" / "app.md").read_text(encoding="utf-8")
        self.assertIn(guidance_map.MODULE_START_MARKER, module_text)
        self.assertRegex(module_text, r"Signature: hmac-sha256:[0-9a-f]{64}")
        status = guidance_map.status(self.repo)
        self.assertTrue(status["local_change_baseline_valid"])
        self.assertEqual(status["modules"][0]["read_guide_when"], "Editing App behavior.")
        self.assertEqual(status["modules"][0]["usually_skip_when"], "Only changing docs.")

    def test_status_validates_signature(self) -> None:
        guidance_map.update(self.repo, self.write_guidance(), "2026-01-01T00:00:00Z")
        result = guidance_map.status(self.repo)
        self.assertTrue(result["signature_valid"])
        self.assertEqual(result["generator_version_status"], "current")
        self.assertTrue(result["modules_valid"])
        self.assertFalse(result["requires_full_read"])

        agents_path = self.repo / "AGENTS.md"
        text = agents_path.read_text(encoding="utf-8").replace("Owns: A", "Owns: changed")
        agents_path.write_text(text, encoding="utf-8")
        tampered = guidance_map.status(self.repo)
        self.assertFalse(tampered["signature_valid"])
        self.assertTrue(tampered["requires_full_read"])

        guidance_map.update(self.repo, self.write_guidance(), "2026-01-01T00:00:00Z")
        module_path = self.repo / ".agents" / "guidance-map" / "modules" / "app.md"
        module_text = module_path.read_text(encoding="utf-8").replace("Owns: A", "Owns: changed")
        module_path.write_text(module_text, encoding="utf-8")
        module_tampered = guidance_map.status(self.repo)
        self.assertTrue(module_tampered["signature_valid"])
        self.assertFalse(module_tampered["modules_valid"])
        self.assertTrue(module_tampered["requires_module_refresh"])

    def test_status_requires_signature_key(self) -> None:
        block = render_test_block("body", "2026-01-01T00:00:00Z", "abc123")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        os.environ.pop(guidance_map.SIGNATURE_SECRET_ENV, None)
        result = guidance_map.status(self.repo)
        self.assertFalse(result["signature_key_available"])
        self.assertFalse(result["signature_valid"])
        self.assertTrue(result["requires_full_read"])

    def test_update_creates_local_signature_key_without_env_secret(self) -> None:
        os.environ.pop(guidance_map.SIGNATURE_SECRET_ENV, None)
        result = guidance_map.update(self.repo, self.write_guidance(), "2026-01-01T00:00:00Z")
        key_source = Path(str(result["signature_key_source"]))
        self.assertTrue(key_source.exists())
        self.assertEqual(key_source.parent, self.repo / ".keys")

        status = guidance_map.status(self.repo)
        self.assertTrue(status["signature_key_available"])
        self.assertTrue(status["signature_valid"])
        self.assertFalse(status["requires_full_read"])

    def test_update_appends_block_when_agents_has_no_block(self) -> None:
        (self.repo / "AGENTS.md").write_text("# Existing\n\nKeep this.\n", encoding="utf-8")
        guidance_map.update(self.repo, self.write_guidance(), "2026-01-01T00:00:00Z")
        text = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Existing\n\nKeep this."))
        self.assertIn(guidance_map.START_MARKER, text)

    def test_update_replaces_block_and_preserves_outside_content(self) -> None:
        old_block = render_test_block("old", "2025-01-01T00:00:00Z", "abc123")
        (self.repo / "AGENTS.md").write_text(f"before\n\n{old_block}\nafter\n", encoding="utf-8")
        guidance_map.update(self.repo, self.write_guidance(self.guidance_text("new")), "2026-01-01T00:00:00Z")
        text = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("before", text)
        self.assertIn("after", text)
        self.assertIn("new", text)
        self.assertNotIn("old", text)
        self.assertEqual(text.count(guidance_map.START_MARKER), 1)

    def test_status_reports_invalid_signature_time(self) -> None:
        block = render_test_block("body", "2026-01-01T00:00:00Z", "abc123")
        block = block.replace("Generated at: 2026-01-01T00:00:00Z", "Generated at: not-a-date")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        result = guidance_map.status(self.repo)
        self.assertTrue(result["has_block"])
        self.assertFalse(result["generated_at_valid"])
        self.assertTrue(result["requires_full_read"])

    def test_status_reports_unsupported_guide_format(self) -> None:
        block = render_test_block("body", "2026-01-01T00:00:00Z", "abc123")
        block = block.replace("Guide format: action-map:v3\n", "")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        result = guidance_map.status(self.repo)
        self.assertTrue(result["has_block"])
        self.assertFalse(result["guide_format_valid"])
        self.assertTrue(result["requires_full_read"])

    def test_status_reports_missing_generator_version(self) -> None:
        block = render_test_block("body", "2026-01-01T00:00:00Z", "abc123")
        block = block.replace("Generator version: 0.2.1\n", "")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        result = guidance_map.status(self.repo)
        self.assertTrue(result["has_block"])
        self.assertEqual(result["generator_version_status"], "missing")
        self.assertFalse(result["generator_version_valid"])
        self.assertTrue(result["requires_full_read"])

    def test_verify_incompatible_generator_version_requires_full_refresh(self) -> None:
        block = render_test_block("body", "2026-01-01T00:00:00Z", "abc123", "0.1.0")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["generator_version_status"], "incompatible")
        self.assertTrue(result["signature_valid"])
        self.assertEqual(result["recommended_action"], "full_refresh")
        self.assertTrue(result["stale"])
        self.assertIn("Generator version is missing, invalid, or incompatible", " ".join(result["reasons"]))

    def test_verify_patch_generator_version_can_reuse_existing_guidance(self) -> None:
        guidance_map.update(self.repo, self.write_guidance(), "2026-01-01T00:00:00Z")
        agents_path = self.repo / "AGENTS.md"
        block = agents_path.read_text(encoding="utf-8")
        block_info = guidance_map.find_block(block)
        assert block_info is not None
        key_id = guidance_map.metadata_value(guidance_map.SIGNATURE_KEY_ID_RE, block_info[2])
        assert key_id is not None
        module_path = self.repo / ".agents" / "guidance-map" / "modules" / "app.md"
        module_body = guidance_map.module_body_from_text(module_path.read_text(encoding="utf-8"))
        module_signature = guidance_map.compute_module_signature(
            TEST_SECRET,
            "App",
            "`app`",
            ".agents/guidance-map/modules/app.md",
            "2026-01-01T00:00:00Z",
            "none",
            key_id,
            module_body,
            "0.2.2",
        )
        module_path.write_text(guidance_map.update_module_signature_text(module_path.read_text(encoding="utf-8"), module_signature), encoding="utf-8")
        block = block.replace("Generator version: 0.2.1", "Generator version: 0.2.2")
        block = re.sub(r"^- Module Signature:\s*.*$", f"- Module Signature: `{module_signature}`", block, count=1, flags=re.MULTILINE)
        block_info = guidance_map.find_block(block)
        assert block_info is not None
        guidance_body = guidance_map.guidance_body_from_block(block_info[2])
        assert guidance_body is not None
        local_baseline = guidance_map.metadata_value(guidance_map.LOCAL_CHANGE_BASELINE_RE, block_info[2])
        signature = guidance_map.compute_signature(
            TEST_SECRET,
            "project-index",
            guidance_map.GENERATOR,
            "0.2.2",
            guidance_map.GUIDE_FORMAT,
            "2026-01-01T00:00:00Z",
            "none",
            guidance_map.SIGNATURE_ALGORITHM,
            key_id,
            guidance_body,
            local_baseline,
        )
        block = re.sub(r"^Signature:\s*.*$", f"Signature: {signature}", block, count=1, flags=re.MULTILINE)
        agents_path.write_text(block, encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["generator_version_status"], "patch-compatible")
        self.assertTrue(result["signature_valid"])
        self.assertFalse(result["requires_full_read"])
        self.assertEqual(result["recommended_action"], "none")
        self.assertFalse(result["stale"])

    def test_generator_version_status_uses_semver_compatibility(self) -> None:
        self.assertEqual(guidance_map.generator_version_status("0.2.2", "0.2.1"), "patch-compatible")
        self.assertEqual(guidance_map.generator_version_status("0.3.0", "0.2.1"), "incompatible")
        self.assertEqual(guidance_map.generator_version_status("1.0.0", "0.2.1"), "incompatible")
        self.assertEqual(guidance_map.generator_version_status("bad", "0.2.1"), "invalid")

    def test_update_rejects_missing_required_sections(self) -> None:
        path = self.write_guidance("### Module Index\n\n#### App\n\n- Module Path: `app`\n")
        with self.assertRaises(guidance_map.GuidanceMapError):
            guidance_map.update(self.repo, path, "2026-01-01T00:00:00Z")

    def test_update_rejects_required_sections_out_of_order(self) -> None:
        text = (
            "### Task Routing\n\n"
            "- To add an API: edit `app/routes`.\n\n"
            "### Agent Editing Rules\n\n"
            "- [MUST] Keep App changes inside `app` unless routing says otherwise.\n\n"
            "### Module Dependency Rules\n\n"
            "- `app` owns application behavior and may depend on shared utilities.\n\n"
            "### Module Index\n\n"
            "#### App\n\n"
            "- Module Path: `app`\n"
            "- Module Guide: `.agents/guidance-map/modules/app.md`\n"
            "- Owns: A\n"
            "- Change here when: B\n"
            "- Do not put here: C\n"
        )
        path = self.write_guidance(text)
        with self.assertRaises(guidance_map.GuidanceMapError):
            guidance_map.update(self.repo, path, "2026-01-01T00:00:00Z")

    def test_status_handles_non_git_project(self) -> None:
        result = guidance_map.status(self.repo)
        self.assertFalse(result["git_available"])
        self.assertEqual(result["current_head"], "none")
        self.assertEqual(result["changed_files"], [])

    def test_classify_changed_files_by_refresh_scope(self) -> None:
        impact = guidance_map.classify_changed_files(
            [
                "pom.xml",
                "src/main/java/app/controller/UserController.java",
                "src/main/java/app/model/User.java",
                "docs/notes.md",
                ".github/workflows/ci.yml",
                "unknown.file",
            ]
        )
        self.assertEqual(impact["boundary_rules"], ["pom.xml"])
        self.assertEqual(impact["task_routing"], ["src/main/java/app/controller/UserController.java"])
        self.assertEqual(impact["module_internal"], ["src/main/java/app/model/User.java"])
        self.assertEqual(impact["docs_only"], ["docs/notes.md", ".github/workflows/ci.yml"])
        self.assertEqual(impact["other"], ["unknown.file"])

    def test_verify_missing_block_requires_full_refresh(self) -> None:
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["severity"], "error")
        self.assertEqual(result["recommended_action"], "full_refresh")
        self.assertTrue(result["stale"])

    def test_malformed_markers_raise(self) -> None:
        text = f"{guidance_map.START_MARKER}\nmissing end"
        with self.assertRaises(guidance_map.GuidanceMapError):
            guidance_map.find_block(text)

    def test_build_queues_context_when_builder_is_active(self) -> None:
        root, git_available = guidance_map.repo_root(self.repo)
        state_dir = guidance_map.build_state_dir(root, git_available)
        active = {
            "build_id": "active-build",
            "repo_root": str(root),
            "project_id": guidance_map.project_id(root, git_available),
            "status": "launching",
            "started_at": guidance_map.utc_now(),
            "pid": None,
        }
        state = guidance_map.read_build_state(state_dir, root, git_available)
        state["active"] = active
        guidance_map.write_active_lock(state_dir, active)
        guidance_map.write_build_state(state_dir, state)

        result = guidance_map.start_guidance_build(
            self.repo,
            reason="test-refresh",
            context="new request context",
            codex_command="definitely-missing-codex",
        )

        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["active_build_id"], "active-build")
        self.assertEqual(result["pending_context_count"], 1)

        with self.assertRaises(guidance_map.GuidanceMapError):
            guidance_map.finish_guidance_build(self.repo, "active-build", "complete")

        drained = guidance_map.drain_build_context(self.repo, "active-build")
        self.assertEqual(drained["pending_context_count"], 1)
        self.assertEqual(drained["pending_contexts"][0]["context"], "new request context")

        finished = guidance_map.finish_guidance_build(self.repo, "active-build", "abandoned")
        self.assertEqual(finished["status"], "finished")
        self.assertFalse(guidance_map.build_active_lock_path(state_dir).exists())

    def test_build_queues_before_launcher_resolution_when_builder_is_active(self) -> None:
        root, git_available = guidance_map.repo_root(self.repo)
        state_dir = guidance_map.build_state_dir(root, git_available)
        active = {
            "build_id": "active-build",
            "repo_root": str(root),
            "project_id": guidance_map.project_id(root, git_available),
            "status": "launching",
            "started_at": guidance_map.utc_now(),
            "pid": None,
        }
        state = guidance_map.read_build_state(state_dir, root, git_available)
        state["active"] = active
        guidance_map.write_active_lock(state_dir, active)
        guidance_map.write_build_state(state_dir, state)

        with mock.patch("guidance_map.shutil.which", return_value=None):
            result = guidance_map.start_guidance_build(
                self.repo,
                reason="active-refresh",
                context="queue without launcher discovery",
                launcher="cli",
            )

        self.assertEqual(result["status"], "queued")
        drained = guidance_map.drain_build_context(self.repo, "active-build")
        self.assertEqual(drained["pending_contexts"][0]["context"], "queue without launcher discovery")
        finished = guidance_map.finish_guidance_build(self.repo, "active-build", "abandoned")
        self.assertEqual(finished["status"], "finished")

    def test_build_starts_script_coordinated_cli_agent(self) -> None:
        fake_codex = self.repo / "fake_codex.py"
        fake_codex.write_text(
            "import pathlib, sys, time\n"
            "args = sys.argv[1:]\n"
            "prompt = sys.stdin.read()\n"
            "if '-o' in args:\n"
            "    pathlib.Path(args[args.index('-o') + 1]).write_text('started\\n', encoding='utf-8')\n"
            "pathlib.Path('captured-prompt.txt').write_text(prompt, encoding='utf-8')\n"
            "time.sleep(5)\n",
            encoding="utf-8",
        )

        result = guidance_map.start_guidance_build(
            self.repo,
            reason="launch-test",
            context="launch context",
            codex_command=f"{sys.executable} {fake_codex}",
        )

        self.assertEqual(result["status"], "started")
        self.assertTrue(Path(str(result["prompt_file"])).exists())
        prompt = Path(str(result["prompt_file"])).read_text(encoding="utf-8")
        self.assertIn("script-coordinated Code Project Guidance Map builder agent", prompt)
        self.assertIn("launch context", prompt)

        pid = int(result["pid"])
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        time.sleep(0.1)
        finished = guidance_map.finish_guidance_build(self.repo, str(result["build_id"]), "abandoned", force=True)
        self.assertEqual(finished["finish_status"], "abandoned")

    def test_default_build_requires_runnable_codex_command(self) -> None:
        old_path = os.environ.get("PATH")
        try:
            os.environ["PATH"] = ""
            with self.assertRaises(guidance_map.GuidanceMapError) as raised:
                guidance_map.resolve_codex_command(None)
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
        self.assertIn("Unable to find a runnable `codex` command", str(raised.exception))

    def test_configured_codex_command_bypasses_default_discovery(self) -> None:
        command = guidance_map.resolve_codex_command(f"{sys.executable} fake_codex.py")
        self.assertEqual(command, [sys.executable, "fake_codex.py"])

    def test_auto_build_falls_back_to_desktop_handoff_in_desktop_thread(self) -> None:
        os.environ["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] = "Codex Desktop"
        with mock.patch("guidance_map.shutil.which", return_value=None):
            result = guidance_map.start_guidance_build(
                self.repo,
                reason="desktop-refresh",
                context="desktop-only request context",
                launcher="auto",
            )

        self.assertEqual(result["status"], "desktop_launch_required")
        self.assertEqual(result["launcher"], "desktop")
        self.assertIn("desktop-only request context", result["prompt"])
        self.assertTrue(Path(str(result["prompt_file"])).exists())
        self.assertIn("build-attach", result["attach_command"])

        attached = guidance_map.attach_desktop_builder_thread(self.repo, str(result["build_id"]), "thread-123")
        self.assertEqual(attached["status"], "attached")
        self.assertEqual(attached["thread_id"], "thread-123")

        queued = guidance_map.start_guidance_build(
            self.repo,
            reason="queued-desktop-refresh",
            context="second desktop request",
            codex_command="definitely-missing-codex",
        )
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(queued["active_build_id"], result["build_id"])

        drained = guidance_map.drain_build_context(self.repo, str(result["build_id"]))
        self.assertEqual(drained["pending_context_count"], 1)
        self.assertEqual(drained["pending_contexts"][0]["context"], "second desktop request")
        finished = guidance_map.finish_guidance_build(self.repo, str(result["build_id"]), "abandoned")
        self.assertEqual(finished["finish_status"], "abandoned")

    def test_cli_launcher_does_not_fallback_to_desktop_handoff(self) -> None:
        os.environ["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] = "Codex Desktop"
        with mock.patch("guidance_map.shutil.which", return_value=None):
            with self.assertRaises(guidance_map.GuidanceMapError) as raised:
                guidance_map.start_guidance_build(self.repo, launcher="cli")
        self.assertIn("Unable to find a runnable `codex` command", str(raised.exception))

    def test_build_attach_rejects_non_desktop_builder(self) -> None:
        fake_codex = self.repo / "fake_codex.py"
        fake_codex.write_text(
            "import sys, time\n"
            "sys.stdin.read()\n"
            "time.sleep(5)\n",
            encoding="utf-8",
        )
        result = guidance_map.start_guidance_build(
            self.repo,
            reason="launch-test",
            context="launch context",
            codex_command=f"{sys.executable} {fake_codex}",
            launcher="cli",
        )
        with self.assertRaises(guidance_map.GuidanceMapError):
            guidance_map.attach_desktop_builder_thread(self.repo, str(result["build_id"]), "thread-123")

        pid = int(result["pid"])
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        time.sleep(0.1)
        guidance_map.finish_guidance_build(self.repo, str(result["build_id"]), "abandoned", force=True)


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class GuidanceMapGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.old_secret = os.environ.get(guidance_map.SIGNATURE_SECRET_ENV)
        self.old_key_home = os.environ.get(guidance_map.SIGNATURE_KEY_HOME_ENV)
        os.environ[guidance_map.SIGNATURE_SECRET_ENV] = TEST_SECRET_HEX
        os.environ[guidance_map.SIGNATURE_KEY_HOME_ENV] = str(self.repo / ".keys")
        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test User")
        (self.repo / "committed.txt").write_text("initial\n", encoding="utf-8")
        self.git("add", "committed.txt")
        self.git("commit", "-m", "initial")

    def tearDown(self) -> None:
        if self.old_secret is None:
            os.environ.pop(guidance_map.SIGNATURE_SECRET_ENV, None)
        else:
            os.environ[guidance_map.SIGNATURE_SECRET_ENV] = self.old_secret
        if self.old_key_home is None:
            os.environ.pop(guidance_map.SIGNATURE_KEY_HOME_ENV, None)
        else:
            os.environ[guidance_map.SIGNATURE_KEY_HOME_ENV] = self.old_key_home
        self.tmp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def commit_guide(self, module_path_value: str = "`src/main/java/app`") -> None:
        module_path = self.repo / ".agents" / "guidance-map" / "modules" / "app.md"
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(
            "# App\n\n"
            f"- Module Path: {module_path_value}\n"
            "- Owns: Application behavior.\n"
            "- Change here when: Application behavior changes.\n"
            "- Do not put here: Shared utilities.\n"
            "- Key entry points: `src/main/java/app/`\n",
            encoding="utf-8",
        )
        index = (
            "### Agent Editing Rules\n\n"
            "- [MUST] Keep App changes inside `src/main/java/app`.\n\n"
            "### Progressive Disclosure\n\n"
            "- Start with AGENTS.md for broad orientation.\n"
            "- Read App guide only when App paths changed.\n\n"
            "### Task Routing\n\n"
            "- To add an API: edit `src/main/java/app/controller`.\n\n"
            "### Module Dependency Rules\n\n"
            "- `app` owns application behavior.\n\n"
            "### Module Index\n\n"
            "#### App\n\n"
            f"- Module Path: {module_path_value}\n"
            "- Module Guide: `.agents/guidance-map/modules/app.md`\n"
            "- Owns: Application behavior.\n"
            "- Change here when: Application behavior changes.\n"
            "- Do not put here: Shared utilities.\n"
            "- Read guide when: Editing App runtime or tests.\n"
            "- Usually skip when: Only changing plugin metadata.\n"
        )
        guidance_path = self.repo / "guidance.md"
        guidance_path.write_text(index, encoding="utf-8")
        guidance_map.update(self.repo, guidance_path, "2030-01-01T00:00:00Z")
        self.git("add", "AGENTS.md", ".agents/guidance-map/modules/app.md")
        self.git("commit", "-m", "guide")

    def test_changed_files_include_committed_staged_unstaged_and_untracked(self) -> None:
        (self.repo / "new_commit.txt").write_text("new\n", encoding="utf-8")
        self.git("add", "new_commit.txt")
        self.git("commit", "-m", "new commit")
        (self.repo / "staged.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "staged.txt")
        (self.repo / "committed.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        block = render_test_block("body", "2000-01-01T00:00:00Z", "abc123")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        result = guidance_map.status(self.repo)

        changed = set(result["changed_files"])
        self.assertIn("new_commit.txt", changed)
        self.assertIn("staged.txt", changed)
        self.assertIn("committed.txt", changed)
        self.assertIn("untracked.txt", changed)

    def test_clean_repo_with_later_timestamp_has_no_changes(self) -> None:
        block = render_test_block("body", "2030-01-01T00:00:00Z", "abc123")
        (self.repo / "AGENTS.md").write_text(block, encoding="utf-8")
        self.git("add", "AGENTS.md")
        self.git("commit", "-m", "guide")
        result = guidance_map.status(self.repo)
        self.assertEqual(result["changed_files"], [])

    def test_verify_boundary_sensitive_changes_refresh_dependency_rules(self) -> None:
        self.commit_guide()
        path = self.repo / "src/main/java/app/pom.xml"
        path.parent.mkdir(parents=True)
        path.write_text("<project />\n", encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["recommended_action"], "refresh_dependency_rules")
        self.assertTrue(result["stale"])
        self.assertEqual(result["change_impact"]["boundary_rules"], ["src/main/java/app/pom.xml"])
        self.assertEqual(result["affected_module_guides"], [".agents/guidance-map/modules/app.md"])
        self.assertEqual(result["affected_modules"][0]["name"], "App")
        self.assertEqual(result["affected_modules"][0]["impact_categories"], ["boundary_rules"])

    def test_verify_task_routing_changes_refresh_routing(self) -> None:
        self.commit_guide()
        path = self.repo / "src/main/java/app/controller/UserController.java"
        path.parent.mkdir(parents=True)
        path.write_text("class UserController {}\n", encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["recommended_action"], "refresh_task_routing_and_affected_modules")
        self.assertTrue(result["stale"])
        self.assertEqual(result["change_impact"]["task_routing"], ["src/main/java/app/controller/UserController.java"])
        self.assertEqual(result["affected_module_guides"], [".agents/guidance-map/modules/app.md"])
        self.assertEqual(result["affected_modules"][0]["changed_files"], ["src/main/java/app/controller/UserController.java"])

    def test_verify_module_internal_changes_refresh_affected_modules(self) -> None:
        self.commit_guide()
        path = self.repo / "src/main/java/app/model/User.java"
        path.parent.mkdir(parents=True)
        path.write_text("class User {}\n", encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["recommended_action"], "refresh_affected_modules")
        self.assertTrue(result["stale"])
        self.assertEqual(result["change_impact"]["module_internal"], ["src/main/java/app/model/User.java"])
        self.assertEqual(result["affected_module_guides"], [".agents/guidance-map/modules/app.md"])
        self.assertEqual(result["affected_modules"][0]["read_guide_when"], "Editing App runtime or tests.")
        self.assertEqual(result["affected_modules"][0]["usually_skip_when"], "Only changing plugin metadata.")
        self.assertEqual(result["unmapped_changed_files"], [])

    def test_update_baselines_existing_dirty_worktree_changes(self) -> None:
        self.commit_guide()
        relpath = "src/main/java/app/model/User.java"
        path = self.repo / relpath
        path.parent.mkdir(parents=True)
        path.write_text("class User {}\n", encoding="utf-8")
        before = guidance_map.verify(self.repo)
        self.assertEqual(before["recommended_action"], "refresh_affected_modules")

        guidance_map.update(self.repo, self.repo / "guidance.md", "2027-01-01T00:00:00Z")
        after = guidance_map.verify(self.repo)
        self.assertNotIn(relpath, after["changed_files"])
        self.assertIn(relpath, after["changed_files_by_source"]["baseline_ignored"])
        self.assertFalse(after["stale"])

        path.write_text("class User { int id; }\n", encoding="utf-8")
        changed_after_refresh = guidance_map.verify(self.repo)
        self.assertEqual(changed_after_refresh["recommended_action"], "refresh_affected_modules")
        self.assertIn(relpath, changed_after_refresh["changed_files"])

    def test_local_change_baseline_ignores_same_content_after_later_commit(self) -> None:
        self.commit_guide()
        relpath = "src/main/java/app/model/User.java"
        path = self.repo / relpath
        path.parent.mkdir(parents=True)
        path.write_text("class User {}\n", encoding="utf-8")

        guidance_map.update(self.repo, self.repo / "guidance.md", "2027-01-01T00:00:00Z")
        self.git("add", relpath)
        env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2027-01-02T00:00:00Z",
            "GIT_COMMITTER_DATE": "2027-01-02T00:00:00Z",
        }
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-m", "code"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            env=env,
        )

        result = guidance_map.verify(self.repo)
        self.assertNotIn(relpath, result["changed_files"])
        self.assertIn(relpath, result["changed_files_by_source"]["baseline_ignored"])
        self.assertFalse(result["stale"])

    def test_verify_multi_path_module_mapping(self) -> None:
        self.commit_guide("`src/main/java/app`, `src/test/java/app`; `shared/app`")
        path = self.repo / "src/test/java/app/AppTest.java"
        path.parent.mkdir(parents=True)
        path.write_text("class AppTest {}\n", encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["recommended_action"], "refresh_affected_modules")
        self.assertEqual(result["affected_module_guides"], [".agents/guidance-map/modules/app.md"])
        self.assertEqual(result["affected_modules"][0]["changed_files"], ["src/test/java/app/AppTest.java"])

    def test_verify_unmapped_code_file_is_reported(self) -> None:
        self.commit_guide()
        path = self.repo / "src/main/java/other/Other.java"
        path.parent.mkdir(parents=True)
        path.write_text("class Other {}\n", encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["recommended_action"], "refresh_affected_modules")
        self.assertEqual(result["affected_modules"], [])
        self.assertEqual(result["unmapped_changed_files"], ["src/main/java/other/Other.java"])
        self.assertIn("do not map", " ".join(result["reasons"]))

    def test_verify_docs_only_changes_do_not_mark_stale(self) -> None:
        self.commit_guide()
        path = self.repo / "docs/notes.md"
        path.parent.mkdir(parents=True)
        path.write_text("# notes\n", encoding="utf-8")
        result = guidance_map.verify(self.repo)
        self.assertEqual(result["recommended_action"], "none")
        self.assertFalse(result["stale"])
        self.assertEqual(result["severity"], "info")
        self.assertEqual(result["affected_modules"], [])


class GuidanceMapCliTests(unittest.TestCase):
    def test_status_cli_outputs_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(guidance_map.__file__).resolve()
            result = subprocess.run(
                [sys.executable, str(script), "status", "--repo", tmp],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            parsed = json.loads(result.stdout)
            self.assertIn("repo_root", parsed)

    def test_verify_cli_can_fail_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(guidance_map.__file__).resolve()
            result = subprocess.run(
                [sys.executable, str(script), "verify", "--repo", tmp, "--fail-on", "error"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            parsed = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(parsed["recommended_action"], "full_refresh")


if __name__ == "__main__":
    unittest.main()
