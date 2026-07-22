# 笔记渲染 Spec

## 目标与非目标

目标是始终生成中文 `notes.md`，并按需转换 `notes.tex` 和 `notes.pdf`。渲染器检查最低质量、
来源信号和图片证据；它不负责调用 LLM 生成正文。

## 输入、输出和公开接口

```text
python scripts/render_notes.py INPUT --output-dir DIR --duration SEC
  [--format markdown|latex|pdf|all]
  [--platform NAME] [--domain NAME] [--provider NAME]
  [--source-signals formula,code,table,figure]
```

`render(...) -> (exit_code, manifest)`。无论其他格式是否成功，输入 Markdown 都复制为
`notes.md` 并进入输出清单。

## 处理流程

渲染器先复制并检查 Markdown，再验证 source signals 和 figure manifest，最后按请求调用 Pandoc
或 XeLaTeX，并在每个阶段更新 `run_manifest.json`。

### 质量等级

| 视频时长 | 最低 CJK 字符 | 最低章节数 | 最低时间戳 | 长视频附加要求 |
|---|---:|---:|---:|---|
| `<5` 分钟 | 40 | 2 | 1 | 无 |
| `5–30` 分钟 | 300 | 5 | 3 | 无 |
| `≥30` 分钟 | 800 | 8 | 6 | `teaching_atoms.tsv` |

公式、代码、表格、配图只有在 `source_signals` 声明对应源证据时才检查。没有该信号时不强制
出现，避免为满足模板而编造内容。

### 图片验证

Markdown 图片必须匹配 `figures/figure_NNN.jpg`。路径集合必须与 `figure_manifest.json` 完全
一致，时间戳为非负有限数，path 唯一，section/caption 为字符串。任何 contact sheet、重命名
的拼接图或路径穿越都会使输出降级并返回非零状态。

### 格式转换与 manifest

- `latex`：Pandoc 生成 `notes.tex`。
- `pdf`：Pandoc 使用 `--pdf-engine=xelatex` 直接生成 `notes.pdf`。
- `all`：同时请求 LaTeX 与 PDF。

`run_manifest.json` 记录 UTC 时间、时长等级、平台、领域、Provider、源信号、图片、各输出状态、
`degraded` 和原因。工具缺失写 `unavailable`；命令或文件失败写 `failed`。

## 配置项

配置来自 CLI 的输出目录、格式、时长、平台、领域、Provider 和 source signals。当前没有独立
TOML 配置；质量阈值由代码版本固定。

## 错误与降级行为

质量不足、图片不一致或转换工具缺失都会保留已生成 Markdown、记录降级并返回非零。流水线
把任何非零渲染结果视为失败，不继续报告成功。

## 安全及兼容要求

图片只允许 `figures/figure_NNN.jpg` 相对路径并与 manifest 一致。未声明源信号时不得强制或
伪造公式、代码、表格和配图。Markdown 是所有输出格式的兼容基线。

## 测试与验收标准

`tests/test_render_notes.py` 覆盖时长边界、Markdown、质量降级、PDF 命令、源信号、图片安全、
manifest 一致性和缺失工具。Pandoc/XeLaTeX 在自动测试中 mock；真实 PDF 尚未验收。

## 已知限制

质量规则是结构下限，不等同于语义质量评分。中文字体、复杂公式和表格的 PDF 排版依赖用户的
Pandoc、XeLaTeX 和字体环境。
