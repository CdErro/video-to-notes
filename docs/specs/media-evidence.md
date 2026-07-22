# 图片证据 Spec

## 目标与非目标

目标是把分析用拼接图与最终笔记图片彻底分离。contact sheet 只帮助 LLM 浏览视频；最终
Markdown 只能引用按 LLM 时间戳重新提取的高清单帧。模块不自行决定笔记章节或编造证据。

## 输入、输出和公开接口

```text
python scripts/media_evidence.py sample VIDEO --output-dir DIR --duration SEC
python scripts/media_evidence.py figures VIDEO --output-dir DIR --candidates JSON
```

| 产物 | 作用 |
|---|---|
| `evidence/frames/frame_NNNN.jpg` | 定时采样的分析帧 |
| `evidence/frame_manifest.tsv` | `frame` 与秒级 `timestamp` |
| `evidence/contact_sheets/contact_NNN.jpg` | 每张最多 16 帧的分析拼接图 |
| `figures/figure_NNN.jpg` | 最终笔记单帧 |
| `figure_manifest.json` | 图片路径、时间戳、章节、caption |

## 处理流程

主流程根据视频时长计算采样间隔：`duration / 16`，限制在 5–30 秒。FFmpeg 使用输入 seek、
单帧输出和 JPEG quality 2；临近 EOF 不做可能越界的浮点取整采样。

Pillow 把采样帧缩略到 320×180，每行四张，并标注时间。LLM 返回候选时间戳后，过滤负数和
重复时间，最多采用主流程传入的六个候选，从原视频重新提取 `figure_NNN.jpg`。

## 配置项

采样命令接受 `--duration`、`--interval` 和可选 `--ffmpeg`。contact sheet 默认每张 16 帧；
主流程的最终候选上限为六张。工具路径也可来自 `.video-to-notes.toml`。

## 错误与降级行为

- FFmpeg 不存在、执行失败或未产生文件时抛出 `EvidenceError`。
- Pillow 缺失、源帧缺失或 tiles 参数非法时显式失败。
- 即使没有最终候选，也写空的 `figure_manifest.json`。

## 安全及兼容要求

- 最终 figure 路径必须相对输出目录，不能引用 contact sheet 或路径穿越。
- manifest 中时间戳必须非负且去重；输出统一使用 JPEG 和 POSIX 风格相对路径。

## 测试与验收标准

`tests/test_media_evidence.py` 覆盖时间戳清单、单帧和章节映射、FFmpeg 错误、空候选、contact
sheet 隔离及 EOF 行为。`tests/test_render_notes.py` 再验证最终 Markdown 与 manifest 一致。

验收标准：`notes.md` 中 contact sheet 引用数为零；所有图片均存在于 `figures/`，且每张均有
来源时间和章节映射。

## 已知限制

当前为均匀时间采样，不做镜头切换或相似度去重。LLM 可能选择信息量较低的时刻；后续可在
不改变最终单帧约束的前提下改进候选选择。
