# lecture-to-notes

AI 驱动的视频讲义与论文解读工具集合，Fork 自
[`ysyecust/lecture-to-notes`](https://github.com/ysyecust/lecture-to-notes)。

- `lecture-to-notes`：将 YouTube、Bilibili、X/Twitter 和小红书视频转换为中文讲义。
- `paper-to-html`：将学术论文转换为结构化中文 HTML 解读。

本 Fork 的 `main` 分支只同步上游，实际定制开发位于默认分支 `tool-only`。

## 仓库结构

```text
scripts/                  视频、字幕、帧与校验辅助脚本
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
- ImageMagick
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
