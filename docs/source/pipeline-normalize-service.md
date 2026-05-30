# `src/hugo_blog/pipeline/normalize_service.py`

这个文件提供单篇 normalize 服务，是 CLI normalizer 和 Admin API 之间的薄封装。

## 主要职责

- 校验目标路径不能逃逸 `content/`。
- 只允许 normalize `content/posts/**.md`。
- 用相对路径精确过滤，避免同名文章被一起处理。
- 调用 `normalize_content()` 写入单篇文章。
- 返回页面元数据、normalize report 和当前校验结果。

## 修改注意

如果未来允许 normalize 其他 section，不要只改这里。还要同步检查 `content_filters.py`、Admin UI、build/preview 校验策略。
