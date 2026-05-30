# 源码说明目录

这一组文档按源码文件组织。左侧目录点击任意条目，可以查看对应 Python 文件在工具链里的职责、主要入口和修改注意事项。

## 阅读建议

- 想理解整体流程，先看 `static_site.py`、`pipeline/export.py`、`pipeline/validate.py`、`preview/serve.py`。
- 想改文章规范化，先看 `pipeline/normalize.py`、`pipeline/normalize_service.py`、`pipeline/metadata.py`、`pipeline/content_filters.py`。
- 想改移动、重命名、pending 流程，先看 `pipeline/article_manifest.py`、`pipeline/link_manifest.py`、`pipeline/content_refactor.py`、`pipeline/content_suggestions.py`。
- 想改 Admin 或 Docs，先看 `preview/admin.py` 和 `preview/admin_ui/src/App.tsx`。
- 想改 Hugo 安装和初始化，先看 `tools/hugo.py`、`init.py` 和 `cli/init.py`。

## 目录约定

文档文件名使用源码路径展开后的形式，例如：

```text
src/hugo_blog/pipeline/metadata.py
-> docs/source/pipeline-metadata.md
```
