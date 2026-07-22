# 自动词典 Spec

## 目标与非目标

目标是把 NJU OS 固定提示词改为通用、可扩展且可审计的词典，并在每次成功字幕修正后学习有
证据的关键词。模块不盲信 LLM 候选，不修改仓库种子，也不覆盖冲突词条。

## 输入、输出和公开接口

- 种子目录：`scripts/glossaries/`，含必选 `general.json` 和可选 `nju-os.json`。
- 用户目录：`~/.video-to-notes/glossaries/<domain>.json`。
- CLI：`glossary.py prompt` 生成 initial prompt；`glossary.py update` 校验并写入候选。
- Python：`detect_domains`、`load_entries`、`replacements`、`update_glossary`。

领域名只允许字母、数字、下划线和连字符，且必须以字母或数字开头。默认始终包含
`general`；上下文同时命中至少两个 NJU OS 提示时加入 `nju-os`；`--domain` 可覆盖自动识别。

## 处理流程

种子先于用户文件读取，词项用 NFKC、trim 和 casefold 归一化。相同归一化原词若指向不同
replacement，不用后读值静默覆盖。

LLM 候选必须包含 `original`、`corrected`、非空整数 `indices`。每个 index 必须同时证明：

1. 原字幕包含 original；
2. 修正字幕包含 replacement；
3. 原字幕与修正字幕不同；
4. 修正后 original 出现次数减少。

证据不符写入 `rejected`；已有不同 replacement 写入 `conflicts`；仅无冲突的新词写入用户词典。

## 配置项

默认用户目录为 `~/.video-to-notes/glossaries/`，CLI 可用 `--root` 覆盖；`--domain` 指定写入
领域，`--audit` 指定本次审计文件。主流程通过上下文自动选择领域或接受用户覆盖。

## 错误与降级行为

证据不符写入 `rejected`；已有不同 replacement 写入 `conflicts`，不覆盖原条目。领域名、JSON
格式、锁或文件 IO 无效时显式失败；冲突存在时 CLI 返回非零。

## 安全及兼容要求

更新期间使用 `.update.lock` 跨平台文件锁，默认等待 10 秒。词典和审计文件先写同目录临时
文件、`fsync`，再 `os.replace`；Windows 短暂 PermissionError 最多重试三次。锁超时不得
删除其他进程的有效锁。

审计文件含 UTC 时间、领域、`added`、`conflicts` 和 `rejected`；当前运行通常写
`glossary_update.json`。种子只读，用户数据与种子分离。

## 测试与验收标准

`tests/test_glossary.py` 覆盖领域检测、可选种子、证据匹配、冲突、重复归一化、危险领域名、
无变化候选、锁超时和 Windows 原子替换重试。

验收标准是：无 SRT 证据的候选永不进入持久词典；并发更新不会产生半写文件；冲突可审计。

## 已知限制

自动领域识别目前只有 `nju-os` 规则，其他领域需显式指定或新增种子和提示。证据校验基于文本
包含关系，不能单独证明语义修正一定正确。
