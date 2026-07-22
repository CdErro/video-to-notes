# Git 提交、推送与 PR 规范

## 适用范围与当前设置

本文约束 Agent 执行分支创建、暂存、提交、push、PR、合并、删分支和上游同步。设置快照日期为
2026-07-22；执行写操作前必须重新读取远端状态，GitHub 当前 ruleset 优先于本文快照。

| 项目 | 当前设置 |
|---|---|
| 仓库 | `CdErro/video-to-notes`，Fork 自 `ysyecust/lecture-to-notes` |
| 默认分支 | `tool-only` |
| 上游镜像 | `main` |
| 受 ruleset 约束 | 默认分支、`main`、`tool-only` |
| 保护规则 | 禁止删除、禁止 non-fast-forward、必须通过 PR |
| PR 规则 | 必需批准数为 0；所有 review thread 必须解决 |
| 合并方式 | merge、squash、rebase 均由 GitHub 允许 |
| 自动删分支 | 关闭，合并后需要显式删除 feature 分支 |
| bypass | 无；Agent 不允许修改或规避 ruleset |

GitHub 未要求批准数不代表可以跳过项目审查。本仓库额外要求每个功能 PR 接受独立 Agent review。

## 开始修改前

1. 运行 `git status --short --branch`、`git branch -vv`，确认当前分支和未提交内容。
2. 读取 `origin`、`upstream` 和默认分支；不得假设本地引用是最新的。
3. 工作树存在用户修改时，只能操作明确属于本任务的路径。禁止使用 `git add -A`、
   `git reset --hard`、`git checkout -- <path>` 或自动 stash 清理用户内容。
4. 如果任务文件与用户未提交修改重叠，停止并请求用户决定；不得覆盖或混入提交。

## 分支规则

定制开发必须从最新 `origin/tool-only` 创建短期分支；不得直接在 `main` 或 `tool-only` 开发。

| 类型 | 命名格式 | PR 目标 |
|---|---|---|
| 新功能 | `feature/<short-slug>` | `tool-only` |
| Bug 修复 | `fix/<short-slug>` | `tool-only` |
| 纯文档 | `docs/<short-slug>` | `tool-only` |
| 仓库维护 | `chore/<short-slug>` | `tool-only` |
| 上游同步 | `sync/upstream-main-YYYYMMDD` | `main` |
| main 合入定制分支 | `sync/main-into-tool-only-YYYYMMDD` | `tool-only` |

分支名使用小写 ASCII、数字和连字符。一个分支只承担一个可独立审查的目标。

## 暂存与提交

1. 使用显式路径暂存，例如 `git add AGENTS.md docs/project/git-workflow.md`。
2. 暂存后运行 `git diff --cached --check`、`git diff --cached --stat` 和
   `git diff --cached`，确认没有无关文件、凭据、Cookie、媒体或运行产物。
3. 使用 Conventional Commits：`feat:`、`fix:`、`docs:`、`test:`、`chore:`、`refactor:`。
4. 每个提交只包含一个逻辑修改；review 修正使用独立 `fix:` 或 `docs:` 提交，不改写已 push 历史。
5. Python 验证统一通过 Conda 环境 `vid2rich` 执行。

最低验证：

```powershell
conda run -n vid2rich python scripts/environment.py doctor --json
conda run -n vid2rich python -m unittest discover -s tests -v
```

若 doctor 因当前任务无关的外部工具而非零，PR 必须记录具体状态；不得把非零检查写成通过。

## Push 规则

- 只 push 当前任务分支：`git push -u origin <branch>`。
- 禁止直接 push `main` 或 `tool-only`；ruleset 要求两者通过 PR 更新。
- 禁止 `--force`、`--force-with-lease`、历史重写和删除受保护分支。
- push 前再次确认 `git status` 和 upstream；不得把本地其他分支误推到任务分支。

## PR 与独立审查

PR 初始状态使用 Draft，定制 PR 的 base 固定为 `tool-only`。PR 描述必须包含：变更目的、实际
修改、用户影响、验证命令与结果、未覆盖范围、关联 Issue，以及是否存在降级或兼容影响。

创建 PR 后必须启动独立 code-review Agent 审查完整 `base...head` diff，而非只看最后一个提交。
审查发现必须修复或由用户明确接受；push 修正后必须复审。只有同时满足以下条件才可合并：

- 独立审查返回 `APPROVE`，没有未处理问题；
- GitHub review thread 全部 resolved；
- 必需检查通过，或非零项已准确记录且不属于本 PR 引入；
- PR diff 只包含当前任务范围；
- PR 已从 Draft 标记为 Ready。

本仓库历史使用 merge commit 保留 feature 提交和 PR 边界，Agent 默认执行：

```powershell
gh pr ready <number> --repo CdErro/video-to-notes
gh pr merge <number> --repo CdErro/video-to-notes --merge --delete-branch
```

GitHub 的自动删分支当前关闭，因此使用 `--delete-branch` 显式删除已合并远端任务分支。合并后
fetch `origin/tool-only` 并以 fast-forward 更新本地 `tool-only`；保留用户未提交修改。

## 上游 `main` 同步

`main` 只接收 upstream 内容。由于 ruleset 要求 PR，旧的 `git push origin main` 直接同步方式
不再适用。Agent只能准备同步 PR，不得未经用户明确授权自动合并到 `main`：

```powershell
git fetch upstream origin
git switch -c sync/upstream-main-YYYYMMDD upstream/main
git push -u origin sync/upstream-main-YYYYMMDD
gh pr create --repo CdErro/video-to-notes --base main `
  --head sync/upstream-main-YYYYMMDD --draft
```

同步 PR 默认使用 merge commit，保留 upstream commit 身份；受保护的 `main` 会额外产生 PR merge
commit，因此这里的“镜像”指代码内容和 upstream 提交可追溯，不保证分支 SHA 完全相同。

上游 main 合并后，如需更新定制分支，应从最新 `tool-only` 创建
`sync/main-into-tool-only-YYYYMMDD`，合并 `origin/main`，解决冲突并通过 PR 回到 `tool-only`。
上游若重新加入已删除发布目录，定制分支继续保持删除；开发代码和安全修复正常保留。

## 禁止行为

- 为方便操作而关闭、修改或绕过 GitHub ruleset。
- 直接向 `main`、`tool-only` push，或把定制提交 PR 到 `main`。
- 未经审查合并 PR，或在 review 修正后跳过复审。
- 使用强制推送、重写已发布提交、自动清理用户修改或提交敏感数据。
- 把“文件已修改”“测试已运行”“测试已通过”视为同一状态。
