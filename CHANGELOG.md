# Changelog

All notable changes to this project are documented here.

This project follows semantic versioning for the guidance generator version. Patch-only generator changes are treated as compatible by the verifier; major or minor mismatches require a full guidance refresh.

## Unreleased

### Added

- Added `action-map:v4` manifest-backed guide trees under `.agents/guidance-map/guides/**`, with `.agents/guidance-map/manifest.json` as the signed machine-readable index.
- Added high-integrity guide validation: `AGENTS.md` signs the manifest digest, the manifest signs guide content digests/source snapshots, guide paths are constrained to the guide tree, and `query` refuses tampered guide files.
- Added v4 file-query routing that scores manifest guide entries by task tokens, tags, read/skip triggers, source globs, changed files, and parent/child relationships before verifying only the selected top guides.
- Added `verify --full` to validate every manifest-backed guide digest and source snapshot, while default verification keeps the quick AGENTS/manifest/changed-guide path.
- Added `cleanup-legacy` to dry-run or remove unreferenced legacy v3 `.agents/guidance-map/modules/*.md` files after migration.
- Added single-builder launch coordination for `guidance_map.py build`, including per-repository build state, active-builder leases, queued request context, `build-drain`, `build-finish`, and stale lease handling.
- Added `--launcher auto|cli|desktop` so default builds launch through `codex exec`, while environments with an available Codex Desktop thread creation tool can explicitly request a Desktop builder prompt with `--launcher desktop` and attach it with `build-attach`.
- Added Desktop fallback output for `desktop_launch_required`, including the builder prompt, attach command, and failure cleanup command.
- Added Desktop-only manual handoff output for `desktop_manual_handoff_required`, including a `.handoff.md` file, short `codex://new` deep link, manual attach id, and cleanup command for users without a runnable CLI.
- Added builder startup health checks that fail early when a launched builder process stays alive but produces no JSONL or last-message output.
- Added per-build `*.metrics.json` files with launcher, handoff mode, startup health, refresh-scope summary, and finish status.
- Added deterministic `scan` and `.agents/guidance-map/project-map.json` output with language, manifest, module-candidate, import, changed-file, and graphify-availability summaries.
- Added `query` to route a task to recommended module guides, source paths, test paths, dependency rules, and optional graphify query commands without loading graph JSON into context. `--run-graphify` can run graphify query explicitly and capture bounded output.
- Added `benchmark-build` to collect deterministic build-readiness, guidance size, project-map, graphify, and latest builder metrics, with opt-in `--start-build`.
- Added `compare-graphify` to place CPGM project-map/build metrics beside local graphify graph metadata and optional query evidence.
- Added post-optimization graphify comparison results showing 0-token CPGM project maps at 0.9s-1.4s and 8.7x-135.3x smaller than corresponding graphify JSON graphs across the benchmark samples.
- Kept legacy module source snapshot support for v3 blocks while v4 uses manifest guide source snapshots for targeted refresh.
- Added module subagent fan-out and lifecycle limits for builder runs, defaulting to 3 concurrent worker slots and 8 total module subagents per build pass, with environment-variable and CLI overrides. Completed module agents must now be immediately reused for the next module task or closed.
- Added tests for active-builder queuing, CLI launcher validation, explicit/manual Desktop handoff, Desktop attachment, startup-health failure detection, ignored tool outputs, build metrics, and queue-before-launcher-resolution behavior.

### Changed

- Replaced the `SessionStart` and `UserPromptSubmit` hooks with a modification-only `Stop` hook driven by Git-visible changes.
- Added read-only builder status checks so an active CLI or Desktop builder suppresses Stop continuation; caller threads now finalize immediately after start, queue, or handoff instead of waiting for builder completion.
- Changed fresh `update` output from v3 flat module guides to v4 `AGENTS.md` + signed manifest + mixed-depth guide tree. Legacy v3 blocks remain inspectable/queryable, and refresh rewrites them into v4.
- Changed `AGENTS.md` to store a compact manifest pointer/digest instead of every module guide signature, reducing startup context and signature churn.
- Changed `benchmark-build` and `compare-graphify` to report manifest bytes, guide counts, parent/leaf counts, average guide size, file-query latency, selected guide context size, and graphify query output metrics.
- Updated skill instructions, hook messages, README copy, CI docs, and plugin metadata so ordinary threads always route map construction through the single builder instead of building directly.
- Shortened the plugin default prompt so Codex Desktop accepts it.
- Changed `--launcher auto` to prefer a runnable CLI, then fall back to Desktop-only manual handoff inside Codex Desktop instead of assuming Desktop can always create a background thread or exposes a script-callable CLI. Users can still request the thread-tool Desktop handoff explicitly with `--launcher desktop`.
- Changed Windows builder launches to request hidden process startup where supported, reducing visible terminal noise for CLI-backed builds.
- Changed `verify` to ignore common generated tool/build/cache outputs such as `graphify-out/`, `node_modules/`, build directories, coverage, and bytecode while still reporting them under `changed_files_by_source.tool_ignored`.

## 0.2.1 - 2026-06-16

### Added

- Added generator version compatibility checks and semver-aware refresh behavior.
- Added signed local-change baselines so existing dirty worktree files do not repeatedly trigger stale guidance unless their content changes.
- Added targeted refresh scope for affected modules, dependency rules, task routing, and unmapped changed files.
- Added hook debounce state scoped by project, session, event, and recommended action.

### Changed

- Improved hook guidance so stale or unverifiable maps route through the helper workflow.
- Documented freshness, signatures, hook behavior, and local-change baseline behavior in README and CI docs.

## 0.2.0 and Earlier - 2026-06-11 to 2026-06-12

### Added

- Added the Codex plugin and `code-project-guidance-map` skill.
- Added marker-delimited `AGENTS.md` project index generation.
- Added per-module Markdown guide files under `.agents/guidance-map/modules/`.
- Added HMAC signatures for module guides and the aggregate `AGENTS.md` index.
- Added `status`, `verify`, and `update` helper commands.
- Added action-map output with agent editing rules, progressive disclosure, task routing, module dependency rules, and module index entries.
- Added freshness hooks for `SessionStart`, `UserPromptSubmit`, and `Stop`.
- Added plugin skill sync tooling and tests to keep the development skill and packaged plugin skill copy aligned.

### Changed

- Moved module internals out of `AGENTS.md` and into lazy-read module guides.
- Required bounded module subagents for module-internal reading and module guide writing.
