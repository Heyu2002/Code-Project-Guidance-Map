# Code Project Guidance Map vs Repomix

评测日期：2026-07-03  
测试根目录：`D:\project\test\repomix-cpgm-benchmark-20260703`  
原始结果：`D:\project\test\repomix-cpgm-benchmark-20260703\_outputs\benchmark-results.json`

## 结论

Repomix 更适合一次性把仓库打包成 AI-friendly 文件，安装和上手非常直接，默认还给出 token 统计和 secret scan。当前插件更适合 Codex 的长期编辑落地：`AGENTS.md` 保持很小，实际任务通过 signed manifest 查询 1-5 个 guide，避免把全仓内容塞进上下文。

本轮数据里，Repomix full 输出为 38,214-863,168 tokens，`--compress` 后仍为 31,916-750,059 tokens；当前插件 query 命中的 guide 约 756-843 估算 tokens。按任务上下文计算，Repomix full 是 CPGM selected context 的 50.5x-1040.0x，Repomix compressed 仍是 42.2x-903.7x。

注意：本报告没有启动 Codex LLM builder。CPGM guide tree 使用 project-map 生成 deterministic benchmark draft，再通过当前插件 `update/verify/query` 路径签名、落盘和查询。因此本报告量化的是“本地文件化索引、可信链、查询和上下文体积”，不是完整 Codex builder 的语义总结质量。

## 测试样本

全部样本均从远程 GitHub 新 clone 到 `D:\project\test\repomix-cpgm-benchmark-20260703`，未使用之前 graphify benchmark 中的 Spring/Flask/bat/Hangfire 样本。

| Repo | Lang | Scale | Structure | Files | Code files | Code LOC | Bytes | Commit |
|---|---:|---|---|---:|---:|---:|---:|---|
| [`pallets/itsdangerous`](https://github.com/pallets/itsdangerous) | Python | small | simple | 50 | 15 | 1,712 | 280.2 KB | `672971d` |
| [`google/gson`](https://github.com/google/gson) | Java | medium | medium | 311 | 262 | 55,620 | 2.25 MB | `c9f3fd5` |
| [`DapperLib/Dapper`](https://github.com/DapperLib/Dapper) | C# | large | medium-complex | 226 | 157 | 26,557 | 1.28 MB | `72a54c4` |
| [`BurntSushi/ripgrep`](https://github.com/BurntSushi/ripgrep) | Rust | large | complex | 222 | 100 | 52,342 | 3.04 MB | `48b0c79` |

初始污染检查在运行任何工具前完成：四个仓库均 `has_agents_md=false`、`has_guidance_dir=false`、`repomix_artifact_count=0`、`keyword_hits=0`。后续 Repomix 运行显式忽略 `.agents/**,AGENTS.md`，避免把 CPGM 产物打入 Repomix 输出。

## 工具版本

| Tool | Version / command result |
|---|---|
| Code Project Guidance Map | `generator_version=0.3.0`, `guide_format=action-map:v4` |
| Codex CLI | `codex-cli 0.142.1` |
| Repomix | `1.16.0` |
| Node | `v24.11.1` |
| Python | `Python 3.13.6` |

Repomix 首次 `npx -y repomix --version` 在本机耗时约 27.6s，后续缓存后 `--version` 为 3.317s。本表中的 Repomix pack 时间是在 npx 缓存后测得。

## 运行耗时

| Repo | CPGM scan | CPGM update | CPGM verify --full | CPGM query | Repomix full | Repomix --compress |
|---|---:|---:|---:|---:|---:|---:|
| `pallets__itsdangerous` | 0.800s | 2.250s | 2.239s | 1.166s | 4.044s | 4.036s |
| `google__gson` | 1.300s | 3.116s | 3.740s | 1.193s | 4.411s | 5.021s |
| `DapperLib__Dapper` | 0.996s | 3.100s | 2.935s | 1.280s | 4.513s | 4.910s |
| `BurntSushi__ripgrep` | 0.866s | 2.789s | 2.912s | 1.139s | 4.282s | 4.485s |

解读：

- 只看本地扫描，CPGM `benchmark-build` 的 scan 是 0.8-1.3s，比 Repomix pack 更快。
- 如果把 CPGM 的 deterministic guide 写入、完整校验和一次 query 都算上，单仓初始化约 6.4-9.3s；Repomix cached pack 约 4.0-5.0s，更适合“一次命令立刻拿全量上下文”。
- CPGM 的收益在后续任务：query 约 1.1-1.3s，只拿 4-6 KB 级上下文；Repomix 每次消费通常面对整个输出文件或依赖外部检索。

## 输出体积与 Token

| Repo | CPGM project-map | AGENTS | Manifest | Guides | Query selected | CPGM selected est. tokens | Repomix full | Full tokens | Repomix compressed | Compressed tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pallets__itsdangerous` | 6.0 KB | 1.4 KB | 7.0 KB | 6.1 KB | 4.3 KB | 756 | 125.8 KB | 38,214 | 95.5 KB | 31,916 |
| `google__gson` | 120.7 KB | 1.4 KB | 8.8 KB | 11.5 KB | 6.2 KB | 843 | 2.23 MB | 531,090 | 1.51 MB | 375,597 |
| `DapperLib__Dapper` | 33.2 KB | 1.4 KB | 9.1 KB | 9.7 KB | 5.6 KB | 817 | 1.28 MB | 284,776 | 658.0 KB | 169,645 |
| `BurntSushi__ripgrep` | 19.8 KB | 1.4 KB | 8.9 KB | 9.5 KB | 5.3 KB | 830 | 2.95 MB | 863,168 | 2.41 MB | 750,059 |

CPGM selected token 是 manifest 中 guide `estimated_tokens` 的求和，Repomix token 来自 Repomix CLI 默认 tokenizer，两者 tokenizer 不完全等价，但足够反映上下文级别差距。

## 上下文比例

| Repo | Full / CPGM selected bytes | Compressed / CPGM selected bytes | Full tokens / CPGM selected est. tokens | Compressed tokens / CPGM selected est. tokens |
|---|---:|---:|---:|---:|
| `pallets__itsdangerous` | 29.1x | 22.1x | 50.5x | 42.2x |
| `google__gson` | 366.1x | 247.7x | 630.0x | 445.5x |
| `DapperLib__Dapper` | 236.9x | 118.5x | 348.6x | 207.6x |
| `BurntSushi__ripgrep` | 567.3x | 464.1x | 1040.0x | 903.7x |

这就是两者最核心的落地差异：Repomix 倾向“把仓库变成一个完整上下文包”，CPGM 倾向“先保留可信索引，再按任务拿极小 guide 子集”。

## CPGM Query 与可信链

| Repo | Guides parent/leaf | Query selected | Verified guides | Manifest valid | Tampered | Stale |
|---|---:|---:|---:|---|---:|---:|
| `pallets__itsdangerous` | 1/6 | 5 | 5 | true | 0 | 0 |
| `google__gson` | 1/8 | 5 | 5 | true | 0 | 0 |
| `DapperLib__Dapper` | 1/8 | 5 | 5 | true | 0 | 0 |
| `BurntSushi__ripgrep` | 1/8 | 5 | 5 | true | 0 | 0 |

本轮 query 使用的任务：

| Repo | Query | Selected guide paths |
|---|---|---|
| `pallets__itsdangerous` | `edit src tests itsdangerous signer serializer validation` | `project/index.md`, `src/index.md`, `docs/index.md`, `github/index.md`, `pre-commit-config-yaml.md` |
| `google__gson` | `edit gson src test json adapter validation` | `project/index.md`, `gson/index.md`, `extras/index.md`, `metrics/index.md`, `pom-xml.md` |
| `DapperLib__Dapper` | `edit Dapper tests data mapping behavior` | `project/index.md`, `dapper/index.md`, `dapper-entityframework/index.md`, `dapper-providertools/index.md`, `dapper-rainbow/index.md` |
| `BurntSushi__ripgrep` | `edit crates core cli tests search behavior` | `project/index.md`, `crates/cli/index.md`, `crates/core/index.md`, `crates/searcher/index.md`, `crates/globset/index.md` |

质量备注：因为本次 guide 内容是 deterministic benchmark skeleton，不是 Codex builder 的语义总结，Python 样本仍出现 docs/config guide 噪声。完整 builder 产物应能显著改善 guide 标题、tags、read_when 和 skip_when 的语义质量。

## 横向优劣

| 维度 | CPGM 当前插件 | Repomix |
|---|---|---|
| 落地形式 | `AGENTS.md` + signed manifest + 分层 guide tree + query | 单个 AI-friendly 输出文件，支持 markdown/xml/json/plain |
| 主要优势 | 启动上下文小、按任务懒加载、可验签、可 CI freshness 检查 | 一条命令打包完整仓库，输出直接可粘贴/上传，token 统计清晰 |
| Token 策略 | query 命中 5 个 guide，本轮约 756-843 估算 tokens | full 38k-863k tokens，compressed 31k-750k tokens |
| 速度 | scan 很快；初始化若含 update/verify/query 慢于 Repomix pack | cached 后 full pack 约 4-5s，简单直接 |
| 安全 | manifest digest + guide content digest；`query` 只读验证通过的 guide；`verify --full` 可检出 tamper/stale | 内置 suspicious file/security check，本轮四仓均通过；但输出文件本身没有 signed trust chain |
| 增量 | manifest 绑定 guide source snapshot，可定位 affected guides | 通常重新 pack；本身不提供 guide 级 freshness |
| 查询 | `guidance_map.py query "<task>"` 返回 guide/source/test 候选 | 无内建任务路由；消费侧通常要让 LLM 读/搜输出文件 |
| 上下文风险 | guide 质量差时 query 会有噪声；完整语义依赖 Codex builder | 大仓库输出容易超过常用上下文；compressed 也可能非常大 |
| 适合场景 | Codex 长期编辑、团队提交 guidance、CI 校验、低上下文任务路由 | 快速给任意 LLM 一份完整仓库快照、代码审查/解释/一次性分析 |

## 推荐定位

CPGM 不应该把 Repomix 当成“要完全替代的同构竞品”。更准确的定位是：

- Repomix 是一次性上下文打包器。
- CPGM 是 Codex 编辑路由和可信项目记忆层。

因此 README/宣传中最有力的差异化应该是：

1. `AGENTS.md` 极小，默认不吞全仓上下文。
2. query 只返回 manifest-verified guide，任务上下文稳定在 KB 级。
3. guide/manifest 可进 git，可 review，可 `verify --full`。
4. Repomix 适合“把完整仓库交给模型”，CPGM 适合“让 Codex 每次只读该读的部分并遵守边界”。

## 复现命令

```powershell
$root = 'D:\project\test\repomix-cpgm-benchmark-20260703'
git clone --depth 1 https://github.com/pallets/itsdangerous.git "$root\pallets__itsdangerous"
git clone --depth 1 https://github.com/google/gson.git "$root\google__gson"
git clone --depth 1 https://github.com/DapperLib/Dapper.git "$root\DapperLib__Dapper"
git clone --depth 1 https://github.com/BurntSushi/ripgrep.git "$root\BurntSushi__ripgrep"
```

```powershell
python .\.agents\skills\code-project-guidance-map\scripts\guidance_map.py benchmark-build --repo <repo>
python .\.agents\skills\code-project-guidance-map\scripts\guidance_map.py update --repo <repo> --guidance-file <repo>\.agents\guidance-map\benchmark-guidance-draft.md
python .\.agents\skills\code-project-guidance-map\scripts\guidance_map.py verify --full --repo <repo>
python .\.agents\skills\code-project-guidance-map\scripts\guidance_map.py query "<task>" --repo <repo>
```

```powershell
npx -y repomix --style markdown --output <output.md> --ignore ".agents/**,AGENTS.md" <repo>
npx -y repomix --style markdown --compress --output <output-compress.md> --ignore ".agents/**,AGENTS.md" <repo>
```
