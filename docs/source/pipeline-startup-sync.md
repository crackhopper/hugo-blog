# `src/hugo_blog/pipeline/startup_sync.py`

这个文件是 preview 启动前的内容索引同步入口。

## 主要职责

- 重建 `content/articles.json`。
- 重建 `content/links.json`。
- 确保新文章拥有稳定 `id`。
- 让外部移动、删除、重命名后的内容在启动 preview 时被重新识别。

## 修改注意

这里应该保持轻量，只做必要索引同步。耗时的 LLM normalize、图片迁移或交互确认不应放到 preview 启动路径。
