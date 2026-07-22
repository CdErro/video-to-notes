# 项目进度

> 记录日期：2026-07-22。实现基线：`tool-only@88bb916`。本文件是阶段快照，不代表远端分支
> 或本机依赖会自动保持不变。

## 当前结论

仓库治理和九项核心定制功能均已实现，并在 2026-07-22 通过完整仓库测试。项目已具备小红书、通用
Provider、自动词典、本地 Whisper、单帧证据、Markdown 优先输出和一键恢复流水线。外部验收
仍不完整：最终代码的小红书样例需重跑，Bilibili Cookie、真实 OpenAI 与真实 PDF 尚未验证。

## 合并记录

| PR | 功能 | 合并提交 | 状态 |
|---:|---|---|---|
| #1 | 环境检测与配置 | `2f8ee66` | 已完成、已测试、已审查 |
| #2 | 小红书视频源 | `d0cf2cc` | 已完成、已测试、已审查 |
| #3 | Kimi/OpenAI Provider | `354bbf0` | 已完成、已测试、已审查 |
| #4 | 证据化自动词典 | `5a20e7f` | 已完成、已测试、已审查 |
| #5 | Markdown 优先输出 | `4eb9281` | 已完成、已测试、已审查 |
| #6 | 最终单帧证据 | `bbd16d3` | 已完成、已测试、已审查 |
| #7 | 本地 Whisper | `bd9d574` | 已完成、已测试、已审查 |
| #8 | 一键流水线 | `88bb916` | 已完成、已测试、已审查 |

## 已完成修改

### 仓库与文档

- GitHub 已确认 `CdErro/video-to-notes` 是 `ysyecust/lecture-to-notes` 的 Fork，默认分支为
  `tool-only`；`main` 保留上游职责。
- 已删除当前树中的归档 PDF/HTML，历史不重写；`docs/superpowers` 已迁至 `design/`。
- `AGENTS.md`、README、License 和忽略规则已整理；`analysis_report.md` 保持本地排除。

### 运行能力

- 环境 doctor/install、setup 脚本和 `vid2rich` 开发路径已建立。
- 小红书三类 URL、官方重定向限制、Cookie 透传和纯图文拒绝已实现。
- Kimi CLI/OpenAI Provider、严格 JSON 校验、三次重试和不自动切换已实现。
- `general`/`nju-os` 与用户词典、证据校验、冲突审计和并发写入已实现。
- faster-whisper small、CPU/INT8/VAD 默认配置和统一 SRT 已实现。
- contact sheet 与最终单帧分离，最终图片和章节时间戳可追踪。
- Markdown、LaTeX/PDF、三级质量规则、manifest 和一键 `--resume` 已实现。

## 原方案最终对照

| 编号 | 原始方案项 | 当前状态 | 实际结果 | 是否调整 | 验证状态 | 后续动作 |
|---:|---|---|---|---|---|---|
| 1 | Fork 与分支治理 | 已完成 | `main`/`tool-only` 分责、无历史重写 | 否 | Git 记录已核对 | 同步本地 main |
| 2 | 发布产物清理 | 已完成 | 当前树删除归档，设计文档保留 | 否 | 文件树已核对 | 防止上游合并带回 |
| 3 | 环境检测与安装 | 已完成 | doctor/install/setup 和路径覆盖 | 优化 | 单元测试通过；本会话 FFmpeg 受限 | 本地终端复核 |
| 4 | 小红书适配 | 已完成 | URL、短链安全、Cookie、图文拒绝 | 优化 | 单元测试及早期样例 | 最终代码重跑 |
| 5 | 通用 video-to-notes | 已完成 | 新 Skill、旧入口兼容、Markdown 优先 | 否 | 单元测试通过 | 继续实测内容质量 |
| 6 | 自动词典 | 已完成 | 证据、锁、原子写、审计 | 优化 | 单元测试通过 | 扩展领域 |
| 7 | LLM 可配置 | 已完成 | Kimi/OpenAI 统一 Provider | 优化 | mock 通过 | 真实 OpenAI 验收 |
| 8 | 单帧图片 | 已完成 | contact sheet 仅分析，最终高清单帧 | 替换错误行为 | 单元测试通过 | 样例重跑 |
| 9 | 本地 Whisper | 已完成 | small、CPU/INT8、VAD、模型缓存 | 否 | 单元测试和真实转写 | 性能观察 |
| 10 | 一键运行与恢复 | 已完成 | 全阶段编排、状态、格式感知 resume | 优化 | 单元/集成测试通过 | 外部 E2E |
| 11 | Bilibili E2E | 部分完成 | 代码支持，真实 Cookie 测试未完成 | 否 | 未完成 | 获得授权后测试 |
| 12 | PDF E2E | 部分完成 | 转换逻辑存在，工具未安装 | 否 | 仅 mock | 安装后真实生成 |
| 13 | GitHub Actions | 未完成 | 当前无 CI workflow | 原计划未明确 | 未验证 | 新增 CI |

## 当前阶段

功能开发阶段已结束，处于外部集成验证、文档完善和发布准备阶段。是否达到“可发布”取决于
[待办事项](backlog.md)中的高优先级验收，而不是仅看代码合并数量。
