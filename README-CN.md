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
- 让 `AGENTS.md` 只保存项目级索引：全局编辑规则、任务路由、依赖规则和 manifest 指针。
- 把模块内部结构、关键入口和局部规则保存到 `.agents/guidance-map/guides/**`。
- 写入 `.agents/guidance-map/manifest.json`，记录 freshness 游标、guide id、父子关系、tags、source globs 和 source snapshot。
- `AGENTS.md`、manifest 和每个 guide 各自只保存一个短内容哈希，各自仅对自己的内容负责。它们用于发现内容变化，不用于身份认证。
- 根据 Git 变化增量刷新受影响 guide，而不是每次全量重读项目。
- 刷新时在 manifest 中记录本地变更基线，让刷新时已经存在的 dirty worktree 文件不会在内容未变时反复触发 stale。
- 只注册一个面向实际修改的 `Stop` hook；不在 `SessionStart` 或 `UserPromptSubmit` 注入上下文，只有 Git 可见修改导致指引 stale 时才协调 builder。

`AGENTS.md` 的固定 marker 是：

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

tree guide 文件有自己的 metadata marker 和短自哈希：

```markdown
<!-- code-project-guidance-map:guide:start -->
Guide ID: backend.api.controllers
Guide kind: leaf
Guide path: .agents/guidance-map/guides/backend/api/controllers.md
Parent guide ID: backend.api
Content hash: sha256:<16 lowercase hex chars>
<!-- code-project-guidance-map:guide:end -->
```

当前生成器版本是 `0.4.0`，当前 guide 格式是 `action-map:v5`。旧的 `action-map:v3` 和 `action-map:v4` 产物仍可被 `status/verify/query` 识别，但下一次 refresh 会统一升级为 v5 self-hashed guide tree。版本缺失、格式非法，或 major/minor 不兼容时需要完整刷新。只有 patch 版本不同会被视为兼容。

freshness 游标全部保存在 manifest。`Generated at` 用来界定已提交 Git 历史；`Local change baseline` 会记录上次刷新时已经存在的 staged、unstaged 和 untracked 文件内容。新开 Codex thread 时，同一批 dirty 文件只要内容没再变化，就不应该再次要求刷新。

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
Use $code-project-guidance-map to create or refresh this repository's self-hashed AGENTS.md project index and manifest-backed guide tree. First decide macro guide-tree boundaries from shallow repo signals, then spawn bounded module subagents to create or refresh `.agents/guidance-map/guides/**`, then use the helper to self-hash each artifact and record source snapshots in the manifest. Do not do module-internal reading in the main thread.
```

构建 helper 默认使用 `guidance_map.py build --launcher auto`。`auto` 按申请来源选择：Codex Desktop 发起时不探测 CLI，直接返回 `desktop_launch_required`，由当前任务创建并 attach 一个新的 Desktop task；Codex CLI 发起时解析并调用 `codex exec`。`--launcher desktop` 和 `--launcher cli` 可以显式覆盖自动选择。无论使用哪条路径，调用方在 started、queued 或 Desktop attach 后都必须立即结束，不能等待 builder 完成。

每次 build 都会在项目 build state 的 `logs/` 目录下写入 `*.prompt.md`、`*.jsonl`、`*.last-message.md` 和 `*.metrics.json`；Desktop handoff 还会写入 `*.handoff.md`。CLI builder 启动后会等待 JSONL 或 last-message 启动信号，如果进程存活但一直没有任何输出，会尽早报错而不是留下一个静默 lease。`verify` 默认忽略 `graphify-out/`、`node_modules/`、缓存、build 目录、coverage 和编译产物，这些路径会出现在 `changed_files_by_source.tool_ignored` 中，但不会让 guidance 变 stale。

也可以不启动 builder，直接使用本地确定性能力：

```powershell
python <installed-skill>\scripts\guidance_map.py scan --repo .
python <installed-skill>\scripts\guidance_map.py query "add an API controller" --repo .
python <installed-skill>\scripts\guidance_map.py benchmark-build --repo .
python <installed-skill>\scripts\guidance_map.py compare-graphify --repo . --query "add an API controller"
```

`scan` 会写入 `.agents/guidance-map/project-map.json`，包含文件树、语言、manifest、模块候选、import、changed files 和 graphify 可用性摘要。`query` 会基于 self-hashed manifest 和 guide tree 推荐 guide、源码路径、测试路径，以及可选 graphify query 命令；命中的 guide 会先校验自己的 content hash 及 manifest 身份绑定，校验失败的 guide 不会返回。只有显式传入 `--run-graphify` 时才会实际运行 graphify query 并截取输出。`compare-graphify` 会把 CPGM 的 project-map/tree-query metrics 和本地 graphify graph metadata 放在同一个 JSON 中。

## 如何使用

首次生成：

```text
Use $code-project-guidance-map to create this repository's self-hashed AGENTS.md project index and per-module guide files.
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

hook 是只读的，并且只注册在 `Stop`。它不会在 `SessionStart` 或 `UserPromptSubmit` 注入上下文；只有 Git 可见的项目修改让索引或 guide tree 过期、缺失或无法校验时才会提示。状态机按项目、session、action 和修改内容指纹降噪。发出提示前，hook 会调用只读的 `guidance_map.py build-status`；如果 CLI 或 Desktop builder 已经运行，就保持静默，让主线程直接结束。如果还没有 builder，则要求 Codex 调用 `guidance_map.py build --launcher auto`：Desktop 发起时优先创建并 attach 新 Desktop thread，CLI 发起时优先调用 `codex exec`。started、queued 或 Desktop attach 成功后必须立即 final，不能等待、轮询、读取或跟随 builder thread。

生成和刷新必须使用 subagents，但只能在脚本协调的 builder agent 内使用。普通主线程只负责启动、排队或交接 builder，成功后立即返回，不能等待或跟随 builder 完成。模块 subagent 直接写自己负责的模块 guide 文件，并且必须限流和管理生命周期：默认同时最多运行 3 个模块 subagent，每次构建总共最多创建 8 个模块 subagent。这里的并发数应当被当成固定 worker slot。某个模块任务完成后，builder 必须先收集结果，然后要么立刻复用同一个已完成 agent 去做下一个模块，要么立刻关闭它再继续；不能把 completed agents 一直堆到构建最后统一关闭。如果仓库天然模块更多，builder 必须把相关路径合并成更粗的模块组，不能继续打开更多 terminal 或 agent pane。可通过 `CODE_PROJECT_GUIDANCE_MAP_MAX_CONCURRENT_MODULE_SUBAGENTS`、`CODE_PROJECT_GUIDANCE_MAP_MAX_TOTAL_MODULE_SUBAGENTS` 或对应的 `build` 参数调整。builder 只负责宏观模块划分和紧凑的 `AGENTS.md` 索引草稿，然后运行 helper 为每个产物生成自哈希。非结构刷新只更新 guide 和 manifest，并保持 `AGENTS.md` 字节不变；只有项目级规则、路由、所有权或 guide tree 拓扑实际变化时才改写它。如果 subagents 不可用，则进入 `plan-only`，只输出有边界的刷新计划，不读模块内部、不写指引文件。

## 会产生什么

成功运行后，`AGENTS.md` 会包含类似下面的紧凑索引：

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
<!-- code-project-guidance-map:end -->
````

对应模块文件保存细节：

````markdown
<!-- code-project-guidance-map:guide:start -->
Guide ID: scheduling.rules
Guide kind: leaf
Guide path: .agents/guidance-map/guides/scheduling/rules.md
Parent guide ID: scheduling
Content hash: sha256:<16 lowercase hex chars>
<!-- code-project-guidance-map:guide:end -->

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
- 哪个产物自己的 content hash 无效，而不把它的责任扩大到其他产物？

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

它不追求完整项目手册，而是沉淀后续 agent 最需要的模块边界、依赖方向、归属规则和紧凑导航线索，并允许完整性问题被定位到单个产物。
