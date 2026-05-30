# `src/hugo_blog/pipeline/normalize.py`

这个文件编排文章规范化，是 `python scripts/normalize.py` 的核心实现。

## 主要职责

- 按顺序处理 `content/posts/` 下的文章。
- 按 front matter 日期倒序处理已有文章。
- 优先处理没有 front matter 的文章。
- 调用 LLM 补摘要和 tags。
- 迁移图片、relref 和 wiki link。
- 支持逐篇确认和预览重启。

## 关键参数

- `--dry-run`：只预览，不写入，不调用 LLM。
- `--apply-all`：跳过确认。
- `--review-each`：逐篇确认，写入后重启 preview。
- `--no-llm`：明确关闭 LLM。

## 修改注意

当前只处理 posts。不要在这里直接扩大范围，应先修改 `content_filters.py` 并补测试。
