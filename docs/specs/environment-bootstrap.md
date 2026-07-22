# 环境检测与配置 Spec

## 目标与非目标

目标是为用户提供只读环境诊断和显式授权的一键安装，并确保 Python 包只进入指定虚拟环境。
本模块不修改全局 PATH，不保存凭据，也不在自动测试中真实安装系统软件。

## 输入、输出和公开接口

```text
scripts/environment.py doctor [--json] [--format FORMAT] [--provider PROVIDER]
                              [--with-transcription] [--config PATH]
scripts/environment.py install [--yes] [--target conda:NAME|venv:PATH] [同上]
```

`doctor()` 返回 `CheckResult` 列表，字段为 `name`、`kind`、`status`、`required`、
`detail`、`path`。状态枚举为：

- `ready`：依赖存在、版本满足且可执行。
- `optional_missing`：当前运行配置不要求该依赖。
- `required_missing`：当前运行必需但未找到。
- `found_unusable`：找到路径但无法正常调用或配置无效。
- `version_unsupported`：版本低于项目下限。

## 处理流程

1. 根据 `--format`、`--provider`、`--with-transcription` 计算必需集合。
2. 检查 Python 版本和包元数据。
3. 读取 `.video-to-notes.toml` 的 `[tools]` 路径覆盖并调用命令获取版本。
4. 检查 OpenAI key 是否存在，但不输出其值。
5. 校验 Whisper 配置和模型缓存完整性。
6. `install` 仅为缺失项生成命令；未传 `--yes` 时等待确认。

## 配置项

默认安装目标为有 Conda 时的 `conda:video-to-notes`，否则为 `venv:.venv`；本仓库开发和
测试明确使用 `conda:vid2rich`。Python 依赖来自 `requirements.txt`。系统工具分别通过
WinGet、Homebrew 或 apt 安装；无支持的包管理器时输出手动指南并返回失败。

## 错误与降级行为

- 安装目标解释器不可用时，先创建环境再安装 requirements。
- 已满足的依赖不重复安装，Whisper 模型已缓存时不重复下载。
- 外部命令失败必须输出可执行的原因；仍有必需手动依赖时安装不能报告成功。

## 安全及兼容要求

- Python 包只能写入显式目标环境，不得调用系统 Python 安装。
- 安装命令按 Windows、macOS、Linux 选择包管理器；自动测试必须 mock 所有安装调用。
- `.video-to-notes.toml` 本地忽略，只提交示例配置。

## 测试与验收标准

`tests/test_environment.py` 覆盖依赖分级、版本、凭据脱敏、目标解释器、安装幂等、模型缓存、
手动指南和 JSON 输出。验收命令：

```powershell
conda run -n vid2rich python scripts/environment.py doctor --json
conda run -n vid2rich python -m unittest tests.test_environment -v
```

## 已知限制

系统包名称和权限取决于操作系统。受限执行环境可能找到 FFmpeg 路径但无法启动，需要在用户
终端复核。安装器不会修改 shell 配置或全局 PATH。
