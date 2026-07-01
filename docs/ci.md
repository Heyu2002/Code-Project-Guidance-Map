# CI Maintenance

Use CI to keep this plugin, the generated `AGENTS.md` project index, and signed module guide files reliable without forcing every run to reread the whole project.

## Plugin Repository CI

This repository should validate that the development skill and distributable plugin copy stay aligned:

```powershell
python scripts\sync_plugin_skill.py --check
python scripts\test_sync_plugin_skill.py
python .agents\skills\code-project-guidance-map\scripts\test_guidance_map.py
python plugins\code-project-guidance-map\skills\code-project-guidance-map\scripts\test_guidance_map.py
python -m json.tool plugins\code-project-guidance-map\.codex-plugin\plugin.json
```

## Target Project CI

Target projects can use the skill helper as a lightweight freshness check:

```powershell
python <installed-skill>\scripts\guidance_map.py verify --repo . --fail-on error
```

This fails only when the guidance index is missing, malformed, has an unsupported guide format, has invalid metadata/signature, or cannot verify its module guide signatures.

Signature verification needs the same plugin signing key that created the block. For CI, provide one of:

- `CODE_PROJECT_GUIDANCE_MAP_SECRET`: shared HMAC secret stored in CI secrets.
- `CODE_PROJECT_GUIDANCE_MAP_KEY_FILE`: path to a mounted key file.

Without a configured key, CI treats an existing generated index or module guide signatures as unverifiable and asks for a plugin refresh.

For stricter projects, use:

```powershell
python <installed-skill>\scripts\guidance_map.py verify --repo . --fail-on stale
```

That also fails when changed files indicate the guidance should be refreshed.

Freshness uses two boundaries:

- `Generated at` bounds committed Git history.
- `Local change baseline` is a signed snapshot of staged, unstaged, and untracked file content that existed during the last refresh. `verify` ignores those local paths while their current content still matches the snapshot, so refreshing a dirty worktree does not cause every later thread to ask for the same refresh again.

## Refresh Scope

`verify` classifies changed files into:

- `boundary_rules`: build files, module manifests, workspace configs, and other changes that can affect dependency direction.
- `task_routing`: controllers, routes, APIs, services, DAOs, SQL mappings, jobs, schedules, WebSocket, MQ, and queue files.
- `module_internal`: ordinary code files that usually require only affected module guide files to refresh.
- `docs_only`: documentation or CI changes that do not require a guidance refresh.
- `other`: unclassified files that should be reviewed by a maintainer.

The goal is conservative maintenance:

- Do not re-read the whole repository for ordinary module-internal changes.
- Re-evaluate `Agent Editing Rules` and `Module Dependency Rules` only for boundary-sensitive changes.
- Refresh `Task Routing` only when entrypoint or layer-flow files changed.
- Keep `AGENTS.md` compact as an index, and keep module detail in `.agents/guidance-map/modules/*.md`.
- Use `status` fields such as `signature_valid`, `modules_valid`, and `requires_module_refresh` to distinguish index-level problems from module-level problems.

`verify` also reports module-level refresh scope:

- `project_id`: stable repository identity used by hooks for project-scoped debounce.
- `affected_modules`: module entries whose `Module Path` matches changed files, including `changed_files` and `impact_categories`.
- `affected_module_guides`: the affected module guide paths to refresh.
- `unmapped_changed_files`: non-doc changed files that do not match any current `Module Index` path.
- `changed_files_by_source.baseline_ignored`: paths ignored because they still match the signed local-change baseline.

Use these fields for progressive disclosure: agents should start from `AGENTS.md`, prefer `affected_module_guides` when available, and read only module guides that match the current task or changed files. Signature verification may inspect all module guide files mechanically, but model context should not load every linked guide for ordinary orientation.

Hook messages are debounced per user-local state file, project, and session. The default state file is under `CODEX_HOME/code-project-guidance-map/hooks/state-v1.json`; tests or custom deployments can set `CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE`. Use `CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL=off|error|stale|all` to control hook verbosity. Stop hooks remain read-only, but after code-edit-like prompts they emit a continuation instruction so Codex calls `guidance_map.py build --launcher auto` before finalizing. The helper starts or coordinates the single builder thread, or synchronizes the current context into the active builder, instead of allowing concurrent map construction.

`guidance_map.py build --launcher auto` supports both surfaces. In CLI, it starts the builder with `codex exec` and requires a runnable `codex` command, or an explicit `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND` / `--codex-command`. In Codex Desktop, `auto` returns `desktop_launch_required`; the current Desktop thread must create a new local project thread with the returned prompt and then run the returned `build-attach` command. To force CLI from Desktop, pass `--launcher cli` or configure `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND`.

Builder subagent fan-out is limited by default so large repositories do not open an unbounded number of terminal or agent panes. The default limits are 3 concurrently running module subagents and 8 total module subagents per build pass. Treat the concurrent limit as fixed worker slots: when a module task finishes, the builder must collect the result, then either reuse that same completed agent immediately for the next module task or close it immediately before continuing. Completed agents must not stay open until the end of the build. Tune the limits with `CODE_PROJECT_GUIDANCE_MAP_MAX_CONCURRENT_MODULE_SUBAGENTS`, `CODE_PROJECT_GUIDANCE_MAP_MAX_TOTAL_MODULE_SUBAGENTS`, `--max-concurrent-module-subagents`, or `--max-total-module-subagents`. When the natural module count exceeds the total limit, the builder must merge related paths into coarser module groups.
