# video-to-notes

AI 驱动的视频讲义与论文解读工具集合，Fork 自
[`ysyecust/lecture-to-notes`](https://github.com/ysyecust/lecture-to-notes)。

- `video-to-notes`：将 YouTube、Bilibili、X/Twitter 和小红书视频转换为中文 Markdown 笔记，并可选生成 LaTeX/PDF。
- `lecture-to-notes`：保留原有 LaTeX 优先流程的兼容入口。
- `paper-to-html`：将学术论文转换为结构化中文 HTML 解读。

本 Fork 的 `main` 分支只同步上游，实际定制开发位于默认分支 `tool-only`。

## 仓库结构

```text
scripts/                  视频、字幕、帧与校验辅助脚本
skills/video-to-notes/    通用视频转中文笔记 Skill
skills/lecture-to-notes/  视频转讲义 Skill
skills/paper-to-html/     论文转 HTML Skill
tests/                    unittest 测试
design/                   设计与实施文档
```

已发布的 PDF、HTML 和 GitHub Pages 内容不在本 Fork 中维护。运行产物应写入被忽略的
`runs/` 或 `artifacts/` 目录。

## 快速开始

检测视频源：

```bash
python scripts/video_source.py detect "<URL>"
python scripts/video_source.py probe "<URL>"
```

X/Twitter 支持 `https://x.com/<user>/status/<id>[/video/<n>]`。下载字幕后使用
`scripts/check_srt_health.py` 检查结构，并在视频时长 10%、50%、90% 三处进行音画语义抽样；
任一检查失败时回退到 Whisper。

小红书支持 `xhslink.com` 短链以及 `/explore/<id>`、`/discovery/item/<id>`
详情页。需要登录态时，可临时读取浏览器 Cookie；工具不会保存 Cookie：

```bash
python scripts/video_source.py probe "<小红书 URL>" --cookies-from-browser chrome
```

字幕语义修正可选择 Kimi CLI 或 OpenAI。Kimi 复用本地登录态；OpenAI 只读取
`.env` 或当前进程中的标准变量 `OPENAI_BASE_URL`、`OPENAI_API_KEY`：

```powershell
conda run -n vid2rich python scripts/llm_correct_srt.py `
  --srt audio.srt --frames frames --out corrected.srt --context "通用视频" `
  --provider openai --model "<模型名>" --env-file .env
```

使用 Kimi 时改为 `--provider kimi-cli`，可用 `--model` 选择模型。Provider
超时或输出结构不合法时最多重试三次，随后保留原字幕，不会自动切换服务。

词典默认合并 `general` 与根据上下文识别的领域；南京大学操作系统词条已迁移为
可选 `nju-os` 种子。LLM 每次成功修正后都会校验证据并更新用户词典，同时在当前
输出目录生成 `glossary_update.json`。可用 `--domain <name>` 覆盖自动识别；用户
词典保存在 `~/.video-to-notes/glossaries/`，冲突只记录、不覆盖。

始终生成 Markdown，并按需转换：

```powershell
conda run -n vid2rich python scripts/render_notes.py draft.md `
  --output-dir runs/demo --duration 600 --platform bilibili `
  --domain general --provider kimi-cli --format all
```

`<5`、`5–30`、`≥30` 分钟视频采用不同的最低质量规则。公式、代码、表格和
配图只在源视频确实包含对应内容时要求；每次运行生成 `run_manifest.json`，记录
环境、平台、领域、Provider、输出与降级原因。

运行测试：

```powershell
conda run -n vid2rich python -m unittest discover -s tests -v
```

安装 Skill 时，将对应 `skills/<name>/` 目录复制到 Codex 或 Claude Code 的 Skills 目录，
并把 `scripts/` 中需要的辅助脚本复制到该 Skill 的 `assets/` 下。

## 核心依赖

- Python 3
- `yt-dlp`
- `ffmpeg`
- Pandoc（生成 LaTeX/PDF 时）
- Whisper（无可用字幕时）
- XeLaTeX（生成 PDF 时）

平台安装方式与完整工作流请查看对应 `SKILL.md`。

## 上游同步

```powershell
git switch main
git fetch upstream
git merge --ff-only upstream/main
git push origin main
git switch tool-only
git merge main
```

不重写 Git 历史。若只需要最新工作树，推荐使用：

```powershell
git clone --filter=blob:none https://github.com/CdErro/video-to-notes.git
```

## License

GPL-3.0。保留原项目许可证与署名。
