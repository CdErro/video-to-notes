# 状态与失败流程

## 状态文件

`pipeline_state.json` 使用原子替换写入，记录 source、artifacts、各阶段状态、降级标记和原因。
阶段状态为 `completed` 或 `failed`，并带 UTC 时间与阶段细节。

主要辅助文件：

| 文件 | 用途 |
|---|---|
| `notes_payload.json` | 保存通过 schema 校验的笔记 JSON，供恢复执行复用 |
| `notes_failure.json` | 记录最终笔记生成失败原因 |
| `figure_manifest.json` | 最终单帧、时间戳、章节和说明映射 |
| `run_manifest.json` | 环境上下文、平台、领域、Provider、输出和降级状态 |
| `glossary_update.json` | 当前运行的词典新增、冲突和拒绝审计 |

## `--resume` 规则

恢复前仍会执行环境检查和视频探测。已有状态中的平台或视频 ID 与当前 URL 不一致时拒绝复用。
每个已完成阶段只有在对应产物仍存在时才跳过。

`render` 还会检查当前请求格式：已有 `notes.md` 不能满足后续 `--format pdf`，必须继续生成
`notes.pdf`。恢复时复用 `notes_payload.json`，避免再次请求 Provider。

## 失败与降级

| 场景 | 行为 |
|---|---|
| 必需环境不是 `ready` | 在下载前终止 |
| 视频探测、下载或抽帧失败 | 终止并返回非零退出码 |
| 无健康字幕且 Whisper 不可用 | 非交互默认终止；明确 `--allow-visual-only` 才降级 |
| Whisper 无语音 | 用户允许时转 visual-only，否则终止 |
| 字幕语义修正失败 | 保留词典修正版，记录降级，继续最终笔记阶段 |
| 最终笔记 JSON 连续三次无效 | 写 `notes_failure.json` 并终止 |
| Pandoc/XeLaTeX 或转换失败 | manifest 标为 unavailable/failed，流水线返回失败 |
| 笔记质量规则不满足 | 保留 Markdown，记录降级；主流程视非零渲染结果为失败 |

不会自动从 Kimi 切换到 OpenAI，或反向切换。失败必须可见，避免在未授权的情况下改变成本、
隐私和输出行为。

## 恢复验收

- 同一 URL、同一输出目录可从最后一个有效阶段继续。
- 不同视频不能复用同一状态目录。
- Markdown 完成后请求 PDF，必须执行 PDF 渲染。
- Provider 笔记失败不能产生看似成功的 `notes.md`。
- 状态和 manifest 中不得保存 URL query、fragment、userinfo 或 Cookie。
