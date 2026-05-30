# `src/hugo_blog/pipeline/validate.py`

这个文件负责内容校验。它不修改 Markdown，只把会导致 preview/build 失败或页面资源缺失的问题整理成报告。

## 主要职责

- 扫描 Markdown 中的图片引用。
- 支持 Obsidian embed、Markdown 图片和 HTML `<img>`。
- 把 `/images/...`、`images/...` 和 URL 编码路径映射到 `static/images/`。
- 优先通过 `static/images/images.json` 判断短图片引用是否有效。
- 生成 `ValidationReport` 和 `ValidationIssue`，供 CLI、Admin API 和 React Issues 页面使用。
- 为缺失图片提供相似文件候选，方便人工修复。

## 关键对象

- `ValidationIssue`：单个问题，包含严重级别、类型、源文件、行号、原始引用、目标路径、消息和候选图片。
- `ValidationReport`：问题集合，`ok` 表示是否没有 error 级别问题。
- `validate_content_tree()`：校验整个内容目录。
- `validate_markdown_text()`：校验内存中的 Markdown 文本，供 Monaco 编辑器保存前后使用。

## 修改注意

校验器应该保持只读。自动修复图片引用属于后续专门的 fixer，不应该混进这个模块。这样 build、serve 和 Admin 都能放心复用同一套判断。

manifest 缺失但根目录图片存在时，校验器返回 `needs_image_normalization` warning；warning 不阻断 preview/build。manifest 指向的实际文件缺失时，返回 `missing_image` error。
