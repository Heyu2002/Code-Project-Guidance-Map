# Changelog

All notable changes to this project are documented here.

This project follows semantic versioning for the guidance generator version. Patch-only generator changes are treated as compatible by the verifier; major or minor mismatches require a full guidance refresh.

## Unreleased

### Added

- Added single-builder launch coordination for `guidance_map.py build`, including per-repository build state, active-builder leases, queued request context, `build-drain`, `build-finish`, and stale lease handling.
- Added `--launcher auto|cli|desktop` so pure CLI users launch through `codex exec`, while pure Codex Desktop users can create a Desktop builder thread from the returned prompt and attach it with `build-attach`.
- Added Desktop fallback output for `desktop_launch_required`, including the builder prompt, attach command, and failure cleanup command.
- Added module subagent fan-out and lifecycle limits for builder runs, defaulting to 3 concurrent worker slots and 8 total module subagents per build pass, with environment-variable and CLI overrides. Completed module agents must now be immediately reused for the next module task or closed.
- Added tests for active-builder queuing, CLI launcher validation, Desktop handoff, Desktop attachment, and queue-before-launcher-resolution behavior.

### Changed

- Updated skill instructions, hook messages, README copy, CI docs, and plugin metadata so ordinary threads always route map construction through the single builder instead of building directly.
- Shortened the plugin default prompt so Codex Desktop accepts it.
- Changed `--launcher auto` to prefer Codex Desktop handoff inside Desktop threads unless a CLI command is explicitly configured, avoiding Windows CLI process access and stdin pipe hangs.
- Changed Windows builder launches to request hidden process startup where supported, reducing visible terminal noise for CLI-backed builds.

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
