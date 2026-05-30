# `src/hugo_blog/pipeline/markdown_document.py`

这个文件负责解析 Markdown 文档结构。

## 主要职责

- 解析 YAML front matter。
- 分离正文 body。
- 判断是否存在 `<!-- more -->`。
- 使用 `markdown-it-py` 找到第一个 heading 行号。

## 关键类型

- `MarkdownDocument`：包含原文、正文、front matter、摘要和首个标题位置。

## 修改注意

这是 metadata 处理的底层依赖。front matter 正则或 more marker 规则变化时，要同步跑 metadata 相关测试。
