# `src/hugo_blog/llm/client.py`

这个文件封装 LLM 配置、`.env` 读取和 OpenAI 兼容聊天补全调用。

## 主要职责

- 读取 `.env` 和环境变量。
- 生成 `LLMConfig`。
- 解析模型返回的 JSON。
- 调用 `/chat/completions` 获取摘要和 tags。

## 关键类型

- `LLMMetadata`：摘要和 tags 的结果对象。
- `LLMConfig`：provider、api key、base url、model。
- `LLMClient`：实际 API 客户端。

## 修改注意

normalizer 默认要求 LLM 可用。这里的失败策略会直接影响 `python scripts/normalize.py` 的体验。
