# 一键流水线 Spec

## 目标与非目标

目标是用一个命令串联环境预检、视频处理、字幕、词典、图片、Provider 和渲染，并支持中断
恢复。流水线不隐藏 Provider 或渲染失败，也不自动安装缺失依赖。

## 输入、输出和公开接口

```powershell
conda run -n vid2rich python scripts/video_to_notes.py "<URL>" `
  --provider kimi-cli --format markdown
```

主要输入参数：

| 参数 | 默认 | 作用 |
|---|---|---|
| `--provider` | `kimi-cli` | `kimi-cli` 或 `openai` |
| `--model` | Kimi: `kimi-code/kimi-for-coding` | Provider 模型 |
| `--provider-timeout` | 300 | 单次调用秒数 |
| `--env-file` | `.env` | OpenAI 变量文件 |
| `--config` | `.video-to-notes.toml` | 工具与 Whisper 配置 |
| `--domain`、`--context` | 自动 | 领域与内容上下文 |
| `--format` | `markdown` | markdown/latex/pdf/all |
| `--cookies-from-browser` | 无 | 临时读取浏览器登录态 |
| `--whisper-model` | 配置值 | tiny/base/small/medium |
| `--output-dir` | 自动生成 | 输出目录 |
| `--resume` | false | 恢复已有状态 |
| `--allow-visual-only` | false | 明确接受无字幕降级 |

## 处理流程

1. 环境预检与 Provider 配置加载。
2. 视频源探测和输出目录创建。
3. 下载视频和候选字幕。
4. 选择健康字幕，否则 Whisper；必要时显式 visual-only。
5. 应用持久词典。
6. 采样帧并生成分析 contact sheet。
7. Provider 分段修正字幕并更新有证据词典。
8. Provider 一次性生成完整笔记 JSON，最多尝试三次。
9. 按返回时间戳生成最终单帧与 Markdown draft。
10. 渲染目标格式并合并最终 manifest。

长于等于 30 分钟的输出额外写 `teaching_atoms.tsv`。最终笔记 prompt 最多读取 50,000 字符
字幕，sections 不能为空，source signals 受固定枚举限制。

## 配置项

配置优先来自 CLI，其次为 `.env` 和 `.video-to-notes.toml`，最后使用代码默认值。Provider、
模型、超时、领域、格式、Cookie 来源、Whisper 模型和输出目录均可显式覆盖。

## 错误与降级行为

阶段完成后立即原子写 `pipeline_state.json`。恢复只跳过状态完成且产物存在的阶段，并校验
source ID、平台及当前请求格式。最终笔记 payload 持久化以支持不重复请求的渲染恢复。

CLI 成功打印输出目录并返回 0。`PipelineError`、Provider、转写或证据错误返回 1。任何非零
渲染结果都被视为流水线失败。

## 安全及兼容要求

状态中的 URL 会清除 query、fragment 和 userinfo。Cookie 不保存；`.env` 不进入产物。
Provider 不自动切换。旧 Skill 入口保留，但新功能以 `video-to-notes` 为主。

## 测试与验收标准

`tests/test_video_to_notes.py` 覆盖默认 Kimi 非 highspeed、非零渲染、跨格式恢复、URL 脱敏、
visual-only 授权、字幕选择、Cookie 透传、Provider 重试、fail-closed 和集成阶段记录。

验收需同时满足完整单元测试、doctor、三个小红书样例、带 Cookie 的 Bilibili、真实 OpenAI
兼容服务和真实 PDF；当前后三项及最终代码的小红书重跑尚未全部完成。

## 已知限制

流水线是串行执行，长视频耗时受下载、CPU Whisper 和 Provider 延迟影响。最终 notes prompt
存在 50,000 字符截断；目前没有远程任务队列、并发阶段调度或成本统计。
