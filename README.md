# Code Project Guidance Map

[中文说明](README-CN.md)

[Changelog](CHANGELOG.md)

Code Project Guidance Map is a Codex plugin and skill that turns repository structure into reusable project memory for Codex.

It does not try to generate a giant project manual. It creates a compact `AGENTS.md` project action index, then stores module-specific detail in a manifest-backed guide tree under `.agents/guidance-map/guides/`.

## Repomix Comparison Summary

See [docs/repomix-comparison.md](docs/repomix-comparison.md) for the full same-dimension benchmark against [Repomix](https://github.com/yamadashy/repomix). The benchmark used four freshly cloned remote repositories under `D:\project\test\repomix-cpgm-benchmark-20260703`, covering Python, Java, C#, and Rust projects from small/simple to large/complex. None of the samples had prior Code Project Guidance Map or Repomix artifacts before the run.

Short version: Repomix is excellent when you want a fast, one-command full repository context package. Code Project Guidance Map is stronger when Codex needs a reusable, reviewable, integrity-checked editing route that keeps startup and task context small. In this run, Repomix full output ranged from 38,214 to 863,168 tokens, and `--compress` still ranged from 31,916 to 750,059 tokens; CPGM query selected 756 to 843 estimated guide tokens. That means Repomix full context was 50.5x to 1040.0x larger than the CPGM selected guide context, while compressed Repomix was still 42.2x to 903.7x larger.

The table below summarizes the practical advantage split: use Repomix for portable full-context snapshots, and use this plugin for Codex editing memory, manifest-backed trust, and task-routed lazy context.

| Dimension | Code Project Guidance Map advantage | Repomix advantage | Measured evidence from this run | Practical difference |
|---|---|---|---|---|
| Default context shape | Tiny `AGENTS.md` plus lazy manifest-verified guide files. | Single AI-friendly full-repo file in Markdown/XML/JSON/plain text. | CPGM selected 4.3-6.2 KB per query; Repomix full output was 125.8 KB-2.95 MB. | CPGM is better for repeated Codex edits; Repomix is better for one-shot upload or paste workflows. |
| Token pressure | Task query returned only 756-843 estimated guide tokens. | Provides explicit token totals for the packed repository. | Repomix full was 38,214-863,168 tokens; compressed was 31,916-750,059 tokens. | CPGM reduces routine task context; Repomix makes total context cost visible. |
| Integrity and freshness | Per-artifact short hashes, source snapshots, and `verify --full`. | Built-in suspicious-file/security check during packing. | All four CPGM manifests were valid with 0 tampered and 0 stale guides; all Repomix runs passed security check. | CPGM detects guidance changes and stale guide scope; Repomix helps avoid leaking suspicious packed content. |
| Query and routing | `guidance_map.py query "<task>"` returns top guide paths, source candidates, and verified guide count. | Output file can be searched or handed to any LLM/tool. | CPGM query took 1.139-1.280s and selected 5 verified guides. | CPGM gives Codex an editing route; Repomix gives a portable corpus. |
| Setup speed | Deterministic scan took 0.800-1.300s. | Cached `npx repomix` full pack took 4.044-4.513s with no project-specific guidance draft. | CPGM scan is faster, but deterministic update + full verify + query makes initialization about 6.4-9.3s. | Repomix wins simplest first package; CPGM pays setup cost for reusable integrity-checked routing. |
| Long-term project memory | Artifacts can live in git, be reviewed, queried, and checked in CI. | Generated output is usually disposable or regenerated. | CPGM wrote compact `AGENTS.md`, manifest, and 7-9 guide files per sample. | CPGM is a project memory layer; Repomix is a context export layer. |

## graphify Comparison Summary

See [docs/graphify-comparison.md](docs/graphify-comparison.md) for the full benchmark against [graphify](https://github.com/safishamsi/graphify) on fresh remote Java, Python, Rust, and C# repositories.

Short version: Code Project Guidance Map is an editing-route memory layer for Codex (`AGENTS.md` plus a self-hashed manifest and lazy guide tree), while graphify is a queryable knowledge-graph index (`graphify-out/graph.json` plus reports/tools). In this run, graphify produced AST-only graphs in 2.65s to 64.30s and estimated 10.4x to 23.7x fewer query tokens than naive full-context reading; this plugin's `verify` path classified fresh repositories in 0.46s to 0.71s, and a native Codex builder run generated a valid Spring guide `AGENTS.md` plus five module guides in 6m14s. After the deterministic pre-scan work, `compare-graphify` measured 0-token CPGM project maps in about 0.9s to 1.4s, with outputs 8.7x to 135.3x smaller than the corresponding graphify JSON graphs. The v5 tree-guide flow adds manifest-backed file query: `query` verifies the manifest and only returns guide files whose self-hash and identity are valid, while graphify remains an explicit deep-structure query path. The report now includes a same-dimension matrix covering format, token/context cost, speed, scale, language coverage, query ability, editing constraints, CI fit, offline behavior, and pre-scan/tree-guide comparisons.

## Background

This plugin comes from the Codex repository feature request: [Feature request: Add a standardized code audit module for modular codebases #26007](https://github.com/openai/codex/issues/26007).

That issue asks Codex to generate and maintain a standardized code audit module for modular codebases, so later agents do not need to reread large parts of the source tree from scratch. Because the feature request is still open and does not currently show an assignee, project, milestone, or linked implementation PR, this repository implements the workflow as a standalone Codex plugin first.

Part of the inspiration also comes from OpenAI's article [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/), especially its framing of repository-local knowledge as the system of record, `AGENTS.md` as a compact map rather than a giant manual, and agent legibility as an engineering goal.

## What It Does

When invoked in a target repository, the skill will:

- Check whether the repository root has `AGENTS.md` and this plugin's marker block.
- Ask before first generation unless the user already explicitly requested it.
- Start or coordinate one Codex builder thread per repository through `guidance_map.py build`.
- Synchronize later build requests into the active builder instead of allowing concurrent map construction.
- Let the builder agent decide the macro module map from shallow repository signals.
- Require bounded module subagents to read module internals and write one module guide file per module group, with default resource limits of 3 concurrent module subagents and 8 total module subagents per build pass.
- Keep `AGENTS.md` as a compact project index: global editing rules, task routing, dependency rules, and a manifest pointer.
- Store module-specific structure, entry points, and local rules in `.agents/guidance-map/guides/**`.
- Write `.agents/guidance-map/manifest.json` with freshness cursors, guide ids, parent/child links, tags, source globs, and source snapshots.
- Give `AGENTS.md`, the manifest, and each guide its own short content hash. Each file is responsible only for its own content; the hashes detect changes but are not authentication.
- Incrementally refresh affected guide-tree leaves from Git changes instead of rereading the whole project.
- Capture the local-change baseline in the manifest during refresh so dirty worktree files do not repeatedly trigger stale guidance until their content changes again.
- Run one modification-only `Stop` hook after Git-visible project changes; it routes stale guidance through the single-builder helper without injecting context at session start or prompt submission.

The fixed `AGENTS.md` marker block is:

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

Tree guide files have their own plugin-owned metadata block and short self-hash:

```markdown
<!-- code-project-guidance-map:guide:start -->
Guide ID: backend.api.controllers
Guide kind: leaf
Guide path: .agents/guidance-map/guides/backend/api/controllers.md
Parent guide ID: backend.api
Content hash: sha256:<16 lowercase hex chars>
<!-- code-project-guidance-map:guide:end -->
```

The current generator version is `0.4.0`, and the current guide format is `action-map:v5`. Legacy `action-map:v3` and `action-map:v4` blocks can still be inspected and queried, but the next refresh rewrites them into the v5 self-hashed guide tree. A missing, invalid, or major/minor-incompatible current version requires a full refresh. Patch-only version differences are treated as compatible.

Freshness cursors live in the manifest. `Generated at` bounds committed Git history, while `Local change baseline` records staged, unstaged, and untracked file content that existed during the last refresh. A new Codex thread should not ask for another refresh for the same dirty files unless those files change again.

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
Use $code-project-guidance-map to refresh the self-hashed AGENTS.md guidance map via its single builder.
```

The build helper uses `guidance_map.py build --launcher auto`. `auto` first launches through `codex exec`, using a runnable `codex` command on PATH or `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND` / `--codex-command`. Do not assume the Codex Desktop app installs a script-callable CLI for every user. If no CLI is available but the request is running inside Codex Desktop, `auto` prepares `desktop_manual_handoff_required`: a `.handoff.md` file, a short `codex://new?path=...&prompt=...` deep link, and attach/cleanup commands so the user can open a new local Desktop thread without pasting the full builder prompt. `--launcher desktop` remains an explicit handoff path for environments where a Codex Desktop thread creation tool is available.

## Usage

Generate the guide when Codex first joins a project:

```text
Use $code-project-guidance-map to request creation of this repository's self-hashed AGENTS.md project index and per-module guide files through the helper build command.
```

Refresh after meaningful structure changes:

```text
Use $code-project-guidance-map to queue a project guidance refresh from recent Git changes through the single builder.
```

Use the guide before larger feature work:

```text
Use $code-project-guidance-map, then help me identify where this feature should be implemented.
```

Use deterministic local routing without launching a builder:

```powershell
python <installed-skill>\scripts\guidance_map.py scan --repo .
python <installed-skill>\scripts\guidance_map.py query "add an API controller" --repo .
python <installed-skill>\scripts\guidance_map.py benchmark-build --repo .
python <installed-skill>\scripts\guidance_map.py compare-graphify --repo . --query "add an API controller"
```

`scan` writes `.agents/guidance-map/project-map.json` with file-tree, language, manifest, module-candidate, import, changed-file, and graphify-availability summaries. `query` reads the self-hashed manifest, scores guide-tree entries, verifies selected guide self-hashes and identities, and recommends guide paths, source paths, test paths, and optional graphify query commands without loading `graphify-out/graph.json` into context. Add `--run-graphify` only when you want the helper to run graphify query and capture bounded output. `benchmark-build` reports deterministic readiness, manifest size, guide-tree size, refresh scope, and latest builder metrics by default; pass `--start-build` only when you intentionally want it to launch the coordinated builder. `compare-graphify` puts CPGM project-map/tree-query metrics beside local graphify graph metadata and optional query evidence.

## Progressive Disclosure

Generated guidance is intentionally layered. Later Codex sessions should start with the compact `AGENTS.md` index, use `guidance_map.py query "<task>"`, and open only the manifest-verified guide files it recommends. Guide files are lazy context, not startup context; ordinary tasks should usually read only 1-5 guide files before editing.

Manifest guide entries include lazy-read hints:

```markdown
- Read guide when: Editing hook behavior, hook state, hook tests, or hook config.
- Usually skip when: Only changing helper signing, README copy, or plugin marketplace metadata.
```

The hook is read-only and is registered only for `Stop`. It does nothing at `SessionStart` or `UserPromptSubmit`, and it emits only when Git-visible project changes make the index or guide tree stale or unverifiable. Debounce state is scoped by project, session, action, and changed-content fingerprint. Before emitting, the hook checks `guidance_map.py build-status`; if a CLI or Desktop builder is already active, it stays silent so the caller thread can finish. Otherwise it tells Codex to call `guidance_map.py build --launcher auto`, then finalize immediately after the request is started, queued, or handed off. The caller must not wait for, poll, read, or follow the builder thread. Set `CODE_PROJECT_GUIDANCE_MAP_HOOK_LEVEL=off|error|stale|all` to tune hook noise.

Subagents are mandatory for generation and refresh, but only inside the script-coordinated builder agent. Ordinary threads must not construct the map directly; they call `guidance_map.py build --launcher auto` and stop once the request is started, queued, or handed off to a Desktop builder thread. They do not wait for or follow builder completion. Module subagents write their assigned guide-tree files directly, but fan-out is capped and lifecycle-managed: by default the builder may run at most 3 module subagents at once and create at most 8 module subagents in one build pass. Treat those concurrent agents as worker slots. When a module task finishes, the builder must collect the result, then either reuse that same completed agent immediately for the next module task or close it immediately before moving on. Completed agents must not pile up until the end of the build. If a repository has more natural modules, the builder must choose a mixed-depth tree and merge related paths instead of opening more terminals or agent panes. Tune this with `CODE_PROJECT_GUIDANCE_MAP_MAX_CONCURRENT_MODULE_SUBAGENTS`, `CODE_PROJECT_GUIDANCE_MAP_MAX_TOTAL_MODULE_SUBAGENTS`, or the matching `build` flags. The builder agent owns only the macro guide tree and compact `AGENTS.md` draft, then runs the helper to self-hash each artifact. Non-structural refreshes update guides and manifest while preserving `AGENTS.md` byte-for-byte; only actual project-level rule, routing, ownership, or guide-tree topology changes rewrite it. If coding changes make guidance stale, Codex should start or synchronize the builder before the final response, then return immediately. If builder subagents are unavailable, the builder falls back to `plan-only`: it outputs the macro guide tree, affected files, bounded subagent scopes, and follow-up command, but does not read module internals or write guidance files.

Builds write observable artifacts under the per-project build state `logs/` directory: `*.prompt.md`, `*.jsonl`, `*.last-message.md`, and `*.metrics.json`. Desktop handoff builds also write `*.handoff.md`. CLI launches wait briefly for a JSONL or last-message startup signal; if the process stays alive but writes nothing, the helper fails early with a diagnostic instead of leaving a silent builder lease behind. Tune that startup window with `CODE_PROJECT_GUIDANCE_MAP_BUILDER_STARTUP_HEALTH_SECONDS`.

`verify` ignores common generated tool outputs such as `graphify-out/`, `node_modules/`, Python caches, Rust/JavaScript/.NET build directories, coverage output, and compiled bytecode. These paths are reported under `changed_files_by_source.tool_ignored` but do not make guidance stale.

Manifest entries bind each guide's identity and deterministic source snapshot. `query` refuses to recommend a guide whose own content hash or manifest-bound identity is invalid. When source or manifest files under a guide's source globs change, that guide becomes the refresh target while unrelated guides can remain valid. Use `verify --full` when CI should validate every guide self-hash and source snapshot.

## Result

After a successful run, `AGENTS.md` contains a compact index like this:

````markdown
<!-- code-project-guidance-map:start -->
## Code Project Guidance Map

Generator: code-project-guidance-map
Generator version: 0.4.0
Guide format: action-map:v5
Content hash: sha256:<16 lowercase hex chars>

### Agent Editing Rules

- [MUST] Put new scheduling business rules in `src/core/scheduling`; expose them through API modules only after service behavior exists.
- [MUST] Treat linked module guides as lazy context; start from this index and read only task-relevant module guides.
- [SHOULD] Reuse existing services before adding orchestration.
- [AVOID] Adding business or web dependencies to shared utility modules.

### Progressive Disclosure

- Start with this `AGENTS.md` index for broad orientation.
- Use `guidance_map.py query "<task>"` before opening guide files.
- Read only manifest-verified guide files returned by query unless the task is explicitly project-wide.
- Do not open the whole guide tree for ordinary orientation.

### Task Routing

- To add a REST API: edit `src/api`; call services from `src/core` instead of duplicating business logic.
- To change scheduling rules: edit `src/core/scheduling`; refresh the Scheduling module guide if behavior changes.

### Module Dependency Rules

- Shared utilities are the lowest-level code and must not depend on business, web, or persistence modules.
- API modules call services; services own business rules; persistence modules own storage adapters and SQL.

### Guidance Manifest

Guidance manifest: `.agents/guidance-map/manifest.json`
<!-- code-project-guidance-map:end -->
````

The self-hashed manifest points at a mixed-depth guide tree:

````markdown
<!-- code-project-guidance-map:guide:start -->
Guide ID: scheduling.rules
Guide kind: leaf
Guide path: .agents/guidance-map/guides/scheduling/rules.md
Parent guide ID: scheduling
Content hash: sha256:<16 lowercase hex chars>
<!-- code-project-guidance-map:guide:end -->

# Scheduling Rules

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
- Which artifact's own content hash is invalid without making that artifact responsible for all others.

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
