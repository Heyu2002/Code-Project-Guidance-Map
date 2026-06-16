# Code Project Guidance Map

[English README](README.md)

Code Project Guidance Map 是一个 Codex plugin + skill，用来把项目结构沉淀成 Codex 可复用的项目记忆。

它的目标不是生成一大篇项目手册，而是在项目根目录生成一个紧凑的 `AGENTS.md` 项目行动索引，并把模块内部细节拆到 `.agents/guidance-map/modules/` 下的独立 Markdown 文件中。

## 背景

这个插件来自 Codex 仓库中的 feature request：[Feature request: Add a standardized code audit module for modular codebases #26007](https://github.com/openai/codex/issues/26007)。

该 issue 希望 Codex 能为模块化代码库生成并维护标准化的 code audit module，让后续 agent 不必每次都从零重新阅读大量源码。由于这个 feature request 目前仍处于 Open 状态，且暂未看到 assignee、project、milestone 或关联开发 PR，这里先把它单独做成一个可安装的 Codex plugin。

这个插件也有一部分灵感来自 OpenAI 的文章 [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)，尤其是其中关于 repository-local knowledge 作为 system of record、`AGENTS.md` 应该是紧凑地图而不是巨型手册，以及 agent legibility 是工程目标的思路。

## 它做什么

在目标项目中调用这个 skill 后，它会：

- 检查项目根目录是否存在 `AGENTS.md` 以及本插件生成的 marker 区块。
- 首次生成时询问用户，除非用户已经明确要求生成或刷新。
- 由主 agent 根据浅层仓库信号决定宏观模块划分。
- 强制使用有边界的模块 subagents 阅读模块内部，并为每个模块写一个独立模块 guide。
- 让 `AGENTS.md` 只保存项目级索引：全局编辑规则、任务路由、依赖规则和模块链接。
- 把模块内部结构、关键入口和局部规则保存到 `.agents/guidance-map/modules/*.md`。
- 给每个模块 guide 生成独立签名，再把模块签名写回 `AGENTS.md`。
- 给 `AGENTS.md` 索引生成总签名，用来检测人工修改、模块链接损坏或签名不一致。
- 根据 Git 变化增量刷新受影响模块，而不是每次全量重读项目。
- 刷新时记录一个已签名的本地变更基线，让刷新时已经存在的 dirty worktree 文件不会在内容未变时反复触发 stale。
- 通过轻量 hooks 在 `SessionStart`、`UserPromptSubmit` 和 `Stop` 时检查指引是否缺失、过期或无法验签。

`AGENTS.md` 的固定 marker 是：

```markdown
<!-- code-project-guidance-map:start -->
<!-- code-project-guidance-map:end -->
```

模块 guide 文件有自己的签名 marker：

```markdown
<!-- code-project-guidance-map:module:start -->
Signature: hmac-sha256:<64 lowercase hex chars>
<!-- code-project-guidance-map:module:end -->
```

当前生成器版本是 `0.2.1`，当前 guide 格式是 `action-map:v3`。版本缺失、格式非法，或 major/minor 不兼容时需要完整刷新。只有 patch 版本不同会被视为兼容。

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
Use $code-project-guidance-map to create or refresh this repository's signed AGENTS.md project index and per-module guide files. First decide macro module boundaries from shallow repo signals, then spawn bounded module subagents to create or refresh `.agents/guidance-map/modules/*.md`, then use the helper to sign module guides, link them from AGENTS.md, and sign the aggregate index. Do not do module-internal reading in the main thread.
```

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

生成的指引是分层的。后续 Codex 会话应该先读紧凑的 `AGENTS.md` 索引，再根据 `Task Routing`、`Module Index` 和 `verify.affected_modules` 选择相关模块，只打开命中的模块 guide。模块 guide 是懒加载上下文，不是启动上下文；普通任务通常只需要在编辑前读取 1-3 个相关模块 guide。

模块索引条目可以包含可选的懒加载提示：

```markdown
- Read guide when: Editing hook behavior, hook state, hook tests, or hook config.
- Usually skip when: Only changing helper signing, README copy, or plugin marketplace metadata.
```

hooks 是只读的。它们会验证当前仓库的 `AGENTS.md` 索引和模块 guide 签名，并在缺失、过期或无法验签时给 Codex 注入有边界的上下文。hook 消息由状态机降噪：状态保存在用户的 Codex home 下，但判断粒度是项目和 session。默认同一个项目、同一个 session、同一个 action 只提示一次。发生过代码编辑类 prompt 后，`Stop` 会发出 continuation system message，要求 Codex 在 final 前立即刷新受影响指引，而不是把刷新留作下一次任务的提醒。hooks 不会自己编辑文件。

生成和刷新必须使用 subagents。模块 subagent 直接写自己负责的模块 guide 文件。主 agent 只负责宏观模块划分和紧凑的 `AGENTS.md` 索引草稿，然后运行 helper 给模块文件签名、把模块签名回填进索引，并写入带总签名的 `AGENTS.md` 区块。如果编码改动让指引过期，Codex 应该在 final 前立即刷新受影响模块；如果 subagents 不可用，则进入 `plan-only`，只输出有边界的刷新计划，不读模块内部、不写指引文件。

## 会产生什么

成功运行后，`AGENTS.md` 会包含类似下面的紧凑索引：

````markdown
<!-- code-project-guidance-map:start -->
## Code Project Guidance Map

Generator: code-project-guidance-map
Generator version: 0.2.1
Guide format: action-map:v3
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
- Read a module guide only when task routing, changed files, `verify.affected_modules`, or module index fields indicate that module is relevant.
- Prefer reading 1-3 module guides before editing unless the task is explicitly cross-module or project-wide.
- Do not open every linked module guide for ordinary orientation.

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
- Read guide when: Editing scheduling rules, scheduling services, strategies, tests, or schedule persistence behavior.
- Usually skip when: Only changing API response shaping, frontend DTOs, documentation, or generic shared helpers.
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
