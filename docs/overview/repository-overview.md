# 仓库总览

## 项目定位

本仓库 Fork 自 `ysyecust/lecture-to-notes`，目标是把面向南京大学操作系统课程的工具扩展为
通用 `video-to-notes`：接收公开视频 URL，生成中文 Markdown 笔记，并按需生成 LaTeX/PDF。
旧 `lecture-to-notes` Skill 保留为兼容入口。

## 仓库治理

- `main`：上游镜像，只通过 fast-forward 同步上游。
- `tool-only`：默认开发分支，接收定制功能 PR。
- `feature/*`：单一功能或文档变更；通过测试和独立审查后合入 `tool-only`。
- 不重写 Git 历史，不强制推送；保留 GPL-3.0 License 与上游署名。

## 目录结构

| 路径 | 职责 |
|---|---|
| `scripts/` | 环境、视频源、Provider、转写、词典、帧证据、渲染与流水线脚本 |
| `scripts/glossaries/` | 只读种子词典：`general` 与可选 `nju-os` |
| `skills/video-to-notes/` | 当前通用 Skill |
| `skills/lecture-to-notes/` | 兼容入口 |
| `tests/` | `unittest` 与外部调用 mock |
| `design/` | 历史设计和实施记录 |
| `docs/` | 当前架构、Spec、进度与风险文档 |
| `runs/`、`artifacts/` | 被忽略的运行产物 |

发布型 PDF、HTML 和 GitHub Pages 内容已从定制分支删除；历史对象仍保留在 Git 历史中。

## 核心能力与入口

一键流程：

```powershell
conda run -n vid2rich python scripts/video_to_notes.py "<URL>" `
  --provider kimi-cli --format markdown
```

独立入口包括：

```powershell
conda run -n vid2rich python scripts/environment.py doctor --json
conda run -n vid2rich python scripts/video_source.py probe "<URL>"
conda run -n vid2rich python scripts/transcribe.py run media.mp4 --output raw.srt
conda run -n vid2rich python scripts/render_notes.py draft.md --output-dir runs/demo --duration 600
```

支持 YouTube、Bilibili、X/Twitter 和小红书视频。小红书纯图文内容被明确拒绝。Kimi CLI
与 OpenAI Responses API 可配置，但失败时不会自动切换 Provider。

## 主要文件职责

| 文件或目录 | 变更职责 | 兼容性影响 |
|---|---|---|
| `AGENTS.md` | 贡献规范、测试和 PR 规则 | 仅开发流程 |
| `.gitignore` | 排除运行产物、虚拟环境和本地配置 | 不影响运行 |
| `requirements.txt`、`environment.yml` | 固定 Python 依赖和环境入口 | Python 需 3.11+ |
| `setup.ps1`、`setup.sh` | 跨平台环境配置入口 | 不修改全局 PATH |
| `scripts/environment.py` | doctor/install 和状态分类 | 新增接口 |
| `scripts/video_source.py` | 平台 URL 与安全探测 | 保留既有平台 |
| `scripts/llm_provider.py` | Kimi/OpenAI 统一接口 | 新增 Provider 抽象 |
| `scripts/llm_correct_srt.py` | 分段语义修正和词典学习 | 失败保留词典修正版 |
| `scripts/transcribe.py` | faster-whisper SRT | 新增本地 fallback |
| `scripts/glossary.py` | 领域词典、证据、锁和审计 | NJU OS 改为可选领域 |
| `scripts/media_evidence.py` | 分析帧与最终单帧 | 修复拼接图引用 |
| `scripts/render_notes.py` | Markdown/LaTeX/PDF 与质量检查 | Markdown 成为默认 |
| `scripts/video_to_notes.py` | 一键编排、状态和恢复 | 新增主入口 |
| `skills/video-to-notes/` | 当前通用工作流和质量规则 | 新增 Skill |
| `skills/lecture-to-notes/` | 旧名称兼容入口 | 保持旧调用 |
| `tests/` | 134 项单元/集成测试基线 | 外部服务均 mock |

## 配置与产物

- 本地工具及 Whisper 配置：`.video-to-notes.toml`，模板见 `.video-to-notes.example.toml`。
- OpenAI 配置：进程环境或用户提供的 `.env`；只读取 `OPENAI_API_KEY` 和
  `OPENAI_BASE_URL`。
- 用户词典：`~/.video-to-notes/glossaries/`。
- 主要产物：`notes.md`、可选 `notes.tex`/`notes.pdf`、`run_manifest.json`、
  `pipeline_state.json`、字幕和图片证据。

更详细的职责与接口见[模块 Spec](../specs/pipeline-orchestration.md)。
