#!/usr/bin/env python3
"""Modification-only Stop hook for code-project-guidance-map.

The hook is intentionally read-only. It verifies guidance after Git-visible project
changes and requests an asynchronous refresh only when no builder is already active.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import hook_state


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_MAP = PLUGIN_ROOT / "skills" / "code-project-guidance-map" / "scripts" / "guidance_map.py"


def read_input() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def hook_output(additional_context: str | None) -> None:
    if not additional_context:
        return
    print(json.dumps({"systemMessage": additional_context}, ensure_ascii=False))


def verify_repo(cwd: str) -> tuple[dict[str, Any] | None, str | None]:
    if not GUIDANCE_MAP.exists():
        return None, f"guidance helper is missing at {GUIDANCE_MAP}"
    result = subprocess.run(
        [sys.executable, str(GUIDANCE_MAP), "verify", "--repo", cwd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stream = result.stdout.strip() or result.stderr.strip()
    try:
        parsed = json.loads(stream) if stream else {}
    except json.JSONDecodeError:
        return None, stream or f"verify exited with code {result.returncode}"
    if result.returncode not in (0, 1):
        return parsed, parsed.get("error") or f"verify exited with code {result.returncode}"
    return parsed, None


def active_build(cwd: str) -> bool:
    result = subprocess.run(
        [sys.executable, str(GUIDANCE_MAP), "build-status", "--repo", cwd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return False
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return bool(parsed.get("active"))


def modification_fingerprint(repo: str, changed_files: list[str]) -> str:
    root = Path(repo).resolve()
    digest = hashlib.sha256()
    for relative in sorted(changed_files):
        digest.update(relative.encode("utf-8", errors="replace"))
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
            content = path.read_bytes() if path.is_file() else b"<missing>"
        except (OSError, ValueError):
            content = b"<unreadable>"
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def actionable_change_summary(verification: dict[str, Any]) -> str:
    action = verification.get("recommended_action") or "review"
    reasons = verification.get("reasons") or []
    reason_text = "; ".join(str(reason) for reason in reasons[:3]) or "guidance map needs review."
    changed = verification.get("changed_files") or []
    changed_text = ""
    if changed:
        preview = ", ".join(str(path) for path in changed[:8])
        suffix = " ..." if len(changed) > 8 else ""
        changed_text = f" Changed files: {preview}{suffix}."
    guides = verification.get("affected_module_guides") or []
    guide_text = ""
    if guides:
        preview = ", ".join(str(path) for path in guides[:5])
        suffix = " ..." if len(guides) > 5 else ""
        guide_text = f" Affected module guides: {preview}{suffix}."
    return f"{reason_text} Recommended action: {action}.{changed_text}{guide_text}"


def context_for(
    verification: dict[str, Any] | None,
    error: str | None,
    include_info: bool = False,
    repo: str | None = None,
) -> str | None:
    repo_arg = repo or "<repo-root>"
    build_command = f"python {GUIDANCE_MAP} build --repo {repo_arg} --launcher auto --context <current-request-summary>"
    if error:
        return (
            "Code Project Guidance Map modification hook: project files changed, but the signed guidance map could not be "
            f"verified. {error}. Start or synchronize the dedicated builder with `{build_command}`. Once the command returns "
            "`started` or `queued`, or once a Desktop builder thread is created and attached, finalize this thread immediately. "
            "Do not wait for, poll, read, or follow the builder thread's completion."
        )
    if not verification:
        return None

    has_problem = bool(verification.get("stale")) or verification.get("severity") == "error" or (
        include_info and verification.get("severity") != "ok"
    )
    if not has_problem:
        return None

    summary = actionable_change_summary(verification)
    return (
        "Code Project Guidance Map modification hook: project changes made the repository AGENTS.md project index or guide "
        f"tree stale or unverifiable. {summary} Start or synchronize the dedicated builder with `{build_command}`. Once the "
        "command returns `started` or `queued`, or once a Desktop builder thread is created and attached, finalize this thread "
        "immediately. Do not wait for, poll, read, or follow the builder thread's completion."
    )


def main() -> int:
    payload = read_input()
    event_name = payload.get("hook_event_name")
    if event_name != "Stop":
        return 0

    cwd = str(payload.get("cwd") or ".")
    verification, error = verify_repo(cwd)
    changed_files = [str(path) for path in (verification or {}).get("changed_files") or []]
    if not changed_files:
        return 0
    repo_root = str((verification or {}).get("repo_root") or cwd)
    project_id = str((verification or {}).get("project_id") or hook_state.project_id_for_cwd(cwd))
    session_id = str(payload.get("session_id") or "unknown")
    event = hook_state.HookEvent(
        event_name=str(event_name),
        project_id=project_id,
        session_id=session_id,
        severity=str((verification or {}).get("severity") or ("error" if error else "ok")),
        recommended_action=str((verification or {}).get("recommended_action") or ("verify_error" if error else "none")),
        stale=bool((verification or {}).get("stale")) or bool(error),
        has_error=bool(error),
        has_changes=True,
        change_fingerprint=modification_fingerprint(repo_root, changed_files),
        build_active=active_build(cwd),
    )
    state = hook_state.load_state()
    decision = hook_state.transition(state, event, hook_state.hook_level())
    hook_state.save_state(decision.state)
    if not decision.should_emit:
        return 0
    hook_output(context_for(verification, error, include_info=decision.include_info, repo=cwd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
