# Code Project Guidance Map

[English README](README.md)

[Changelog](CHANGELOG.md)

Code Project Guidance Map 是一个 Codex plugin + skill，用来把项目结构沉淀成 Codex 可复用的项目记忆。

它的目标不是生成一大篇项目手册，而是在项目根目录生成一个紧凑的 `AGENTS.md` 项目行动索引，并把模块内部细节拆到 `.agents/guidance-map/guides/` 下的 manifest-backed 分层 Markdown 文件中。

## graphify 对比摘要

完整报告见 [docs/graphify-comparison.md](docs/graphify-comparison.md)。一句话：当前插件是 Codex 编辑路由记忆层，graphify 是可查询知识图谱索引。本轮新增 deterministic pre-scan 后，`compare-graphify` 在四个 Java/Python/Rust/C# 样本上产出 0-token CPGM project-map，最终复测耗时约 0.9s-1.4s，体积比对应 graphify JSON 小 8.7x-135.3x；但 graphify 仍然更适合符号邻居、调用路径和影响面深查。推荐落地方式是先用 CPGM 的 `project-map`/`AGENTS.md` 做编辑范围路由，再用 graphify 对疑难模块做结构检索。

## 背景

这个插件来自 Codex 仓库中的 feature request：[Feature request: Add a standardized code audit module for modular codebases #26007](https://github.com/openai/codex/issues/26007)。

该 issue 希望 Codex 能为模块化代码库生成并维护标准化的 code audit module，让后续 agent 不必每次都从零重新阅读大量源码。由于这个 feature request 目前仍处于 Open 状态，且暂未看到 assignee、project、milestone 或关联开发 PR，这里先把它单独做成一个可安装的 Codex plugin。

这个插件也有一部分灵感来自 OpenAI 的文章 [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)，尤其是其中关于 repository-local knowledge 作为 system of record、`AGENTS.md` 应该是紧凑地图而不是巨型手册，以及 agent legibility 是工程目标的思路。

## 它做什么

在目标项目中调用这个 skill 后，它会：

- 检查项目根目录是否存在 `AGENTS.md` 以及本插件生成的 marker 区块。
- 首次生成时询问用户，除非用户已经明确要求生成或刷新。
- 由主 agent 根据浅层仓库信号决定宏观模块划分。
- 强制使用有边界的模块 subagents 阅读模块内部，并为每个模块组写一个独立模块 guide；默认限制为每次构建最多同时运行 3 个模块 subagent、总共最多创建 8 个模块 subagent。
- 让 `AGENTS.md` 只保存项目级索引：全局编辑规则、任务路由、依赖规则和模块链接。
- 把模块内部结构、关键入口和局部规则保存到 `.agents/guidance-map/guides/**`。
- 写入 `.agents/guidance-map/manifest.json`，记录 guide id、父子关系、tags、source globs、content digest 和 source snapshot。
- 给 `AGENTS.md` 索引和 manifest 生成签名，用来检测人工修改、manifest 替换、guide 路径逃逸或 guide 内容篡改。
- 根据 Git 变化增量刷新受影响 guide，而不是每次全量重读项目。
- 刷新时记录一个已签名的本地变更基线，让刷新时已经存在的 dirty worktree 文件不会在内容未变时反复触发 stale。
- 只注册一个面向实际修改的 `Stop` hook；不在 `SessionStart` 或 `UserPromptSubmit` 注入上下文，只有 Git 可见修改导致指引 stale 时才协调 builder。

`AGENTS.md` 的固定 marker 是：

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

tree guide 文件有自己的 metadata marker；可信性来自 manifest 中的 content digest，而不是每个文件本地 HMAC：

```markdown
<!-- code-project-guidance-map:guide:start -->
Guide ID: backend.api.controllers
Guide kind: leaf
Guide path: .agents/guidance-map/guides/backend/api/controllers.md
Parent guide ID: backend.api
<!-- code-project-guidance-map:guide:end -->
```

当前生成器版本是 `0.3.0`，当前 guide 格式是 `action-map:v4`。旧的 `action-map:v3` 产物仍可被 `status/verify/query` 识别，但下一次 refresh 会统一升级为 v4 manifest-backed guide tree。版本缺失、格式非法，或 major/minor 不兼容时需要完整刷新。只有 patch 版本不同会被视为兼容。

本地变更的新鲜度按内容判断。`Generated at` 用来界定已提交 Git 历史；已签名的 `Local change baseline` 会记录上次刷新时已经存在的 staged、unstaged 和 untracked 文件内容。新开 Codex thread 时，同一批 dirty 文件只要内容没再变化，就不应该再次要求刷新。

## 快速启动

克隆仓库：

```powershell
git clone <repo-url>
cd Code-Project-Guidance-Map-Skills
```

把当前仓库注册为 Codex plugin marketplace：

```powershell
codex plugin marketplace add <absolute-path-to-this-repo>
```

从 marketplace 安装插件：

```powershell
codex plugin add code-project-guidance-map@code-project-guidance-map
```

Windows 示例：

```powershell
codex plugin marketplace add D:\work\Code-Project-Guidance-Map-Skills
codex plugin add code-project-guidance-map@code-project-guidance-map
```

安装后，在你想生成指引的项目中新开一个 Codex 线程，然后输入：

```text
Use $code-project-guidance-map to create or refresh this repository's signed AGENTS.md project index and manifest-backed guide tree. First decide macro guide-tree boundaries from shallow repo signals, then spawn bounded module subagents to create or refresh `.agents/guidance-map/guides/**`, then use the helper to write the manifest, record guide digests/source snapshots, and sign AGENTS.md. Do not do module-internal reading in the main thread.
```

构建 helper 默认使用 `guidance_map.py build --launcher auto`。`auto` 会优先通过 `codex exec` 启动 builder，因此 agent 环境里需要有可运行的 `codex` 命令，或者设置 `CODE_PROJECT_GUIDANCE_MAP_CODEX_COMMAND` / `--codex-command` 指向可运行的 Codex CLI。不要假设安装 Codex Desktop 后所有用户都会自动拥有可被脚本调用的 CLI；如果没有 CLI 但当前请求运行在 Codex Desktop 中，`auto` 会返回 `desktop_manual_handoff_required`，并生成 `.handoff.md`、短 `codex://new?path=...&prompt=...` deep link、attach 命令和失败清理命令，用户可以用新的本地 Desktop thread 接力 builder。`--launcher desktop` 仅保留给确实具备 Desktop thread creation tool 的环境作为显式 handoff 路径。

每次 build 都会在项目 build state 的 `logs/` 目录下写入 `*.prompt.md`、`*.jsonl`、`*.last-message.md` 和 `*.metrics.json`；Desktop handoff 还会写入 `*.handoff.md`。CLI builder 启动后会等待 JSONL 或 last-message 启动信号，如果进程存活但一直没有任何输出，会尽早报错而不是留下一个静默 lease。`verify` 默认忽略 `graphify-out/`、`node_modules/`、缓存、build 目录、coverage 和编译产物，这些路径会出现在 `changed_files_by_source.tool_ignored` 中，但不会让 guidance 变 stale。

也可以不启动 builder，直接使用本地确定性能力：

```powershell
python <installed-skill>\scripts\guidance_map.py scan --repo .
python <installed-skill>\scripts\guidance_map.py query "add an API controller" --repo .
python <installed-skill>\scripts\guidance_map.py benchmark-build --repo .
python <installed-skill>\scripts\guidance_map.py compare-graphify --repo . --query "add an API controller"
```

`scan` 会写入 `.agents/guidance-map/project-map.json`，包含文件树、语言、manifest、模块候选、import、changed files 和 graphify 可用性摘要。`query` 会基于 signed manifest 和 guide tree 推荐 guide、源码路径、测试路径，以及可选 graphify query 命令；命中的 guide 会先校验 content digest，篡改过的 guide 不会作为可信建议返回。只有显式传入 `--run-graphify` 时才会实际运行 graphify query 并截取输出。`compare-graphify` 会把 CPGM 的 project-map/tree-query metrics 和本地 graphify graph metadata 放在同一个 JSON 中。

## 如何使用

首次生成：

```text
Use $code-project-guidance-map to create this repository's signed AGENTS.md project index and per-module guide files.
```

项目结构发生明显变化后刷新：

```text
Use $code-project-guidance-map to refresh the project guidance from recent Git changes, updating only affected module guide files when possible.
```

做较大功能前先对齐模块边界：

```text
Use $code-project-guidance-map, then help me identify where this feature should be implemented.
```

## 渐进式披露

生成的指引是分层的。后续 Codex 会话应该先读紧凑的 `AGENTS.md` 索引，再运行 `guidance_map.py query "<task>"` 选择 manifest-verified guide，只打开命中的 guide。guide 是懒加载上下文，不是启动上下文；普通任务通常只需要在编辑前读取 1-5 个相关 guide。

模块索引条目可以包含可选的懒加载提示：

```markdown
- Read guide when: Editing hook behavior, hook state, hook tests, or hook config.
- Usually skip when: Only changing helper signing, README copy, or plugin marketplace metadata.
```

hook 是只读的，并且只注册在 `Stop`。它不会在 `SessionStart` 或 `UserPromptSubmit` 注入上下文；只有 Git 可见的项目修改让索引或 guide tree 过期、缺失或无法验签时才会提示。状态机按项目、session、action 和修改内容指纹降噪。发出提示前，hook 会调用只读的 `guidance_map.py build-status`；如果 CLI 或 Desktop builder 已经运行，就保持静默，让主线程直接结束。如果还没有 builder，则要求 Codex 调用 `guidance_map.py build --launcher auto`，并在 started、queued 或 Desktop handoff/attach 成功后立即 final，不能等待、轮询、读取或跟随 builder thread。

生成和刷新必须使用 subagents，但只能在脚本协调的 builder agent 内使用。普通主线程只负责启动、排队或交接 builder，成功后立即返回，不能等待或跟随 builder 完成。模块 subagent 直接写自己负责的模块 guide 文件，并且必须限流和管理生命周期：默认同时最多运行 3 个模块 subagent，每次构建总共最多创建 8 个模块 subagent。这里的并发数应当被当成固定 worker slot。某个模块任务完成后，builder 必须先收集结果，然后要么立刻复用同一个已完成 agent 去做下一个模块，要么立刻关闭它再继续；不能把 completed agents 一直堆到构建最后统一关闭。如果仓库天然模块更多，builder 必须把相关路径合并成更粗的模块组，不能继续打开更多 terminal 或 agent pane。可通过 `CODE_PROJECT_GUIDANCE_MAP_MAX_CONCURRENT_MODULE_SUBAGENTS`、`CODE_PROJECT_GUIDANCE_MAP_MAX_TOTAL_MODULE_SUBAGENTS` 或对应的 `build` 参数调整。builder 只负责宏观模块划分和紧凑的 `AGENTS.md` 索引草稿，然后运行 helper 给模块文件签名、把模块签名回填进索引，并写入带总签名的 `AGENTS.md` 区块。如果 subagents 不可用，则进入 `plan-only`，只输出有边界的刷新计划，不读模块内部、不写指引文件。

## 会产生什么

成功运行后，`AGENTS.md` 会包含类似下面的紧凑索引：

````markdown
<!-- code-project-guidance-map:start -->
## Code Project Guidance Map

Generator: code-project-guidance-map
Generator version: 0.3.0
Guide format: action-map:v4
Generated at: 2026-06-15T10:30:00Z
Git baseline: abc1234
Signature key id: repo:1a2b3c4d5e6f7890
Signature: hmac-sha256:<64 lowercase hex chars>

### Agent Editing Rules

- [MUST] Put new scheduling business rules in `src/core/scheduling`; expose them through API modules only after service behavior exists.
- [MUST] Treat linked module guides as lazy context; start from this index and read only task-relevant module guides.
- [SHOULD] Reuse existing services before adding orchestration.
- [AVOID] Adding business or web dependencies to shared utility modules.

### Progressive Disclosure

- Start with this `AGENTS.md` index for broad orientation.
- Use `guidance_map.py query "<task>"` before opening guide files.
- Read only manifest-verified guide files returned by query unless the task is explicitly cross-module or project-wide.
- Do not open the whole guide tree for ordinary orientation.

### Task Routing

- To add a REST API: edit `src/api`; call services from `src/core` instead of duplicating business logic.
- To change scheduling rules: edit `src/core/scheduling`; refresh the Scheduling module guide if behavior changes.

### Module Dependency Rules

- Shared utilities are the lowest-level code and must not depend on business, web, or persistence modules.
- API modules call services; services own business rules; persistence modules own storage adapters and SQL.

### Guidance Manifest

Guidance manifest: `.agents/guidance-map/manifest.json`
Guidance manifest digest: `sha256:<64 lowercase hex chars>`
<!-- code-project-guidance-map:end -->
````

对应模块文件保存细节：

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

这种结构能帮助 Codex 更快回答：

- 某个行为由哪个模块负责？
- 哪个模块 guide 需要刷新？
- 修改前应该先读哪些目录？
- 签名问题是影响整个索引，还是只影响某个模块 guide？

## 分发给别人使用

这个仓库已经包含可分发的 plugin 包：

- 开发用 skill：`.agents/skills/code-project-guidance-map/`
- 可安装 plugin：`plugins/code-project-guidance-map/`
- plugin manifest：`plugins/code-project-guidance-map/.codex-plugin/plugin.json`
- plugin hooks：`plugins/code-project-guidance-map/hooks/`
- 本地 marketplace：`.agents/plugins/marketplace.json`

安装方式：

```powershell
codex plugin marketplace add <absolute-path-to-this-repo>
codex plugin add code-project-guidance-map@code-project-guidance-map
```

如果要放到团队内部 marketplace：

1. 把这个仓库发布到团队可访问的位置，例如 GitHub、内部 Git 或共享目录。
2. 保留 `plugins/code-project-guidance-map/.codex-plugin/plugin.json`。
3. 保留 `.agents/plugins/marketplace.json`；它的 marketplace 名称是 `code-project-guidance-map`。
4. 告诉使用者先添加 marketplace，再安装 `code-project-guidance-map@code-project-guidance-map`。

## 开发和验证

开发用 skill 是唯一源头：

```text
.agents/skills/code-project-guidance-map/
```

修改后同步到 plugin 副本：

```powershell
python scripts\sync_plugin_skill.py
python scripts\sync_plugin_skill.py --check
```

验证：

```powershell
python scripts\test_sync_plugin_skill.py
python .agents\skills\code-project-guidance-map\scripts\test_guidance_map.py
python plugins\code-project-guidance-map\skills\code-project-guidance-map\scripts\test_guidance_map.py
python plugins\code-project-guidance-map\hooks\test_guidance_map_hook.py
python <codex-checkout>\codex-rs\skills\src\assets\samples\skill-creator\scripts\quick_validate.py .agents\skills\code-project-guidance-map
python <codex-checkout>\codex-rs\skills\src\assets\samples\skill-creator\scripts\quick_validate.py plugins\code-project-guidance-map\skills\code-project-guidance-map
python <plugin-creator-skill>\scripts\validate_plugin.py plugins\code-project-guidance-map
```

GitHub Actions 和目标项目 `verify` CI 接入方式见 [docs/ci.md](docs/ci.md)。

本地开发时，如果插件已经安装过，改完后重新安装：

```powershell
python <plugin-creator-skill>\scripts\update_plugin_cachebuster.py plugins\code-project-guidance-map
codex plugin add code-project-guidance-map@code-project-guidance-map
```

然后新开 Codex 线程，让 Codex 重新加载插件。

## 项目主旨

这个项目的目标是让 Codex 从“临时读代码”走向“可复用、可验证、可增量刷新的项目记忆”。

它不追求完整项目手册，而是沉淀后续 agent 最需要的模块边界、依赖方向、归属规则和紧凑导航线索，并允许签名问题被定位到单个模块 guide。
