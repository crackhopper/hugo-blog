# 内容处理流水线

流水线分成两类：源文档规范化和 Hugo 导出。

## 规范化

`blog-normalize` 只处理 `content/posts/` 下的文章。默认会在写入前询问确认；使用 `--apply-all` 可以跳过确认；使用 `--review-each` 可以逐篇确认，并在每次写入后重启预览。

它处理的内容包括：

- 缺失的 front matter
- 缺失的 `title`、`date`、`tags` 或 `draft`
- 删除 front matter 里的 `description`
- 在正文第一个标题前补摘要和 `<!-- more -->`
- Markdown 图片语法迁移为 Obsidian embed
- 图片文件名规范化
- broken image 检查；存在缺失图片时跳过该文件写入
- Hugo `relref` 迁移为 Obsidian wiki link
- broken wiki link 的发现和可选交互修复

`content/pending/` 会被规范化、预览导出、wiki link 索引和 Admin 全部跳过。这个目录用于暂存还不准备进入博客流水线的笔记。

常用命令：

```bash
python scripts/normalize.py
python scripts/normalize.py --apply-all
python scripts/normalize.py --review-each
python scripts/normalize.py --dry-run
```

## 导出

`blog-build` 和 `blog-serve` 会调用 `hugo_blog.pipeline.export`。

导出阶段读取 `content/`，把 Obsidian wiki link 和图片 embed 转成 Hugo 可读 Markdown，然后写入 `.hugo_temp_content/`。导出阶段不修改 `content/` 原文。

预览模式会额外生成 `.hugo_temp_content/admin/index.md`，作为 1313 Hugo 站点跳转到 1314 React Admin/Docs 的入口。Docs 不再复制到 Hugo 预览站；文档阅读统一由 `http://<host>:1314/docs/` 提供。

## 校验

`hugo_blog.pipeline.validate` 在 preview/build 前检查图片引用。它会识别三类写法：

- Obsidian embed：`![[image.png]]`
- Markdown 图片：`![alt](/images/image.png)`
- HTML 图片：`<img src="/images/image.png">`

引用会统一映射到 `static/images/`。URL 编码路径会先解码，例如 `/images/C%2B%2B.png` 会按 `static/images/C++.png` 检查。

`python scripts/serve.py` 会先启动 1314 Admin，再执行校验。若发现 broken image，Hugo 预览端口 1313 不会启动，终端会打印 Issues URL，可以在 Admin 里查看错误并打开 Markdown 编辑器修复。`build` 和 `deploy` 遇到同类错误会直接失败。

## 图片 manifest

图片资产只在 `static/images/` 内管理。`static/images/images.json` 记录 Obsidian 短文件名到实际文件路径的映射：

```json
{
  "小白学写编译器_1_编译基础概念-一个例子-01.png": "2020/06/小白学写编译器_1_编译基础概念-一个例子-01.png"
}
```

源文档仍写短引用：

```markdown
![[小白学写编译器_1_编译基础概念-一个例子-01.png]]
```

导出时 converter 通过 manifest 生成 Hugo 路径：

```markdown
![小白学写编译器_1_编译基础概念-一个例子-01](/images/2020/06/小白学写编译器_1_编译基础概念-一个例子-01.png)
```

Admin 保存或 normalize 写入时会对单篇文章执行图片归一化：如果 `![[compile.png]]` 能在 `static/images/` 下按文件名找到，就移动到文章日期目录 `YYYY/MM/`，生成安全文件名，更新 `images.json`，并把原文引用改成新的 Obsidian 短引用。

## 摘要规则

摘要写在正文里，不写入 front matter：

```markdown
这里是摘要。

<!-- more -->

# 正文标题
```

如果已有 `<!-- more -->` 或 `<!--more-->`，标记前面的文本就是摘要。

## 文章 manifest 与移动

`content/articles.json` 记录每篇 Markdown 的稳定 `id`、当前路径、历史路径、标题、草稿状态、出链、入链和图片引用。`python scripts/serve.py` 启动时会先同步这个 manifest，因此作者在 Obsidian 或文件管理器里移动、重命名文章后，系统仍能通过 front matter `id` 或正文指纹识别同一篇文章。

`content/links.json` 是文章链接索引。源文档里继续写 Obsidian wiki link；导出阶段通过这个索引生成 Hugo `relref`。如果 Admin 里执行移动或重命名，`content_refactor.py` 会负责：

- 移动 Markdown 文件
- 更新 front matter 标题
- 修复其他文章里指向旧文章的 wiki link
- 重建 `links.json` 和 `articles.json`
- 对常规 posts 重新 normalize
- 触发 preview 重新预处理

`pending` 是隔离区。移动到 `content/pending/` 后，默认不 normalize、不导出、不进入普通 Admin 列表。Admin 可以切换到 Pending 列表，让 LLM 给出几个恢复到 `posts/` 下的目录建议，用户点击其中一个后再走同一套移动/重命名流程。

## Admin 操作

Admin 的文章列表只默认显示常规内容，可以切换 Normal/Pending 范围。常规列表支持：

- 标题、date、modified 排序
- 目录、草稿状态、normalize 状态和关键词过滤
- 单篇 normalize
- 多选 normalize
- 保存全部 front matter 并重启 preview
- 移动到 pending

Pending 列表支持调用 LLM 获取多个目录建议。建议只作为候选，最终移动由用户点击确认。
