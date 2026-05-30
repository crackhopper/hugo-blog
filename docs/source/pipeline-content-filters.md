# `src/hugo_blog/pipeline/content_filters.py`

这个文件定义内容目录的过滤规则。

## 主要职责

- 跳过 `content/pending/`。
- 定义哪些内容可被 normalize/Admin 处理。
- 提供普通 Markdown 遍历和可处理 Markdown 遍历。

## 当前规则

- `iter_content_markdown_files()`：用于 Hugo 导出和 wiki link 索引，会跳过 pending。
- `iter_processable_markdown_files()`：用于 normalize 和 Admin，只返回 `content/posts/` 下的文章。

## 修改注意

如果未来要让项目页也进入 Admin，需要先改这里，再同步更新 normalize 和 Admin 的测试。
