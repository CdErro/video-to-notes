# video-to-notes 文档

本目录描述 `video-to-notes` Fork 的当前实现、设计约束和项目进度。实现基线为
`tool-only@88bb916`，进度记录日期为 2026-07-22；后续变更应同步更新对应主文档。

## 阅读顺序

1. [仓库总览](overview/repository-overview.md)：了解项目边界、目录和运行入口。
2. [环境依赖](overview/environment.md)：完成环境检测与本地配置。
3. [系统架构](architecture/system-architecture.md)与
   [数据流](architecture/pipeline-data-flow.md)：理解模块关系和一键流程。
4. [模块 Spec](specs/pipeline-orchestration.md)：按职责查看接口、错误处理和验收标准。
5. [项目进度](project/progress.md)与[待办事项](project/backlog.md)：确认已完成、已验证和未完成内容。

## 文档分区

| 分区 | 职责 |
|---|---|
| `overview/` | 仓库定位、目录、依赖与操作说明 |
| `architecture/` | 当前架构、数据流、状态与失败路径 |
| `specs/` | 各模块的详细设计与验收标准 |
| `project/` | 原始方案、决策、进度、验证和风险 |

`design/` 保留历史设计与实施记录，不作为当前行为的唯一依据。运行时事实以代码、测试和
`run_manifest.json` 为准。本文档不记录 API key、Cookie、私有媒体或本地运行产物。
