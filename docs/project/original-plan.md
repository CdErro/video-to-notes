# 原始定制方案

## 记录范围

本文件还原从首次定制需求到三项补充功能计划的目标。无法从现有记录确认的细节不补写。
实现结果见[项目进度](progress.md)，方案变化见[决策记录](decisions.md)。

## 1. 仓库治理

**目标**：保留 Fork 关系和 GPL-3.0，上游 `main` 仅作镜像，`tool-only` 作为默认开发分支；
删除发布 PDF/HTML，保留设计文档，不重写历史。

**计划**：建立 `CdErro/video-to-notes` Fork；配置 `origin`/`upstream`；迁移
`docs/superpowers` 到 `design`；删除归档产物；使用 feature PR 合入 `tool-only`。

**验收**：默认分支正确；License 不变；`main` 无定制提交；发布产物不在当前工作树；后续可
fast-forward 同步上游。

## 2. 环境检测与一键配置

**目标**：为 Python、Conda、Provider、Whisper、FFmpeg、Pandoc、XeLaTeX 等提供只读检测和
显式安装；所有开发与测试使用 `vid2rich`。

**计划**：新增 `environment.py` 的 `doctor/install`、JSON 输出、状态分类、Conda/venv 目标、
跨平台 setup 脚本、requirements 和 environment.yml；不修改全局 PATH。

**验收**：安装幂等；自动测试只 mock 安装；已安装 FFmpeg 不重复安装；缺少系统包管理器时
给出手动指南。

## 3. 小红书视频

**目标**：支持 `xhslink.com`、`/explore/<id>` 和 `/discovery/item/<id>` 视频。

**计划**：限制短链只能跳转到小红书官方域名；复用 yt-dlp extractor；记录原始和 canonical
URL；支持可选浏览器 Cookie；拒绝纯图文。

**验收**：公开短、中、长样例可探测/下载；外域跳转被拒绝；Cookie 不保存。

## 4. 通用 Provider 与字幕修正

**目标**：移除课程专用限制，支持可配置 Kimi CLI 与 OpenAI Responses API。

**计划**：统一 `Provider.correct`；Kimi 解析 stream-json，OpenAI 使用环境变量；结构无效或
超时最多重试三次；不自动切换 Provider。

**验收**：两类 Provider 的结构化输出、失败和降级均有测试；key 不写入仓库。

## 5. 自动词典

**目标**：每次工具运行可从可靠字幕修正中学习关键词，NJU OS 降为可选种子领域。

**计划**：默认合并 `general` 和自动领域；候选携带原/修正字幕和 SRT index；使用锁、原子
替换和审计；冲突不覆盖。

**验收**：无证据不写入；并发安全；新增、拒绝和冲突均可追踪。

## 6. Markdown 优先输出

**目标**：新增通用 `video-to-notes`，始终生成中文 Markdown，按需生成 LaTeX/PDF。

**计划**：保留旧 Skill；按 `<5`、`5–30`、`≥30` 分钟设置质量等级；仅在有源证据时要求
公式、代码、表格和图片；写 `run_manifest.json`。

**验收**：Markdown 必有；转换工具缺失时明确失败；输出和降级状态可查。

## 7. 单帧图片证据

**目标**：修复笔记直接引用 contact sheet 的问题。

**计划**：写 `frame_manifest.tsv`；contact sheet 仅供 LLM；按返回时间戳提取 `figures/` 高清
单帧，并记录章节映射。

**验收**：最终 Markdown 只引用 `figure_NNN.jpg`；三个本地样例不再引用拼接图。

## 8. 本地 Whisper

**目标**：无字幕视频可在本地转写。

**计划**：采用 `faster-whisper small`，本机默认 CPU/INT8/8 线程、自动语言和 VAD；环境检测
支持 `--with-transcription`；setup 可预下载模型。

**验收**：统一生成 SRT；配置可覆盖；在 `vid2rich` 运行并通过测试。

## 9. 一键流水线

**目标**：用户不再手动串联脚本和中间产物。

**计划**：统一入口串联检测、探测、下载、字幕、Whisper、修正、词典、抽帧、笔记和渲染；
支持 `.env`、Cookie、领域、模型、格式、状态与 `--resume`。

**验收**：环境和单元测试通过；三个小红书样例端到端；Bilibili 在 Cookie 授权后验证。

## 无法从现有记录确认

没有确认正式发布版本号、性能 SLA、GPU 自动选型阈值、CI 平台矩阵或发布包形式。这些内容
不属于已承诺的原始验收标准。
