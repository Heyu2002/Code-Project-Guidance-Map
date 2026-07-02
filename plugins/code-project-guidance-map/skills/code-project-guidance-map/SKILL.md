---
name: code-project-guidance-map
description: Create or refresh a structured AGENTS.md project action index plus a signed manifest-backed guide tree. Use when the user asks Codex to read a project, map code structure, document module ownership, clarify module dependency boundaries, initialize project guidance, refresh an AGENTS.md project guide, or keep concise project editing guidance up to date from Git changes. Ordinary invocations must run the helper `build` command so a single script-coordinated Codex builder thread owns map construction; only that builder may perform the direct macro-map, bounded-subagent, and signing workflow.
---

# Code Project Guidance Map

## Objective

Create or refresh the `code-project-guidance-map` block in the repository root `AGENTS.md`, plus `.agents/guidance-map/manifest.json` and manifest-backed Markdown guide files under `.agents/guidance-map/guides/`.

`AGENTS.md` is only the project action index. It should contain project-level metadata, global editing/routing/dependency rules, progressive-disclosure rules, and the signed manifest pointer/digest. Do not put module-internal structure, long file inventories, guide-tree internals, or deep implementation notes directly in `AGENTS.md`.

The guide tree contains the module-specific detail. Guide files are lazy context, not startup context: later agents should run `guidance_map.py query "<task>"` and read only the manifest-verified guide files returned for the task. Each manifest entry records guide id, parent id, path, tags, read/skip triggers, source globs, content digest, and source snapshot. `AGENTS.md` signs the manifest digest, and the manifest signs the guide digests. A guide whose content digest does not match the manifest must not be read as trusted context.

This skill must protect the main thread context and enforce a single construction owner. Ordinary Codex threads must not construct or refresh the map directly. They must hand off to `guidance_map.py build`, which creates or coordinates one Codex builder thread and exits after the builder is running or the request has been queued. If another builder is already active, the script records the new request context for that active builder; it must not start a second builder.

The script-coordinated builder may do shallow repository scanning, macro module planning, index integration, and the final helper command, but module-internal reading and module-guide writing must still run in bounded module subagents.

The builder must also protect the user's machine from subagent fan-out. Unless the builder prompt gives different values, run no more than 3 module subagents at the same time and create no more than 8 module subagents in one build pass. Treat those numbers as hard resource limits, not suggestions.

## Markers

Manage only the content between these exact `AGENTS.md` markers:

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

Tree guide files use these exact metadata markers:

```markdown
<!-- code-project-guidance-map:guide:start -->
<!-- code-project-guidance-map:guide:end -->
```

Do not rewrite user-authored content outside the `AGENTS.md` marker block. Do not manually edit manifest signatures or generated guide metadata; use the helper.

## Entry Mode Gate

First determine whether this agent is the script-coordinated builder.

- If the prompt includes a build id from `guidance_map.py build` and says this is the script-coordinated Code Project Guidance Map builder agent, continue to `Builder Agent Workflow` below. Do not call `guidance_map.py build` again.
- Otherwise, do not inspect module internals, decide module boundaries, spawn module subagents, write guide files, or run `guidance_map.py update`. Locate the repository root and run:

```bash
python <skill-dir>/scripts/guidance_map.py build --repo <repo-root> --launcher auto --context "<brief current user request and any relevant thread context>"
```

- If the command returns `status: started`, report that the CLI-launched builder agent was launched and stop this thread's map work.
- If the command returns `status: queued`, report that another builder is already running and that this thread's context was synchronized for the active builder to consume before it finishes.
- If the command returns `status: desktop_manual_handoff_required`, this is the Desktop-only fallback for users without a runnable CLI. Open the returned `desktop_deep_link` when possible, or create a new local Codex Desktop thread in the returned repo with the returned `handoff_prompt`. The new Desktop thread must read the returned `handoff_file`, run the attach command inside it, then execute the builder prompt file. After handing off, stop this thread's map work. If the handoff cannot be started, run the returned `finish_failed_command` with an explanatory message.
- If the command returns `status: desktop_launch_required`, this is an explicit `--launcher desktop` handoff path. Use it only when the Codex Desktop thread creation tool is actually available. Create a new local project thread with the returned `prompt`, then run the returned `attach_command` with the created thread id. If thread creation fails, run the returned `finish_failed_command` with an explanatory message. After attach succeeds, report that the Desktop builder thread was launched and stop this thread's map work.
- If the command fails because `codex` is unavailable or cannot be started outside Codex Desktop, report the failure and ask the user to install Codex CLI or set `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND` / `--codex-command`. Do not assume the Codex Desktop app installed a script-callable CLI, and do not fall back to direct construction in the current thread.

Launcher behavior:

- `--launcher auto` starts the builder with `codex exec` when a runnable CLI exists. If no CLI exists and the current environment is Codex Desktop, it prepares a Desktop-only manual handoff using a `.handoff.md` file and short `codex://new` deep link instead of failing or building in the current thread.
- `--launcher cli` always starts the builder with `codex exec`. It needs a runnable `codex` command on PATH, or `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND` / `--codex-command` pointing at one. Do not assume every Codex Desktop install exposes a runnable CLI.
- `--launcher desktop` is an explicit handoff path for environments where the Codex Desktop thread creation tool is available. It creates the single build lease and returns a Desktop builder prompt, and the current Desktop thread must call the app's thread creation tool.

## Builder Agent Workflow

1. Locate the repository root.
   - Prefer `git rev-parse --show-toplevel`.
   - If Git is unavailable or the directory is not a Git repository, use the current working directory.

2. Inspect `AGENTS.md` state with:

```bash
python <skill-dir>/scripts/guidance_map.py status --repo <repo-root>
```

Then classify freshness and refresh scope with:

```bash
python <skill-dir>/scripts/guidance_map.py verify --repo <repo-root>
```

Also read the deterministic project map produced by the build helper:

```bash
python <skill-dir>/scripts/guidance_map.py scan --repo <repo-root>
```

The scan writes `.agents/guidance-map/project-map.json` with file-tree, language, manifest, module-candidate, import, changed-file, and graphify-availability summaries. Use it for macro module planning before any source-level exploration.

3. If `AGENTS.md` is missing or has no guidance block, ask the user whether to read the project and generate the guide. If the user already explicitly requested generation or refresh, treat that as consent and continue.

4. If a guidance block exists:
   - Read its `Generator version`, `Generated at` timestamp, guide format, signature key id, aggregate signature, manifest path, and manifest digest.
   - Use the script `verify` JSON to inspect Git changes since that timestamp, including committed, staged, unstaged, and untracked files. The helper filters out local changes whose current content still matches the signed `Local change baseline` captured during the last refresh.
   - If the generator version is missing, invalid, or has a different major/minor version from the current helper, perform a full refresh through the mandatory subagent workflow.
   - If only the patch version differs, keep the existing project index and module guide files as reusable unless Git changes require a scoped refresh.
   - If the aggregate `AGENTS.md` signature is invalid, perform a full refresh.
   - If the manifest is invalid, missing, mismatched with `AGENTS.md`, or one or more changed guide files are tampered, refresh the affected guide files and manifest.
   - If `recommended_action` is `refresh_dependency_rules`, re-evaluate project-level `Agent Editing Rules`, `Module Dependency Rules`, and affected module index entries.
   - If `recommended_action` is `refresh_task_routing_and_affected_modules`, refresh task routing guidance and affected module guides.
   - If `recommended_action` is `refresh_affected_modules`, re-read only affected modules and refresh only their module guide files.
   - If `recommended_action` is `none`, report that the guide is current unless the user explicitly asks for a full refresh.

5. Define `run_mode` before any source reading beyond shallow inspection:
   - `no-op`: `verify.recommended_action` is `none`, the existing block, manifest, and changed guide digests are valid, and the user did not explicitly request generation or full refresh.
   - `generate`: `AGENTS.md` is missing or has no guidance block and the user consents or already requested generation.
   - `full_refresh`: `verify.recommended_action` is `full_refresh`, index metadata/signature/format/version is invalid, module boundaries are no longer trustworthy, or the user explicitly requests a full refresh.
   - `incremental_refresh`: `verify.recommended_action` is `refresh_dependency_rules`, `refresh_task_routing_and_affected_modules`, `refresh_affected_modules`, or `review_changed_files`.
   - `plan-only`: a safe fallback when `run_mode` would otherwise be `generate`, `full_refresh`, or `incremental_refresh`, but no subagent/delegation tool is available.
   - For `generate`, `full_refresh`, and `incremental_refresh`, module subagents are mandatory.
   - If no subagent/delegation tool is available for any non-`no-op` run mode, switch to `plan-only`; do not fall back to builder-thread module-internal source reading.
   - In `plan-only`, output only the proposed macro module map, affected changed files, bounded subagent scopes, and the exact follow-up `$code-project-guidance-map` request needed to perform the refresh when subagents are available.
   - In `plan-only`, do not write `AGENTS.md`, do not create or update module guide files, do not run `guidance_map.py update`, and do not read module internals.

6. Decide the macro module map before delegation.
   - The builder agent owns the global guide tree: choose concise guide ids/names, group paths into modules, decide parent/leaf depth by complexity, decide whether the run is full or incremental, and define bounded scopes for subagents.
   - Start from `.agents/guidance-map/project-map.json`; prefer its module candidates, language summary, manifests, and changed-file summary over broad recursive source reading.
   - Keep the macro module map within the builder prompt's total module-subagent limit. If the repository has more natural modules than the limit allows, merge small or related paths into coarser module groups rather than spawning more agents.
   - Allowed in the builder thread before delegation: file listing, top-level directory inspection, root build/package manifests, existing `AGENTS.md` index, manifest, `verify` JSON, guide paths, and names of known packages/modules.
   - Not allowed in the builder thread: opening source files across modules to infer internals, recursive implementation reading, broad import tracing, or writing module summaries from source content.
   - Do not spawn module subagents until the draft macro map exists.
   - Do not delegate the global module-boundary decision.
   - Let the actual code structure drive module boundaries. Do not force a top-level-only or all-directories scheme.

7. Run mandatory module subagents.
   - Treat invocation of this skill as authorization to use subagents for this workflow. Do not ask again for subagent approval.
   - Spawn one bounded module subagent per useful module group, but never exceed the builder prompt's total module-subagent limit. For incremental updates, cover every affected module group and changed-file scope by merging related scopes if needed. For full refreshes, cover every macro module group after applying the total limit.
   - Treat the concurrent module-subagent limit as a fixed worker-slot count. Each worker slot may own only one module task at a time.
   - Never launch all module subagents at once. Run them in batches and keep active module subagents at or below the builder prompt's concurrent module-subagent limit.
   - When a module subagent completes, immediately collect its final result and verify its expected module guide file exists.
   - If more module groups remain and the subagent tool supports sending a new task to the same completed agent, prefer reusing that same agent with a fresh assignment for the next module group. The fresh assignment must name the new module, output path, bounded path scope, and must tell the agent not to edit previous module guide files.
   - If you do not immediately reuse a completed module subagent, close it before starting or waiting on other module work. Completed agents must not remain open until the end of the build.
   - After a reused agent completes its final assigned module, close it immediately after collecting its result.
   - Before final validation and `build-finish`, close every module subagent that is still open.
   - Give each module subagent: guide id, guide title, parent guide id if any, bounded path scope, guide output path under `.agents/guidance-map/guides/`, relevant changed files if any, and the exact guide file format.
   - Each module subagent must create or update only its assigned guide file, normally under `.agents/guidance-map/guides/<module>/<topic>.md` or `.agents/guidance-map/guides/<module>/index.md`.
   - Module subagents must not decide global module boundaries and must not edit unrelated module guide files.
   - Module subagents may update their own guide-index entry draft or return it, but the final `AGENTS.md` and manifest write must go through the helper so signatures stay consistent.
   - Do not start another project-map builder from a module subagent.
   - If the repository is too large to represent usefully within the total module-subagent limit, prefer a coarser but complete guide tree and explicitly note the grouping tradeoff in the final summary. Do not start extra module subagents without the user explicitly increasing the limit.

8. Write the project index and guide-tree draft in a temporary file.
   - The draft contains project-level guidance plus a helper-only `### Guide Index`; the helper removes `Guide Index` from final `AGENTS.md` and writes it into `manifest.json`.
   - Use this section order: `### Agent Editing Rules`, optional `### Progressive Disclosure`, `### Task Routing`, `### Module Dependency Rules`, `### Guide Index`.
   - `Agent Editing Rules` is the highest-value section. Write 4-8 project-specific editing constraints with `[MUST]`, `[SHOULD]`, or `[AVOID]` tags.
   - `Agent Editing Rules` must include one `[MUST]` rule telling later agents that linked module guides are lazy context and should not all be opened for broad orientation.
   - `Progressive Disclosure`, when present, should answer "which guides should I read now?" in 3-6 bullets. It must say to start with `AGENTS.md`, run `guidance_map.py query "<task>"`, read only manifest-verified guide files returned by query, prefer `verify.affected_guides` when available, and avoid opening every guide unless the task is explicitly project-wide.
   - `Task Routing` should answer "where do I edit for this task?" in 4-10 bullets using the shape `- To <task>: edit/read <paths>; ...`.
   - `Module Dependency Rules` should contain 4-10 dependency rules as direct bullets.
   - Put all guide entries under `### Guide Index`.
   - Use a short, human-friendly guide name as each `####` heading.
   - Each guide index entry must include these fields:
     - `Guide ID`: stable dotted id, such as `backend.api.controllers`.
     - `Guide Kind`: `parent` or `leaf`.
     - `Guide Path`: repo-relative path under `.agents/guidance-map/guides/`.
     - `Source Globs`: source/test globs this guide owns.
     - `Owns`: concise capability or domain ownership.
     - `Change here when`: concise edit-routing guidance.
     - `Do not put here`: concise boundary warning.
   - Each guide index entry may also include:
     - `Parent Guide ID`: for nested guides.
     - `Tags`: comma-separated routing terms.
     - `Read guide when`: concrete triggers for opening that module guide.
     - `Usually skip when`: concrete tasks that should not require opening that module guide.
   - Do not include `Key entry points`, internal structure, or long implementation notes in `AGENTS.md`; those belong in guide files.
   - Parent guides are optional. Create a parent `index.md` only when it reduces routing ambiguity or expresses cross-child boundaries, shared rules, or external interface contracts. Do not duplicate child implementation details in parent guides.

9. Each guide file must use this compact shape:

````markdown
# <short guide name>

- Module Path: `<primary path or path list>`
- Owns: <concise capability/domain ownership>
- Change here when: <right edit cases>
- Do not put here: <responsibilities that belong elsewhere>
- Key entry points:

```text
<small file/directory list>
```

## Internal Structure

- <concise structure notes>

## Local Rules

- <module-specific constraints if needed>
````

The helper adds or replaces tree-guide metadata at the top of each file, then records the file content digest and source snapshot in the signed manifest.

10. Update `AGENTS.md`, write `manifest.json`, and record all guide digests with:

```bash
python <skill-dir>/scripts/guidance_map.py update --repo <repo-root> --guidance-file <temp-index.md>
```

The helper creates `AGENTS.md` if needed, appends the block if missing, replaces only the marker block if present, writes guide metadata, writes `.agents/guidance-map/manifest.json`, signs the manifest, writes the manifest digest into `AGENTS.md`, and signs the aggregate `AGENTS.md` index.

Manifest guide entries include deterministic source snapshots for the guide source globs. When source or manifest files change, `verify` can target the affected guide without treating unrelated guides as stale. `query` must not recommend a guide whose content digest no longer matches the signed manifest.

When graphify evidence is useful and `graphify-out/graph.json` exists, prefer `python <skill-dir>/scripts/guidance_map.py query "<task>" --repo <repo-root> --use-graphify` or the explicit `--run-graphify` form. Do not read `graphify-out/graph.json` directly into model context.

11. Before finalizing, drain synchronized context from other threads:

```bash
python <skill-dir>/scripts/guidance_map.py build-drain --repo <repo-root> --build-id <build-id>
```

If the command returns pending contexts, fold them into the current build context, re-run `verify`, and perform another build pass. Repeat until the pending context list is empty.

12. Release the builder lease:

```bash
python <skill-dir>/scripts/guidance_map.py build-finish --repo <repo-root> --build-id <build-id> --status complete
```

If the build cannot complete, release with `--status failed --message <reason>`. Do not leave an active lease behind.

## Output Format

Use this shape inside the generated `AGENTS.md` block:

````markdown
## Code Project Guidance Map

Generator: code-project-guidance-map
Generator version: 0.3.0
Guide format: action-map:v4
Generated at: <ISO-8601 timestamp>
Git baseline: <HEAD sha or none>
Local change baseline: sha256:<digest>:<encoded local-change snapshot>
Signature key id: <repo-scoped key id>
Signature: hmac-sha256:<64 lowercase hex chars>

### Agent Editing Rules

- [MUST] <project-specific editing rule that prevents likely wrong edits>
- [MUST] Treat linked module guides as lazy context: start from this AGENTS.md index and read only task-relevant module guides.
- [SHOULD] <project-specific preferred edit pattern>
- [AVOID] <project-specific dependency, ownership, or duplication risk>

### Progressive Disclosure

- Start with this `AGENTS.md` index for broad orientation.
- Use `guidance_map.py query "<task>"` before opening guide files.
- Read only manifest-verified guide files returned by query unless the task is explicitly cross-module or project-wide.
- Do not open the whole guide tree for ordinary orientation.

### Task Routing

- To add a REST API: edit/read `<paths>`; keep behavior in `<owning module>`.
- To change persistence SQL: edit/read `<paths>`; keep SQL beside the owning mapper/DAO.

### Module Dependency Rules

- <project-specific dependency direction or boundary rule>
- <project-specific forbidden dependency or ownership rule>

### Guidance Manifest

Guidance manifest: `.agents/guidance-map/manifest.json`
Guidance manifest digest: `sha256:<64 lowercase hex chars>`
````

Use this shape at the top of each guide after helper metadata is applied:

````markdown
<!-- code-project-guidance-map:guide:start -->
Guide ID: backend.api.controllers
Guide kind: leaf
Guide path: .agents/guidance-map/guides/backend/api/controllers.md
Parent guide ID: backend.api
<!-- code-project-guidance-map:guide:end -->

# <short module name>

- Module Path: `<primary path or path list>`
- Owns: <one concise sentence>
- Change here when: <one concise sentence>
- Do not put here: <one concise sentence>
- Key entry points: ...
````

## Incremental Update Rules

- Treat the script's `verify.changed_files`, `change_impact`, `affected_guides`, and `recommended_action` as the update scope.
- Treat `Local change baseline` as the dirty-worktree freshness boundary: a file that was already dirty during the last refresh should not trigger another refresh until its content changes again.
- In the script-coordinated builder agent, use module subagents for affected-guide rereads and guide rewrites.
- Do not re-evaluate `Agent Editing Rules` or `Module Dependency Rules` for ordinary module-internal changes.
- Re-evaluate project-level rules only when `change_impact.boundary_rules` is non-empty or index metadata/signature/format/version is invalid.
- Refresh task-routing guidance when `change_impact.task_routing` is non-empty.
- Map changed files back to existing manifest guide `source_globs` when possible.
- Re-read only affected guides unless changed files indicate a project-wide restructure.
- Preserve unchanged guide files when their content digest and source snapshot still match.
- Do a full refresh when:
  - `AGENTS.md` marker metadata is missing or invalid;
  - `Generator version` is missing, invalid, or has a different major/minor version from the current helper;
  - the aggregate `AGENTS.md` signature is missing or invalid;
  - many directories moved or were deleted;
  - build/package manifests changed in ways that alter guide-tree or module boundaries;
  - the existing index is too stale to safely patch incrementally.
- Do a guide-level refresh when only one or more guide content digests are invalid, missing, or affected by local source changes.
- After a coding task changes files and `verify.recommended_action` is `refresh_dependency_rules`, `refresh_task_routing_and_affected_modules`, or `refresh_affected_modules`, the current thread must invoke `guidance_map.py build --launcher auto` before final response so the script-coordinated builder handles the refresh. Do not refresh directly in the current thread.
- If the script-coordinated builder cannot use subagents, it must switch to `plan-only` and report the bounded refresh plan instead of silently skipping the guidance update.

## Safety Rules

- Never edit target project files other than `AGENTS.md`, `.agents/guidance-map/manifest.json`, and `.agents/guidance-map/guides/**` unless the user explicitly asks.
- Never construct or refresh the map directly from an ordinary Codex thread. Ordinary threads must use `guidance_map.py build --launcher auto` and stop after the request is started, queued, or handed off to a Desktop manual/thread-tool builder thread.
- Never run more than one project-map builder for the same repository. If a builder is active, synchronize context into that builder through `guidance_map.py build`.
- Never remove user-authored `AGENTS.md` content outside the marker block.
- Never perform project-wide or module-internal full reads in the builder thread. Use bounded module subagents.
- Never exceed the module-subagent total or concurrent limits from the builder prompt. Defaults are 8 total module subagents per build pass and 3 running at the same time.
- Never leave completed module subagents open after their result has been collected. Reuse the same agent immediately for the next module task or close it immediately.
- If subagents are unavailable and `run_mode` is not `no-op`, the script-coordinated builder must switch to `plan-only` and output the bounded refresh plan without reading module internals or writing guidance files.
- Treat generated manifest signatures and guide metadata blocks as plugin-owned. Manual edits invalidate signatures/digests and require a plugin refresh.
- If marker structure is malformed, stop and report the issue instead of guessing.
- Do not include secrets, credentials, or private environment details in `AGENTS.md` or module guides.
- Do not write signing secrets into the repository. The helper stores a local key outside the target repository by default, or uses `CODE_PROJECT_GUIDANCE_MAP_SECRET` / `CODE_PROJECT_GUIDANCE_MAP_KEY_FILE` when configured.
- Standardize on `AGENTS.md`; do not create or update `Agent.md`.

## Validation

After updating a guide:

1. Re-run `status` to confirm `has_block` is true, `signature_valid` is true, and `manifest_valid` is true.
2. Verify `AGENTS.md` still contains any pre-existing content outside the marker block.
3. Summarize whether the run was full or incremental, which module subagents were used, how many guide files were written, and which changed files drove an incremental update.
4. Run `build-drain` until no pending contexts remain, then run `build-finish` to release the single-builder lease.
