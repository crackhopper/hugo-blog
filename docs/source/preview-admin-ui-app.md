# `src/hugo_blog/preview/admin_ui/src/App.tsx`

这个文件是 React Admin/Docs 的主界面。

## 主要职责

- 根据路径切换 `/admin/`、`/issues/`、`/editor/` 和 `/docs/`。
- 渲染文章管理表格。
- 保存单篇文章并跳转预览。
- 批量保存所有改动并重启 preview。
- 渲染内容错误报告。
- 使用 Monaco 编辑原始 Markdown。
- 渲染 Docs 左侧目录、正文和右侧页内目录。

## 关键交互

- Admin 顶部按钮 `Save all & restart preview` 会保存所有已修改文章，然后重启 Hugo 预览。
- Issues 页面从 `GET /api/validation` 读取错误报告，并可跳转到对应文章编辑器。
- Editor 页面通过 `GET /api/content/<path>` 读取原文，通过 `PUT /api/content/<path>` 保存原文。
- Editor 的 Preview 按钮只在当前内容校验通过后可用。
- Docs 页面从 `GET /api/docs` 和 `GET /api/docs/<path>` 读取 Markdown。

## 修改注意

这里没有引入完整 Markdown 渲染库，而是使用轻量渲染函数覆盖当前 docs 需要的标题、段落、列表、代码块和链接。若 docs 语法继续复杂化，再考虑引入专门渲染库。
