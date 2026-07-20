# CI Maintenance

Use CI to keep this plugin, the generated `AGENTS.md` project index, self-hashed manifest, and manifest-backed guide tree reliable without forcing every run to reread the whole project.

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

Target projects can also produce deterministic local planning artifacts without launching Codex:

```powershell
python <installed-skill>\scripts\guidance_map.py scan --repo .
python <installed-skill>\scripts\guidance_map.py benchmark-build --repo .
python <installed-skill>\scripts\guidance_map.py compare-graphify --repo . --query "request routing"
```

`scan` writes `.agents/guidance-map/project-map.json` with file-tree, language, manifest, module-candidate, import, changed-file, and graphify-availability summaries. `benchmark-build` reports project-map size, manifest size, guide-tree size, refresh scope, latest builder metrics, and graphify availability; it only starts a builder when `--start-build` is passed. `compare-graphify` compares those deterministic CPGM metrics and file-query metrics with local graphify graph metadata. Add `--run-graphify` only when CI intentionally allows running graphify query.

This fails only when the guidance index is missing, malformed, has an unsupported guide format, has invalid metadata/self-hash, cannot verify the manifest, or detects unsafe/tampered changed guide files.

Current `action-map:v5` verification needs no signing key. `AGENTS.md`, the manifest, and each guide carry independent short content hashes. These hashes detect content changes but are not authentication. Legacy v3/v4 artifacts may still require their historical key material until they are refreshed to v5.

For stricter projects, use:

```powershell
python <installed-skill>\scripts\guidance_map.py verify --repo . --fail-on stale
```

That also fails when changed files indicate the guidance should be refreshed.

For maximum integrity checking, add a scheduled or stricter job:

```powershell
python <installed-skill>\scripts\guidance_map.py verify --repo . --full --fail-on stale
```

`--full` validates every manifest-backed guide self-hash, manifest identity binding, and guide source snapshot. Ordinary quick verification checks AGENTS.md, manifest integrity, changed files, and changed guide files without hashing the entire guide tree.

Freshness uses two boundaries:

- Manifest `Generated at` bounds committed Git history.
- Manifest `Local change baseline` is a snapshot of staged, unstaged, and untracked file content that existed during the last refresh. `verify` ignores those local paths while their current content still matches the snapshot, so refreshing a dirty worktree does not cause every later thread to ask for the same refresh again.

## Refresh Scope

`verify` classifies changed files into:

- `boundary_rules`: build files, module manifests, workspace configs, and other changes that can affect dependency direction.
- `task_routing`: controllers, routes, APIs, services, DAOs, SQL mappings, jobs, schedules, WebSocket, MQ, and queue files.
- `module_internal`: ordinary code files that usually require only affected module guide files to refresh.
- `docs_only`: documentation or CI changes that do not require a guidance refresh.
- `other`: unclassified files that should be reviewed by a maintainer.

The goal is conservative maintenance:

- Do not re-read the whole repository for ordinary module-internal changes.
- Use boundary-sensitive and routing classifications to decide what to inspect, but change `AGENTS.md` only after confirming project structure, ownership, routing, dependency rules, or guide-tree topology actually changed.
- Ordinary implementation and guide-detail refreshes must preserve `AGENTS.md` byte-for-byte; freshness cursors update in the manifest only.
- Keep `AGENTS.md` compact as an index, and keep module detail in `.agents/guidance-map/guides/**`.
- Use `status` fields such as `content_hash_valid`, `manifest_content_hash_valid`, `manifest_valid`, `tampered_guides`, `stale_guides`, and `requires_module_refresh` to distinguish index-level problems from guide-level problems.

`verify` also reports guide-level refresh scope:

- `project_id`: stable repository identity used by hooks for project-scoped debounce.
- `affected_guides`: manifest guide entries whose `source_globs` match changed files, including `changed_files` and `impact_categories`.
- `affected_module_guides`: compatibility alias containing the affected guide paths to refresh.
- `unmapped_changed_files`: non-doc changed files that do not match any current manifest guide source globs.
- `changed_files_by_source.baseline_ignored`: paths ignored because they still match the manifest local-change baseline.
- `changed_files_by_source.tool_ignored`: generated tool/build/cache outputs such as `graphify-out/`, `node_modules/`, build directories, coverage, and bytecode that are reported for observability but do not make guidance stale.

Use these fields for progressive disclosure: agents should start from `AGENTS.md`, prefer `guidance_map.py query "<task>"`, and read only manifest-verified guide files that match the current task or changed files. Full verification may inspect all guide files mechanically, but model context should not load every linked guide for ordinary orientation.

The plugin registers only a read-only `Stop` hook. It does not run on `SessionStart` or `UserPromptSubmit`; it emits only after Git-visible project modifications make guidance stale. Messages are debounced per user-local state file, project, session, action, and changed-content fingerprint. The default state file is under `CODEX_HOME/code-project-guidance-map/hooks/state-v1.json`; tests or custom deployments can set `CODE_PROJECT_GUIDANCE_MAP_HOOK_STATE_FILE`. Use `CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL=off|error|stale|all` to control hook verbosity. Before emitting, the hook calls `guidance_map.py build-status`. An active builder suppresses the continuation so the caller can finish; otherwise Codex starts or synchronizes the builder and immediately finalizes after `started`, `queued`, or Desktop handoff/attach, without waiting for completion.

`guidance_map.py build --launcher auto` follows the request origin. From Codex Desktop it returns `desktop_launch_required` before probing the CLI, so the caller creates and attaches a new Desktop thread. From Codex CLI it resolves and starts `codex exec`, using `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND` / `--codex-command` when configured. `--launcher desktop` and `--launcher cli` force a specific path. The caller must finalize immediately after start, queue, or Desktop attach and must not monitor builder completion.

Each build writes `*.metrics.json` under the project build-state `logs/` directory with launcher, handoff mode, startup health, refresh-scope summary, and finish status. CLI launches also wait for a JSONL or last-message startup signal and fail early when the process stays alive but produces no startup output. Tune that window with `CODE_PROJECT_GUIDANCE_MAP_BUILDER_STARTUP_HEALTH_SECONDS`.

Manifest guide entries include deterministic guide source snapshots. Code or manifest changes under one guide's source globs invalidate that guide's refresh target without requiring unrelated guides to be treated as stale. `query` refuses to recommend a guide whose own content hash or manifest-bound identity is invalid.

Builder subagent fan-out is limited by default so large repositories do not open an unbounded number of terminal or agent panes. The default limits are 3 concurrently running module subagents and 8 total module subagents per build pass. Treat the concurrent limit as fixed worker slots: when a module task finishes, the builder must collect the result, then either reuse that same completed agent immediately for the next module task or close it immediately before continuing. Completed agents must not stay open until the end of the build. Tune the limits with `CODE_PROJECT_GUIDANCE_MAP_MAX_CONCURRENT_MODULE_SUBAGENTS`, `CODE_PROJECT_GUIDANCE_MAP_MAX_TOTAL_MODULE_SUBAGENTS`, `--max-concurrent-module-subagents`, or `--max-total-module-subagents`. When the natural module count exceeds the total limit, the builder must merge related paths into coarser module groups.
