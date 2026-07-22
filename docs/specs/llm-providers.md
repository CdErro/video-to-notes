# LLM Provider Spec

## 目标与非目标

目标是用统一接口接入 Kimi CLI 和 OpenAI Responses API，并在本地验证结构化结果。模块不
自动切换 Provider，不持久化 key，也不接受未经 schema 校验的最终结果。

## 输入、输出和公开接口

```python
class Provider(Protocol):
    name: str
    model: str
    def correct(self, prompt, image, schema) -> dict: ...
    def generate(self, prompt, images, schema) -> dict: ...
```

`create_provider(name, model, env_file, timeout)` 创建实现。`correct` 用于单图字幕分段，
`generate` 用于多张 contact sheet 的笔记生成。

## 处理流程

### Kimi CLI

命令形式为 `kimi -p <prompt> [-m <model>] --output-format stream-json`。Prompt 明确要求非交互
执行、不要进入 Plan Mode。实现逐行解析 JSONL，从事件中的结构化输出、output、result、
content、text、message 等候选中反向寻找最终 JSON，并忽略末尾元数据。

一键流程默认模型为 `kimi-code/kimi-for-coding`，不是 highspeed；默认超时 300 秒。用户可用
`--model` 和 `--provider-timeout` 覆盖。

### OpenAI

从进程环境或指定 `.env` 读取 `OPENAI_API_KEY` 和可选 `OPENAI_BASE_URL`，已有环境变量不被
覆盖。调用 `client.responses.create`，图片以内嵌 data URL 发送，输出使用 strict JSON schema。
未提供正确拼写的 key 时立即失败。

## 配置项

Provider 名、模型、env file 和 timeout 由调用方传入。一键流程的 Kimi 默认模型为
`kimi-code/kimi-for-coding`，默认超时 300 秒；OpenAI 模型必须由默认策略或用户参数给出。

## 错误与降级行为

本地校验支持 object、array、string、integer、number、boolean、null、required、items 和
`additionalProperties: false`。Provider 只负责单次调用；字幕修正和笔记生成的调用方最多
重试三次。

- 字幕修正三次失败：保留词典修正版并记录降级。
- 最终笔记三次失败：写 `notes_failure.json`，主流程失败退出。
- 不因超时、无效结构或服务错误自动切换 Provider。

## 安全及兼容要求

`.env`、key、图像内容和 Provider 原始响应不得写入 Git。异常只输出必要错误摘要。自定义
OpenAI 兼容地址必须仍实现当前 Responses API 与结构化输出语义。

## 测试与验收标准

`tests/test_llm_provider.py` mock 两类 Provider，覆盖 JSONL、末尾元数据、多图、额外字段拒绝、
Responses API、自定义 base URL 和 key 拼写。真实 OpenAI 调用未验证，不得据单元测试声称可用。

## 已知限制

Kimi CLI 可能完成内部工具调用但不返回业务 JSON；当前策略是本地校验和显式失败。兼容
OpenAI 的第三方服务可能不支持 strict schema，需要真实服务验收。
