# LLM 元数据生成

LLM 只用于补齐缺失的文章元数据。已有的非空 tags 和已有摘要会保留，不会覆盖。

## 配置

Provider 配置写在 `.env`：

```bash
LLM_PROVIDER="deepseek"
LLM_BASE_URL="https://api.deepseek.com"
LLM_MODEL="your-model"
LLM_API_KEY="your-key"
```

客户端使用 OpenAI 兼容的 `/chat/completions` 请求。默认 provider 是 DeepSeek，但代码只依赖 `base_url`、`api_key` 和 `model`。

## 输出约定

模型必须返回严格 JSON：

```json
{
  "abstract": "80 到 140 字中文摘要",
  "tags": ["标签1", "标签2"]
}
```

如果返回不是合法 JSON、缺少字段或网络失败，会得到空结果。写入模式下，如果没有配置 `LLM_API_KEY` 和 `LLM_MODEL`，normalize 会直接失败，避免静默生成不完整内容。

## 离线模式

写入模式下可以用 `--no-llm` 禁止 API 调用：

```bash
python scripts/normalize.py --no-llm
```

`--dry-run` 永远不会调用 LLM。默认写入模式会先询问是否处理元数据候选；`--apply-all` 跳过这个确认；`--review-each` 逐篇确认并预览。首次配置建议运行：

```bash
python3 init.py
```

每当 LLM 生成摘要或 tags，normalizer 会在写入前把生成内容打印出来，便于人工检查。
