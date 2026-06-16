# Code Project Guidance Map

[中文说明](README-CN.md)

Code Project Guidance Map is a Codex plugin and skill that turns repository structure into reusable project memory for Codex.

It does not try to generate a giant project manual. It creates a compact `AGENTS.md` project action index, then stores module-specific detail in separate signed Markdown files under `.agents/guidance-map/modules/`.

## Background

This plugin comes from the Codex repository feature request: [Feature request: Add a standardized code audit module for modular codebases #26007](https://github.com/openai/codex/issues/26007).

That issue asks Codex to generate and maintain a standardized code audit module for modular codebases, so later agents do not need to reread large parts of the source tree from scratch. Because the feature request is still open and does not currently show an assignee, project, milestone, or linked implementation PR, this repository implements the workflow as a standalone Codex plugin first.

Part of the inspiration also comes from OpenAI's article [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/), especially its framing of repository-local knowledge as the system of record, `AGENTS.md` as a compact map rather than a giant manual, and agent legibility as an engineering goal.

## What It Does

When invoked in a target repository, the skill will:

- Check whether the repository root has `AGENTS.md` and this plugin's marker block.
- Ask before first generation unless the user already explicitly requested it.
- Let the main agent decide the macro module map from shallow repository signals.
- Require bounded module subagents to read module internals and write one module guide file per module.
- Keep `AGENTS.md` as a compact project index: global editing rules, task routing, dependency rules, and module links.
- Store module-specific structure, entry points, and local rules in `.agents/guidance-map/modules/*.md`.
- Sign every module guide, then write the module signatures into `AGENTS.md`.
- Sign the aggregate `AGENTS.md` index so manual edits or broken module links are detectable.
- Incrementally refresh affected module guides from Git changes instead of rereading the whole project.
- Run lightweight hooks on `SessionStart`, `UserPromptSubmit`, and `Stop` to detect stale, missing, or unverifiable guidance before code edits and after a task ends.

The fixed `AGENTS.md` marker block is:

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

Module guide files have their own plugin-owned signature block:

```markdown
<!-- code-project-guidance-map:module:start -->
Signature: hmac-sha256:<64 lowercase hex chars>
<!-- code-project-guidance-map:module:end -->
```

The current generator version is `0.1.0`, and the current guide format is `action-map:v3`. A missing, invalid, or major/minor-incompatible version requires a full refresh. Patch-only version differences are treated as compatible.

## Quick Start

Clone this repository:

```powershell
git clone <repo-url>
cd Code-Project-Guidance-Map-Skills
```

Register this repository as a Codex plugin marketplace:

```powershell
codex plugin marketplace add <absolute-path-to-this-repo>
```

Install the plugin from that marketplace:

```powershell
codex plugin add code-project-guidance-map@code-project-guidance-map
```

Windows example:

```powershell
codex plugin marketplace add D:\work\Code-Project-Guidance-Map-Skills
codex plugin add code-project-guidance-map@code-project-guidance-map
```

After installation, open a new Codex thread in the project you want to map and invoke:

```text
Use $code-project-guidance-map to create or refresh this repository's signed AGENTS.md project index and per-module guide files. First decide macro module boundaries from shallow repo signals, then spawn bounded module subagents to create or refresh `.agents/guidance-map/modules/*.md`, then use the helper to sign module guides, link them from AGENTS.md, and sign the aggregate index. Do not do module-internal reading in the main thread.
```

## Usage

Generate the guide when Codex first joins a project:

```text
Use $code-project-guidance-map to create this repository's signed AGENTS.md project index and per-module guide files.
```

Refresh after meaningful structure changes:

```text
Use $code-project-guidance-map to refresh the project guidance from recent Git changes, updating only affected module guide files when possible.
```

Use the guide before larger feature work:

```text
Use $code-project-guidance-map, then help me identify where this feature should be implemented.
```

Hooks are read-only. They verify the current repository's guidance and add bounded context when the index or module guides are missing, stale, or unverifiable. Hook reminders are state-machine driven: state is stored in the user's Codex home, but debounce decisions are scoped by project and session so one stale project does not silence another. By default, the same project/session/action is only reported once; `Stop` reminders only appear after a code-edit-like prompt in that session. Set `CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL=off|error|stale|all` to tune hook noise.

Subagents are mandatory for generation and refresh. Module subagents write their assigned module guide files directly. The main agent owns only the macro module map and the compact `AGENTS.md` index draft, then runs the helper to sign module files, backfill module signatures into the index, and write the aggregate signed `AGENTS.md` block. If subagents are unavailable, the skill falls back to `plan-only`: it outputs the macro module map, affected files, bounded subagent scopes, and follow-up command, but does not read module internals or write guidance files.

## Result

After a successful run, `AGENTS.md` contains a compact index like this:

````markdown
<!-- code-project-guidance-map:start -->
## Code Project Guidance Map

Generator: code-project-guidance-map
Generator version: 0.1.0
Guide format: action-map:v3
Generated at: 2026-06-15T10:30:00Z
Git baseline: abc1234
Signature key id: repo:1a2b3c4d5e6f7890
Signature: hmac-sha256:<64 lowercase hex chars>

### Agent Editing Rules

- [MUST] Put new scheduling business rules in `src/core/scheduling`; expose them through API modules only after service behavior exists.
- [SHOULD] Reuse existing services before adding orchestration.
- [AVOID] Adding business or web dependencies to shared utility modules.

### Task Routing

- To add a REST API: edit `src/api`; call services from `src/core` instead of duplicating business logic.
- To change scheduling rules: edit `src/core/scheduling`; refresh the Scheduling module guide if behavior changes.

### Module Dependency Rules

- Shared utilities are the lowest-level code and must not depend on business, web, or persistence modules.
- API modules call services; services own business rules; persistence modules own storage adapters and SQL.

### Module Index

#### Scheduling

- Module Path: `src/core/scheduling`
- Module Guide: `.agents/guidance-map/modules/scheduling.md`
- Module Signature: `hmac-sha256:<64 lowercase hex chars>`
- Owns: Scheduling rules, shift rotation decisions, and scheduling-domain service behavior.
- Change here when: A task changes how schedules are calculated, validated, or persisted through domain services.
- Do not put here: HTTP response shaping, frontend-only DTOs, or generic shared helpers.
<!-- code-project-guidance-map:end -->
````

The linked module file contains the detail:

````markdown
<!-- code-project-guidance-map:module:start -->
Signature: hmac-sha256:<64 lowercase hex chars>
<!-- code-project-guidance-map:module:end -->

# Scheduling

- Module Path: `src/core/scheduling`
- Owns: Scheduling rules, shift rotation decisions, and scheduling-domain service behavior.
- Change here when: A task changes how schedules are calculated, validated, or persisted through domain services.
- Do not put here: HTTP response shaping, frontend-only DTOs, or generic shared helpers.
- Key entry points:

```text
src/core/scheduling/
  services/
  strategies/
  tests/
```

## Internal Structure

- `services/` owns scheduling use cases.
- `strategies/` owns rotation variants.

## Local Rules

- Keep scheduling rules in services or strategies, not in API adapters.
````

This layout helps Codex answer:

- Which module owns a behavior?
- Which module guide should be refreshed?
- Which directories should be read before editing?
- Whether a broken signature affects the whole index or only one module guide.

## Distribution

This repository already contains a distributable plugin package:

- Development skill: `.agents/skills/code-project-guidance-map/`
- Installable plugin: `plugins/code-project-guidance-map/`
- Plugin manifest: `plugins/code-project-guidance-map/.codex-plugin/plugin.json`
- Plugin hooks: `plugins/code-project-guidance-map/hooks/`
- Local marketplace: `.agents/plugins/marketplace.json`

To install the plugin, users need access to this repository and then run:

```powershell
codex plugin marketplace add <absolute-path-to-this-repo>
codex plugin add code-project-guidance-map@code-project-guidance-map
```

To publish it through a team marketplace:

1. Publish this repository somewhere the team can access, such as GitHub, an internal Git server, or a shared directory.
2. Keep `plugins/code-project-guidance-map/.codex-plugin/plugin.json`.
3. Keep `.agents/plugins/marketplace.json`; its marketplace name is `code-project-guidance-map`.
4. Tell users to add the marketplace first and then install `code-project-guidance-map@code-project-guidance-map`.

## Development And Validation

The development skill is the source of truth:

```text
.agents/skills/code-project-guidance-map/
```

After changing the skill, sync it into the distributable plugin copy:

```powershell
python scripts\sync_plugin_skill.py
python scripts\sync_plugin_skill.py --check
```

Treat drift between the development skill and plugin skill copy as a release blocker.

Then validate:

```powershell
python scripts\test_sync_plugin_skill.py
python .agents\skills\code-project-guidance-map\scripts\test_guidance_map.py
python plugins\code-project-guidance-map\skills\code-project-guidance-map\scripts\test_guidance_map.py
python plugins\code-project-guidance-map\hooks\test_guidance_map_hook.py
python <codex-checkout>\codex-rs\skills\src\assets\samples\skill-creator\scripts\quick_validate.py .agents\skills\code-project-guidance-map
python <codex-checkout>\codex-rs\skills\src\assets\samples\skill-creator\scripts\quick_validate.py plugins\code-project-guidance-map\skills\code-project-guidance-map
python <plugin-creator-skill>\scripts\validate_plugin.py plugins\code-project-guidance-map
```

See [docs/ci.md](docs/ci.md) for GitHub Actions and target-project `verify` CI guidance.

If the plugin is already installed locally, reinstall it after changes:

```powershell
python <plugin-creator-skill>\scripts\update_plugin_cachebuster.py plugins\code-project-guidance-map
codex plugin add code-project-guidance-map@code-project-guidance-map
```

Then start a new Codex thread so Codex loads the updated plugin.

## Project Intent

This project moves Codex from temporary source reading toward reusable project memory.

The goal is not a complete project manual. The plugin preserves module boundaries, dependency direction, ownership rules, and compact navigation cues in a form later Codex sessions can verify and refresh incrementally.
