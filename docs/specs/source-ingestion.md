# 视频源接入 Spec

## 目标与非目标

目标是安全识别支持的视频 URL、探测可播放元数据，并向主流程提供 canonical URL。支持
YouTube、Bilibili、X/Twitter 和小红书视频；不支持小红书纯图文笔记，也不负责保存 Cookie。

## 输入、输出和公开接口

```text
detect_platform(url) -> platform
resolve_xiaohongshu_url(url, max_redirects=5) -> canonical_url
probe_source(url, cookies_from_browser=None) -> metadata

python scripts/video_source.py detect "<URL>"
python scripts/video_source.py probe "<URL>" [--cookies-from-browser chrome]
```

元数据至少包含 `platform`、`id`、`title`、`uploader`、正数 `duration`、`webpage_url`、
`has_thumbnail` 和 `subtitle_languages`。小红书额外返回 original/canonical URL。

## 处理流程

- YouTube：`youtu.be/<id>`、`/watch?v=<id>`、`/live|shorts|embed/<id>`。
- Bilibili：`b23.tv/*`、`bilibili.com/video/BV...`。
- X/Twitter：`/<user>/status/<id>`，可带 `/video/<n>`。
- 小红书：`xhslink.com/*`、`/explore/<id>`、`/discovery/item/<id>`。

小红书短链采用禁用自动重定向的 HTTP opener，逐跳读取 `Location`。每一跳必须仍属于
`xhslink.com` 或 `xiaohongshu.com` 官方域名，最多五次；最终 URL 去除 query 和 fragment。

探测调用 `yt-dlp --dump-single-json --no-playlist --skip-download`，不会创建媒体。主流程随后
用 canonical URL 下载单个视频、候选中英文字幕和 info JSON。

## 配置项

`--cookies-from-browser <browser>` 是唯一登录态配置，只把浏览器名称透传给 yt-dlp，不生成
Cookie 文件。短链最大重定向次数默认五次，当前 CLI 不开放修改。

## 错误与降级行为

- URL scheme、host 或 path 不匹配时抛出 `UnsupportedSourceError`，CLI 返回 2。
- 网络、extractor、无效 JSON、缺少 ID 或非正时长抛出 `ProbeError`，CLI 返回 1。
- 小红书 payload 无 `formats` 时明确报告纯图文不受支持。

本模块没有跨平台降级：探测失败必须显式返回失败。

## 安全及兼容要求

- 小红书短链每一跳必须仍为官方域名。
- Cookie 只在子进程调用期间读取，不保存到运行目录。
- 写入状态的 URL 必须移除 query、fragment 和 userinfo，避免泄露 token。

## 测试与验收标准

`tests/test_video_source.py` 覆盖各平台 URL、外部重定向拒绝、Cookie 透传、元数据校验和图文
拒绝；自动测试 mock 网络与 yt-dlp。验收要求公开小红书 URL 能探测视频，恶意跳转不能访问。

## 已知限制

平台页面和 extractor 会变化；部分视频需要登录态或地区权限。Bilibili 真实端到端仍需用户
授权浏览器 Cookie 后验证。
