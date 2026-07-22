# 决策与方案变化

## 已确认决策

| 决策 | 原方案或问题 | 当前方案 | 原因与影响 |
|---|---|---|---|
| 保留 Git 历史 | 删除大型归档后可考虑清历史 | 只删当前树，不使用 filter-repo | 保持 Fork 和上游同步；代价是历史包仍大 |
| Markdown 优先 | 原项目偏 LaTeX/PDF | `notes.md` 始终生成，其他格式按需 | 降低默认依赖，便于检查和二次编辑 |
| 通用词典 | 固定 `nju_os.txt` | `general` + 自动/显式领域 + 用户词典 | 支持任意视频；增加证据、锁和审计复杂度 |
| Provider 可配置 | 单一工具路径 | Kimi CLI 与 OpenAI Responses API | 兼容本地登录和自定义服务；必须处理不同响应格式 |
| Kimi 普通模型 | 曾考虑其他模式 | 默认 `kimi-code/kimi-for-coding`，禁用 highspeed 默认 | 控制消耗并允许更长等待 |
| 不自动切换 Provider | 服务失败可尝试备用 | 同一 Provider 重试后显式失败/降级 | 避免意外成本、凭据边界和不可重复结果 |
| contact sheet 分离 | 样例把拼接图写入笔记 | 拼接图仅分析，最终重新提取单帧 | 提高可读性和证据可追踪性 |
| fail closed | 曾用重复字幕生成假笔记 | 最终 JSON 失败写 failure artifact 并退出 | 防止低质量结果被误认为成功 |
| 格式感知恢复 | 仅看 render 阶段完成 | `--resume` 检查本次请求的实际输出 | Markdown 运行后仍可追加 PDF |
| 本地 Whisper | 原流程依赖已有字幕/手工模型 | faster-whisper small，CPU/INT8 保守默认 | 适配当前机器；长视频耗时增加 |

## 在原方案上的优化

### 安全性

- 小红书短链逐跳校验官方域名，不让 HTTP 客户端自动访问外域。
- 状态中的 URL 去除 query、fragment 和 userinfo，避免分享 token 或内嵌凭据泄露。
- `.env` 只允许两个 OpenAI 变量且不覆盖进程环境；Cookie 只透传。
- 词典 domain 做路径安全校验，更新使用锁与同目录原子替换。

### 稳定性

- Kimi JSONL 从尾部寻找有效业务 JSON，忽略尾随元数据并执行本地 schema 校验。
- subtitle Provider 失败保留词典修正版，同时把原始错误写入状态。
- 所有非零渲染结果都使流水线失败，避免 unavailable PDF 被报告为成功。
- `notes_payload.json` 支持恢复时复用已验证结果。

### 可维护性与体验

- 环境必需项随格式、Provider 和转写模式动态计算。
- 独立脚本继续可用，一键入口只负责编排。
- 输出 manifest 把平台、领域、Provider、图片、降级和各格式状态集中记录。
- Windows 原子替换对短暂 PermissionError 做有限重试。

## 原计划外新增内容

| 新增内容 | 类型 | 作用 | 是否需继续观察 |
|---|---|---|---|
| `notes_failure.json` | 缺陷修复 | 明确记录最终笔记失败 | 否 |
| `notes_payload.json` | 恢复优化 | 避免恢复渲染时重复调用 LLM | 是，关注 schema 迁移 |
| URL userinfo 脱敏 | 安全修复 | 防止状态文件泄露凭据 | 否 |
| Pillow 设为主流程必需 | 环境完善 | contact sheet 是必经步骤 | 否 |
| EOF 抽帧容错 | 兼容修复 | 避免接近视频结尾的失败 | 是，关注异常时长媒体 |
| `teaching_atoms.tsv` | 质量审计 | 长视频记录章节证据 | 是，格式尚未版本化 |

## 代价与后续评审点

- 多个 manifest 和状态文件提高可追踪性，也带来 schema 版本管理责任。
- CPU Whisper 和串行 Provider 使长视频运行时间较长，尚无性能 SLA。
- `source_signals` 和文本长度规则只能提供结构下限，不能替代语义质量评估。
- OpenAI 兼容服务、Bilibili 登录态和真实 PDF 尚未完成外部验收。
