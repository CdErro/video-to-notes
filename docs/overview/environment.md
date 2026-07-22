# 环境依赖

## 支持基线

所有 Python 开发和测试使用本地 Conda 环境 `vid2rich`。项目要求 Python 3.11 及以上；
固定依赖见 `requirements.txt` 和 `environment.yml`。

| 依赖 | 最低/固定版本 | 用途 | 必需条件 |
|---|---:|---|---|
| Python | 3.11 | 所有脚本 | 始终 |
| yt-dlp | 2026.6.9 | 探测、下载和字幕 | 始终 |
| Pillow | 未固定 | contact sheet | 始终 |
| FFmpeg/ffprobe | 4.0 | 音视频和抽帧 | 始终 |
| faster-whisper | 1.2.1 | 本地转写 | `--with-transcription` |
| OpenAI SDK | 2.44.0 | OpenAI Provider | `--provider openai` |
| Kimi CLI | 0.26.0 | Kimi Provider | `--provider kimi-cli` |
| Pandoc | 系统版本 | Markdown→LaTeX/PDF | LaTeX/PDF |
| XeLaTeX | 系统版本 | PDF | PDF |
| ImageMagick | 可选 | 辅助图像处理 | 非主流程必需 |

## 检测与安装

只读检测：

```powershell
conda run -n vid2rich python scripts/environment.py doctor --with-transcription --json
```

状态包括 `ready`、`optional_missing`、`required_missing`、`found_unusable` 和
`version_unsupported`。`required` 由输出格式、Provider 和是否启用转写共同决定。

安装命令会展示计划并等待确认；自动化场景必须显式使用 `--yes`：

```powershell
conda run -n vid2rich python scripts/environment.py install --target conda:vid2rich
conda run -n vid2rich python scripts/environment.py install --target conda:vid2rich --yes
```

`setup.ps1` 和 `setup.sh` 是便捷入口。Python 包只安装到目标 Conda/venv；外部工具使用
WinGet、Homebrew 或 apt。脚本不修改全局 PATH；不可见工具应在本地配置中覆盖路径：

```toml
[tools]
ffmpeg = "C:/tools/ffmpeg/bin/ffmpeg.exe"
ffprobe = "C:/tools/ffmpeg/bin/ffprobe.exe"
```

## Whisper 默认配置

```toml
[whisper]
model = "small"
device = "cpu"
compute_type = "int8"
cpu_threads = 8
vad_filter = true
```

语言默认自动识别。可用 `scripts/transcribe.py download-model --model small` 预下载模型；
模型存入用户 Hugging Face 缓存，不进入仓库。

## OpenAI 配置

不要提交 `.env`。运行时可传入：

```dotenv
OPENAI_BASE_URL=https://example.invalid/v1
OPENAI_API_KEY=replace-me
```

变量名必须为 `OPENAI_API_KEY`；`OPNEAI_API_KEY` 是拼写错误。已有进程环境变量优先于
`.env`，加载器不会覆盖它们。

## 2026-07-22 本机复核

`vid2rich` 中 Python 3.13.14、yt-dlp 2026.7.4、faster-whisper 1.2.1、Pillow
12.3.0、OpenAI 2.44.0、Kimi CLI 0.28.1 和 Whisper `small` 缓存均被发现。Pandoc、
XeLaTeX、ImageMagick 未安装；OpenAI key 未提供，符合当前测试安排。

FFmpeg 8.1.2 与 ffprobe 路径存在，但本次受限执行会话返回 `[WinError 5]`，状态为
`found_unusable`。这不等同于软件缺失；发布前应在普通本地终端重新运行 doctor 并确认
二者为 `ready`。
