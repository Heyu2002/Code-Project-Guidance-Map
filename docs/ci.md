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

Hook reminders are debounced per user-local state file, project, and session. The default state file is under `CODEX_HOME/code-project-guidance-map/hooks/state-v1.json`; tests or custom deployments can set `CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE`. Use `CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL=off|error|stale|all` to control hook verbosity.
