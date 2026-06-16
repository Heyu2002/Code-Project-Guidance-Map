#!/usr/bin/env python3
"""Codex hooks for code-project-guidance-map.

The hooks are intentionally read-only. They verify the generated AGENTS.md index
and signed module guides, then add bounded model context when guidance is stale
or unverifiable.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import hook_state


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_MAP = PLUGIN_ROOT / "skills" / "code-project-guidance-map" / "scripts" / "guidance_map.py"

ACTION_PATTERNS = (
    r"\b(add|change|modify|edit|implement|fix|refactor|update|delete|remove|write|create)\b",
    r"(\u65b0\u589e|\u4fee\u6539|\u5b9e\u73b0|\u4fee\u590d|\u91cd\u6784|\u66f4\u65b0|\u5220\u9664|\u521b\u5efa|\u8c03\u6574|\u6539\u4e00\u4e2a|\u5199\u4e00\u4e2a)",
)

CODE_CONTEXT_PATTERNS = (
    r"\b(api|endpoint|controller|service|dao|repository|mapper|sql|schema|migration|test|bug|feature)\b",
    r"(\u63a5\u53e3|\u63a7\u5236\u5668|\u670d\u52a1|\u6570\u636e\u5e93|\u6301\u4e45\u5316|\u6a21\u5757|\u529f\u80fd|\u4ee3\u7801|\u6d4b\u8bd5|\u62a5\u9519|\u95ee\u9898|\u7f3a\u9677|\u903b\u8f91)",
)

DIRECT_CODE_PATTERNS = (
    r"\b(src|app|lib|packages|modules|web|server|client|frontend|backend)/",
    r"\.(py|js|jsx|ts|tsx|java|kt|go|rs|cs|php|rb|sql|xml|yaml|yml|toml|json)\b",
)


def read_input() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def hook_output(event_name: str, additional_context: str | None) -> None:
    if not additional_context:
        return
    if event_name == "Stop":
        print(json.dumps({"systemMessage": additional_context}, ensure_ascii=False))
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": additional_context,
                }
            },
            ensure_ascii=False,
        )
    )


def pattern_matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def prompt_looks_like_code_edit(prompt: str) -> bool:
    lowered = prompt.casefold()
    if pattern_matches(DIRECT_CODE_PATTERNS, lowered):
        return True
    return pattern_matches(ACTION_PATTERNS, lowered) and pattern_matches(CODE_CONTEXT_PATTERNS, lowered)


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
    event_name: str,
    verification: dict[str, Any] | None,
    error: str | None,
    include_info: bool = False,
) -> str | None:
    if error:
        return (
            "Code Project Guidance Map hook: AGENTS.md action map could not be verified. "
            f"{error}. Before the next code edit, suggest running $code-project-guidance-map to refresh the signed project index "
            "with bounded module subagents; do not do a main-thread full project read."
        )
    if not verification:
        return None

    has_problem = bool(verification.get("stale")) or verification.get("severity") == "error" or (
        include_info and verification.get("severity") != "ok"
    )
    if not has_problem:
        return None

    summary = actionable_change_summary(verification)
    if event_name == "UserPromptSubmit":
        return (
            "Code Project Guidance Map hook: this looks like a code-edit request, and the repository "
            f"AGENTS.md project index or module guides are stale or unverifiable. {summary} Before editing code, use "
            "$code-project-guidance-map to refresh the signed project index and affected module guide files with bounded module subagents, "
            "or explicitly explain why the edit can proceed without it."
        )
    if event_name == "Stop":
        return (
            "Code Project Guidance Map hook: this task finished while the repository AGENTS.md project index or module guides "
            f"are stale, missing, or unverifiable. {summary} Before the next code edit, run $code-project-guidance-map "
            "to refresh the signed project index and affected module guide files with bounded module subagents."
        )
    return (
        "Code Project Guidance Map hook: this repository's AGENTS.md project index or module guides are stale, missing, "
        f"or unverifiable. {summary} Before the first code edit in this thread, suggest running "
        "$code-project-guidance-map with bounded module subagents."
    )


def main() -> int:
    payload = read_input()
    event_name = payload.get("hook_event_name")
    if event_name not in {"SessionStart", "UserPromptSubmit", "Stop"}:
        return 0

    prompt = str(payload.get("prompt") or "")
    prompt_is_code_edit = False
    if event_name == "UserPromptSubmit":
        if "$code-project-guidance-map" in prompt or "code-project-guidance-map" in prompt:
            return 0
        prompt_is_code_edit = prompt_looks_like_code_edit(prompt)
        if not prompt_is_code_edit:
            return 0

    cwd = str(payload.get("cwd") or ".")
    verification, error = verify_repo(cwd)
    project_id = str((verification or {}).get("project_id") or hook_state.project_id_for_cwd(cwd))
    session_id = str(payload.get("session_id") or "unknown")
    event = hook_state.HookEvent(
        event_name=str(event_name),
        project_id=project_id,
        session_id=session_id,
        prompt_is_code_edit=prompt_is_code_edit,
        severity=str((verification or {}).get("severity") or ("error" if error else "ok")),
        recommended_action=str((verification or {}).get("recommended_action") or ("verify_error" if error else "none")),
        stale=bool((verification or {}).get("stale")) or bool(error),
        has_error=bool(error),
    )
    state = hook_state.load_state()
    decision = hook_state.transition(state, event, hook_state.hook_level())
    hook_state.save_state(decision.state)
    if not decision.should_emit:
        return 0
    hook_output(event_name, context_for(event_name, verification, error, include_info=decision.include_info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
