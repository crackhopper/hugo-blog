# `src/hugo_blog/pipeline/content_inventory.py`

这个文件给 Admin 提供内容列表。

## 主要职责

- 枚举 `content/` 下的 Markdown。
- 支持 `normal` 和 `pending` 两个 scope。
- `normal` 排除 `content/pending/`。
- `pending` 只返回 `content/pending/`。
- 为每个文件附加 `metadata_for_listing()` 生成的展示字段。

## 修改注意

这个模块是展示层 inventory，不负责 normalize。是否允许处理某篇文章，应由 `content_filters.py`、`normalize_service.py` 或具体 API 决定。
