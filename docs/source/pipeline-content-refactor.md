# `src/hugo_blog/pipeline/content_refactor.py`

这个文件封装文章移动和重命名。Admin 里的改名、移入 pending、从 pending 恢复，都应该走这里。

## 主要职责

- 校验源路径和目标路径必须在 `content/` 内。
- 移动 Markdown 文件。
- 可选更新 front matter `title`。
- 用移动前的 `links.json` 判断哪些 wiki link 指向旧文章。
- 把这些 wiki link 更新到新目标。
- 重建 `content/links.json` 和 `content/articles.json`。
- 对恢复到 `posts/` 的文章执行单篇 normalize。

## 修改注意

这个模块的边界是“源 Markdown”。它不直接写 `.hugo_temp_content/`，也不直接调用 Hugo。预览刷新由调用方负责。

更新引用时只处理文档 wiki link，不处理图片 embed。
