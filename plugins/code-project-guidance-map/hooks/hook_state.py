"""State machine for guidance-map hook notifications."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HOOK_LEVEL_ENV = "CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL"
HOOK_STATE_FILE_ENV = "CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE"
VALID_HOOK_LEVELS = {"off", "error", "stale", "all"}


@dataclass(frozen=True)
class HookEvent:
    event_name: str
    project_id: str
    session_id: str
    prompt_is_code_edit: bool
    severity: str
    recommended_action: str
    stale: bool
    has_error: bool


@dataclass(frozen=True)
class HookDecision:
    should_emit: bool
    include_info: bool
    state: dict[str, Any]


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def state_file_path() -> Path:
    configured = os.environ.get(HOOK_STATE_FILE_ENV)
    if configured:
        return Path(configured).expanduser()
    return codex_home() / "code-project-guidance-map" / "hooks" / "state-v1.json"


def normalize_hook_level(raw: str | None) -> str:
    level = (raw or "stale").strip().casefold()
    return level if level in VALID_HOOK_LEVELS else "stale"


def hook_level() -> str:
    return normalize_hook_level(os.environ.get(HOOK_LEVEL_ENV))


def load_state(path: Path | None = None) -> dict[str, Any]:
    path = path or state_file_path()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "projects": {}}
    if not isinstance(loaded, dict):
        return {"version": 1, "projects": {}}
    loaded.setdefault("version", 1)
    loaded.setdefault("projects", {})
    if not isinstance(loaded["projects"], dict):
        loaded["projects"] = {}
    return loaded


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or state_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def repo_root(start: Path) -> tuple[Path, bool]:
    result = run_git(start, ["rev-parse", "--show-toplevel"])
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve(), True
    return start.resolve(), False


def repo_identity(repo: Path, git_available: bool) -> str:
    if git_available:
        remote = run_git(repo, ["config", "--get", "remote.origin.url"])
        if remote.returncode == 0 and remote.stdout.strip():
            return f"git:{remote.stdout.strip()}"
    return f"path:{repo.resolve()}"


def project_id_for_cwd(cwd: str) -> str:
    root, git_available = repo_root(Path(cwd))
    digest = hashlib.sha256(repo_identity(root, git_available).encode("utf-8")).hexdigest()
    return f"repo:{digest[:16]}"


def stable_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", value.strip()) or "unknown"


def action_key(event: HookEvent) -> str:
    action = "verify_error" if event.has_error else event.recommended_action or "none"
    return f"{stable_token(event.severity)}:{stable_token(action)}"


def event_is_relevant(event: HookEvent, level: str) -> bool:
    if level == "off":
        return False
    if level == "error":
        return event.has_error or event.severity == "error"
    if level == "all":
        return event.has_error or event.stale or event.severity != "ok"
    return event.has_error or event.stale or event.severity == "error"


def session_state(state: dict[str, Any], project_id: str, session_id: str) -> dict[str, Any]:
    projects = state.setdefault("projects", {})
    project = projects.setdefault(project_id, {"sessions": {}})
    sessions = project.setdefault("sessions", {})
    session = sessions.setdefault(
        session_id,
        {
            "notified_actions": [],
            "stop_notified_actions": [],
            "saw_code_edit_prompt": False,
        },
    )
    session.setdefault("notified_actions", [])
    session.setdefault("stop_notified_actions", [])
    session.setdefault("saw_code_edit_prompt", False)
    return session


def transition(state: dict[str, Any], event: HookEvent, level: str) -> HookDecision:
    next_state = copy.deepcopy(state)
    session = session_state(next_state, event.project_id, event.session_id)
    if event.prompt_is_code_edit:
        session["saw_code_edit_prompt"] = True

    normalized_level = normalize_hook_level(level)
    include_info = normalized_level == "all"
    if not event_is_relevant(event, normalized_level):
        return HookDecision(False, include_info, next_state)

    key = action_key(event)
    if event.event_name == "Stop":
        if not session.get("saw_code_edit_prompt"):
            return HookDecision(False, include_info, next_state)
        stop_notified = session.setdefault("stop_notified_actions", [])
        if key in stop_notified:
            return HookDecision(False, include_info, next_state)
        stop_notified.append(key)
        return HookDecision(True, include_info, next_state)

    notified = session.setdefault("notified_actions", [])
    if key in notified:
        return HookDecision(False, include_info, next_state)
    notified.append(key)
    return HookDecision(True, include_info, next_state)
