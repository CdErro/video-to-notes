# 验证、缺陷与风险

> 验证记录区分“代码已修改”“功能已完成”和“已在真实外部环境验证”。实现基线为
> `tool-only@88bb916`，环境复核日期为 2026-07-22。

## 已执行验证

| 类型 | 方法 | 结果 | 未覆盖范围 |
|---|---|---|---|
| 完整单元测试 | `conda run -n vid2rich python -m unittest discover -s tests -v` | 2026-07-22：134 tests，OK，3 个 zsh-only skip | 真实网络、凭据和系统渲染器 |
| 环境检测 | UTF-8 下执行 `conda run --no-capture-output ... doctor --with-transcription --json` | JSON 可读取，但因 FFmpeg/ffprobe `found_unusable` 返回 1 | 当前受限会话不能启动 FFmpeg |
| 小红书本地 smoke | 短、中、长三个样例 | 曾生成 Markdown；最终图片无 contact sheet 引用 | 短/中早于最终 fail-closed 修复 |
| Whisper 实测 | 中、长小红书媒体 | 曾生成 38/208 个 segment，中文识别 | 性能、更多语种、噪声视频 |
| Provider | Kimi 本地运行及两类 Provider mock | 长样例曾完成 Kimi；单元测试通过 | 真实 OpenAI 服务 |
| PDF | Pandoc/XeLaTeX mock | 转换调用和失败路径通过 | 真实中文 PDF |
| Bilibili | 检测与 mock | 代码路径通过 | 带登录 Cookie 的真实 E2E |

## 2026-07-22 环境结果

Ready/已发现：Python 3.13.14、yt-dlp 2026.7.4、Pillow 12.3.0、faster-whisper
1.2.1、OpenAI 2.44.0、Kimi CLI 0.28.1、Whisper `small` 缓存。

Optional missing：Pandoc、XeLaTeX、ImageMagick、OPENAI_API_KEY。FFmpeg/ffprobe 8.1.2
路径存在，但本次受限会话启动返回 `[WinError 5]`，因此 doctor 报 `found_unusable`。这项结果需
在普通用户终端复核，不能标记为本轮通过。

普通 `conda run ... --json` 还可能在 Windows GBK 控制台转发上述中文错误时触发
`UnicodeEncodeError`。设置 UTF-8 并使用 `--no-capture-output` 可稳定获得 JSON，但只解决
输出编码，不会把 FFmpeg 状态变为 `ready`。

## 已修复缺陷

| 问题 | 根因 | 修复 | 回归防护 |
|---|---|---|---|
| 最终笔记引用拼接图 | 分析图直接进入输出 | 按时间戳重新提取单帧，严格校验路径 | media/render tests |
| Provider 失败仍生成假笔记 | 重复字幕作为 fallback | 写 `notes_failure.json` 并失败退出 | fail-closed test |
| render code 1 被当作成功 | 只判断部分退出码 | 任意非零都失败 | render status test |
| 缺 Pillow 未预检 | contact sheet 后加入主流程 | doctor 将 Pillow 设为必需 | environment profile test |
| URL token/userinfo 进入状态 | 保存原始 URL | query、fragment、userinfo 脱敏 | URL tests |
| 语义修正错误丢失 | fallback 覆盖异常上下文 | 错误写阶段状态和降级原因 | integration test |
| Markdown resume 跳过 PDF | 仅看阶段完成 | 校验当前格式实际产物 | cross-format resume test |
| Windows 原子写偶发失败 | 文件替换短暂占用 | 有限重试 | glossary atomic test |

## 暂时规避或未修复

- Kimi 可能不返回业务 JSON：通过重试和 fail-closed 规避，未消除第三方不确定性。
- FFmpeg 当前会话 `[WinError 5]`：路径覆盖和本地终端复核是当前措施，根因可能是执行沙箱。
- CPU 长视频耗时：采用 small/int8/8 线程，没有性能优化或 SLA。
- 平台 extractor 变化：依赖 yt-dlp 更新和真实 smoke，没有稳定平台契约。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 当前缓解 | 推荐措施 |
|---|---|---|---|---|---|
| 高 | 外部 E2E 不完整 | 发布前未重跑样例 | 核心流程可能在真实服务失败 | mock 与旧 smoke | 完成 backlog 高优先级测试 |
| 高 | Provider 结构不稳定 | Kimi/OpenAI 兼容服务改变输出 | 最终笔记失败 | schema、三次重试、fail-closed | 保存脱敏失败分类并观察 |
| 中 | 视频平台变化 | 页面、登录或 extractor 更新 | 探测/下载中断 | yt-dlp、显式错误 | 定期 smoke 与版本更新 |
| 中 | PDF 环境差异 | 缺字体或 TeX 包 | PDF 缺字/失败 | Markdown 始终保留 | 建立真实 PDF fixture |
| 中 | 状态 schema 演进 | 新版本恢复旧目录 | 恢复错误 | `schema_version` 字段 | 定义兼容与迁移策略 |
| 中 | 词典误学习 | LLM 候选文本碰巧满足证据 | 后续替换错误 | 证据和冲突保护 | 增加人工回滚/禁用词条 |
| 中 | 无远端 CI | PR 只做本地检查 | 回归进入 tool-only | 独立 review | 增加 GitHub Actions |
| 低 | Git 历史较大 | 完整 clone | 下载空间增加 | 保留上游关系 | 推荐 `--filter=blob:none` |
| 低 | 文档状态过期 | 代码变更不更新文档 | 交接误判 | 标注基线和日期 | PR 模板加入文档检查 |

## 回归验证命令

```powershell
conda run -n vid2rich python scripts/environment.py doctor --json
conda run -n vid2rich python -m unittest discover -s tests -v
```

需要诊断中文错误时，按[环境依赖](../overview/environment.md)中的 Windows UTF-8 命令执行。

真实测试还应检查退出码、`pipeline_state.json`、`run_manifest.json`、`notes_failure.json`、
图片路径和敏感信息，而不能只检查 `notes.md` 是否存在。
