# `src/hugo_blog/pipeline/image_normalizer.py`

这个文件负责单篇 Markdown 的图片归一化。

## 主要职责

- 解析 `![[...]]` 图片引用。
- 对 manifest 未命中的短文件名，在 `static/images/` 内查找同名文件。
- 根据文章 date 生成 `YYYY/MM/` 日期目录。
- 根据文章标题和图片所在 heading 生成安全文件名。
- 移动图片文件，更新 `images.json`。
- 把原文引用更新为新的 Obsidian 短引用。

## 命名规则

```text
{article_slug}-{heading_slug}-{NN}.{ext}
```

特殊符号统一转 `_`，连续 `_` 合并，扩展名小写。

## 修改注意

这个模块只处理单篇文章。批量删除无用图片不应该放在这里，应该留给 normalize 的专门清理流程，并默认 dry-run。
