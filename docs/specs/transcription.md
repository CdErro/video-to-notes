# 本地转写 Spec

## 目标与非目标

目标是在视频没有健康字幕时，用 `faster-whisper` 生成统一 SRT。默认配置适配当前无 CUDA 的
本机；模块不执行字幕语义修正，也不在仓库内保存模型。

## 输入、输出和公开接口

```text
python scripts/transcribe.py run MEDIA --output raw.srt [配置覆盖]
python scripts/transcribe.py download-model --model small [--cache-dir PATH]
```

核心接口 `transcribe_media(media, output, config, initial_prompt)` 返回模型、device、
compute type、线程数、语言、语言概率、时长和 segment 数。

## 处理流程

1. 读取并校验配置。
2. 根据 context 和 domain 合并词典，构造 Whisper initial prompt。
3. 加载模型并启用 VAD 转写。
4. 丢弃空 segment，重新连续编号，写标准 SRT。
5. 无有效文本时不保留空的成功产物，并抛出 `TranscriptionError`。

## 配置项

| 项 | 默认值 |
|---|---|
| model | `small` |
| device | `cpu` |
| compute_type | `int8` |
| cpu_threads | `min(8, CPU 数)` |
| language | 自动识别 |
| vad_filter | `true` |

优先级为 CLI 参数高于 `.video-to-notes.toml`，配置文件高于默认值。模型仅允许 `tiny`、
`base`、`small`、`medium`；device 为 `cpu`/`cuda`，线程数必须为正数。

## 错误与降级行为

缺包、模型加载、媒体读取、推理或空语音都转换为可操作的 `TranscriptionError`。是否允许
visual-only 由一键流水线决定：非交互模式必须显式传入 `--allow-visual-only`。

## 安全及兼容要求

模型缓存位于用户目录或显式 `cache_dir`。转写内容属于运行产物，应写入被忽略的输出目录。
CPU/INT8 是默认而非唯一配置；CUDA 用户可显式覆盖 device 和 compute type。

## 测试与验收标准

`tests/test_transcribe.py` 覆盖默认值、TOML/CLI 覆盖、非法配置、SRT 与 metadata、空语音和
编号连续性。自动测试 mock faster-whisper；真实本机已使用 `small` 完成中文样例转写。

## 已知限制

模型首次下载需要网络和磁盘空间。CPU 长视频转写耗时明显；硬件自动选择目前只提供保守默认
配置，不执行 GPU 性能基准。
