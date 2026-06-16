---
name: code-project-guidance-map
description: Create or refresh a structured AGENTS.md project action index plus signed per-module Markdown guides. Use when the user asks Codex to read a project, map code structure, document module ownership, clarify module dependency boundaries, initialize project guidance, refresh an AGENTS.md project guide, or keep concise project editing guidance up to date from Git changes. When invoked, the main agent must decide macro module boundaries first, then use mandatory bounded subagents to create or refresh individual module guide files; do not perform project-wide or module-internal reading in the main thread.
---

# Code Project Guidance Map

## Objective

Create or refresh the `code-project-guidance-map` block in the repository root `AGENTS.md`, plus signed per-module Markdown guide files under the target repository.

`AGENTS.md` is only the project action index. It should contain project-level metadata, global editing/routing/dependency rules, progressive-disclosure rules, and concise module index entries that link to separate module guides. Do not put module-internal structure, long file inventories, or deep implementation notes directly in `AGENTS.md`.

The module guides contain the module-specific detail. They are lazy context, not startup context: later agents should read a module guide only when the task routing, changed files, `verify.affected_modules`, or module index fields indicate that module is relevant. Each module guide has its own signature block. The `AGENTS.md` index records each module guide path and module signature, then gets its own aggregate signature.

This skill must protect the main thread context. The main agent may do shallow repository scanning, macro module planning, index integration, and the final helper command, but module-internal reading and module-guide writing must run in subagents.

## Markers

Manage only the content between these exact `AGENTS.md` markers:

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

Module guide files use these exact module signature markers:

```markdown
<!-- code-project-guidance-map:module:start -->
<!-- code-project-guidance-map:module:end -->
```

Do not rewrite user-authored content outside the `AGENTS.md` marker block. Do not manually edit signature blocks; use the helper.

## Workflow

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

3. If `AGENTS.md` is missing or has no guidance block, ask the user whether to read the project and generate the guide. If the user already explicitly requested generation or refresh, treat that as consent and continue.

4. If a guidance block exists:
   - Read its `Generator version`, `Generated at` timestamp, guide format, signature key id, aggregate signature, and module index.
   - Use the script `verify` JSON to inspect Git changes since that timestamp, including committed, staged, unstaged, and untracked files. The helper filters out local changes whose current content still matches the signed `Local change baseline` captured during the last refresh.
   - If the generator version is missing, invalid, or has a different major/minor version from the current helper, perform a full refresh through the mandatory subagent workflow.
   - If only the patch version differs, keep the existing project index and module guide files as reusable unless Git changes require a scoped refresh.
   - If the aggregate `AGENTS.md` signature is invalid, perform a full refresh.
   - If only one or more module guide signatures are invalid or missing, refresh only those module guide files and the project index signatures.
   - If `recommended_action` is `refresh_dependency_rules`, re-evaluate project-level `Agent Editing Rules`, `Module Dependency Rules`, and affected module index entries.
   - If `recommended_action` is `refresh_task_routing_and_affected_modules`, refresh task routing guidance and affected module guides.
   - If `recommended_action` is `refresh_affected_modules`, re-read only affected modules and refresh only their module guide files.
   - If `recommended_action` is `none`, report that the guide is current unless the user explicitly asks for a full refresh.

5. Define `run_mode` before any source reading beyond shallow inspection:
   - `no-op`: `verify.recommended_action` is `none`, the existing block and module guide signatures are valid, and the user did not explicitly request generation or full refresh.
   - `generate`: `AGENTS.md` is missing or has no guidance block and the user consents or already requested generation.
   - `full_refresh`: `verify.recommended_action` is `full_refresh`, index metadata/signature/format/version is invalid, module boundaries are no longer trustworthy, or the user explicitly requests a full refresh.
   - `incremental_refresh`: `verify.recommended_action` is `refresh_dependency_rules`, `refresh_task_routing_and_affected_modules`, `refresh_affected_modules`, or `review_changed_files`.
   - `plan-only`: a safe fallback when `run_mode` would otherwise be `generate`, `full_refresh`, or `incremental_refresh`, but no subagent/delegation tool is available.
   - For `generate`, `full_refresh`, and `incremental_refresh`, module subagents are mandatory.
   - If no subagent/delegation tool is available for any non-`no-op` run mode, switch to `plan-only`; do not fall back to main-thread module-internal source reading.
   - In `plan-only`, output only the proposed macro module map, affected changed files, bounded subagent scopes, and the exact follow-up `$code-project-guidance-map` request needed to perform the refresh when subagents are available.
   - In `plan-only`, do not write `AGENTS.md`, do not create or update module guide files, do not run `guidance_map.py update`, and do not read module internals.

6. Decide the macro module map before delegation.
   - The main agent owns the global module map: choose concise module names, group paths into modules, decide whether the run is full or incremental, and define bounded scopes for subagents.
   - Allowed in the main thread before delegation: file listing, top-level directory inspection, root build/package manifests, existing `AGENTS.md` index, `verify` JSON, module guide paths, and names of known packages/modules.
   - Not allowed in the main thread: opening source files across modules to infer internals, recursive implementation reading, broad import tracing, or writing module summaries from source content.
   - Do not spawn module subagents until the draft macro map exists.
   - Do not delegate the global module-boundary decision.
   - Let the actual code structure drive module boundaries. Do not force a top-level-only or all-directories scheme.

7. Run mandatory module subagents.
   - Treat invocation of this skill as authorization to use subagents for this workflow. Do not ask again for subagent approval.
   - Spawn one bounded module subagent per useful module group. For incremental updates, cover every affected module group and changed-file scope. For full refreshes, cover every macro module group.
   - Give each module subagent: module name, bounded path scope, module guide output path, relevant changed files if any, and the exact module guide format.
   - Each module subagent must create or update only its assigned module guide file, normally under `.agents/guidance-map/modules/<module-slug>.md`.
   - Module subagents must not decide global module boundaries and must not edit unrelated module guide files.
   - Module subagents may update their own module index entry draft or return it, but the final `AGENTS.md` write must go through the helper so signatures stay consistent.

8. Write the project index draft in a temporary file.
   - The index draft is the content that will appear inside the `AGENTS.md` marker block after metadata/signature lines.
   - Use this section order: `### Agent Editing Rules`, optional `### Progressive Disclosure`, `### Task Routing`, `### Module Dependency Rules`, `### Module Index`.
   - `Agent Editing Rules` is the highest-value section. Write 4-8 project-specific editing constraints with `[MUST]`, `[SHOULD]`, or `[AVOID]` tags.
   - `Agent Editing Rules` must include one `[MUST]` rule telling later agents that linked module guides are lazy context and should not all be opened for broad orientation.
   - `Progressive Disclosure`, when present, should answer "which guides should I read now?" in 3-6 bullets. It must say to start with `AGENTS.md`, read only task-relevant module guides, prefer `verify.affected_modules` when available, and avoid opening every module guide unless the task is explicitly project-wide.
   - `Task Routing` should answer "where do I edit for this task?" in 4-10 bullets using the shape `- To <task>: edit/read <paths>; ...`.
   - `Module Dependency Rules` should contain 4-10 dependency rules as direct bullets.
   - Put all module entries under `### Module Index`.
   - Use a short, human-friendly module name as each `####` heading.
   - Each module index entry must include exactly these fields before signing:
     - `Module Path`: primary path or path list.
     - `Module Guide`: repo-relative path to the module guide file.
     - `Owns`: concise capability or domain ownership.
     - `Change here when`: concise edit-routing guidance.
     - `Do not put here`: concise boundary warning.
   - Each module index entry may also include these optional lazy-read fields:
     - `Read guide when`: concrete triggers for opening that module guide.
     - `Usually skip when`: concrete tasks that should not require opening that module guide.
   - Do not include `Key entry points`, internal structure, or long implementation notes in `AGENTS.md`; those belong in module guide files.
   - The helper will add or replace `Module Signature` in each module index entry.

9. Each module guide file must use this compact shape:

````markdown
# <short module name>

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

The helper signs module guide files by adding or replacing the module signature block at the top of each file.

10. Update `AGENTS.md` and sign all module guides with:

```bash
python <skill-dir>/scripts/guidance_map.py update --repo <repo-root> --guidance-file <temp-index.md>
```

The helper creates `AGENTS.md` if needed, appends the block if missing, replaces only the marker block if present, signs each module guide file, writes each module signature back into `### Module Index`, and signs the aggregate `AGENTS.md` index.

## Output Format

Use this shape inside the generated `AGENTS.md` block:

````markdown
## Code Project Guidance Map

Generator: code-project-guidance-map
Generator version: 0.2.1
Guide format: action-map:v3
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
- Read a module guide only when task routing, changed files, `verify.affected_modules`, or module index fields indicate that module is relevant.
- Prefer reading 1-3 module guides before editing unless the task is explicitly cross-module or project-wide.
- Do not open every linked module guide for ordinary orientation.

### Task Routing

- To add a REST API: edit/read `<paths>`; keep behavior in `<owning module>`.
- To change persistence SQL: edit/read `<paths>`; keep SQL beside the owning mapper/DAO.

### Module Dependency Rules

- <project-specific dependency direction or boundary rule>
- <project-specific forbidden dependency or ownership rule>

### Module Index

#### <short module name>

- Module Path: `<primary path or path list>`
- Module Guide: `.agents/guidance-map/modules/<module-slug>.md`
- Module Signature: `hmac-sha256:<64 lowercase hex chars>`
- Owns: <one concise sentence>
- Change here when: <one concise sentence>
- Do not put here: <one concise sentence>
- Read guide when: <optional concrete triggers for opening this guide>
- Usually skip when: <optional concrete cases that should not open this guide>
````

Use this shape at the top of each module guide after signing:

````markdown
<!-- code-project-guidance-map:module:start -->
Signature: hmac-sha256:<64 lowercase hex chars>
<!-- code-project-guidance-map:module:end -->

# <short module name>

- Module Path: `<primary path or path list>`
- Owns: <one concise sentence>
- Change here when: <one concise sentence>
- Do not put here: <one concise sentence>
- Key entry points: ...
````

## Incremental Update Rules

- Treat the script's `verify.changed_files`, `change_impact`, `modules`, and `recommended_action` as the update scope.
- Treat `Local change baseline` as the dirty-worktree freshness boundary: a file that was already dirty during the last refresh should not trigger another refresh until its content changes again.
- Use module subagents for affected-module rereads and module guide rewrites.
- Do not re-evaluate `Agent Editing Rules` or `Module Dependency Rules` for ordinary module-internal changes.
- Re-evaluate project-level rules only when `change_impact.boundary_rules` is non-empty or index metadata/signature/format/version is invalid.
- Refresh task-routing guidance when `change_impact.task_routing` is non-empty.
- Map changed files back to existing module guide paths when possible.
- Re-read only affected modules unless changed files indicate a project-wide restructure.
- Preserve unchanged module guide files when their signatures remain valid and their source paths still match.
- Do a full refresh when:
  - `AGENTS.md` marker metadata is missing or invalid;
  - `Generator version` is missing, invalid, or has a different major/minor version from the current helper;
  - the aggregate `AGENTS.md` signature is missing or invalid;
  - many directories moved or were deleted;
  - build/package manifests changed in ways that alter module boundaries;
  - the existing index is too stale to safely patch incrementally.
- Do a module-level refresh when only one or more module guide signatures are invalid, missing, or affected by local source changes.
- After a coding task changes files and `verify.recommended_action` is `refresh_dependency_rules`, `refresh_task_routing_and_affected_modules`, or `refresh_affected_modules`, refresh the affected guidance immediately before the final response. Do not leave it as a reminder for the next task.
- If that immediate post-edit refresh is required but subagents are unavailable, switch to `plan-only` and report the bounded refresh plan instead of silently skipping the guidance update.

## Safety Rules

- Never edit target project files other than `AGENTS.md` and `.agents/guidance-map/modules/*.md` unless the user explicitly asks.
- Never remove user-authored `AGENTS.md` content outside the marker block.
- Never perform project-wide or module-internal full reads in the main thread. Use bounded module subagents.
- If subagents are unavailable and `run_mode` is not `no-op`, switch to `plan-only` and output the bounded refresh plan without reading module internals or writing guidance files.
- Treat generated signature blocks as plugin-owned. Manual edits invalidate signatures and require a plugin refresh.
- If marker structure is malformed, stop and report the issue instead of guessing.
- Do not include secrets, credentials, or private environment details in `AGENTS.md` or module guides.
- Do not write signing secrets into the repository. The helper stores a local key outside the target repository by default, or uses `CODE_PROJECT_GUIDANCE_MAP_SECRET` / `CODE_PROJECT_GUIDANCE_MAP_KEY_FILE` when configured.
- Standardize on `AGENTS.md`; do not create or update `Agent.md`.

## Validation

After updating a guide:

1. Re-run `status` to confirm `has_block` is true, `signature_valid` is true, and `modules_valid` is true.
2. Verify `AGENTS.md` still contains any pre-existing content outside the marker block.
3. Summarize whether the run was full or incremental, which module subagents were used, how many module guide files were written, and which changed files drove an incremental update.
